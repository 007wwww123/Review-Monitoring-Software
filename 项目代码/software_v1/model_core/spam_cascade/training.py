from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Optional

import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    f1_score,
    precision_recall_fscore_support,
)
from torch import Tensor, nn
from torch.nn.utils import clip_grad_norm_
from torch.optim import Optimizer
from torch.utils.data import DataLoader
from tqdm import tqdm

from .modeling import AlbertSemanticClassifier, BehaviorLSTMClassifier, CascadeDetector


@dataclass
class EpochResult:
    loss: float
    macro_f1: float
    report: str


@dataclass
class SemanticEpochResult:
    loss: float
    authenticity_loss: float
    semantic_loss: float
    authenticity_accuracy: float
    semantic_accuracy: float
    authenticity_macro_f1: float
    semantic_macro_f1: float
    authenticity_report: str = ""
    semantic_report: str = ""

    @property
    def selection_score(self) -> float:
        # The standalone ALBERT stage is an authenticity binary classifier.
        # Fine-grained semantic types are learned later by the fusion stage.
        return self.authenticity_macro_f1

    def as_dict(self) -> dict[str, float]:
        return {
            "loss": self.loss,
            "authenticity_loss": self.authenticity_loss,
            "semantic_loss": self.semantic_loss,
            "authenticity_accuracy": self.authenticity_accuracy,
            "semantic_accuracy": self.semantic_accuracy,
            "authenticity_macro_f1": self.authenticity_macro_f1,
            "semantic_macro_f1": self.semantic_macro_f1,
            "selection_score": self.selection_score,
        }


@dataclass
class BehaviorEpochResult:
    loss: float
    binary_loss: float
    type_loss: float
    accuracy: float
    macro_f1: float
    abnormal_precision: float
    abnormal_recall: float
    abnormal_f1: float
    average_precision: float
    binary_report: str = ""
    type_report: str = ""

    @property
    def selection_score(self) -> float:
        return (self.abnormal_f1 + self.average_precision) / 2.0

    def as_dict(self) -> dict[str, float]:
        return {
            "loss": self.loss,
            "binary_loss": self.binary_loss,
            "type_loss": self.type_loss,
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1,
            "abnormal_precision": self.abnormal_precision,
            "abnormal_recall": self.abnormal_recall,
            "abnormal_f1": self.abnormal_f1,
            "average_precision": self.average_precision,
            "selection_score": self.selection_score,
        }


@dataclass
class FusionEpochResult:
    loss: float
    authenticity_accuracy: float
    semantic_accuracy: float
    authenticity_macro_f1: float
    semantic_macro_f1: float
    behavior_abnormal_f1: float
    gate_mean: float
    authenticity_report: str = ""
    semantic_report: str = ""
    behavior_report: str = ""

    @property
    def selection_score(self) -> float:
        # Final model selection is based only on fused real/fake performance.
        return self.authenticity_macro_f1

    def as_dict(self) -> dict[str, float]:
        return {
            "loss": self.loss,
            "authenticity_accuracy": self.authenticity_accuracy,
            "semantic_accuracy": self.semantic_accuracy,
            "authenticity_macro_f1": self.authenticity_macro_f1,
            "semantic_macro_f1": self.semantic_macro_f1,
            "behavior_abnormal_f1": self.behavior_abnormal_f1,
            "gate_mean": self.gate_mean,
            "selection_score": self.selection_score,
        }


def _move(batch: dict[str, Tensor], device: torch.device) -> dict[str, Tensor]:
    return {key: value.to(device, non_blocking=True) for key, value in batch.items()}


def balanced_class_weights(labels: Tensor, num_classes: int) -> Tensor:
    """Return inverse-frequency weights with mean weight close to one."""
    counts = torch.bincount(labels.to(torch.long).cpu(), minlength=num_classes).to(torch.float32)
    weights = torch.zeros_like(counts)
    present = counts > 0
    weights[present] = counts[present].sum() / (present.sum() * counts[present])
    return weights


def powered_class_weights(labels: Tensor, num_classes: int, exponent: float = 0.5) -> Tensor:
    """Return softened inverse-frequency weights with stable loss scale."""
    if not 0.0 <= exponent <= 1.0:
        raise ValueError("class-weight exponent must be between zero and one")
    labels = labels.to(torch.long).cpu()
    labels = labels[labels >= 0]
    counts = torch.bincount(labels, minlength=num_classes).to(torch.float32)
    present = counts > 0
    weights = torch.zeros_like(counts)
    if not torch.any(present):
        return weights
    inverse = counts[present].sum() / (present.sum() * counts[present])
    weights[present] = inverse.pow(exponent)
    sample_mean = (weights[present] * counts[present]).sum() / counts[present].sum()
    weights[present] /= sample_mean
    return weights


def _conditional_cross_entropy(
    logits: Tensor,
    labels: Tensor,
    loss_fn: nn.Module,
) -> Tensor:
    valid = labels >= 0
    if torch.any(valid):
        return loss_fn(logits[valid], labels[valid])
    return logits.sum() * 0.0


def _safe_average_precision(truth: list[int], probabilities: list[float]) -> float:
    if len(set(truth)) < 2:
        return 0.0
    return float(average_precision_score(truth, probabilities))


def _semantic_losses(
    output: Any,
    authenticity_labels: Tensor,
    semantic_labels: Tensor,
    authenticity_loss_fn: nn.Module,
    semantic_loss_fn: nn.Module,
    authenticity_weight: float,
    semantic_weight: float,
) -> tuple[Tensor, Tensor, Tensor]:
    authenticity_loss = authenticity_loss_fn(output.authenticity_logits, authenticity_labels)
    if semantic_weight == 0.0:
        semantic_loss = output.semantic_logits.sum() * 0.0
        return authenticity_weight * authenticity_loss, authenticity_loss, semantic_loss
    type_labels = semantic_labels - 1
    type_labels = type_labels.masked_fill(semantic_labels == 0, -100)
    semantic_loss = _conditional_cross_entropy(
        output.semantic_logits[..., 1:], type_labels, semantic_loss_fn
    )
    total_loss = authenticity_weight * authenticity_loss + semantic_weight * semantic_loss
    return total_loss, authenticity_loss, semantic_loss


def train_semantic_epoch(
    model: AlbertSemanticClassifier,
    loader: DataLoader,
    optimizer: Optimizer,
    device: torch.device,
    authenticity_class_weights: Optional[Tensor] = None,
    semantic_class_weights: Optional[Tensor] = None,
    authenticity_weight: float = 1.0,
    semantic_weight: float = 1.0,
    binary_only: bool = False,
    gradient_accumulation_steps: int = 1,
    max_grad_norm: float = 1.0,
    amp_enabled: bool = True,
    scaler: Optional[torch.cuda.amp.GradScaler] = None,
    scheduler: Optional[Any] = None,
) -> SemanticEpochResult:
    if gradient_accumulation_steps < 1:
        raise ValueError("gradient_accumulation_steps must be at least one")

    model.train()
    use_amp = bool(amp_enabled and device.type == "cuda")
    scaler = scaler or torch.cuda.amp.GradScaler(enabled=use_amp)
    authenticity_loss_fn = nn.CrossEntropyLoss(
        weight=authenticity_class_weights.to(device) if authenticity_class_weights is not None else None
    )
    semantic_loss_fn = nn.CrossEntropyLoss(
        weight=semantic_class_weights.to(device) if semantic_class_weights is not None else None
    )

    optimizer.zero_grad(set_to_none=True)
    total_loss = 0.0
    total_authenticity_loss = 0.0
    total_semantic_loss = 0.0
    sample_count = 0
    authenticity_truth: list[int] = []
    authenticity_predictions: list[int] = []
    semantic_truth: list[int] = []
    semantic_predictions: list[int] = []

    progress = tqdm(loader, desc="semantic train")
    for step, batch in enumerate(progress, start=1):
        batch = _move(batch, device)
        authenticity_labels = batch.pop("authenticity_labels")
        semantic_labels = batch.pop("semantic_labels")
        batch_size = authenticity_labels.size(0)

        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            loss, authenticity_loss, semantic_loss = _semantic_losses(
                output,
                authenticity_labels,
                semantic_labels,
                authenticity_loss_fn,
                semantic_loss_fn,
                authenticity_weight,
                semantic_weight,
            )
            backward_loss = loss / gradient_accumulation_steps

        scaler.scale(backward_loss).backward()
        should_update = step % gradient_accumulation_steps == 0 or step == len(loader)
        if should_update:
            scaler.unscale_(optimizer)
            clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            if scheduler is not None:
                scheduler.step()

        total_loss += float(loss.detach()) * batch_size
        total_authenticity_loss += float(authenticity_loss.detach()) * batch_size
        total_semantic_loss += float(semantic_loss.detach()) * batch_size
        sample_count += batch_size
        authenticity_truth.extend(authenticity_labels.detach().cpu().tolist())
        authenticity_predictions.extend(output.authenticity_logits.detach().argmax(-1).cpu().tolist())
        if not binary_only:
            semantic_truth.extend(semantic_labels.detach().cpu().tolist())
            semantic_predictions.extend(
                output.semantic_relative_probabilities.detach().argmax(-1).cpu().tolist()
            )
        progress.set_postfix(loss=f"{total_loss / sample_count:.4f}")

    return SemanticEpochResult(
        loss=total_loss / max(sample_count, 1),
        authenticity_loss=total_authenticity_loss / max(sample_count, 1),
        semantic_loss=total_semantic_loss / max(sample_count, 1),
        authenticity_accuracy=accuracy_score(authenticity_truth, authenticity_predictions),
        semantic_accuracy=(
            accuracy_score(semantic_truth, semantic_predictions) if semantic_truth else 0.0
        ),
        authenticity_macro_f1=f1_score(
            authenticity_truth, authenticity_predictions, average="macro", zero_division=0
        ),
        semantic_macro_f1=(
            f1_score(semantic_truth, semantic_predictions, average="macro", zero_division=0)
            if semantic_truth
            else 0.0
        ),
    )


@torch.no_grad()
def evaluate_semantic(
    model: AlbertSemanticClassifier,
    loader: DataLoader,
    device: torch.device,
    semantic_label_names: list[str],
    authenticity_class_weights: Optional[Tensor] = None,
    semantic_class_weights: Optional[Tensor] = None,
    authenticity_weight: float = 1.0,
    semantic_weight: float = 1.0,
    binary_only: bool = False,
    amp_enabled: bool = True,
) -> SemanticEpochResult:
    model.eval()
    use_amp = bool(amp_enabled and device.type == "cuda")
    authenticity_loss_fn = nn.CrossEntropyLoss(
        weight=authenticity_class_weights.to(device) if authenticity_class_weights is not None else None
    )
    semantic_loss_fn = nn.CrossEntropyLoss(
        weight=semantic_class_weights.to(device) if semantic_class_weights is not None else None
    )

    total_loss = 0.0
    total_authenticity_loss = 0.0
    total_semantic_loss = 0.0
    sample_count = 0
    authenticity_truth: list[int] = []
    authenticity_predictions: list[int] = []
    semantic_truth: list[int] = []
    semantic_predictions: list[int] = []

    for batch in tqdm(loader, desc="semantic validation"):
        batch = _move(batch, device)
        authenticity_labels = batch.pop("authenticity_labels")
        semantic_labels = batch.pop("semantic_labels")
        batch_size = authenticity_labels.size(0)
        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            loss, authenticity_loss, semantic_loss = _semantic_losses(
                output,
                authenticity_labels,
                semantic_labels,
                authenticity_loss_fn,
                semantic_loss_fn,
                authenticity_weight,
                semantic_weight,
            )

        total_loss += float(loss.detach()) * batch_size
        total_authenticity_loss += float(authenticity_loss.detach()) * batch_size
        total_semantic_loss += float(semantic_loss.detach()) * batch_size
        sample_count += batch_size
        authenticity_truth.extend(authenticity_labels.cpu().tolist())
        authenticity_predictions.extend(output.authenticity_logits.argmax(-1).cpu().tolist())
        if not binary_only:
            semantic_truth.extend(semantic_labels.cpu().tolist())
            semantic_predictions.extend(
                output.semantic_relative_probabilities.argmax(-1).cpu().tolist()
            )

    authenticity_names = ["real", "fake"]
    authenticity_labels_order = list(range(len(authenticity_names)))
    return SemanticEpochResult(
        loss=total_loss / max(sample_count, 1),
        authenticity_loss=total_authenticity_loss / max(sample_count, 1),
        semantic_loss=total_semantic_loss / max(sample_count, 1),
        authenticity_accuracy=accuracy_score(authenticity_truth, authenticity_predictions),
        semantic_accuracy=(
            accuracy_score(semantic_truth, semantic_predictions) if semantic_truth else 0.0
        ),
        authenticity_macro_f1=f1_score(
            authenticity_truth, authenticity_predictions, average="macro", zero_division=0
        ),
        semantic_macro_f1=(
            f1_score(semantic_truth, semantic_predictions, average="macro", zero_division=0)
            if semantic_truth
            else 0.0
        ),
        authenticity_report=classification_report(
            authenticity_truth,
            authenticity_predictions,
            labels=authenticity_labels_order,
            target_names=authenticity_names,
            zero_division=0,
        ),
        semantic_report=(
            classification_report(
                semantic_truth,
                semantic_predictions,
                labels=list(range(len(semantic_label_names))),
                target_names=semantic_label_names,
                zero_division=0,
            )
            if semantic_truth
            else ""
        ),
    )


def train_behavior_epoch(
    model: BehaviorLSTMClassifier,
    loader: DataLoader,
    optimizer: Optimizer,
    device: torch.device,
    binary_class_weights: Optional[Tensor] = None,
    type_class_weights: Optional[Tensor] = None,
    type_loss_weight: float = 0.3,
    gradient_accumulation_steps: int = 1,
    max_grad_norm: float = 1.0,
    amp_enabled: bool = True,
    scaler: Optional[torch.cuda.amp.GradScaler] = None,
    scheduler: Optional[Any] = None,
) -> BehaviorEpochResult:
    model.train()
    use_amp = bool(amp_enabled and device.type == "cuda")
    scaler = scaler or torch.cuda.amp.GradScaler(enabled=use_amp)
    binary_loss_fn = nn.CrossEntropyLoss(
        weight=binary_class_weights.to(device) if binary_class_weights is not None else None
    )
    type_loss_fn = nn.CrossEntropyLoss(
        weight=type_class_weights.to(device) if type_class_weights is not None else None
    )
    optimizer.zero_grad(set_to_none=True)
    total_loss = 0.0
    total_binary_loss = 0.0
    total_type_loss = 0.0
    sample_count = 0
    type_sample_count = 0
    truth: list[int] = []
    predictions: list[int] = []
    abnormal_probabilities: list[float] = []
    type_truth: list[int] = []
    type_predictions: list[int] = []
    progress = tqdm(loader, desc="behavior train")
    for step, batch in enumerate(progress, start=1):
        batch = _move(batch, device)
        binary_labels = batch.pop("binary_labels")
        type_labels = batch.pop("type_labels")
        batch_size = binary_labels.size(0)
        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            binary_loss = binary_loss_fn(output.normality_logits, binary_labels)
            type_loss = _conditional_cross_entropy(output.type_logits, type_labels, type_loss_fn)
            loss = binary_loss + type_loss_weight * type_loss
            backward_loss = loss / gradient_accumulation_steps
        scaler.scale(backward_loss).backward()
        should_update = step % gradient_accumulation_steps == 0 or step == len(loader)
        if should_update:
            scaler.unscale_(optimizer)
            clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            if scheduler is not None:
                scheduler.step()

        probabilities = torch.softmax(output.normality_logits.detach(), dim=-1)
        total_loss += float(loss.detach()) * batch_size
        total_binary_loss += float(binary_loss.detach()) * batch_size
        sample_count += batch_size
        truth.extend(binary_labels.detach().cpu().tolist())
        predictions.extend(output.normality_logits.detach().argmax(-1).cpu().tolist())
        abnormal_probabilities.extend(probabilities[..., 1].cpu().tolist())
        valid_types = type_labels >= 0
        if torch.any(valid_types):
            valid_type_count = int(valid_types.sum().item())
            total_type_loss += float(type_loss.detach()) * valid_type_count
            type_sample_count += valid_type_count
            type_truth.extend(type_labels[valid_types].detach().cpu().tolist())
            type_predictions.extend(
                output.type_logits[valid_types].detach().argmax(-1).cpu().tolist()
            )
        progress.set_postfix(loss=f"{total_loss / sample_count:.4f}")
    return _behavior_result(
        total_loss,
        total_binary_loss,
        total_type_loss,
        sample_count,
        type_sample_count,
        truth,
        predictions,
        abnormal_probabilities,
        type_truth,
        type_predictions,
    )


@torch.no_grad()
def evaluate_behavior(
    model: BehaviorLSTMClassifier,
    loader: DataLoader,
    device: torch.device,
    binary_class_weights: Optional[Tensor] = None,
    type_class_weights: Optional[Tensor] = None,
    type_loss_weight: float = 0.3,
    amp_enabled: bool = True,
) -> BehaviorEpochResult:
    model.eval()
    use_amp = bool(amp_enabled and device.type == "cuda")
    binary_loss_fn = nn.CrossEntropyLoss(
        weight=binary_class_weights.to(device) if binary_class_weights is not None else None
    )
    type_loss_fn = nn.CrossEntropyLoss(
        weight=type_class_weights.to(device) if type_class_weights is not None else None
    )
    total_loss = 0.0
    total_binary_loss = 0.0
    total_type_loss = 0.0
    sample_count = 0
    type_sample_count = 0
    truth: list[int] = []
    predictions: list[int] = []
    abnormal_probabilities: list[float] = []
    type_truth: list[int] = []
    type_predictions: list[int] = []
    for batch in tqdm(loader, desc="behavior eval"):
        batch = _move(batch, device)
        binary_labels = batch.pop("binary_labels")
        type_labels = batch.pop("type_labels")
        batch_size = binary_labels.size(0)
        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            binary_loss = binary_loss_fn(output.normality_logits, binary_labels)
            type_loss = _conditional_cross_entropy(output.type_logits, type_labels, type_loss_fn)
            loss = binary_loss + type_loss_weight * type_loss
        probabilities = torch.softmax(output.normality_logits, dim=-1)
        total_loss += float(loss) * batch_size
        total_binary_loss += float(binary_loss) * batch_size
        sample_count += batch_size
        truth.extend(binary_labels.cpu().tolist())
        predictions.extend(output.normality_logits.argmax(-1).cpu().tolist())
        abnormal_probabilities.extend(probabilities[..., 1].cpu().tolist())
        valid_types = type_labels >= 0
        if torch.any(valid_types):
            valid_type_count = int(valid_types.sum().item())
            total_type_loss += float(type_loss) * valid_type_count
            type_sample_count += valid_type_count
            type_truth.extend(type_labels[valid_types].cpu().tolist())
            type_predictions.extend(output.type_logits[valid_types].argmax(-1).cpu().tolist())
    return _behavior_result(
        total_loss,
        total_binary_loss,
        total_type_loss,
        sample_count,
        type_sample_count,
        truth,
        predictions,
        abnormal_probabilities,
        type_truth,
        type_predictions,
    )


def _behavior_result(
    total_loss: float,
    total_binary_loss: float,
    total_type_loss: float,
    sample_count: int,
    type_sample_count: int,
    truth: list[int],
    predictions: list[int],
    abnormal_probabilities: list[float],
    type_truth: list[int],
    type_predictions: list[int],
) -> BehaviorEpochResult:
    precision, recall, abnormal_f1, _ = precision_recall_fscore_support(
        truth, predictions, labels=[1], average=None, zero_division=0
    )
    type_report = ""
    if type_truth:
        type_report = classification_report(
            type_truth,
            type_predictions,
            labels=[0, 1, 2],
            target_names=["review_manipulation", "crowdturfing", "bot_like"],
            zero_division=0,
        )
    return BehaviorEpochResult(
        loss=total_loss / max(sample_count, 1),
        binary_loss=total_binary_loss / max(sample_count, 1),
        type_loss=total_type_loss / max(type_sample_count, 1),
        accuracy=accuracy_score(truth, predictions),
        macro_f1=f1_score(truth, predictions, average="macro", zero_division=0),
        abnormal_precision=float(precision[0]),
        abnormal_recall=float(recall[0]),
        abnormal_f1=float(abnormal_f1[0]),
        average_precision=_safe_average_precision(truth, abnormal_probabilities),
        binary_report=classification_report(
            truth,
            predictions,
            labels=[0, 1],
            target_names=["normal", "abnormal"],
            zero_division=0,
        ),
        type_report=type_report,
    )


def _fusion_losses(
    output: Any,
    authenticity_labels: Tensor,
    semantic_labels: Tensor,
    behavior_binary_labels: Tensor,
    behavior_type_labels: Tensor,
    authenticity_loss_fn: nn.Module,
    semantic_type_loss_fn: nn.Module,
    behavior_binary_loss_fn: nn.Module,
    behavior_type_loss_fn: nn.Module,
    behavior_type_loss_weight: float,
) -> Tensor:
    final_auth = authenticity_loss_fn(output.fusion.authenticity_logits, authenticity_labels)
    semantic_auth_aux = authenticity_loss_fn(
        output.semantic.authenticity_logits, authenticity_labels
    )
    behavior_binary = _conditional_cross_entropy(
        output.behavior.normality_logits, behavior_binary_labels, behavior_binary_loss_fn
    )
    behavior_type = _conditional_cross_entropy(
        output.behavior.type_logits, behavior_type_labels, behavior_type_loss_fn
    )
    return (
        final_auth
        + 0.5 * behavior_binary
        + behavior_type_loss_weight * behavior_type
        + 0.5 * semantic_auth_aux
    )


def train_fusion_epoch(
    model: CascadeDetector,
    loader: DataLoader,
    optimizer: Optimizer,
    device: torch.device,
    authenticity_class_weights: Optional[Tensor] = None,
    semantic_type_class_weights: Optional[Tensor] = None,
    behavior_binary_class_weights: Optional[Tensor] = None,
    behavior_type_class_weights: Optional[Tensor] = None,
    behavior_type_loss_weight: float = 0.3,
    gradient_accumulation_steps: int = 1,
    max_grad_norm: float = 1.0,
    amp_enabled: bool = True,
    scaler: Optional[torch.cuda.amp.GradScaler] = None,
    scheduler: Optional[Any] = None,
    encoders_trainable: bool = True,
) -> FusionEpochResult:
    model.train()
    if not encoders_trainable:
        model.semantic.eval()
        model.behavior.eval()
    use_amp = bool(amp_enabled and device.type == "cuda")
    scaler = scaler or torch.cuda.amp.GradScaler(enabled=use_amp)
    authenticity_loss_fn = nn.CrossEntropyLoss(
        weight=(
            authenticity_class_weights.to(device)
            if authenticity_class_weights is not None
            else None
        )
    )
    semantic_type_loss_fn = nn.CrossEntropyLoss(
        weight=(
            semantic_type_class_weights.to(device)
            if semantic_type_class_weights is not None
            else None
        )
    )
    behavior_binary_loss_fn = nn.CrossEntropyLoss(
        weight=(
            behavior_binary_class_weights.to(device)
            if behavior_binary_class_weights is not None
            else None
        )
    )
    behavior_type_loss_fn = nn.CrossEntropyLoss(
        weight=(
            behavior_type_class_weights.to(device)
            if behavior_type_class_weights is not None
            else None
        )
    )
    optimizer.zero_grad(set_to_none=True)
    total_loss = 0.0
    sample_count = 0
    auth_truth: list[int] = []
    auth_predictions: list[int] = []
    semantic_truth: list[int] = []
    semantic_predictions: list[int] = []
    behavior_truth: list[int] = []
    behavior_predictions: list[int] = []
    gate_total = 0.0
    progress = tqdm(loader, desc="fusion train")
    for step, batch in enumerate(progress, start=1):
        batch = _move(batch, device)
        authenticity_labels = batch.pop("authenticity_labels")
        semantic_labels = batch.pop("semantic_labels")
        behavior_binary_labels = batch.pop("behavior_binary_labels")
        behavior_type_labels = batch.pop("behavior_type_labels")
        batch_size = authenticity_labels.size(0)
        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            loss = _fusion_losses(
                output,
                authenticity_labels,
                semantic_labels,
                behavior_binary_labels,
                behavior_type_labels,
                authenticity_loss_fn,
                semantic_type_loss_fn,
                behavior_binary_loss_fn,
                behavior_type_loss_fn,
                behavior_type_loss_weight,
            )
            backward_loss = loss / gradient_accumulation_steps
        scaler.scale(backward_loss).backward()
        should_update = step % gradient_accumulation_steps == 0 or step == len(loader)
        if should_update:
            scaler.unscale_(optimizer)
            clip_grad_norm_(model.parameters(), max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
            optimizer.zero_grad(set_to_none=True)
            if scheduler is not None:
                scheduler.step()
        total_loss += float(loss.detach()) * batch_size
        sample_count += batch_size
        gate_total += float(output.fusion.gate_weights.detach().mean()) * batch_size
        auth_truth.extend(authenticity_labels.detach().cpu().tolist())
        auth_predictions.extend(output.fusion.authenticity_logits.detach().argmax(-1).cpu().tolist())
        valid_behavior = behavior_binary_labels >= 0
        if torch.any(valid_behavior):
            behavior_truth.extend(behavior_binary_labels[valid_behavior].detach().cpu().tolist())
            behavior_predictions.extend(
                output.behavior.normality_logits[valid_behavior].detach().argmax(-1).cpu().tolist()
            )
        progress.set_postfix(loss=f"{total_loss / sample_count:.4f}")
    return _fusion_result(
        total_loss,
        sample_count,
        auth_truth,
        auth_predictions,
        semantic_truth,
        semantic_predictions,
        behavior_truth,
        behavior_predictions,
        gate_total,
    )


@torch.no_grad()
def evaluate_fusion(
    model: CascadeDetector,
    loader: DataLoader,
    device: torch.device,
    authenticity_class_weights: Optional[Tensor] = None,
    semantic_type_class_weights: Optional[Tensor] = None,
    behavior_binary_class_weights: Optional[Tensor] = None,
    behavior_type_class_weights: Optional[Tensor] = None,
    behavior_type_loss_weight: float = 0.3,
    amp_enabled: bool = True,
) -> FusionEpochResult:
    model.eval()
    use_amp = bool(amp_enabled and device.type == "cuda")
    authenticity_loss_fn = nn.CrossEntropyLoss(
        weight=(
            authenticity_class_weights.to(device)
            if authenticity_class_weights is not None
            else None
        )
    )
    semantic_type_loss_fn = nn.CrossEntropyLoss(
        weight=(
            semantic_type_class_weights.to(device)
            if semantic_type_class_weights is not None
            else None
        )
    )
    behavior_binary_loss_fn = nn.CrossEntropyLoss(
        weight=(
            behavior_binary_class_weights.to(device)
            if behavior_binary_class_weights is not None
            else None
        )
    )
    behavior_type_loss_fn = nn.CrossEntropyLoss(
        weight=(
            behavior_type_class_weights.to(device)
            if behavior_type_class_weights is not None
            else None
        )
    )
    total_loss = 0.0
    sample_count = 0
    auth_truth: list[int] = []
    auth_predictions: list[int] = []
    semantic_truth: list[int] = []
    semantic_predictions: list[int] = []
    behavior_truth: list[int] = []
    behavior_predictions: list[int] = []
    gate_total = 0.0
    for batch in tqdm(loader, desc="fusion validation"):
        batch = _move(batch, device)
        authenticity_labels = batch.pop("authenticity_labels")
        semantic_labels = batch.pop("semantic_labels")
        behavior_binary_labels = batch.pop("behavior_binary_labels")
        behavior_type_labels = batch.pop("behavior_type_labels")
        batch_size = authenticity_labels.size(0)
        with torch.cuda.amp.autocast(enabled=use_amp):
            output = model(**batch)
            loss = _fusion_losses(
                output,
                authenticity_labels,
                semantic_labels,
                behavior_binary_labels,
                behavior_type_labels,
                authenticity_loss_fn,
                semantic_type_loss_fn,
                behavior_binary_loss_fn,
                behavior_type_loss_fn,
                behavior_type_loss_weight,
            )
        total_loss += float(loss) * batch_size
        sample_count += batch_size
        gate_total += float(output.fusion.gate_weights.mean()) * batch_size
        auth_truth.extend(authenticity_labels.cpu().tolist())
        auth_predictions.extend(output.fusion.authenticity_logits.argmax(-1).cpu().tolist())
        valid_behavior = behavior_binary_labels >= 0
        if torch.any(valid_behavior):
            behavior_truth.extend(behavior_binary_labels[valid_behavior].cpu().tolist())
            behavior_predictions.extend(
                output.behavior.normality_logits[valid_behavior].argmax(-1).cpu().tolist()
            )
    return _fusion_result(
        total_loss,
        sample_count,
        auth_truth,
        auth_predictions,
        semantic_truth,
        semantic_predictions,
        behavior_truth,
        behavior_predictions,
        gate_total,
        include_reports=True,
    )


def _fusion_result(
    total_loss: float,
    sample_count: int,
    auth_truth: list[int],
    auth_predictions: list[int],
    semantic_truth: list[int],
    semantic_predictions: list[int],
    behavior_truth: list[int],
    behavior_predictions: list[int],
    gate_total: float,
    include_reports: bool = False,
) -> FusionEpochResult:
    behavior_f1 = (
        f1_score(behavior_truth, behavior_predictions, labels=[1], average=None, zero_division=0)[0]
        if behavior_truth
        else 0.0
    )
    return FusionEpochResult(
        loss=total_loss / max(sample_count, 1),
        authenticity_accuracy=accuracy_score(auth_truth, auth_predictions),
        semantic_accuracy=(
            accuracy_score(semantic_truth, semantic_predictions) if semantic_truth else 0.0
        ),
        authenticity_macro_f1=f1_score(auth_truth, auth_predictions, average="macro", zero_division=0),
        semantic_macro_f1=(
            f1_score(semantic_truth, semantic_predictions, average="macro", zero_division=0)
            if semantic_truth
            else 0.0
        ),
        behavior_abnormal_f1=float(behavior_f1),
        gate_mean=gate_total / max(sample_count, 1),
        authenticity_report=(
            classification_report(
                auth_truth,
                auth_predictions,
                labels=[0, 1],
                target_names=["real", "fake"],
                zero_division=0,
            )
            if include_reports
            else ""
        ),
        semantic_report=(
            classification_report(
                semantic_truth,
                semantic_predictions,
                labels=[0, 1, 2, 3],
                target_names=["real", "misleading", "exaggerated", "advertising"],
                zero_division=0,
            )
            if include_reports and semantic_truth
            else ""
        ),
        behavior_report=(
            classification_report(
                behavior_truth,
                behavior_predictions,
                labels=[0, 1],
                target_names=["normal", "abnormal"],
                zero_division=0,
            )
            if include_reports and behavior_truth
            else ""
        ),
    )


def save_checkpoint(model: nn.Module, directory: str | Path, name: str) -> Path:
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.pt"
    torch.save(model.state_dict(), path)
    return path


def save_training_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: Optimizer,
    scheduler: Optional[Any],
    scaler: Optional[torch.cuda.amp.GradScaler],
    epoch: int,
    best_score: float,
    epochs_without_improvement: int,
    metadata: Optional[dict[str, Any]] = None,
) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    payload = {
        "epoch": epoch,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict() if scheduler is not None else None,
        "scaler_state": scaler.state_dict() if scaler is not None else None,
        "best_score": best_score,
        "epochs_without_improvement": epochs_without_improvement,
        "metadata": metadata or {},
    }
    torch.save(payload, temporary)
    temporary.replace(target)
    return target


def load_training_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: Optional[Optimizer] = None,
    scheduler: Optional[Any] = None,
    scaler: Optional[torch.cuda.amp.GradScaler] = None,
    map_location: str | torch.device = "cpu",
) -> dict[str, Any]:
    checkpoint = torch.load(path, map_location=map_location)
    model.load_state_dict(checkpoint["model_state"])
    if optimizer is not None and checkpoint.get("optimizer_state") is not None:
        optimizer.load_state_dict(checkpoint["optimizer_state"])
    if scheduler is not None and checkpoint.get("scheduler_state") is not None:
        scheduler.load_state_dict(checkpoint["scheduler_state"])
    if scaler is not None and checkpoint.get("scaler_state") is not None:
        scaler.load_state_dict(checkpoint["scaler_state"])
    return checkpoint


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
