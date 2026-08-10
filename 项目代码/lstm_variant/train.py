from __future__ import annotations

import argparse
from dataclasses import asdict
import math
from pathlib import Path
import random

import numpy as np
import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from spam_cascade.config import CascadeConfig
from spam_cascade.data import (
    SEMANTIC_LABELS,
    BehaviorFeatureBuilder,
    BehaviorSequenceDataset,
    FusionReviewDataset,
    SemanticReviewDataset,
    collate_behavior,
    collate_fusion,
    load_reviews,
)
from spam_cascade.modeling import AlbertSemanticClassifier, BehaviorLSTMClassifier, CascadeDetector
from spam_cascade.training import (
    append_jsonl,
    balanced_class_weights,
    evaluate_behavior,
    evaluate_fusion,
    evaluate_semantic,
    load_training_checkpoint,
    powered_class_weights,
    save_checkpoint,
    save_training_checkpoint,
    train_behavior_epoch,
    train_fusion_epoch,
    train_semantic_epoch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train semantic-first fake-review cascade")
    parser.add_argument("--stage", choices=["semantic", "behavior", "fusion"], required=True)
    parser.add_argument("--data", required=True, help="Training TSV file")
    parser.add_argument("--val-data", help="Validation TSV file; required for behavior and fusion training")
    parser.add_argument("--config", default="configs/base.json")
    parser.add_argument("--output", default="checkpoints")
    parser.add_argument("--epochs", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--learning-rate", type=float)
    parser.add_argument("--semantic-learning-rate", type=float, default=1e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=1)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--early-stopping-patience", type=int)
    parser.add_argument("--resume", help="Path to latest.pt or another full training checkpoint")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--class-weighting", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--class-weight-exponent", type=float, default=0.5)
    parser.add_argument("--behavior-type-loss-weight", type=float, default=0.3)
    parser.add_argument("--semantic-checkpoint")
    parser.add_argument("--behavior-checkpoint")
    parser.add_argument("--freeze-encoders-epochs", type=int, default=1)
    parser.add_argument("--save-every-epoch", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def make_loader(dataset, args: argparse.Namespace, shuffle: bool, device: torch.device, collate_fn=None):
    workers = max(args.num_workers, 0)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=shuffle,
        num_workers=workers,
        pin_memory=device.type == "cuda",
        persistent_workers=workers > 0,
        collate_fn=collate_fn,
    )


def semantic_targets(frame) -> tuple[torch.Tensor, torch.Tensor]:
    authenticity = torch.as_tensor(frame["authenticity_target"].to_numpy(), dtype=torch.long)
    if "semantic_type" in frame.columns:
        semantic_series = frame["semantic_type"]
    else:
        semantic_series = frame["authenticity_target"].map(lambda _: "real")
    semantic = torch.as_tensor(
        semantic_series.map(SEMANTIC_LABELS)
        .fillna(SEMANTIC_LABELS["real"])
        .astype("int64")
        .to_numpy(),
        dtype=torch.long,
    )
    return authenticity, semantic


def train_semantic(args: argparse.Namespace, config: CascadeConfig, device: torch.device) -> None:
    output_directory = Path(args.output)
    output_directory.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(config.albert_name_or_path)

    train_frame = load_reviews(args.data)
    train_dataset = SemanticReviewDataset(train_frame, tokenizer, config.max_length)
    train_loader = make_loader(train_dataset, args, shuffle=True, device=device)

    validation_loader = None
    if args.val_data:
        validation_frame = load_reviews(args.val_data)
        validation_dataset = SemanticReviewDataset(validation_frame, tokenizer, config.max_length)
        validation_loader = make_loader(validation_dataset, args, shuffle=False, device=device)
    else:
        print("warning: --val-data is not set; best-model selection will use training loss")

    authenticity_targets, _ = semantic_targets(train_frame)
    authenticity_class_weights = (
        balanced_class_weights(authenticity_targets, 2) if args.class_weighting else None
    )
    if authenticity_class_weights is not None:
        print("authenticity_class_weights=", authenticity_class_weights.tolist())

    model = AlbertSemanticClassifier(config).to(device)
    # Stage one is a pure real/fake classifier. The fine-grained semantic head
    # stays in the checkpoint for interface compatibility, but is not optimized
    # until the later fusion stage.
    optimizer = AdamW(
        list(model.encoder.parameters()) + list(model.authenticity_head.parameters()),
        lr=args.learning_rate,
        weight_decay=args.weight_decay,
    )
    updates_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation_steps)
    total_updates = max(updates_per_epoch * args.epochs, 1)
    warmup_steps = int(total_updates * args.warmup_ratio)
    scheduler = get_linear_schedule_with_warmup(optimizer, warmup_steps, total_updates)
    amp_enabled = bool(args.amp and device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)

    start_epoch = 1
    best_score = float("-inf")
    epochs_without_improvement = 0
    if args.resume:
        checkpoint = load_training_checkpoint(
            args.resume,
            model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            map_location=device,
        )
        start_epoch = int(checkpoint["epoch"]) + 1
        best_score = float(checkpoint.get("best_score", best_score))
        epochs_without_improvement = int(checkpoint.get("epochs_without_improvement", 0))
        print(f"resumed_from={args.resume} next_epoch={start_epoch} best_score={best_score:.6f}")

    metadata = {
        "stage": "semantic_binary",
        "config": asdict(config),
        "training_arguments": vars(args),
    }
    history_path = output_directory / "history.jsonl"
    if not args.resume and history_path.exists():
        history_path.unlink()

    for epoch in range(start_epoch, args.epochs + 1):
        train_result = train_semantic_epoch(
            model,
            train_loader,
            optimizer,
            device,
            authenticity_class_weights=authenticity_class_weights,
            semantic_class_weights=None,
            semantic_weight=0.0,
            binary_only=True,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            max_grad_norm=args.max_grad_norm,
            amp_enabled=amp_enabled,
            scaler=scaler,
            scheduler=scheduler,
        )

        validation_result = None
        if validation_loader is not None:
            validation_result = evaluate_semantic(
                model,
                validation_loader,
                device,
                config.semantic_labels,
                authenticity_class_weights=authenticity_class_weights,
                semantic_class_weights=None,
                semantic_weight=0.0,
                binary_only=True,
                amp_enabled=amp_enabled,
            )
            score = validation_result.selection_score
        else:
            score = -train_result.loss

        record = {"epoch": epoch, "train": train_result.as_dict()}
        if validation_result is not None:
            record["validation"] = validation_result.as_dict()
        append_jsonl(history_path, record)

        print(
            f"epoch={epoch} train_loss={train_result.loss:.6f} "
            f"train_auth_accuracy={train_result.authenticity_accuracy:.6f} "
            f"train_auth_f1={train_result.authenticity_macro_f1:.6f}"
        )
        if validation_result is not None:
            print(
                f"epoch={epoch} val_loss={validation_result.loss:.6f} "
                f"val_auth_accuracy={validation_result.authenticity_accuracy:.6f} "
                f"val_auth_f1={validation_result.authenticity_macro_f1:.6f} "
                f"val_selection_score={validation_result.selection_score:.6f}"
            )
            print("authenticity validation report:\n" + validation_result.authenticity_report)

        improved = score > best_score
        if improved:
            best_score = score
            epochs_without_improvement = 0
            save_training_checkpoint(
                output_directory / "best.pt",
                model,
                optimizer,
                scheduler,
                scaler,
                epoch,
                best_score,
                epochs_without_improvement,
                metadata,
            )
            save_checkpoint(model, output_directory, "semantic_albert_best")
            print(f"best_checkpoint_updated epoch={epoch} score={best_score:.6f}")
        else:
            epochs_without_improvement += 1

        save_training_checkpoint(
            output_directory / "latest.pt",
            model,
            optimizer,
            scheduler,
            scaler,
            epoch,
            best_score,
            epochs_without_improvement,
            metadata,
        )
        if args.save_every_epoch:
            save_training_checkpoint(
                output_directory / f"epoch_{epoch:03d}.pt",
                model,
                optimizer,
                scheduler,
                scaler,
                epoch,
                best_score,
                epochs_without_improvement,
                metadata,
            )

        if (
            validation_result is not None
            and args.early_stopping_patience > 0
            and epochs_without_improvement >= args.early_stopping_patience
        ):
            print(f"early_stopping epoch={epoch} best_score={best_score:.6f}")
            break

    save_checkpoint(model, output_directory, "semantic_albert_last")


def train_behavior(args: argparse.Namespace, config: CascadeConfig, device: torch.device) -> None:
    if not args.val_data:
        raise ValueError("--val-data is required for formal behavior training")
    output_directory = Path(args.output)
    output_directory.mkdir(parents=True, exist_ok=True)
    frame = load_reviews(args.data)
    validation_frame = load_reviews(args.val_data)
    builder = BehaviorFeatureBuilder(config.minimum_history, config.maximum_history)
    samples = builder.build(frame)
    validation_samples = builder.build(validation_frame)
    if not samples or not validation_samples:
        raise ValueError("behavior sequence construction produced an empty dataset")
    dataset = BehaviorSequenceDataset(samples)
    validation_dataset = BehaviorSequenceDataset(validation_samples)
    loader = make_loader(dataset, args, shuffle=True, device=device, collate_fn=collate_behavior)
    validation_loader = make_loader(
        validation_dataset, args, shuffle=False, device=device, collate_fn=collate_behavior
    )
    binary_targets = torch.tensor([sample.binary_label for sample in samples], dtype=torch.long)
    type_targets = torch.tensor(
        [sample.type_label for sample in samples if sample.type_label >= 0], dtype=torch.long
    )
    binary_weights = (
        powered_class_weights(binary_targets, 2, args.class_weight_exponent)
        if args.class_weighting
        else None
    )
    type_weights = (
        powered_class_weights(type_targets, 3, args.class_weight_exponent)
        if args.class_weighting and type_targets.numel()
        else None
    )
    print(f"behavior_train_samples={len(samples)} behavior_val_samples={len(validation_samples)}")
    if binary_weights is not None:
        print("behavior_binary_class_weights=", binary_weights.tolist())
        if type_weights is not None:
            print("behavior_type_class_weights=", type_weights.tolist())
        else:
            print("behavior_type_class_weights=disabled_no_type_labels")

    model = BehaviorLSTMClassifier(config).to(device)
    optimizer = AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    updates_per_epoch = math.ceil(len(loader) / args.gradient_accumulation_steps)
    total_updates = max(updates_per_epoch * args.epochs, 1)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(total_updates * args.warmup_ratio), total_updates
    )
    amp_enabled = bool(args.amp and device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)
    start_epoch = 1
    best_score = float("-inf")
    epochs_without_improvement = 0
    if args.resume:
        checkpoint = load_training_checkpoint(
            args.resume, model, optimizer, scheduler, scaler, map_location=device
        )
        start_epoch = int(checkpoint["epoch"]) + 1
        best_score = float(checkpoint.get("best_score", best_score))
        epochs_without_improvement = int(checkpoint.get("epochs_without_improvement", 0))

    metadata = {
        "stage": "behavior",
        "config": asdict(config),
        "training_arguments": vars(args),
        "behavior_type_supervision_samples": int(type_targets.numel()),
        "label_policy": {
            "label=1": "normal=0",
            "label=-1": "abnormal=1",
            "behavior_type": "optional_conditional_auxiliary_target",
            "history_below_minimum": "masked",
        },
    }
    history_path = output_directory / "history.jsonl"
    if not args.resume and history_path.exists():
        history_path.unlink()

    for epoch in range(start_epoch, args.epochs + 1):
        train_result = train_behavior_epoch(
            model,
            loader,
            optimizer,
            device,
            binary_class_weights=binary_weights,
            type_class_weights=type_weights,
            type_loss_weight=args.behavior_type_loss_weight,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            max_grad_norm=args.max_grad_norm,
            amp_enabled=amp_enabled,
            scaler=scaler,
            scheduler=scheduler,
        )
        validation_result = evaluate_behavior(
            model,
            validation_loader,
            device,
            binary_class_weights=binary_weights,
            type_class_weights=type_weights,
            type_loss_weight=args.behavior_type_loss_weight,
            amp_enabled=amp_enabled,
        )
        append_jsonl(
            history_path,
            {
                "epoch": epoch,
                "train": train_result.as_dict(),
                "validation": validation_result.as_dict(),
            },
        )
        print(
            f"epoch={epoch} behavior_train_loss={train_result.loss:.6f} "
            f"behavior_val_loss={validation_result.loss:.6f} "
            f"val_abnormal_f1={validation_result.abnormal_f1:.6f} "
            f"val_pr_auc={validation_result.average_precision:.6f} "
            f"val_selection_score={validation_result.selection_score:.6f}"
        )
        print("behavior binary validation report:\n" + validation_result.binary_report)
        if validation_result.type_report:
            print("behavior type validation report:\n" + validation_result.type_report)
        improved = validation_result.selection_score > best_score
        if improved:
            best_score = validation_result.selection_score
            epochs_without_improvement = 0
            save_training_checkpoint(
                output_directory / "best.pt",
                model,
                optimizer,
                scheduler,
                scaler,
                epoch,
                best_score,
                epochs_without_improvement,
                metadata,
            )
            save_checkpoint(model, output_directory, "behavior_lstm_best")
        else:
            epochs_without_improvement += 1
        save_training_checkpoint(
            output_directory / "latest.pt",
            model,
            optimizer,
            scheduler,
            scaler,
            epoch,
            best_score,
            epochs_without_improvement,
            metadata,
        )
        if args.save_every_epoch:
            save_training_checkpoint(
                output_directory / f"epoch_{epoch:03d}.pt",
                model,
                optimizer,
                scheduler,
                scaler,
                epoch,
                best_score,
                epochs_without_improvement,
                metadata,
            )
        if (
            args.early_stopping_patience > 0
            and epochs_without_improvement >= args.early_stopping_patience
        ):
            print(f"early_stopping epoch={epoch} best_score={best_score:.6f}")
            break
    save_checkpoint(model, output_directory, "behavior_lstm_last")


def _load_module_weights(path: str, module: torch.nn.Module, device: torch.device) -> None:
    payload = torch.load(path, map_location=device)
    state = payload.get("model_state", payload) if isinstance(payload, dict) else payload
    if not isinstance(state, dict):
        raise ValueError(f"checkpoint does not contain a state dictionary: {path}")
    if state and all(key.startswith("module.") for key in state):
        state = {key.removeprefix("module."): value for key, value in state.items()}
    expected_keys = set(module.state_dict())
    if not expected_keys.intersection(state):
        module_prefix = "semantic." if isinstance(module, AlbertSemanticClassifier) else "behavior."
        nested_state = {
            key.removeprefix(module_prefix): value
            for key, value in state.items()
            if key.startswith(module_prefix)
        }
        if nested_state:
            state = nested_state
    module.load_state_dict(state)


def _set_encoder_trainability(model: CascadeDetector, enabled: bool) -> None:
    model.semantic.requires_grad_(enabled)
    model.behavior.requires_grad_(enabled)
    model.fusion.requires_grad_(True)


def train_fusion(args: argparse.Namespace, config: CascadeConfig, device: torch.device) -> None:
    if not args.val_data or not args.semantic_checkpoint or not args.behavior_checkpoint:
        raise ValueError(
            "fusion training requires --val-data, --semantic-checkpoint, and --behavior-checkpoint"
        )
    output_directory = Path(args.output)
    output_directory.mkdir(parents=True, exist_ok=True)
    tokenizer = AutoTokenizer.from_pretrained(config.albert_name_or_path)
    builder = BehaviorFeatureBuilder(config.minimum_history, config.maximum_history)
    train_frame = load_reviews(args.data)
    validation_frame = load_reviews(args.val_data)
    train_samples = builder.build(
        train_frame, include_insufficient=True, include_unavailable=True
    )
    validation_samples = builder.build(
        validation_frame, include_insufficient=True, include_unavailable=True
    )
    train_dataset = FusionReviewDataset(
        train_frame, train_samples, tokenizer, config.max_length
    )
    validation_dataset = FusionReviewDataset(
        validation_frame, validation_samples, tokenizer, config.max_length
    )
    train_loader = make_loader(
        train_dataset, args, shuffle=True, device=device, collate_fn=collate_fusion
    )
    validation_loader = make_loader(
        validation_dataset, args, shuffle=False, device=device, collate_fn=collate_fusion
    )
    authenticity_targets, semantic_targets_all = semantic_targets(train_frame)
    semantic_type_targets = semantic_targets_all[semantic_targets_all > 0] - 1
    behavior_binary_targets = torch.tensor(
        [sample.binary_label for sample in train_samples if sample.binary_label >= 0],
        dtype=torch.long,
    )
    behavior_type_targets = torch.tensor(
        [sample.type_label for sample in train_samples if sample.type_label >= 0],
        dtype=torch.long,
    )
    if args.class_weighting:
        authenticity_weights = powered_class_weights(
            authenticity_targets, 2, args.class_weight_exponent
        )
        semantic_type_weights = (
            powered_class_weights(semantic_type_targets, 3, args.class_weight_exponent)
            if semantic_type_targets.numel()
            else None
        )
        behavior_binary_weights = (
            powered_class_weights(behavior_binary_targets, 2, args.class_weight_exponent)
            if behavior_binary_targets.numel()
            else None
        )
        behavior_type_weights = (
            powered_class_weights(behavior_type_targets, 3, args.class_weight_exponent)
            if behavior_type_targets.numel()
            else None
        )
    else:
        authenticity_weights = None
        semantic_type_weights = None
        behavior_binary_weights = None
        behavior_type_weights = None
    print(
        f"fusion_train_samples={len(train_samples)} "
        f"fusion_val_samples={len(validation_samples)}"
    )
    if authenticity_weights is not None:
        print("fusion_authenticity_class_weights=", authenticity_weights.tolist())
        if semantic_type_weights is not None:
            print("fusion_semantic_type_class_weights=", semantic_type_weights.tolist())
        if behavior_binary_weights is not None:
            print("fusion_behavior_binary_class_weights=", behavior_binary_weights.tolist())
        if behavior_type_weights is not None:
            print("fusion_behavior_type_class_weights=", behavior_type_weights.tolist())
    model = CascadeDetector(config).to(device)
    _load_module_weights(args.semantic_checkpoint, model.semantic, device)
    _load_module_weights(args.behavior_checkpoint, model.behavior, device)
    optimizer = AdamW(
        [
            {"params": model.semantic.parameters(), "lr": args.semantic_learning_rate},
            {"params": model.behavior.parameters(), "lr": args.learning_rate},
            {"params": model.fusion.parameters(), "lr": args.learning_rate},
        ],
        weight_decay=args.weight_decay,
    )
    updates_per_epoch = math.ceil(len(train_loader) / args.gradient_accumulation_steps)
    total_updates = max(updates_per_epoch * args.epochs, 1)
    scheduler = get_linear_schedule_with_warmup(
        optimizer, int(total_updates * args.warmup_ratio), total_updates
    )
    amp_enabled = bool(args.amp and device.type == "cuda")
    scaler = torch.cuda.amp.GradScaler(enabled=amp_enabled)
    best_score = float("-inf")
    epochs_without_improvement = 0
    start_epoch = 1
    if args.resume:
        checkpoint = load_training_checkpoint(
            args.resume, model, optimizer, scheduler, scaler, map_location=device
        )
        start_epoch = int(checkpoint["epoch"]) + 1
        best_score = float(checkpoint.get("best_score", best_score))
        epochs_without_improvement = int(checkpoint.get("epochs_without_improvement", 0))
    metadata = {
        "stage": "fusion",
        "config": asdict(config),
        "training_arguments": vars(args),
        "label_policy": {
            "semantic_type": "conditional_on_fake",
            "behavior_type": "conditional_on_abnormal",
            "insufficient_evidence": "behavior_auxiliary_loss_mask_only",
            "history_below_minimum": "semantic_dominant_gate",
        },
    }
    history_path = output_directory / "history.jsonl"
    if not args.resume and history_path.exists():
        history_path.unlink()
    for epoch in range(start_epoch, args.epochs + 1):
        encoders_trainable = epoch > args.freeze_encoders_epochs
        _set_encoder_trainability(model, encoders_trainable)
        train_result = train_fusion_epoch(
            model,
            train_loader,
            optimizer,
            device,
            authenticity_class_weights=authenticity_weights,
            semantic_type_class_weights=semantic_type_weights,
            behavior_binary_class_weights=behavior_binary_weights,
            behavior_type_class_weights=behavior_type_weights,
            behavior_type_loss_weight=args.behavior_type_loss_weight,
            gradient_accumulation_steps=args.gradient_accumulation_steps,
            max_grad_norm=args.max_grad_norm,
            amp_enabled=amp_enabled,
            scaler=scaler,
            scheduler=scheduler,
            encoders_trainable=encoders_trainable,
        )
        validation_result = evaluate_fusion(
            model,
            validation_loader,
            device,
            authenticity_class_weights=authenticity_weights,
            semantic_type_class_weights=semantic_type_weights,
            behavior_binary_class_weights=behavior_binary_weights,
            behavior_type_class_weights=behavior_type_weights,
            behavior_type_loss_weight=args.behavior_type_loss_weight,
            amp_enabled=amp_enabled,
        )
        append_jsonl(
            history_path,
            {"epoch": epoch, "train": train_result.as_dict(), "validation": validation_result.as_dict()},
        )
        print(
            f"epoch={epoch} fusion_train_loss={train_result.loss:.6f} "
            f"fusion_val_loss={validation_result.loss:.6f} "
            f"val_auth_f1={validation_result.authenticity_macro_f1:.6f} "
            f"val_gate_mean={validation_result.gate_mean:.6f}"
        )
        print("fusion authenticity validation report:\n" + validation_result.authenticity_report)
        if validation_result.behavior_report:
            print("fusion behavior validation report:\n" + validation_result.behavior_report)
        improved = validation_result.selection_score > best_score
        if improved:
            best_score = validation_result.selection_score
            epochs_without_improvement = 0
            save_training_checkpoint(
                output_directory / "best.pt", model, optimizer, scheduler, scaler,
                epoch, best_score, epochs_without_improvement, metadata,
            )
            save_checkpoint(model, output_directory, "cascade_fusion_best")
        else:
            epochs_without_improvement += 1
        save_training_checkpoint(
            output_directory / "latest.pt", model, optimizer, scheduler, scaler,
            epoch, best_score, epochs_without_improvement, metadata,
        )
        if args.save_every_epoch:
            save_training_checkpoint(
                output_directory / f"epoch_{epoch:03d}.pt",
                model,
                optimizer,
                scheduler,
                scaler,
                epoch,
                best_score,
                epochs_without_improvement,
                metadata,
            )
        if (
            args.early_stopping_patience > 0
            and epochs_without_improvement >= args.early_stopping_patience
        ):
            print(f"early_stopping epoch={epoch} best_score={best_score:.6f}")
            break
    save_checkpoint(model, output_directory, "cascade_fusion_last")


def main() -> None:
    args = parse_args()
    stage_defaults = {
        "semantic": {"epochs": 3, "batch_size": 16, "learning_rate": 2e-5, "patience": 2},
        "behavior": {"epochs": 20, "batch_size": 512, "learning_rate": 1e-3, "patience": 3},
        "fusion": {"epochs": 5, "batch_size": 16, "learning_rate": 1e-4, "patience": 2},
    }[args.stage]
    args.epochs = args.epochs if args.epochs is not None else stage_defaults["epochs"]
    args.batch_size = (
        args.batch_size if args.batch_size is not None else stage_defaults["batch_size"]
    )
    args.learning_rate = (
        args.learning_rate
        if args.learning_rate is not None
        else stage_defaults["learning_rate"]
    )
    args.early_stopping_patience = (
        args.early_stopping_patience
        if args.early_stopping_patience is not None
        else stage_defaults["patience"]
    )
    if args.epochs < 1:
        raise ValueError("--epochs must be at least one")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least one")
    if args.gradient_accumulation_steps < 1:
        raise ValueError("--gradient-accumulation-steps must be at least one")
    if not 0.0 <= args.class_weight_exponent <= 1.0:
        raise ValueError("--class-weight-exponent must be between zero and one")
    if args.freeze_encoders_epochs < 0:
        raise ValueError("--freeze-encoders-epochs cannot be negative")
    if args.early_stopping_patience < 0:
        raise ValueError("--early-stopping-patience cannot be negative")
    if args.behavior_type_loss_weight < 0.0:
        raise ValueError("--behavior-type-loss-weight cannot be negative")
    set_seed(args.seed)
    config = CascadeConfig.from_json(args.config)
    config.validate()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device} amp={bool(args.amp and device.type == 'cuda')}")
    if args.stage == "semantic":
        train_semantic(args, config, device)
    elif args.stage == "behavior":
        train_behavior(args, config, device)
    else:
        train_fusion(args, config, device)


if __name__ == "__main__":
    main()
