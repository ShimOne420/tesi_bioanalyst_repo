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
  lat: number;
  lon: number;
};

export type IndicatorRow = {
  month: string;
  temperature_mean_area_c: number | null;
  precipitation_mean_area_mm: number | null;
  cell_count_land: number | null;
  cells_with_species_records: number | null;
  species_count_observed_area: number | null;
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
