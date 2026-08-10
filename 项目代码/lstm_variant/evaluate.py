from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer

from spam_cascade.config import CascadeConfig
from spam_cascade.data import (
    BehaviorFeatureBuilder,
    FusionReviewDataset,
    collate_fusion,
    load_reviews,
)
from spam_cascade.modeling import CascadeDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate a frozen fusion checkpoint")
    parser.add_argument("--data", required=True, help="Sealed test TSV")
    parser.add_argument("--checkpoint", required=True, help="cascade_fusion_best.pt")
    parser.add_argument("--config", default="configs/base.json")
    parser.add_argument("--output", default="reports/fusion_test.json")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--amp", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_weights(model: torch.nn.Module, path: str | Path, device: torch.device) -> None:
    payload = torch.load(path, map_location=device)
    state = payload.get("model_state", payload) if isinstance(payload, dict) else payload
    if not isinstance(state, dict):
        raise ValueError("checkpoint does not contain a model state dictionary")
    if state and all(key.startswith("module.") for key in state):
        state = {key.removeprefix("module."): value for key, value in state.items()}
    model.load_state_dict(state)


def main() -> None:
    args = parse_args()
    if args.batch_size < 1 or args.num_workers < 0:
        raise ValueError("batch size must be positive and workers cannot be negative")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    use_amp = bool(args.amp and device.type == "cuda")
    config = CascadeConfig.from_json(args.config)
    config.validate()

    frame = load_reviews(args.data)
    tokenizer = AutoTokenizer.from_pretrained(config.albert_name_or_path)
    builder = BehaviorFeatureBuilder(config.minimum_history, config.maximum_history)
    samples = builder.build(frame, include_insufficient=True, include_unavailable=True)
    dataset = FusionReviewDataset(frame, samples, tokenizer, config.max_length)
    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=args.num_workers,
        pin_memory=device.type == "cuda",
        persistent_workers=args.num_workers > 0,
        collate_fn=collate_fusion,
    )

    model = CascadeDetector(config).to(device)
    load_weights(model, args.checkpoint, device)
    model.eval()

    truth: list[int] = []
    predictions: list[int] = []
    fake_probabilities: list[float] = []
    gate_sum = 0.0
    sample_count = 0

    with torch.no_grad():
        for batch in tqdm(loader, desc="sealed fusion test"):
            labels = batch.pop("authenticity_labels")
            batch.pop("semantic_labels")
            batch.pop("behavior_binary_labels")
            batch.pop("behavior_type_labels")
            batch = {key: value.to(device, non_blocking=True) for key, value in batch.items()}
            labels = labels.to(device, non_blocking=True)

            with torch.cuda.amp.autocast(enabled=use_amp):
                output = model(**batch)
            probabilities = torch.softmax(output.fusion.authenticity_logits, dim=-1)
            batch_size = labels.size(0)

            truth.extend(labels.cpu().tolist())
            predictions.extend(probabilities.argmax(-1).cpu().tolist())
            fake_probabilities.extend(probabilities[:, 1].cpu().tolist())
            gate_sum += float(output.fusion.gate_weights.mean()) * batch_size
            sample_count += batch_size

    report = classification_report(
        truth,
        predictions,
        labels=[0, 1],
        target_names=["real", "fake"],
        output_dict=True,
        zero_division=0,
    )
    matrix = confusion_matrix(truth, predictions, labels=[0, 1]).tolist()
    result = {
        "evaluation": "sealed_internal_test",
        "device": str(device),
        "amp": use_amp,
        "samples": sample_count,
        "data_path": str(Path(args.data).resolve()),
        "data_sha256": sha256(args.data),
        "checkpoint_path": str(Path(args.checkpoint).resolve()),
        "checkpoint_sha256": sha256(args.checkpoint),
        "accuracy": accuracy_score(truth, predictions),
        "macro_f1": f1_score(truth, predictions, average="macro", zero_division=0),
        "fake_average_precision": average_precision_score(truth, fake_probabilities),
        "roc_auc": roc_auc_score(truth, fake_probabilities) if len(set(truth)) == 2 else None,
        "gate_mean": gate_sum / max(sample_count, 1),
        "confusion_matrix": {
            "labels": ["real", "fake"],
            "rows_true_columns_predicted": matrix,
        },
        "classification_report": report,
    }

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)

    print("sealed internal test complete")
    print(f"samples={sample_count}")
    print(f"accuracy={result['accuracy']:.6f}")
    print(f"macro_f1={result['macro_f1']:.6f}")
    print(f"fake_average_precision={result['fake_average_precision']:.6f}")
    print(f"roc_auc={result['roc_auc']:.6f}")
    print(f"gate_mean={result['gate_mean']:.6f}")
    print("confusion_matrix rows=true columns=predicted:")
    print(np.asarray(matrix))
    print(
        classification_report(
            truth,
            predictions,
            labels=[0, 1],
            target_names=["real", "fake"],
            zero_division=0,
        )
    )
    print(f"report_saved={target}")


if __name__ == "__main__":
    main()
