from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from bioanalyst_model_utils import (  # noqa: E402
    latest_monthly_column,
    months_after_table_coverage,
    ndvi_table_covers_months,
    resolve_forecast_months,
)


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

    def test_ndvi_wide_columns_detect_future_gap(self) -> None:
        columns = ["Country", "Latitude", "Longitude", "NDVI_11/2020", "NDVI_12/2020"]

        self.assertEqual(str(latest_monthly_column(columns, "NDVI").date()), "2020-12-01")
        self.assertTrue(
            months_after_table_coverage(
                [pd.Timestamp("2020-12-01"), pd.Timestamp("2021-01-01")],
                columns,
                "NDVI",
            )
        )
        self.assertFalse(
            months_after_table_coverage(
                [pd.Timestamp("2020-11-01"), pd.Timestamp("2020-12-01")],
                columns,
                "NDVI",
            )
        )

    def test_missing_ndvi_source_does_not_claim_coverage(self) -> None:
        self.assertFalse(ndvi_table_covers_months({}, [pd.Timestamp("2022-06-01")]))


if __name__ == "__main__":
    unittest.main()
