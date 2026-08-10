import unittest

import torch

from spam_cascade.modeling import (
    BehaviorLSTMClassifier,
    behavior_relative_probabilities,
    semantic_relative_probabilities,
)
from spam_cascade.config import CascadeConfig


class HierarchicalProbabilityTest(unittest.TestCase):
    def test_lstm_behavior_output_contract(self) -> None:
        config = CascadeConfig()
        model = BehaviorLSTMClassifier(config).eval()
        sequence = torch.randn(2, 4, config.behavior_input_size)
        lengths = torch.tensor([4, 2])
        available = torch.tensor([1.0, 1.0])
        with torch.no_grad():
            output = model(sequence, lengths, available)
        self.assertEqual(tuple(output.normality_logits.shape), (2, 2))
        self.assertEqual(tuple(output.type_logits.shape), (2, 3))
        self.assertEqual(tuple(output.relative_probabilities.shape), (2, 5))
        self.assertEqual(tuple(output.pooled_output.shape), (2, config.behavior_hidden_size))

    def test_semantic_match_scores_are_independent(self) -> None:
        authenticity = torch.tensor([[0.0, 2.0]])
        semantic = torch.tensor([[5.0, 1.0, 2.0, 3.0]])
        relative = semantic_relative_probabilities(authenticity, semantic)
        self.assertEqual(tuple(relative.shape), (1, 4))
        self.assertTrue(torch.all(relative >= 0.0))
        self.assertTrue(torch.all(relative <= 1.0))
        self.assertFalse(torch.allclose(relative.sum(-1), torch.ones(1)))

    def test_behavior_relative_probabilities_sum_to_one(self) -> None:
        normality = torch.tensor([[0.0, 2.0]])
        behavior_types = torch.tensor([[1.0, 2.0, 3.0]])
        relative = behavior_relative_probabilities(
            normality, behavior_types, torch.tensor([1.0])
        )
        self.assertEqual(tuple(relative.shape), (1, 5))
        self.assertTrue(torch.allclose(relative.sum(-1), torch.ones(1)))

    def test_missing_behavior_becomes_insufficient_evidence(self) -> None:
        relative = behavior_relative_probabilities(
            torch.tensor([[0.0, 2.0]]),
            torch.tensor([[1.0, 2.0, 3.0]]),
            torch.tensor([0.0]),
        )
        expected = torch.tensor([[0.0, 0.0, 0.0, 0.0, 1.0]])
        self.assertTrue(torch.allclose(relative, expected))


if __name__ == "__main__":
    unittest.main()
