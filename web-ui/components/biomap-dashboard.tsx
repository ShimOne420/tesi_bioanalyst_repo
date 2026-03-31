"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { buildBoundsFromCity, CITY_OPTIONS } from "../lib/cities";
import type { DatasetMetadata, IndicatorResponse, SelectionBounds } from "../lib/types";

const EuropeSelectionMap = dynamic(
  () => import("./europe-selection-map").then((mod) => mod.EuropeSelectionMap),
  {
    ssr: false,
    loading: () => <div className="panel map-panel panel-inner">Caricamento mappa...</div>
  }
);

function toMonthStart(value: string) {
  return `${value}-01`;
}

function formatNumber(value: number | null, unit: string) {
  if (value === null || Number.isNaN(value)) {
    return "n.d.";
  }

  return `${value.toFixed(2)} ${unit}`;
}

export function BiomapDashboard() {
  const [selectedCity, setSelectedCity] = useState<string>("milano");
  const [halfWindowDeg, setHalfWindowDeg] = useState<number>(0.5);
  const [startMonth, setStartMonth] = useState<string>("");
  const [endMonth, setEndMonth] = useState<string>("");
  const [manualBounds, setManualBounds] = useState<SelectionBounds | null>(null);
  const [result, setResult] = useState<IndicatorResponse | null>(null);
  const [metadata, setMetadata] = useState<DatasetMetadata | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;

    async function loadMetadata() {
      try {
        const response = await fetch("/api/metadata", { cache: "no-store" });
        if (!response.ok) {
          throw new Error("Non sono riuscito a leggere il periodo disponibile del dataset.");
        }

        const payload = (await response.json()) as DatasetMetadata;
        if (cancelled) {
          return;
        }

        setMetadata(payload);
        setStartMonth(payload.period.minMonth);
        setEndMonth(payload.period.maxMonth);
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

  const selectedCityConfig = useMemo(
    () => CITY_OPTIONS.find((city) => city.value === selectedCity) ?? null,
    [selectedCity]
  );

  const cityPreviewBounds = useMemo(() => {
    if (!selectedCityConfig) {
      return null;
    }

    return buildBoundsFromCity(selectedCityConfig, halfWindowDeg);
  }, [halfWindowDeg, selectedCityConfig]);

  const activeBounds = manualBounds ?? cityPreviewBounds;

  async function handleSubmit() {
    if (!manualBounds && !selectedCityConfig) {
      setError("Seleziona una citta oppure disegna un rettangolo sulla mappa.");
      return;
    }

    if (!startMonth || !endMonth) {
      setError("Il periodo non e ancora pronto: attendi il caricamento dei metadati.");
      return;
    }

    if (startMonth > endMonth) {
      setError("La data iniziale non puo essere successiva alla data finale.");
      return;
    }

    setError("");
    setLoading(true);

    const body = manualBounds
      ? {
          selectionMode: "bbox" as const,
          label: "manual_area",
          bounds: manualBounds,
          start: toMonthStart(startMonth),
          end: toMonthStart(endMonth)
        }
      : {
          selectionMode: "city" as const,
          city: selectedCityConfig?.value,
          label: selectedCityConfig?.value,
          halfWindowDeg,
          start: toMonthStart(startMonth),
          end: toMonthStart(endMonth)
        };

    try {
      const response = await fetch("/api/indicators", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });

      if (!response.ok) {
        throw new Error("Richiesta non completata.");
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

  const latestRow = result?.monthly.at(-1) ?? null;

  return (
    <main className="page-shell">
      <section className="hero">
        <span className="eyebrow">BioMap Explorer</span>
        <h1>Seleziona un&apos;area europea e calcola gli indicatori.</h1>
        <p>
          Questa interfaccia e pensata per il progetto BioMap: puoi scegliere una citta
          europea oppure disegnare manualmente un rettangolo sulla mappa, definire il
          periodo e ottenere in output specie osservate, temperatura media e
          precipitazioni medie.
        </p>
      </section>

      <section className="layout-grid">
        <div className="panel">
          <div className="panel-inner">
            <h2 className="section-title">Controlli</h2>
            <p className="section-copy">
              La citta e il rettangolo sulla mappa sono alternativi. Se disegni una nuova
              area, la selezione manuale ha la priorita.
            </p>

            <div className="controls-grid">
              <div className="field-group">
                <label htmlFor="city">Citta europea</label>
                <select
                  id="city"
                  value={selectedCity}
                  onChange={(event) => {
                    setSelectedCity(event.target.value);
                    setManualBounds(null);
                  }}
                >
                  {CITY_OPTIONS.map((city) => (
                    <option key={city.value} value={city.value}>
                      {city.label} · {city.country}
                    </option>
                  ))}
                </select>
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

              <div className="field-row">
                <div className="field-group">
                  <label htmlFor="start-month">Mese iniziale</label>
                  <input
                    id="start-month"
                    type="month"
                    min={metadata?.period.minMonth}
                    max={metadata?.period.maxMonth}
                    value={startMonth}
                    onChange={(event) => setStartMonth(event.target.value)}
                  />
                </div>

                <div className="field-group">
                  <label htmlFor="end-month">Mese finale</label>
                  <input
                    id="end-month"
                    type="month"
                    min={metadata?.period.minMonth}
                    max={metadata?.period.maxMonth}
                    value={endMonth}
                    onChange={(event) => setEndMonth(event.target.value)}
                  />
                </div>
              </div>

              {metadata ? (
                <p className="small-note">
                  Periodo disponibile nel dataset: {metadata.period.minMonth} → {metadata.period.maxMonth}
                </p>
              ) : null}

              <div className="selection-card">
                {manualBounds ? (
                  <>
                    <strong>Area manuale attiva.</strong>
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
              </div>

              <div className="action-row">
                <button className="primary-button" type="button" onClick={handleSubmit} disabled={loading}>
                  {loading ? "Calcolo in corso..." : "Conferma e calcola indicatori"}
                </button>

                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => setManualBounds(null)}
                >
                  Azzera selezione manuale
                </button>
              </div>

              <p className="small-note">
                Se le specie risultano spesso vuote su aree molto piccole, allarga la finestra
                della citta oppure seleziona un rettangolo piu grande.
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
            }}
          />
        </div>
      </section>

      <section className="result-stack">
        {result ? (
          <>
            {result.notes.length ? (
              <div className={`status ${result.sourceMode === "demo" ? "info" : "info"}`}>
                {result.notes.map((note) => (
                  <div key={note}>{note}</div>
                ))}
              </div>
            ) : null}

            <div className="stat-grid">
              <div className="stat-card">
                <span>Modalita dati</span>
                <strong>{result.sourceMode}</strong>
              </div>
              <div className="stat-card">
                <span>Periodo</span>
                <strong>
                  {result.start.slice(0, 7)} → {result.end.slice(0, 7)}
                </strong>
              </div>
              <div className="stat-card">
                <span>Temperatura ultimo mese</span>
                <strong>{formatNumber(latestRow?.temperature_mean_area_c ?? null, "°C")}</strong>
              </div>
              <div className="stat-card">
                <span>Precipitazione ultimo mese</span>
                <strong>{formatNumber(latestRow?.precipitation_mean_area_mm ?? null, "mm")}</strong>
              </div>
              <div className="stat-card">
                <span>Specie osservate ultimo mese</span>
                <strong>
                  {latestRow?.species_count_observed_area === null ||
                  latestRow?.species_count_observed_area === undefined
                    ? "n.d."
                    : latestRow.species_count_observed_area}
                </strong>
              </div>
            </div>

            <div className="panel">
              <div className="panel-inner">
                <h2 className="section-title">Output mensile</h2>
                <p className="section-copy">
                  Tabella mensile dell&apos;area selezionata. Se l&apos;app e collegata al
                  backend locale o a un backend remoto, qui vedrai i dati reali; altrimenti
                  viene mostrata una demo trasparente.
                </p>

                {result.downloads ? (
                  <div className="action-row" style={{ marginBottom: 16 }}>
                    <Link className="secondary-button" href={result.downloads.csvUrl}>
                      Scarica CSV
                    </Link>
                    <Link className="secondary-button" href={result.downloads.excelCsvUrl}>
                      Scarica CSV per Excel
                    </Link>
                    <Link className="secondary-button" href={result.downloads.xlsxUrl}>
                      Scarica XLSX
                    </Link>
                  </div>
                ) : null}

                <div className="table-shell">
                  <table>
                    <thead>
                      <tr>
                        <th>Mese</th>
                        <th>Temperatura media</th>
                        <th>Precipitazioni medie</th>
                        <th>Celle di terra</th>
                        <th>Celle con specie</th>
                        <th>Specie osservate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.monthly.map((row) => (
                        <tr key={row.month}>
                          <td>{row.month.slice(0, 7)}</td>
                          <td>{formatNumber(row.temperature_mean_area_c, "°C")}</td>
                          <td>{formatNumber(row.precipitation_mean_area_mm, "mm")}</td>
                          <td>{row.cell_count_land ?? "n.d."}</td>
                          <td>{row.cells_with_species_records ?? "n.d."}</td>
                          <td>{row.species_count_observed_area ?? "n.d."}</td>
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
                Seleziona una citta oppure disegna un rettangolo sulla mappa, scegli il
                periodo e premi il pulsante di conferma per vedere gli indicatori.
              </p>

              {activeBounds ? (
                <div className="selection-card">
                  Area pronta per il calcolo:
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
