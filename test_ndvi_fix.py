from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

from bioanalyst_model_utils import find_monthly_column  # noqa: E402


class NdviColumnMatchingTest(unittest.TestCase):
    def test_matches_biocube_month_year_format(self) -> None:
        columns = ["Country", "Latitude", "Longitude", "NDVI_06/2019"]

        result = find_monthly_column(columns, "NDVI", pd.Timestamp("2019-06-01"))

        self.assertEqual(result, "NDVI_06/2019")

    def test_matching_is_case_insensitive(self) -> None:
        columns = ["ndvi_2019-06"]

        result = find_monthly_column(columns, "NDVI", pd.Timestamp("2019-06-01"))

        self.assertEqual(result, "ndvi_2019-06")

    def test_missing_month_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(KeyError, "2019-06"):
            find_monthly_column(["NDVI_05/2019"], "NDVI", pd.Timestamp("2019-06-01"))


if __name__ == "__main__":
    unittest.main()
