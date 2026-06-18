import type { CellRow, IndicatorRow } from "./types";

export type ObservedVariableKey =
  | "temperature"
  | "ndvi"
  | "swvl1"
  | "swvl2"
  | "stl1"
  | "stl2"
  | "cropland"
  | "arable"
  | "forest";

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
    key: "stl1",
    label: "STL1",
    unit: "°C",
    decimals: 2,
    palette: ["#dbe5f6", "#f3c45f", "#b04a3c"],
    monthlyValue: (row) => row.stl1_mean_area,
    cellValue: (row) => row.stl1_mean
  },
  {
    key: "stl2",
    label: "STL2",
    unit: "°C",
    decimals: 2,
    palette: ["#e9edf8", "#f0b05d", "#8f3d35"],
    monthlyValue: (row) => row.stl2_mean_area,
    cellValue: (row) => row.stl2_mean
  },
  {
    key: "cropland",
    label: "Cropland",
    unit: "",
    decimals: 3,
    palette: ["#f2e7a8", "#b7b95a", "#66772f"],
    monthlyValue: (row) => row.cropland_mean_area,
    cellValue: (row) => row.cropland_mean
  },
  {
    key: "arable",
    label: "Arable",
    unit: "",
    decimals: 3,
    palette: ["#f6e8c7", "#d3a85c", "#8f5f1c"],
    monthlyValue: (row) => row.arable_mean_area,
    cellValue: (row) => row.arable_mean
  },
  {
    key: "forest",
    label: "Forest",
    unit: "",
    decimals: 3,
    palette: ["#d9ecd7", "#66a860", "#1f5b2f"],
    monthlyValue: (row) => row.forest_mean_area,
    cellValue: (row) => row.forest_mean
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
