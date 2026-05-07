from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from biomap_metric_utils import cell_metric_columns, continuous_metric_summary  # noqa: E402


class BiomapMetricUtilsTest(unittest.TestCase):
    def test_ndvi_observed_zero_is_excluded_from_all_metrics(self) -> None:
        predicted = np.array([2.0, 4.0, 0.0, 8.0])
        observed = np.array([1.0, 2.0, 0.0, 4.0])

        metrics = continuous_metric_summary(predicted, observed, group="vegetation", variable="NDVI")
        columns = cell_metric_columns(predicted, observed, group="vegetation", variable="NDVI")

        self.assertEqual(metrics["valid_cell_count"], 3)
        self.assertEqual(columns["valid_observation"].tolist(), [True, True, False, True])
        self.assertAlmostEqual(metrics["mae"], 7.0 / 3.0)
        self.assertAlmostEqual(metrics["wape_pct"], 100.0)
        self.assertAlmostEqual(metrics["smape_pct"], 200.0 / 3.0)
        self.assertAlmostEqual(metrics["smaape_pct"], metrics["smape_pct"])

    def test_non_ndvi_keeps_zero_observations(self) -> None:
        predicted = np.array([2.0, 4.0, 0.0, 8.0])
        observed = np.array([1.0, 2.0, 0.0, 4.0])

        metrics = continuous_metric_summary(predicted, observed, group="climate", variable="tp")

        self.assertEqual(metrics["valid_cell_count"], 4)
        self.assertAlmostEqual(metrics["wape_pct"], 100.0)
        self.assertAlmostEqual(metrics["smape_pct"], 50.0)

    def test_wape_and_smape_match_reference_script(self) -> None:
        observed = np.array([0.2, 0.4, 0.6])
        predicted = np.array([0.1, 0.5, 0.9])
        abs_error = np.abs(observed - predicted)
        expected_wape = abs_error.sum() / np.abs(observed).sum() * 100.0
        expected_smape = np.mean(abs_error / ((np.abs(observed) + np.abs(predicted)) / 2.0) * 100.0)

        metrics = continuous_metric_summary(predicted, observed, group="vegetation", variable="NDVI")

        self.assertFalse(math.isnan(metrics["wape_pct"]))
        self.assertAlmostEqual(metrics["wape_pct"], expected_wape)
        self.assertAlmostEqual(metrics["smape_pct"], expected_smape)
        self.assertAlmostEqual(metrics["smaape_pct"], expected_smape)


if __name__ == "__main__":
    unittest.main()
