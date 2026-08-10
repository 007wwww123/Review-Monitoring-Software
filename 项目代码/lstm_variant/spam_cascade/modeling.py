from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import torch
from torch import Tensor, nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from transformers import AlbertModel

from .config import CascadeConfig


@dataclass
class SemanticOutput:
    authenticity_logits: Tensor
    semantic_logits: Tensor
    semantic_relative_probabilities: Tensor
    pooled_output: Tensor

    @property
    def semantic_match_scores(self) -> Tensor:
        """Independent text-side match scores retained for final reporting."""
        return self.semantic_relative_probabilities


@dataclass
class BehaviorOutput:
    normality_logits: Tensor
    type_logits: Tensor
    relative_probabilities: Tensor
    pooled_output: Tensor
    attention_weights: Optional[Tensor]

    @property
    def logits(self) -> Tensor:
        """Backward-compatible alias for the primary normal/abnormal logits."""
        return self.normality_logits


@dataclass
class FusionOutput:
    authenticity_logits: Tensor
    semantic_type_logits: Tensor
    semantic_relative_probabilities: Tensor
    fused_output: Tensor
    gate_weights: Tensor
    text_authenticity_probabilities: Tensor
    semantic_match_scores: Tensor
    behavior_normality_probabilities: Tensor
    behavior_match_scores: Tensor


@dataclass
class CascadeOutput:
    semantic: SemanticOutput
    behavior: BehaviorOutput
    fusion: FusionOutput


def semantic_relative_probabilities(
    authenticity_logits: Tensor,
    semantic_logits: Tensor,
) -> Tensor:
    """Return four independent text-semantic match scores.

    Authenticity remains a separate real/fake task. These scores are not mixed
    with P(real) or P(fake), and may overlap because a review can match several
    language patterns at once. Until fine-grained supervision is available,
    they are evidence-only outputs and do not affect standalone ALBERT training.
    """
    if authenticity_logits.size(-1) != 2 or semantic_logits.size(-1) != 4:
        raise ValueError("semantic matcher expects two authenticity and four match logits")
    return torch.sigmoid(semantic_logits)


def behavior_relative_probabilities(
    normality_logits: Tensor,
    type_logits: Tensor,
    behavior_available: Optional[Tensor] = None,
) -> Tensor:
    """Derive normal, three abnormal types, and insufficient-evidence scores."""
    if normality_logits.size(-1) != 2 or type_logits.size(-1) != 3:
        raise ValueError("behavior hierarchy expects two normality and three type logits")
    normality = torch.softmax(normality_logits, dim=-1)
    abnormal_types = torch.softmax(type_logits, dim=-1)
    if behavior_available is None:
        available = torch.ones_like(normality[..., :1])
    else:
        available = behavior_available.to(normality.dtype).reshape(-1, 1)
    insufficient = 1.0 - available
    return torch.cat(
        [
            available * normality[..., :1],
            available * normality[..., 1:2] * abnormal_types,
            insufficient,
        ],
        dim=-1,
    )


class AlbertSemanticClassifier(nn.Module):
    """First-stage semantic classifier.

    ALBERT is responsible for both authenticity screening and language-oriented
    fine-grained classification. LSTM is deliberately not applied to token
    embeddings; the two stages retain separate responsibilities.
    """

    def __init__(self, config: CascadeConfig) -> None:
        super().__init__()
        self.encoder = AlbertModel.from_pretrained(config.albert_name_or_path)
        hidden_size = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(config.classifier_dropout)
        self.authenticity_head = nn.Linear(hidden_size, 2)
        self.semantic_head = nn.Linear(hidden_size, config.semantic_num_labels)

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor,
        token_type_ids: Optional[Tensor] = None,
    ) -> SemanticOutput:
        output = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
            return_dict=True,
        )
        pooled = self.dropout(output.pooler_output)
        authenticity_logits = self.authenticity_head(pooled)
        semantic_logits = self.semantic_head(pooled)
        return SemanticOutput(
            authenticity_logits=authenticity_logits,
            semantic_logits=semantic_logits,
            semantic_relative_probabilities=semantic_relative_probabilities(
                authenticity_logits, semantic_logits
            ),
            pooled_output=pooled,
        )


class TemporalAttention(nn.Module):
    def __init__(self, hidden_size: int) -> None:
        super().__init__()
        self.score = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.Tanh(),
            nn.Linear(hidden_size, 1, bias=False),
        )

    def forward(self, states: Tensor, mask: Tensor) -> tuple[Tensor, Tensor]:
        scores = self.score(states).squeeze(-1)
        scores = scores.masked_fill(~mask, torch.finfo(scores.dtype).min)
        weights = torch.softmax(scores, dim=-1)
        pooled = torch.bmm(weights.unsqueeze(1), states).squeeze(1)
        return pooled, weights


class BehaviorLSTMClassifier(nn.Module):
    """Hierarchical behavior classifier over chronological user events."""

    def __init__(self, config: CascadeConfig) -> None:
        super().__init__()
        recurrent_dropout = config.behavior_dropout if config.behavior_num_layers > 1 else 0.0
        self.lstm = nn.LSTM(
            input_size=config.behavior_input_size,
            hidden_size=config.behavior_hidden_size,
            num_layers=config.behavior_num_layers,
            batch_first=True,
            dropout=recurrent_dropout,
        )
        self.attention = (
            TemporalAttention(config.behavior_hidden_size)
            if config.use_behavior_attention
            else None
        )
        self.dropout = nn.Dropout(config.behavior_dropout)
        self.normality_head = nn.Linear(config.behavior_hidden_size, 2)
        self.type_head = nn.Linear(
            config.behavior_hidden_size, config.behavior_type_num_labels
        )

    def forward(
        self,
        sequence: Tensor,
        lengths: Tensor,
        behavior_available: Optional[Tensor] = None,
    ) -> BehaviorOutput:
        if torch.any(lengths < 1):
            raise ValueError("all behavior sequences must contain at least one time step")
        packed = pack_padded_sequence(
            sequence,
            lengths.detach().cpu(),
            batch_first=True,
            enforce_sorted=False,
        )
        packed_states, (hidden, _) = self.lstm(packed)
        states, _ = pad_packed_sequence(
            packed_states,
            batch_first=True,
            total_length=sequence.size(1),
        )
        mask = torch.arange(sequence.size(1), device=lengths.device)[None, :] < lengths[:, None]
        if self.attention is not None:
            pooled, weights = self.attention(states, mask)
        else:
            pooled = hidden[-1]
            weights = None
        pooled = self.dropout(pooled)
        normality_logits = self.normality_head(pooled)
        type_logits = self.type_head(pooled)
        return BehaviorOutput(
            normality_logits=normality_logits,
            type_logits=type_logits,
            relative_probabilities=behavior_relative_probabilities(
                normality_logits, type_logits, behavior_available
            ),
            pooled_output=pooled,
            attention_weights=weights,
        )


class GatedFusionClassifier(nn.Module):
    """Missing-aware vector gate over aligned semantic and behavior evidence."""

    def __init__(self, config: CascadeConfig, semantic_hidden_size: int) -> None:
        super().__init__()
        fusion_size = config.fusion_hidden_size
        self.semantic_projection = nn.Sequential(
            nn.Linear(semantic_hidden_size + 2 + config.semantic_num_labels, fusion_size),
            nn.GELU(),
            nn.LayerNorm(fusion_size),
            nn.Dropout(config.fusion_dropout),
        )
        self.behavior_projection = nn.Sequential(
            nn.Linear(
                config.behavior_hidden_size + 2 + config.behavior_num_labels,
                fusion_size,
            ),
            nn.GELU(),
            nn.LayerNorm(fusion_size),
            nn.Dropout(config.fusion_dropout),
        )
        self.gate = nn.Sequential(
            nn.Linear(fusion_size * 2 + 1, fusion_size),
            nn.GELU(),
            nn.Linear(fusion_size, fusion_size),
            nn.Sigmoid(),
        )
        self.dropout = nn.Dropout(config.fusion_dropout)
        self.authenticity_head = nn.Linear(fusion_size, 2)
        self.semantic_type_head = nn.Linear(fusion_size, 3)

    def forward(
        self,
        semantic: SemanticOutput,
        behavior: BehaviorOutput,
        behavior_available: Tensor,
    ) -> FusionOutput:
        availability = behavior_available.to(semantic.pooled_output.dtype).reshape(-1, 1)
        semantic_probabilities = torch.softmax(semantic.authenticity_logits, dim=-1)
        behavior_probabilities = torch.softmax(behavior.normality_logits, dim=-1)
        semantic_input = torch.cat(
            [
                semantic.pooled_output,
                semantic_probabilities,
                semantic.semantic_relative_probabilities,
            ],
            dim=-1,
        )
        behavior_input = torch.cat(
            [
                behavior.pooled_output,
                behavior_probabilities,
                behavior.relative_probabilities,
            ],
            dim=-1,
        )
        semantic_aligned = self.semantic_projection(semantic_input)
        behavior_aligned = self.behavior_projection(behavior_input)
        learned_gate = self.gate(
            torch.cat([semantic_aligned, behavior_aligned, availability], dim=-1)
        )
        effective_gate = availability * learned_gate + (1.0 - availability)
        fused = effective_gate * semantic_aligned + (1.0 - effective_gate) * behavior_aligned
        fused = self.dropout(fused)
        authenticity_logits = self.authenticity_head(fused)
        semantic_type_logits = self.semantic_type_head(fused)
        return FusionOutput(
            authenticity_logits=authenticity_logits,
            semantic_type_logits=semantic_type_logits,
            # Text matching is computed before LSTM and carried through fusion
            # unchanged as auxiliary evidence, not as the final authenticity.
            semantic_relative_probabilities=semantic.semantic_match_scores,
            fused_output=fused,
            gate_weights=effective_gate,
            text_authenticity_probabilities=semantic_probabilities,
            semantic_match_scores=semantic.semantic_match_scores,
            behavior_normality_probabilities=behavior_probabilities,
            behavior_match_scores=behavior.relative_probabilities,
        )


class CascadeDetector(nn.Module):
    """Semantic-first cascade with hierarchical behavior and gated fusion."""

    def __init__(self, config: CascadeConfig) -> None:
        super().__init__()
        config.validate()
        self.config = config
        self.semantic = AlbertSemanticClassifier(config)
        self.behavior = BehaviorLSTMClassifier(config)
        self.fusion = GatedFusionClassifier(config, self.semantic.encoder.config.hidden_size)

    def semantic_forward(self, **batch: Tensor) -> SemanticOutput:
        return self.semantic(**batch)

    def behavior_forward(
        self,
        sequence: Tensor,
        lengths: Tensor,
        behavior_available: Optional[Tensor] = None,
    ) -> BehaviorOutput:
        return self.behavior(sequence, lengths, behavior_available)

    def fusion_forward(
        self,
        semantic: SemanticOutput,
        behavior: BehaviorOutput,
        behavior_available: Tensor,
    ) -> FusionOutput:
        return self.fusion(semantic, behavior, behavior_available)

    def forward(
        self,
        input_ids: Tensor,
        attention_mask: Tensor,
        sequence: Tensor,
        lengths: Tensor,
        behavior_available: Tensor,
        token_type_ids: Optional[Tensor] = None,
    ) -> CascadeOutput:
        semantic = self.semantic(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        behavior = self.behavior(sequence, lengths, behavior_available)
        fusion = self.fusion(semantic, behavior, behavior_available)
        return CascadeOutput(semantic=semantic, behavior=behavior, fusion=fusion)
