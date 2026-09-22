from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parent / "tessera_indicators"
sys.path.insert(0, str(MODULE_ROOT / "src"))

from tessera_indicators.contracts import validate_samples
from tessera_indicators.metrics import regression_metrics
from tessera_indicators.spatial import add_spatial_split


class TesseraIndicatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame({"sample_id": ["a", "b", "c"], "longitude": [10.0, -4.0, 20.0], "latitude": [44.0, 41.0, 63.0], "target_value": [0.2, 0.5, 0.8], "coverage_fraction": [1.0, 0.9, 0.8], "emb_000": [1.0, 2.0, 3.0]})

    def test_sample_contract_and_spatial_split(self) -> None:
        self.assertEqual(validate_samples(self.frame), ["emb_000"])
        split = add_spatial_split(self.frame)
        self.assertTrue(set(split.split).issubset({"train", "validation", "test"}))
        self.assertEqual(split.loc[0, "macro_region"], "mediterranean_italy")

    def test_metrics_are_zero_for_exact_predictions(self) -> None:
        metrics = regression_metrics(np.array([0.2, 0.5]), np.array([0.2, 0.5]))
        self.assertEqual(metrics["mae"], 0.0)
        self.assertEqual(metrics["rmse"], 0.0)

    def test_duplicate_target_support_is_rejected(self) -> None:
        duplicate = pd.concat([self.frame, self.frame.iloc[[0]]], ignore_index=True)
        with self.assertRaises(ValueError):
            validate_samples(duplicate)


if __name__ == "__main__":
    unittest.main()
