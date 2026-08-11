import unittest

import numpy as np
import pandas as pd

from spam_cascade.data import BehaviorFeatureBuilder


class BehaviorFeatureBuilderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            [
                {
                    "review_id": 1,
                    "user_id": "u1",
                    "prod_id": "p1",
                    "rating": 1,
                    "date": pd.Timestamp("2025-01-01"),
                    "text": "first",
                    "label": 1,
                    "behavior_type": "normal",
                },
                {
                    "review_id": 2,
                    "user_id": "u1",
                    "prod_id": "p2",
                    "rating": 5,
                    "date": pd.Timestamp("2025-01-02"),
                    "text": "second",
                    "label": -1,
                    "behavior_type": "review_manipulation",
                },
                {
                    "review_id": 3,
                    "user_id": "u1",
                    "prod_id": "p3",
                    "rating": 3,
                    "date": pd.Timestamp("2025-01-03"),
                    "text": "third",
                    "label": -1,
                    "behavior_type": None,
                },
            ]
        )

    def test_binary_training_uses_label_and_masks_missing_type(self) -> None:
        samples = BehaviorFeatureBuilder(1, 30).build(self.frame)
        self.assertEqual(len(samples), 2)
        self.assertEqual(samples[0].binary_label, 1)
        self.assertEqual(samples[0].type_label, 0)
        self.assertEqual(samples[0].length, 2)
        self.assertAlmostEqual(float(samples[0].sequence[-1, 1]), 1.0)
        self.assertEqual(samples[1].binary_label, 1)
        self.assertEqual(samples[1].type_label, -100)

    def test_fusion_samples_use_explicit_availability_mask(self) -> None:
        samples = BehaviorFeatureBuilder(1, 30).build(
            self.frame, include_insufficient=True, include_unavailable=True
        )
        self.assertEqual(len(samples), 3)
        self.assertEqual(samples[0].behavior_available, 0.0)
        self.assertEqual(samples[0].binary_label, -100)
        self.assertEqual(samples[1].behavior_available, 1.0)
        self.assertEqual(samples[2].behavior_available, 1.0)
        self.assertEqual(samples[2].binary_label, 1)

    def test_label_only_data_trains_binary_head_without_type_labels(self) -> None:
        frame = self.frame.drop(columns=["behavior_type"])
        samples = BehaviorFeatureBuilder(1, 30).build(frame)
        self.assertEqual([sample.binary_label for sample in samples], [1, 1])
        self.assertEqual([sample.type_label for sample in samples], [-100, -100])

    def test_online_and_training_builders_produce_identical_target_sequence(self) -> None:
        builder = BehaviorFeatureBuilder(1, 30)
        training_sample = builder.build(self.frame)[-1]
        history = self.frame.iloc[:2].to_dict("records")
        target = self.frame.iloc[2].to_dict()
        online_sequence, history_length, available = builder.build_inference_sequence(
            history, target
        )
        np.testing.assert_allclose(online_sequence, training_sample.sequence)
        self.assertEqual(history_length, 2)
        self.assertEqual(available, 1.0)

    def test_online_builder_rejects_future_history(self) -> None:
        builder = BehaviorFeatureBuilder(1, 30)
        target = self.frame.iloc[1].to_dict()
        with self.assertRaisesRegex(ValueError, "past events"):
            builder.build_inference_sequence([self.frame.iloc[2].to_dict()], target)


if __name__ == "__main__":
    unittest.main()
