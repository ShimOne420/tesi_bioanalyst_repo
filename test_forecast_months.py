from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from bioanalyst_model_utils import resolve_forecast_months  # noqa: E402


class ForecastMonthsTest(unittest.TestCase):
    def test_2021_inference_uses_dynamic_climate_limit(self) -> None:
        info = resolve_forecast_months(
            "2021-04-01",
            "2021-05-01",
            climate_last_available=pd.Timestamp("2021-12-01"),
        )

        self.assertEqual(str(info["forecast_month"].date()), "2021-06-01")
        self.assertTrue(info["compare_available"])
        self.assertEqual(str(info["climate_last_available"].date()), "2021-12-01")


if __name__ == "__main__":
    unittest.main()
