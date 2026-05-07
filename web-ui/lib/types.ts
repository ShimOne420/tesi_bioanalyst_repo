export type SelectionBounds = {
  minLat: number;
  maxLat: number;
  minLon: number;
  maxLon: number;
};

export type CityOption = {
  value: string;
  label: string;
  country: string;
  countryCode?: string;
  lat: number;
  lon: number;
  population?: number;
};

export type IndicatorRow = {
  month: string;
  temperature_mean_area_c: number | null;
  precipitation_mean_area_mm: number | null;
  precipitation_mean_daily_area_mm?: number | null;
  precipitation_unit?: string | null;
  ndvi_mean_area: number | null;
  swvl1_mean_area: number | null;
  swvl2_mean_area: number | null;
  cropland_mean_area: number | null;
  valid_cell_count: number | null;
  cell_count_land: number | null;
  cells_with_species_records: number | null;
  species_count_observed_area: number | null;
};

export type FeatureMetricRow = {
  month: string;
  feature_key: string;
  label: string;
  unit: string;
  predicted_mean: number | null;
  observed_mean: number | null;
  mae: number | null;
  rmse: number | null;
  bias: number | null;
  wape_pct: number | null;
  smape_pct: number | null;
  smaape_pct: number | null;
  valid_cell_count: number | null;
};

export type DownloadLinks = {
  csvUrl: string;
  excelCsvUrl: string;
  xlsxUrl: string;
};

export type IndicatorResponse = {
  status: "ok";
  sourceMode: "local" | "proxy" | "demo";
  label: string;
  selectionMode: "city" | "bbox";
  bounds: SelectionBounds;
  start: string;
  end: string;
  monthly: IndicatorRow[];
  // Reserved for a future forecast/backtest view; the main dashboard ignores it.
  features?: FeatureMetricRow[];
  notes: string[];
  downloads?: DownloadLinks;
};

export type DatasetMetadata = {
  period: {
    minMonth: string;
    maxMonth: string;
  };
  cities: CityOption[];
  note?: string;
};
