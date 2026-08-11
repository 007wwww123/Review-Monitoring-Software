from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass
class CascadeConfig:
    albert_name_or_path: str = "albert/albert-base-v2"
    max_length: int = 256
    semantic_num_labels: int = 4
    behavior_num_labels: int = 5
    behavior_type_num_labels: int = 3
    behavior_input_size: int = 10
    behavior_hidden_size: int = 128
    behavior_num_layers: int = 1
    behavior_dropout: float = 0.2
    fusion_hidden_size: int = 256
    fusion_dropout: float = 0.2
    classifier_dropout: float = 0.1
    use_behavior_attention: bool = True
    real_exit_threshold: float = 0.92
    semantic_exit_threshold: float = 0.85
    behavior_trigger_threshold: float = 0.65
    uncertainty_entropy_threshold: float = 0.55
    authenticity_threshold: float = 0.5
    allow_type_override: bool = False
    minimum_history: int = 1
    maximum_history: int = 30
    semantic_labels: list[str] = field(
        default_factory=lambda: ["real", "misleading", "exaggerated", "advertising"]
    )
    behavior_labels: list[str] = field(
        default_factory=lambda: [
            "normal",
            "review_manipulation",
            "crowdturfing",
            "bot_like",
            "insufficient_evidence",
        ]
    )

    @classmethod
    def from_json(cls, path: str | Path) -> "CascadeConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls(**json.load(handle))

    def save_json(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(asdict(self), handle, ensure_ascii=False, indent=2)

    def validate(self) -> None:
        if self.semantic_num_labels != len(self.semantic_labels):
            raise ValueError("semantic_num_labels must match semantic_labels")
        if self.semantic_labels != ["real", "misleading", "exaggerated", "advertising"]:
            raise ValueError("semantic_labels must keep the hierarchical output order")
        if self.behavior_num_labels != len(self.behavior_labels):
            raise ValueError("behavior_num_labels must match behavior_labels")
        if self.behavior_labels != [
            "normal",
            "review_manipulation",
            "crowdturfing",
            "bot_like",
            "insufficient_evidence",
        ]:
            raise ValueError("behavior_labels must keep the hierarchical output order")
        if self.behavior_type_num_labels != 3:
            raise ValueError("behavior_type_num_labels must be three")
        if self.fusion_hidden_size < 1:
            raise ValueError("fusion_hidden_size must be positive")
        if self.minimum_history < 1 or self.maximum_history < self.minimum_history:
            raise ValueError("invalid history length settings")
        for name in (
            "real_exit_threshold",
            "semantic_exit_threshold",
            "behavior_trigger_threshold",
            "uncertainty_entropy_threshold",
            "authenticity_threshold",
        ):
            value: Any = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.allow_type_override:
            raise ValueError("allow_type_override must remain false for uncalibrated type heads")
