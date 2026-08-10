from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch import Tensor
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizerBase


SEMANTIC_LABELS = {"real": 0, "misleading": 1, "exaggerated": 2, "advertising": 3}
BEHAVIOR_LABELS = {
    "normal": 0,
    "review_manipulation": 1,
    "crowdturfing": 2,
    "bot_like": 3,
    "insufficient_evidence": 4,
}
BEHAVIOR_TYPE_LABELS = {
    "review_manipulation": 0,
    "crowdturfing": 1,
    "bot_like": 2,
}
ABNORMAL_BEHAVIOR_TYPES = frozenset(BEHAVIOR_TYPE_LABELS)


def load_reviews(path: str | Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep="\t", low_memory=False)
    unnamed = [column for column in frame.columns if column.startswith("Unnamed:")]
    if unnamed:
        frame = frame.rename(columns={unnamed[0]: "review_id"})
    elif frame.columns[0] == "":
        frame = frame.rename(columns={frame.columns[0]: "review_id"})
    if "review_id" not in frame.columns:
        frame.insert(0, "review_id", np.arange(len(frame), dtype=np.int64))
    if frame["review_id"].isna().any() or frame["review_id"].duplicated().any():
        raise ValueError("review_id must be non-null and unique within each TSV file")
    required = {"user_id", "prod_id", "rating", "label", "date", "text"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    frame["text"] = frame["text"].fillna("").astype(str)
    frame["authenticity_target"] = (frame["label"].astype(int) == -1).astype("int64")
    return frame


class SemanticReviewDataset(Dataset[dict[str, Tensor]]):
    def __init__(
        self,
        frame: pd.DataFrame,
        tokenizer: PreTrainedTokenizerBase,
        max_length: int,
    ) -> None:
        self.frame = frame.reset_index(drop=True)
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.frame)

    def __getitem__(self, index: int) -> dict[str, Tensor]:
        row = self.frame.iloc[index]
        encoded = self.tokenizer(
            row["text"],
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        item = {key: value.squeeze(0) for key, value in encoded.items()}
        item["authenticity_labels"] = torch.tensor(row["authenticity_target"], dtype=torch.long)
        semantic = SEMANTIC_LABELS.get(str(row.get("semantic_type", "real")), 0)
        item["semantic_labels"] = torch.tensor(semantic, dtype=torch.long)
        return item


@dataclass
class BehaviorSample:
    review_id: Any
    sequence: np.ndarray
    length: int
    behavior_available: float
    binary_label: int
    type_label: int

    @property
    def label(self) -> int:
        """Backward-compatible alias for the primary binary target."""
        return self.binary_label


class BehaviorFeatureBuilder:
    """Build leakage-safe sequences from the target event and its prior history."""

    feature_names = (
        "log_time_gap_hours",
        "rating",
        "rating_mean_before",
        "rating_std_before",
        "rating_deviation",
        "extreme_rating_ratio",
        "review_count_log",
        "unique_product_ratio",
        "same_product_ratio",
        "text_length_log",
    )

    def __init__(self, minimum_history: int = 3, maximum_history: int = 30) -> None:
        self.minimum_history = minimum_history
        self.maximum_history = maximum_history

    @staticmethod
    def _event_features(history: pd.DataFrame, current: pd.Series) -> np.ndarray:
        prior_ratings = history["rating"].astype(float).to_numpy()
        current_rating = float(current["rating"])
        mean = float(prior_ratings.mean()) if len(prior_ratings) else current_rating
        std = float(prior_ratings.std()) if len(prior_ratings) > 1 else 0.0
        previous_date = history.iloc[-1]["date"] if len(history) else current["date"]
        gap_hours = max((current["date"] - previous_date).total_seconds() / 3600.0, 0.0)
        products = history["prod_id"].astype(str) if len(history) else pd.Series(dtype=str)
        return np.asarray(
            [
                np.log1p(gap_hours),
                current_rating / 5.0,
                mean / 5.0,
                std / 5.0,
                abs(current_rating - mean) / 4.0,
                float(np.mean(np.isin(prior_ratings, [1.0, 5.0]))) if len(prior_ratings) else 0.0,
                np.log1p(len(history)),
                float(products.nunique() / len(products)) if len(products) else 0.0,
                float(np.mean(products == str(current["prod_id"]))) if len(products) else 0.0,
                np.log1p(len(str(current["text"]))) / 10.0,
            ],
            dtype=np.float32,
        )

    def build(
        self,
        frame: pd.DataFrame,
        *,
        include_insufficient: bool = False,
        include_unavailable: bool = False,
    ) -> list[BehaviorSample]:
        """Build hierarchical behavior samples without using future events.

        The target event is included as the final time step because its rating
        and time gap are observable at inference. Labels and later events never
        enter the feature sequence.
        """
        samples: list[BehaviorSample] = []
        has_behavior_type = "behavior_type" in frame.columns
        ordered = frame.sort_values(["user_id", "date", "review_id"], kind="stable")
        for _, group in ordered.groupby("user_id", sort=False):
            group = group.reset_index(drop=True)
            event_vectors: list[np.ndarray] = []
            for index, row in group.iterrows():
                history = group.iloc[:index]
                event_vectors.append(self._event_features(history, row))
                history_available = index >= self.minimum_history
                if not history_available and not include_unavailable:
                    continue
                sequence = np.stack(event_vectors[max(0, len(event_vectors) - self.maximum_history) :])

                if "authenticity_target" in row.index:
                    authenticity_target = int(row["authenticity_target"])
                else:
                    raw_label = int(row["label"])
                    if raw_label not in {-1, 1}:
                        raise ValueError(f"unsupported binary label: {raw_label}")
                    authenticity_target = int(raw_label == -1)

                behavior_name = "insufficient_evidence"
                if has_behavior_type:
                    raw_behavior_name = row.get(
                        "behavior_type", "insufficient_evidence"
                    )
                    if (
                        pd.notna(raw_behavior_name)
                        and str(raw_behavior_name) in BEHAVIOR_LABELS
                    ):
                        behavior_name = str(raw_behavior_name)

                if not history_available:
                    binary_label = -100
                    type_label = -100
                else:
                    binary_label = authenticity_target
                    type_label = -100
                if history_available and behavior_name in ABNORMAL_BEHAVIOR_TYPES:
                    type_label = BEHAVIOR_TYPE_LABELS[behavior_name]
                samples.append(
                    BehaviorSample(
                        review_id=row["review_id"],
                        sequence=sequence,
                        length=len(sequence),
                        behavior_available=float(history_available),
                        binary_label=binary_label,
                        type_label=type_label,
                    )
                )
        return samples


class BehaviorSequenceDataset(Dataset[BehaviorSample]):
    def __init__(self, samples: list[BehaviorSample]) -> None:
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> BehaviorSample:
        return self.samples[index]


def collate_behavior(samples: list[BehaviorSample]) -> dict[str, Tensor]:
    max_length = max(sample.length for sample in samples)
    feature_size = samples[0].sequence.shape[-1]
    sequences = torch.zeros(len(samples), max_length, feature_size, dtype=torch.float32)
    lengths = torch.tensor([sample.length for sample in samples], dtype=torch.long)
    available = torch.tensor(
        [sample.behavior_available for sample in samples], dtype=torch.float32
    )
    binary_labels = torch.tensor([sample.binary_label for sample in samples], dtype=torch.long)
    type_labels = torch.tensor([sample.type_label for sample in samples], dtype=torch.long)
    for index, sample in enumerate(samples):
        sequences[index, : sample.length] = torch.from_numpy(sample.sequence)
    return {
        "sequence": sequences,
        "lengths": lengths,
        "behavior_available": available,
        "binary_labels": binary_labels,
        "type_labels": type_labels,
    }


class FusionReviewDataset(Dataset[dict[str, Any]]):
    """Pair tokenized review text with its leakage-safe behavior sequence."""

    def __init__(
        self,
        frame: pd.DataFrame,
        samples: list[BehaviorSample],
        tokenizer: PreTrainedTokenizerBase,
        max_length: int,
    ) -> None:
        if frame["review_id"].duplicated().any():
            raise ValueError("review_id must be unique for fusion training")
        self.rows = frame.set_index("review_id", drop=False)
        self.samples = samples
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        sample = self.samples[index]
        row = self.rows.loc[sample.review_id]
        encoded = self.tokenizer(
            str(row["text"]),
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        item: dict[str, Any] = {key: value.squeeze(0) for key, value in encoded.items()}
        item.update(
            {
                "sequence": sample.sequence,
                "length": sample.length,
                "behavior_available": sample.behavior_available,
                "authenticity_labels": int(row["authenticity_target"]),
                "semantic_labels": SEMANTIC_LABELS.get(str(row.get("semantic_type", "real")), 0),
                "behavior_binary_labels": sample.binary_label,
                "behavior_type_labels": sample.type_label,
            }
        )
        return item


def collate_fusion(items: list[dict[str, Any]]) -> dict[str, Tensor]:
    max_sequence_length = max(int(item["length"]) for item in items)
    feature_size = int(items[0]["sequence"].shape[-1])
    sequences = torch.zeros(
        len(items), max_sequence_length, feature_size, dtype=torch.float32
    )
    for index, item in enumerate(items):
        length = int(item["length"])
        sequences[index, :length] = torch.from_numpy(item["sequence"])

    batch: dict[str, Tensor] = {
        "sequence": sequences,
        "lengths": torch.tensor([item["length"] for item in items], dtype=torch.long),
        "behavior_available": torch.tensor(
            [item["behavior_available"] for item in items], dtype=torch.float32
        ),
        "authenticity_labels": torch.tensor(
            [item["authenticity_labels"] for item in items], dtype=torch.long
        ),
        "semantic_labels": torch.tensor(
            [item["semantic_labels"] for item in items], dtype=torch.long
        ),
        "behavior_binary_labels": torch.tensor(
            [item["behavior_binary_labels"] for item in items], dtype=torch.long
        ),
        "behavior_type_labels": torch.tensor(
            [item["behavior_type_labels"] for item in items], dtype=torch.long
        ),
    }
    token_keys = [key for key in ("input_ids", "attention_mask", "token_type_ids") if key in items[0]]
    for key in token_keys:
        batch[key] = torch.stack([item[key] for item in items])
    return batch
