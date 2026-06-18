"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";

import { TrendChart } from "./trend-chart";
import { buildBoundsFromCity, CITY_OPTIONS } from "../lib/cities";
import {
  OBSERVED_VARIABLES,
  getObservedVariable,
  type ObservedVariableKey
} from "../lib/observed-variables";
import type {
  CellRow,
  CellsResponse,
  DashboardMode,
  DatasetMetadata,
  IndicatorResponse,
  IndicatorRow,
  SelectionBounds
} from "../lib/types";

const EuropeSelectionMap = dynamic(
  () => import("./europe-selection-map").then((mod) => mod.EuropeSelectionMap),
  {
    ssr: false,
    loading: () => <div className="panel map-panel panel-inner">Caricamento mappa...</div>
  }
);

const IndicatorMap = dynamic(
  () => import("./indicator-map").then((mod) => mod.IndicatorMap),
  {
    ssr: false,
    loading: () => <div className="status info">Caricamento mappa tematica...</div>
  }
);

type AreaSource = "city" | "map" | "coordinates";

type CoordinateForm = {
  minLat: string;
  maxLat: string;
  minLon: string;
  maxLon: string;
};

const FALLBACK_FORECAST_TARGET_MONTHS = [
  "2026-04",
  "2026-05",
  "2026-06",
  "2026-07",
  "2026-08",
  "2026-09"
];

function toMonthStart(value: string) {
  return `${value}-01`;
}

function enumerateMonths(minMonth: string, maxMonth: string) {
  const values: string[] = [];
  const cursor = new Date(`${minMonth}-01T00:00:00`);
  const end = new Date(`${maxMonth}-01T00:00:00`);

  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = String(cursor.getMonth() + 1).padStart(2, "0");
    values.push(`${year}-${month}`);
    cursor.setMonth(cursor.getMonth() + 1);
  }

  return values;
}

function formatMonthLabel(value: string) {
  const date = new Date(`${value}-01T00:00:00`);
  return new Intl.DateTimeFormat("it-IT", {
    month: "long",
    year: "numeric"
  }).format(date);
}

function formatNumber(value: number | null, unit: string, decimals = 2) {
  if (value === null || Number.isNaN(value)) {
    return "n.d.";
  }

  const formatted = value.toFixed(decimals);
  return unit ? `${formatted} ${unit}` : formatted;
}

function isFiniteNumber(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function mean(values: Array<number | null | undefined>) {
  const validValues = values.filter(isFiniteNumber);
  if (!validValues.length) {
    return null;
  }

  return validValues.reduce((total, value) => total + value, 0) / validValues.length;
}

function landCoverComposite(row: IndicatorRow) {
  if (
    !isFiniteNumber(row.forest_mean_area) ||
    !isFiniteNumber(row.arable_mean_area) ||
    !isFiniteNumber(row.cropland_mean_area)
  ) {
    return null;
  }

  return row.forest_mean_area - (row.arable_mean_area + row.cropland_mean_area);
}

function computeLandCoverChange(rows: IndicatorRow[]) {
  if (rows.length < 2) {
    return null;
  }

  const first = landCoverComposite(rows[0]);
  const last = landCoverComposite(rows.at(-1) ?? rows[rows.length - 1]);
  if (!isFiniteNumber(first) || !isFiniteNumber(last)) {
    return null;
  }

  return last - first;
}

function computeLinearSlope(values: Array<number | null | undefined>) {
  const points = values
    .map((value, index) => ({ x: index, y: value }))
    .filter((point): point is { x: number; y: number } => isFiniteNumber(point.y));

  if (points.length < 2) {
    return null;
  }

  const xMean = points.reduce((total, point) => total + point.x, 0) / points.length;
  const yMean = points.reduce((total, point) => total + point.y, 0) / points.length;
  const denominator = points.reduce((total, point) => total + (point.x - xMean) ** 2, 0);
  if (denominator === 0) {
    return null;
  }

  const numerator = points.reduce((total, point) => total + (point.x - xMean) * (point.y - yMean), 0);
  return numerator / denominator;
}

function computeAverageSlope(
  rows: IndicatorRow[],
  selectors: Array<(row: IndicatorRow) => number | null | undefined>
) {
  const slopes = selectors
    .map((selector) => computeLinearSlope(rows.map(selector)))
    .filter(isFiniteNumber);

  if (!slopes.length) {
    return null;
  }

  return slopes.reduce((total, slope) => total + slope, 0) / slopes.length;
}

function computeNdviTrend(rows: IndicatorRow[]) {
  return computeLinearSlope(rows.map((row) => row.ndvi_mean_area));
}

async function readApiError(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: unknown; error?: unknown };
    const message = payload.detail ?? payload.error;
    if (typeof message === "string" && message.trim()) {
      return message;
    }
  } catch {
    // La risposta puo non essere JSON, in quel caso usiamo il fallback leggibile.
  }

  return fallback;
}

function boundsToCoordinateForm(bounds: SelectionBounds): CoordinateForm {
  return {
    minLat: bounds.minLat.toFixed(4),
    maxLat: bounds.maxLat.toFixed(4),
    minLon: bounds.minLon.toFixed(4),
    maxLon: bounds.maxLon.toFixed(4)
  };
}

function parseCoordinateBounds(form: CoordinateForm): { bounds?: SelectionBounds; error?: string } {
  const minLat = Number(form.minLat);
  const maxLat = Number(form.maxLat);
  const minLon = Number(form.minLon);
  const maxLon = Number(form.maxLon);

  if ([minLat, maxLat, minLon, maxLon].some((value) => Number.isNaN(value))) {
    return { error: "Inserisci coordinate numeriche valide." };
  }

  if (minLat < -90 || maxLat > 90 || minLon < -180 || maxLon > 180) {
    return { error: "Le coordinate devono rispettare latitudine [-90, 90] e longitudine [-180, 180]." };
  }

  if (minLat >= maxLat || minLon >= maxLon) {
    return { error: "Il bounding box richiede minLat < maxLat e minLon < maxLon." };
  }

  return { bounds: { minLat, maxLat, minLon, maxLon } };
}

const TABLE_COLUMNS: Array<{
  label: string;
  value: (row: IndicatorRow) => string | number | null;
  display: (row: IndicatorRow) => string | number;
}> = [
  {
    label: "Mese",
    value: (row) => row.month.slice(0, 7),
    display: (row) => row.month.slice(0, 7)
  },
  {
    label: "Temperatura media",
    value: (row) => row.temperature_mean_area_c,
    display: (row) => formatNumber(row.temperature_mean_area_c, "°C")
  },
  {
    label: "NDVI",
    value: (row) => row.ndvi_mean_area,
    display: (row) => formatNumber(row.ndvi_mean_area, "", 3)
  },
  {
    label: "SWVL1",
    value: (row) => row.swvl1_mean_area,
    display: (row) => formatNumber(row.swvl1_mean_area, "", 3)
  },
  {
    label: "SWVL2",
    value: (row) => row.swvl2_mean_area,
    display: (row) => formatNumber(row.swvl2_mean_area, "", 3)
  },
  {
    label: "STL1",
    value: (row) => row.stl1_mean_area,
    display: (row) => formatNumber(row.stl1_mean_area, "°C")
  },
  {
    label: "STL2",
    value: (row) => row.stl2_mean_area,
    display: (row) => formatNumber(row.stl2_mean_area, "°C")
  },
  {
    label: "Cropland",
    value: (row) => row.cropland_mean_area,
    display: (row) => formatNumber(row.cropland_mean_area, "", 3)
  },
  {
    label: "Arable",
    value: (row) => row.arable_mean_area,
    display: (row) => formatNumber(row.arable_mean_area, "", 3)
  },
  {
    label: "Forest",
    value: (row) => row.forest_mean_area,
    display: (row) => formatNumber(row.forest_mean_area, "", 3)
  }
];

function normalizeExportValue(value: string | number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "";
  }

  return String(value);
}

function escapeCsvValue(value: string | number | null | undefined) {
  const normalized = normalizeExportValue(value);
  if (/[",\n\r]/.test(normalized)) {
    return `"${normalized.replace(/"/g, '""')}"`;
  }

  return normalized;
}

function escapeHtmlValue(value: string | number | null | undefined) {
  return normalizeExportValue(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function downloadBlob(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function buildExportFilename(result: IndicatorResponse, extension: "csv" | "xls") {
  const label = result.label.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "") || "selected_area";
  return `biomap_${label}_${result.start.slice(0, 7)}_${result.end.slice(0, 7)}.${extension}`;
}

function exportRowsAsCsv<T>(
  result: IndicatorResponse,
  rows: T[],
  columns: Array<{ label: string; value: (row: T) => string | number | null }>
) {
  const header = columns.map((column) => escapeCsvValue(column.label)).join(",");
  const csvRows = rows.map((row) => columns.map((column) => escapeCsvValue(column.value(row))).join(","));
  const csv = `\uFEFF${[header, ...csvRows].join("\r\n")}`;
  downloadBlob(buildExportFilename(result, "csv"), csv, "text/csv;charset=utf-8");
}

function exportRowsAsExcel<T>(
  result: IndicatorResponse,
  rows: T[],
  columns: Array<{ label: string; value: (row: T) => string | number | null }>
) {
  const header = columns.map((column) => `<th>${escapeHtmlValue(column.label)}</th>`).join("");
  const tableRows = rows
    .map((row) => {
      const cells = columns.map((column) => `<td>${escapeHtmlValue(column.value(row))}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  const html = `<!DOCTYPE html><html><head><meta charset="utf-8" /></head><body><table><thead><tr>${header}</tr></thead><tbody>${tableRows}</tbody></table></body></html>`;
  downloadBlob(buildExportFilename(result, "xls"), html, "application/vnd.ms-excel;charset=utf-8");
}

function exportTableAsCsv(result: IndicatorResponse) {
  exportRowsAsCsv(result, result.monthly, TABLE_COLUMNS);
}

function exportTableAsExcel(result: IndicatorResponse) {
  exportRowsAsExcel(result, result.monthly, TABLE_COLUMNS);
}

export function BiomapDashboard() {
  const [dashboardMode, setDashboardMode] = useState<DashboardMode>("observed");
  const [selectedCity, setSelectedCity] = useState<string>("");
  const [cityQuery, setCityQuery] = useState<string>("");
  const [halfWindowDeg, setHalfWindowDeg] = useState<number>(0.5);
  const [startMonth, setStartMonth] = useState<string>("");
  const [endMonth, setEndMonth] = useState<string>("");
  const [forecastTargetMonth, setForecastTargetMonth] = useState<string>(FALLBACK_FORECAST_TARGET_MONTHS[0]);
  const [manualBounds, setManualBounds] = useState<SelectionBounds | null>(null);
  const [areaSource, setAreaSource] = useState<AreaSource>("city");
  const [coordinateForm, setCoordinateForm] = useState<CoordinateForm>({
    minLat: "",
    maxLat: "",
    minLon: "",
    maxLon: ""
  });
  const [result, setResult] = useState<IndicatorResponse | null>(null);
  const [selectedVariableKey, setSelectedVariableKey] = useState<ObservedVariableKey>("temperature");
  const [selectedOutputMonth, setSelectedOutputMonth] = useState<string>("");
  const [cellRows, setCellRows] = useState<CellRow[]>([]);
  const [cellsLoading, setCellsLoading] = useState<boolean>(false);
  const [cellsError, setCellsError] = useState<string>("");
  const [metadata, setMetadata] = useState<DatasetMetadata | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;

    async function loadMetadata() {
      try {
        const response = await fetch("/api/metadata", { cache: "no-store" });
        if (!response.ok) {
          throw new Error(
            await readApiError(response, "Non sono riuscito a leggere il periodo disponibile del dataset.")
          );
        }

        const payload = (await response.json()) as DatasetMetadata;
        if (cancelled) {
          return;
        }

        setMetadata(payload);
        setStartMonth(payload.period.minMonth);
        setEndMonth(payload.period.maxMonth);
        if (payload.forecast?.targetMonths?.length) {
          setForecastTargetMonth(payload.forecast.targetMonths[0]);
        }

        if (payload.cities.length) {
          const defaultCity =
            payload.cities.find(
              (city) =>
                city.label.toLowerCase() === "milano" || city.label.toLowerCase() === "milan"
            ) ?? payload.cities[0];

          setSelectedCity(defaultCity.value);
        }
      } catch (metadataError) {
        if (cancelled) {
          return;
        }

        setError(
          metadataError instanceof Error
            ? metadataError.message
            : "Errore nel caricamento dei metadati del dataset."
        );
      }
    }

    void loadMetadata();

    return () => {
      cancelled = true;
    };
  }, []);

  const cityOptions = metadata?.cities ?? CITY_OPTIONS;

  useEffect(() => {
    if (!selectedCity && cityOptions.length) {
      setSelectedCity(cityOptions[0].value);
    }
  }, [cityOptions, selectedCity]);

  useEffect(() => {
    setResult(null);
    setCellRows([]);
    setCellsError("");
    setError("");
  }, [dashboardMode]);

  const selectedCityConfig = useMemo(
    () => cityOptions.find((city) => city.value === selectedCity) ?? null,
    [cityOptions, selectedCity]
  );

  const filteredCityOptions = useMemo(() => {
    const query = cityQuery.trim().toLowerCase();
    const base = query
      ? cityOptions.filter((city) =>
          `${city.label} ${city.country}`.toLowerCase().includes(query)
        )
      : cityOptions;

    if (!selectedCityConfig) {
      return base.slice(0, 200);
    }

    const sliced = base.slice(0, 200);
    if (sliced.some((city) => city.value === selectedCityConfig.value)) {
      return sliced;
    }

    return [selectedCityConfig, ...sliced];
  }, [cityOptions, cityQuery, selectedCityConfig]);

  const cityPreviewBounds = useMemo(() => {
    if (!selectedCityConfig) {
      return null;
    }

    return buildBoundsFromCity(selectedCityConfig, halfWindowDeg);
  }, [halfWindowDeg, selectedCityConfig]);

  const availableMonths = useMemo(() => {
    if (!metadata) {
      return [];
    }

    return enumerateMonths(metadata.period.minMonth, metadata.period.maxMonth);
  }, [metadata]);

  const forecastTargetMonths = useMemo(() => {
    return metadata?.forecast?.targetMonths?.length
      ? metadata.forecast.targetMonths
      : FALLBACK_FORECAST_TARGET_MONTHS;
  }, [metadata]);

  useEffect(() => {
    if (!forecastTargetMonths.includes(forecastTargetMonth)) {
      setForecastTargetMonth(forecastTargetMonths[0] ?? FALLBACK_FORECAST_TARGET_MONTHS[0]);
    }
  }, [forecastTargetMonth, forecastTargetMonths]);

  const activeBounds = manualBounds ?? cityPreviewBounds;
  const activeAreaLabel = manualBounds
    ? areaSource === "coordinates"
      ? "Coordinate manuali"
      : "Rettangolo disegnato"
    : "Citta";
  const selectedVariable = getObservedVariable(selectedVariableKey);
  const outputMonths = result?.monthly.map((row) => row.month) ?? [];
  const dashboardModeLabel = dashboardMode === "forecast" ? "previsione" : "osservazione";

  useEffect(() => {
    if (!result?.monthly.length) {
      setSelectedOutputMonth("");
      setCellRows([]);
      return;
    }

    const latestMonth = result.monthly.at(-1)?.month ?? result.monthly[0].month;
    setSelectedOutputMonth(latestMonth);
    setCellRows([]);
    setCellsError("");
  }, [result]);

  useEffect(() => {
    if (!result?.cellsUrl || !selectedOutputMonth) {
      setCellRows([]);
      return;
    }

    const controller = new AbortController();
    const cellsUrl = result.cellsUrl;

    async function loadCells() {
      setCellsLoading(true);
      setCellsError("");

      try {
        const response = await fetch(`${cellsUrl}?month=${encodeURIComponent(selectedOutputMonth.slice(0, 7))}`, {
          cache: "no-store",
          signal: controller.signal
        });

        if (!response.ok) {
          throw new Error(await readApiError(response, "Non sono riuscito a leggere le celle per la mappa."));
        }

        const payload = (await response.json()) as CellsResponse;
        setCellRows(payload.cells);
      } catch (cellsRequestError) {
        if (controller.signal.aborted) {
          return;
        }
        setCellRows([]);
        setCellsError(
          cellsRequestError instanceof Error
            ? cellsRequestError.message
            : "Errore imprevisto nel caricamento celle."
        );
      } finally {
        if (!controller.signal.aborted) {
          setCellsLoading(false);
        }
      }
    }

    void loadCells();

    return () => controller.abort();
  }, [result, selectedOutputMonth]);

  function activateCoordinateBounds() {
    const parsed = parseCoordinateBounds(coordinateForm);
    if (parsed.error || !parsed.bounds) {
      setError(parsed.error ?? "Coordinate non valide.");
      return;
    }

    setManualBounds(parsed.bounds);
    setAreaSource("coordinates");
    setError("");
  }

  async function handleSubmit() {
    if (!manualBounds && !selectedCityConfig) {
      setError("Seleziona una citta oppure disegna un rettangolo sulla mappa.");
      return;
    }

    if (dashboardMode === "observed" && (!startMonth || !endMonth)) {
      setError("Il periodo non e ancora pronto: attendi il caricamento dei metadati.");
      return;
    }

    if (dashboardMode === "observed" && startMonth > endMonth) {
      setError("La data iniziale non puo essere successiva alla data finale.");
      return;
    }

    setError("");
    setLoading(true);

    const baseBody = manualBounds
      ? {
          selectionMode: "bbox" as const,
          label: areaSource === "coordinates" ? "coordinate_area" : "manual_area",
          bounds: manualBounds
        }
      : {
          selectionMode: "city" as const,
          city: selectedCityConfig?.value,
          label: selectedCityConfig?.value,
          halfWindowDeg
        };

    const endpoint = dashboardMode === "forecast" ? "/api/forecast" : "/api/indicators";
    const body =
      dashboardMode === "forecast"
        ? {
            ...baseBody,
            targetMonth: toMonthStart(forecastTargetMonth)
          }
        : {
            ...baseBody,
            start: toMonthStart(startMonth),
            end: toMonthStart(endMonth)
          };

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        throw new Error(await readApiError(response, "Richiesta non completata."));
      }

      const payload = (await response.json()) as IndicatorResponse;
      setResult(payload);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Errore imprevisto durante il calcolo."
      );
    } finally {
      setLoading(false);
    }
  }

  const meanTemperature = useMemo(
    () => mean(result?.monthly.map((row) => row.temperature_mean_area_c) ?? []),
    [result]
  );
  const thermalStressIndicator = useMemo(
    () =>
      computeAverageSlope(result?.monthly ?? [], [
        (row) => row.temperature_mean_area_c,
        (row) => row.stl1_mean_area,
        (row) => row.stl2_mean_area
      ]),
    [result]
  );
  const soilMoistureTrend = useMemo(
    () =>
      computeLinearSlope(
        (result?.monthly ?? []).map((row) => mean([row.swvl1_mean_area, row.swvl2_mean_area]))
      ),
    [result]
  );
  const landCoverChange = useMemo(() => computeLandCoverChange(result?.monthly ?? []), [result]);
  const ndviTrend = useMemo(() => computeNdviTrend(result?.monthly ?? []), [result]);

  return (
    <main className="page-shell">
      <div className="mode-toggle" role="tablist" aria-label="Modalita dashboard">
        <button
          className={`mode-toggle-button ${dashboardMode === "observed" ? "active" : ""}`}
          type="button"
          onClick={() => setDashboardMode("observed")}
        >
          Osservazione
        </button>
        <button
          className={`mode-toggle-button ${dashboardMode === "forecast" ? "active" : ""}`}
          type="button"
          onClick={() => setDashboardMode("forecast")}
        >
          Previsione
        </button>
      </div>

      <section className="hero">
        <span className="eyebrow">BioMap Explorer</span>
        <h1>Ecosystem Biodiversity monitoring</h1>
        <p>
          Questa interfaccia e pensata per il progetto BioMap: puoi scegliere una citta
          europea, inserire coordinate o disegnare manualmente un rettangolo sulla mappa, poi
          passare da osservazione a previsione mantenendo la stessa area di lavoro.
        </p>
      </section>

      <section className="layout-grid">
        <div className="panel">
          <div className="panel-inner">
            <h2 className="section-title">Controlli</h2>
            <p className="section-copy">
              Citta, coordinate e rettangolo sulla mappa sono alternative. L&apos;ultima
              selezione manuale impostata diventa l&apos;area attiva. La modalita attuale e{" "}
              <strong>{dashboardModeLabel}</strong>.
            </p>

            <div className="controls-grid">
              <div className="field-group">
                <label htmlFor="city">Citta europea</label>
                <input
                  id="city-filter"
                  type="text"
                  placeholder="Filtra per citta o paese"
                  value={cityQuery}
                  onChange={(event) => setCityQuery(event.target.value)}
                />
                <select
                  id="city"
                  value={selectedCity}
                  onChange={(event) => {
                    setSelectedCity(event.target.value);
                    setManualBounds(null);
                    setAreaSource("city");
                  }}
                  disabled={!cityOptions.length}
                >
                  {filteredCityOptions.map((city) => (
                    <option key={city.value} value={city.value}>
                      {city.label} · {city.country}
                    </option>
                  ))}
                </select>
                <p className="small-note">
                  {cityQuery.trim()
                    ? `Filtro attivo: ${filteredCityOptions.length} risultati mostrati su ${cityOptions.length} citta.`
                    : `${cityOptions.length} citta europee disponibili.`}
                </p>
              </div>

              <div className="field-group">
                <label htmlFor="window">Ampiezza attorno alla citta (gradi)</label>
                <input
                  id="window"
                  type="number"
                  min="0.25"
                  max="2"
                  step="0.25"
                  value={halfWindowDeg}
                  onChange={(event) => setHalfWindowDeg(Number(event.target.value))}
                />
              </div>

              {dashboardMode === "observed" ? (
                <>
                  <div className="field-row">
                    <div className="field-group">
                      <label htmlFor="start-month">Mese iniziale</label>
                      <select
                        id="start-month"
                        value={startMonth}
                        onChange={(event) => setStartMonth(event.target.value)}
                        disabled={!availableMonths.length}
                      >
                        {!availableMonths.length ? (
                          <option value="">Caricamento periodo...</option>
                        ) : null}
                        {availableMonths.map((month) => (
                          <option key={month} value={month}>
                            {formatMonthLabel(month)}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="field-group">
                      <label htmlFor="end-month">Mese finale</label>
                      <select
                        id="end-month"
                        value={endMonth}
                        onChange={(event) => setEndMonth(event.target.value)}
                        disabled={!availableMonths.length}
                      >
                        {!availableMonths.length ? (
                          <option value="">Caricamento periodo...</option>
                        ) : null}
                        {availableMonths.map((month) => (
                          <option key={month} value={month}>
                            {formatMonthLabel(month)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {metadata ? (
                    <p className="small-note">
                      Periodo disponibile nel dataset: {metadata.period.minMonth} → {metadata.period.maxMonth}
                    </p>
                  ) : null}
                </>
              ) : (
                <div className="field-group">
                  <label htmlFor="forecast-target-month">Mese da prevedere</label>
                  <select
                    id="forecast-target-month"
                    value={forecastTargetMonth}
                    onChange={(event) => setForecastTargetMonth(event.target.value)}
                  >
                    {forecastTargetMonths.map((month) => (
                      <option key={month} value={month}>
                        {formatMonthLabel(month)}
                      </option>
                    ))}
                  </select>
                  <p className="small-note">
                    {forecastTargetMonth === "2026-04"
                      ? "Aprile 2026 usa il forecast one-step."
                      : `La selezione ${forecastTargetMonth} usa il rollout multi-step da 2026-04 al mese target.`}
                    {metadata?.forecast?.cacheConfigured === false
                      ? " Configura FORECAST_CACHE_DIR per leggere i run gia salvati."
                      : null}
                  </p>
                  {metadata?.forecast?.availableMonths?.length ? (
                    <p className="small-note">
                      Cache disponibile: {metadata.forecast.availableMonths.join(", ")}
                    </p>
                  ) : null}
                </div>
              )}

              <div className="field-group">
                <label>Coordinate bounding box</label>
                <div className="coordinate-grid">
                  <input
                    type="number"
                    step="0.01"
                    placeholder="minLat"
                    value={coordinateForm.minLat}
                    onChange={(event) =>
                      setCoordinateForm((current) => ({ ...current, minLat: event.target.value }))
                    }
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="maxLat"
                    value={coordinateForm.maxLat}
                    onChange={(event) =>
                      setCoordinateForm((current) => ({ ...current, maxLat: event.target.value }))
                    }
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="minLon"
                    value={coordinateForm.minLon}
                    onChange={(event) =>
                      setCoordinateForm((current) => ({ ...current, minLon: event.target.value }))
                    }
                  />
                  <input
                    type="number"
                    step="0.01"
                    placeholder="maxLon"
                    value={coordinateForm.maxLon}
                    onChange={(event) =>
                      setCoordinateForm((current) => ({ ...current, maxLon: event.target.value }))
                    }
                  />
                </div>
                <button className="secondary-button" type="button" onClick={activateCoordinateBounds}>
                  Usa coordinate
                </button>
              </div>

              <div className="selection-card">
                {manualBounds ? (
                  <>
                    <strong>{activeAreaLabel} attivo.</strong>
                    <br />
                    lat {manualBounds.minLat.toFixed(2)} .. {manualBounds.maxLat.toFixed(2)}
                    <br />
                    lon {manualBounds.minLon.toFixed(2)} .. {manualBounds.maxLon.toFixed(2)}
                  </>
                ) : selectedCityConfig && cityPreviewBounds ? (
                  <>
                    <strong>Citta attiva:</strong> {selectedCityConfig.label}
                    <br />
                    lat {cityPreviewBounds.minLat.toFixed(2)} .. {cityPreviewBounds.maxLat.toFixed(2)}
                    <br />
                    lon {cityPreviewBounds.minLon.toFixed(2)} .. {cityPreviewBounds.maxLon.toFixed(2)}
                  </>
                ) : (
                  "Seleziona una citta o un rettangolo sulla mappa."
                )}
                <br />
                <br />
                <strong>{dashboardMode === "forecast" ? "Mese target:" : "Periodo selezionato:"}</strong>{" "}
                {dashboardMode === "forecast"
                  ? forecastTargetMonth
                  : startMonth && endMonth
                    ? `${startMonth} → ${endMonth}`
                    : "n.d."}
              </div>

              <div className="action-row">
                <button className="primary-button" type="button" onClick={handleSubmit} disabled={loading}>
                  {loading ? "Calcolo in corso..." : "Conferma e calcola indicatori"}
                </button>

                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => {
                    setManualBounds(null);
                    setAreaSource("city");
                  }}
                >
                  Azzera selezione manuale
                </button>
              </div>

              <p className="small-note">
                Se le specie risultano spesso vuote su aree molto piccole, allarga la finestra
                della citta oppure seleziona un rettangolo piu grande. In modalita forecast il
                frontend legge solo run gia salvati nella cache `previsioni`.
              </p>

              {error ? <div className="status error">{error}</div> : null}
            </div>
          </div>
        </div>

        <div className="panel map-panel">
          <EuropeSelectionMap
            manualBounds={manualBounds}
            previewBounds={manualBounds ? null : cityPreviewBounds}
            onBoundsChange={(bounds) => {
              setManualBounds(bounds);
              if (bounds) {
                setAreaSource("map");
                setCoordinateForm(boundsToCoordinateForm(bounds));
              } else {
                setAreaSource("city");
              }
            }}
          />
        </div>
      </section>

      <section className="result-stack">
        {result ? (
          <>
            {result.notes.length ? (
              <div className="status info">
                {result.notes.map((note) => (
                  <div key={note}>{note}</div>
                ))}
              </div>
            ) : null}

            <p className="period-heading">
              Periodo di riferimento: {result.start.slice(0, 7)} → {result.end.slice(0, 7)}
            </p>

            <div className="stat-grid">
              <div className="stat-card">
                <span>Thermal stress indicator</span>
                <strong>{formatNumber(thermalStressIndicator, "°C/mese", 4)}</strong>
              </div>
              <div className="stat-card">
                <span>Soil moisture trend</span>
                <strong>{formatNumber(soilMoistureTrend, "", 4)}</strong>
              </div>
              <div className="stat-card">
                <span>Temperatura media</span>
                <strong>{formatNumber(meanTemperature, "°C")}</strong>
              </div>
              <div className="stat-card">
                <span>Land cover change</span>
                <strong>{formatNumber(landCoverChange, "", 3)}</strong>
              </div>
              <div className="stat-card">
                <span>NDVI trend</span>
                <strong>{formatNumber(ndviTrend, "NDVI/mese", 4)}</strong>
              </div>
            </div>

            <div className="panel">
              <div className="panel-inner">
                <h2 className="section-title">
                  Mappa tematica {result.dashboardMode === "forecast" ? "forecast" : "osservativa"}
                </h2>
                <p className="section-copy">
                  Visualizza la variabile selezionata sulle celle dell&apos;area calcolata.
                </p>

                <div className="toolbar-row">
                  <div className="field-group">
                    <label htmlFor="observed-variable">Variabile</label>
                    <select
                      id="observed-variable"
                      value={selectedVariableKey}
                      onChange={(event) => setSelectedVariableKey(event.target.value as ObservedVariableKey)}
                    >
                      {OBSERVED_VARIABLES.map((variable) => (
                        <option key={variable.key} value={variable.key}>
                          {variable.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="field-group">
                    <label htmlFor="output-month">Mese mappa</label>
                    <select
                      id="output-month"
                      value={selectedOutputMonth}
                      onChange={(event) => setSelectedOutputMonth(event.target.value)}
                    >
                      {outputMonths.map((month) => (
                        <option key={month} value={month}>
                          {month.slice(0, 7)}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                {cellsError ? <div className="status error">{cellsError}</div> : null}
                {cellsLoading ? <div className="status info">Caricamento celle della mappa...</div> : null}

                {activeBounds && selectedOutputMonth && !cellsLoading && !cellsError ? (
                  <IndicatorMap
                    bounds={activeBounds}
                    cells={cellRows}
                    variable={selectedVariable}
                    month={selectedOutputMonth}
                  />
                ) : null}
              </div>
            </div>

            <div className="panel">
              <div className="panel-inner">
                <h2 className="section-title">
                  Trend {result.dashboardMode === "forecast" ? "forecast" : "osservativo"}
                </h2>
                <p className="section-copy">
                  Andamento di {selectedVariable.label.toLowerCase()} nel periodo calcolato.
                </p>
                <TrendChart rows={result.monthly} variable={selectedVariable} />
              </div>
            </div>

            <div className="panel">
              <div className="panel-inner">
                <h2 className="section-title">
                  Output {result.dashboardMode === "forecast" ? "forecast" : "osservativo"} mensile
                </h2>
                <p className="section-copy">
                  {result.dashboardMode === "forecast"
                    ? "Tabella mensile del rollout forecast caricato da cache. Non viene eseguito alcun run live dal frontend."
                    : "Tabella dell&apos;area selezionata con variabili osservate in colonna. La sezione forecast/backtest resta separata e non entra in questa vista."}
                </p>

                <p className="small-note">
                  Periodo effettivamente calcolato: {result.start.slice(0, 7)} → {result.end.slice(0, 7)}
                </p>

                <div className="action-row" style={{ marginBottom: 16 }}>
                  <button className="secondary-button" type="button" onClick={() => exportTableAsCsv(result)}>
                    Esporta CSV
                  </button>
                  <button className="secondary-button" type="button" onClick={() => exportTableAsExcel(result)}>
                    Esporta Excel
                  </button>
                </div>

                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        {TABLE_COLUMNS.map((column) => (
                          <th key={column.label}>{column.label}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {result.monthly.map((row) => (
                        <tr key={row.month}>
                          {TABLE_COLUMNS.map((column) => (
                            <td key={column.label}>{column.display(row)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="panel">
            <div className="panel-inner">
              <h2 className="section-title">Output</h2>
              <p className="section-copy">
                Seleziona una citta, inserisci coordinate oppure disegna un rettangolo sulla mappa, scegli{" "}
                {dashboardMode === "forecast" ? "il mese target" : "il periodo"} e premi il pulsante di
                conferma per vedere gli indicatori.
              </p>

              {activeBounds ? (
                <div className="selection-card">
                  Area pronta per il calcolo ({activeAreaLabel.toLowerCase()}):
                  <br />
                  lat {activeBounds.minLat.toFixed(2)} .. {activeBounds.maxLat.toFixed(2)}
                  <br />
                  lon {activeBounds.minLon.toFixed(2)} .. {activeBounds.maxLon.toFixed(2)}
                </div>
              ) : null}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
