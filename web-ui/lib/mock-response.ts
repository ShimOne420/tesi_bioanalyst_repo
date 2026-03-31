import type { IndicatorResponse, IndicatorRow, SelectionBounds } from "./types";

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
      cell_count_land: Math.round(areaFactor),
      cells_with_species_records: Math.max(0, Math.round(areaFactor * 0.2 + seasonal * 3)),
      species_count_observed_area: Math.max(0, Math.round(areaFactor * 0.4 + seasonal * 4 + 3))
    };
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
    notes: [
      "Modalita demo attiva: questa anteprima mostra l'interfaccia ma non usa ancora il dataset reale.",
      "Per dati reali in locale puoi attivare il bridge verso lo script Python; per Vercel serve un backend dati dedicato."
    ]
  };
}
