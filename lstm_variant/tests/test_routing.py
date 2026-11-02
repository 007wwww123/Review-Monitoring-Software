import unittest

from spam_cascade.config import CascadeConfig
from spam_cascade.routing import DecisionRouter


class DecisionRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.router = DecisionRouter(CascadeConfig())

    def test_real_prediction_still_runs_fusion(self) -> None:
        decision = self.router.route([0.99, 0.01], [0.99, 0.003, 0.003, 0.004], 0, 0.0)
        self.assertEqual(decision.route, "run_fusion")
        self.assertFalse(decision.behavior_available)

    def test_fake_prediction_still_runs_fusion(self) -> None:
        decision = self.router.route([0.02, 0.98], [0.01, 0.02, 0.02, 0.95], 0, 0.0)
        self.assertEqual(decision.route, "run_fusion")
        self.assertEqual(decision.semantic_label, "advertising")

    def test_behavior_trigger_overrides_real_exit(self) -> None:
        decision = self.router.route([0.99, 0.01], [0.99, 0.003, 0.003, 0.004], 5, 0.9)
        self.assertEqual(decision.route, "run_fusion")

    def test_short_history_uses_masked_fusion(self) -> None:
        decision = self.router.route([0.55, 0.45], [0.55, 0.2, 0.15, 0.1], 0, 0.0)
        self.assertEqual(decision.route, "run_fusion")
        self.assertFalse(decision.behavior_available)

    def test_fusion_output_controls_final_decision(self) -> None:
        route = self.router.route([0.55, 0.45], [0.55, 0.2, 0.15, 0.1], 5, 0.0)
        decision = self.router.finalize(
            route,
            behavior_label="bot_like",
            behavior_confidence=0.9,
            fusion_authenticity_probabilities=[0.1, 0.9],
            fusion_semantic_probabilities=[0.05, 0.1, 0.15, 0.7],
        )
        self.assertEqual(decision.authenticity, "fake")
        self.assertEqual(decision.semantic_type, "advertising")
        self.assertEqual(decision.behavior_type, "bot_like")

    def test_missing_history_uses_insufficient_behavior_axis(self) -> None:
        route = self.router.route([0.55, 0.45], [0.55, 0.2, 0.15, 0.1], 0, 0.0)
        decision = self.router.finalize(
            route,
            fusion_authenticity_probabilities=[0.8, 0.2],
            fusion_semantic_probabilities=[0.8, 0.1, 0.05, 0.05],
        )
        self.assertEqual(decision.authenticity, "real")
        self.assertEqual(decision.behavior_type, "insufficient_evidence")


if __name__ == "__main__":
    unittest.main()
