import type { FeatureMetricRow, IndicatorResponse, IndicatorRow, SelectionBounds } from "./types";

function monthRange(start: string, end: string): string[] {
  const months: string[] = [];
  const cursor = new Date(`${start}-01T00:00:00Z`);
  const endDate = new Date(`${end}-01T00:00:00Z`);

  while (cursor <= endDate) {
    months.push(cursor.toISOString().slice(0, 10));
    cursor.setUTCMonth(cursor.getUTCMonth() + 1);
  }

  return months;
}

export function createDemoResponse(input: {
  label: string;
  selectionMode: "city" | "bbox";
  bounds: SelectionBounds;
  startMonth: string;
  endMonth: string;
}): IndicatorResponse {
  const months = monthRange(input.startMonth, input.endMonth);
  const latCenter = (input.bounds.minLat + input.bounds.maxLat) / 2;
  const lonCenter = (input.bounds.minLon + input.bounds.maxLon) / 2;
  const areaFactor =
    Math.max(1, (input.bounds.maxLat - input.bounds.minLat) * (input.bounds.maxLon - input.bounds.minLon)) * 12;

  const monthly: IndicatorRow[] = months.map((month, index) => {
    const seasonal = Math.sin((index / 12) * Math.PI * 2 - Math.PI / 3);
    const rainSeasonal = Math.cos((index / 12) * Math.PI * 2);

    return {
      month,
      temperature_mean_area_c: Number((12 + seasonal * 11 + (50 - latCenter) * 0.18).toFixed(2)),
      precipitation_mean_area_mm: Number((48 + rainSeasonal * 22 + Math.abs(lonCenter) * 0.3).toFixed(2)),
      precipitation_unit: "mm/mese",
      cell_count_land: Math.round(areaFactor),
      cells_with_species_records: Math.max(0, Math.round(areaFactor * 0.2 + seasonal * 3)),
      species_count_observed_area: Math.max(0, Math.round(areaFactor * 0.4 + seasonal * 4 + 3))
    };
  });

  const features: FeatureMetricRow[] = months.flatMap((month, index) => {
    const seasonal = Math.sin((index / 12) * Math.PI * 2 - Math.PI / 3);
    const rainSeasonal = Math.cos((index / 12) * Math.PI * 2);
    const validCellCount = Math.max(1, Math.round(areaFactor));
    const rows = [
      {
        feature_key: "t2m",
        label: "Temperatura 2m",
        unit: "°C",
        observed_mean: 12 + seasonal * 11 + (50 - latCenter) * 0.18,
        predicted_mean: 12.4 + seasonal * 10.7 + (50 - latCenter) * 0.16,
        noise: 1.1
      },
      {
        feature_key: "tp",
        label: "Precipitazione totale",
        unit: "mm/mese",
        observed_mean: 48 + rainSeasonal * 22 + Math.abs(lonCenter) * 0.3,
        predicted_mean: 45 + rainSeasonal * 18 + Math.abs(lonCenter) * 0.25,
        noise: 8.5
      },
      {
        feature_key: "NDVI",
        label: "NDVI",
        unit: "native",
        observed_mean: 0.46 + seasonal * 0.12,
        predicted_mean: 0.45 + seasonal * 0.1,
        noise: 0.05
      },
      {
        feature_key: "swvl1",
        label: "SWVL1",
        unit: "native",
        observed_mean: 0.24 + rainSeasonal * 0.04,
        predicted_mean: 0.23 + rainSeasonal * 0.035,
        noise: 0.03
      },
      {
        feature_key: "swvl2",
        label: "SWVL2",
        unit: "native",
        observed_mean: 0.28 + rainSeasonal * 0.035,
        predicted_mean: 0.27 + rainSeasonal * 0.03,
        noise: 0.025
      },
      {
        feature_key: "Cropland",
        label: "Cropland",
        unit: "native",
        observed_mean: 0.34 + Math.abs(lonCenter) * 0.002,
        predicted_mean: 0.33 + Math.abs(lonCenter) * 0.0018,
        noise: 0.04
      }
    ];

    return rows.map((row) => {
      const diff = row.predicted_mean - row.observed_mean;
      const mae = Math.abs(diff) + row.noise;
      const rmse = Math.sqrt(mae * mae + row.noise * row.noise * 0.35);
      const obsAbs = Math.abs(row.observed_mean);
      const denom = (Math.abs(row.observed_mean) + Math.abs(row.predicted_mean)) / 2;
      const wape = obsAbs === 0 ? null : (mae / obsAbs) * 100;
      const smape = denom === 0 ? 0 : (mae / denom) * 100;

      return {
        month,
        feature_key: row.feature_key,
        label: row.label,
        unit: row.unit,
        predicted_mean: Number(row.predicted_mean.toFixed(4)),
        observed_mean: Number(row.observed_mean.toFixed(4)),
        mae: Number(mae.toFixed(4)),
        rmse: Number(rmse.toFixed(4)),
        bias: Number(diff.toFixed(4)),
        wape_pct: wape === null ? null : Number(wape.toFixed(2)),
        smape_pct: Number(smape.toFixed(2)),
        smaape_pct: Number(smape.toFixed(2)),
        valid_cell_count: row.feature_key === "NDVI" ? Math.round(validCellCount * 0.92) : validCellCount
      };
    });
  });

  return {
    status: "ok",
    sourceMode: "demo",
    label: input.label,
    selectionMode: input.selectionMode,
    bounds: input.bounds,
    start: `${input.startMonth}-01`,
    end: `${input.endMonth}-01`,
    monthly,
    features,
    notes: [
      "Modalita demo attiva: questa anteprima mostra l'interfaccia ma non usa ancora il dataset reale.",
      "Per dati reali in locale puoi attivare il bridge verso lo script Python; per Vercel serve un backend dati dedicato."
    ]
  };
}
