import type { CellRow, IndicatorRow } from "./types";

export type ObservedVariableKey =
  | "temperature"
  | "precipitation"
  | "ndvi"
  | "swvl1"
  | "swvl2"
  | "cropland";

export type ObservedVariable = {
  key: ObservedVariableKey;
  label: string;
  unit: string;
  decimals: number;
  palette: [string, string, string];
  monthlyValue: (row: IndicatorRow) => number | null;
  cellValue: (row: CellRow) => number | null;
};

export const OBSERVED_VARIABLES: ObservedVariable[] = [
  {
    key: "temperature",
    label: "Temperatura media",
    unit: "°C",
    decimals: 2,
    palette: ["#2f5f9f", "#f2cc59", "#b54835"],
    monthlyValue: (row) => row.temperature_mean_area_c,
    cellValue: (row) => row.temperature_mean_c
  },
  {
    key: "precipitation",
    label: "Precipitazione mensile",
    unit: "mm/mese",
    decimals: 2,
    palette: ["#d8f0f5", "#56a6c8", "#145a8d"],
    monthlyValue: (row) => row.precipitation_mean_area_mm,
    cellValue: (row) => row.precipitation_mean_mm
  },
  {
    key: "ndvi",
    label: "NDVI",
    unit: "",
    decimals: 3,
    palette: ["#d9c5a1", "#8fbf6a", "#1f6b3a"],
    monthlyValue: (row) => row.ndvi_mean_area,
    cellValue: (row) => row.ndvi_mean
  },
  {
    key: "swvl1",
    label: "SWVL1",
    unit: "",
    decimals: 3,
    palette: ["#e5e7e0", "#7fc4b8", "#176b73"],
    monthlyValue: (row) => row.swvl1_mean_area,
    cellValue: (row) => row.swvl1_mean
  },
  {
    key: "swvl2",
    label: "SWVL2",
    unit: "",
    decimals: 3,
    palette: ["#e5e7e0", "#78b8c8", "#245b86"],
    monthlyValue: (row) => row.swvl2_mean_area,
    cellValue: (row) => row.swvl2_mean
  },
  {
    key: "cropland",
    label: "Cropland",
    unit: "",
    decimals: 3,
    palette: ["#f2e7a8", "#b7b95a", "#66772f"],
    monthlyValue: (row) => row.cropland_mean_area,
    cellValue: (row) => row.cropland_mean
  }
];

export function getObservedVariable(key: ObservedVariableKey) {
  return OBSERVED_VARIABLES.find((variable) => variable.key === key) ?? OBSERVED_VARIABLES[0];
}

export function formatObservedValue(variable: ObservedVariable, value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "n.d.";
  }

  const formatted = value.toFixed(variable.decimals);
  return variable.unit ? `${formatted} ${variable.unit}` : formatted;
}
