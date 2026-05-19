"use client";

import { useEffect, useMemo } from "react";

import { MapContainer, Rectangle, TileLayer, Tooltip, useMap } from "react-leaflet";

import type { CellRow, SelectionBounds } from "../lib/types";
import type { ObservedVariable } from "../lib/observed-variables";
import { formatObservedValue } from "../lib/observed-variables";

type IndicatorMapProps = {
  bounds: SelectionBounds;
  cells: CellRow[];
  variable: ObservedVariable;
  month: string;
};

const CELL_HALF_DEGREES = 0.125;
const NO_DATA_COLOR = "#c8c8bd";

function BoundsViewport({ bounds }: { bounds: SelectionBounds }) {
  const map = useMap();

  useEffect(() => {
    map.fitBounds(
      [
        [bounds.minLat, bounds.minLon],
        [bounds.maxLat, bounds.maxLon]
      ],
      { padding: [28, 28] }
    );
  }, [bounds, map]);

  return null;
}

function hexToRgb(hex: string) {
  const normalized = hex.replace("#", "");
  const value = parseInt(normalized, 16);
  return {
    r: (value >> 16) & 255,
    g: (value >> 8) & 255,
    b: value & 255
  };
}

function interpolateColor(start: string, end: string, amount: number) {
  const a = hexToRgb(start);
  const b = hexToRgb(end);
  const mix = (from: number, to: number) => Math.round(from + (to - from) * amount);
  return `rgb(${mix(a.r, b.r)}, ${mix(a.g, b.g)}, ${mix(a.b, b.b)})`;
}

function colorForValue(value: number | null, min: number, max: number, palette: [string, string, string]) {
  if (value === null || Number.isNaN(value)) {
    return NO_DATA_COLOR;
  }

  const span = max - min || 1;
  const normalized = Math.max(0, Math.min(1, (value - min) / span));
  if (normalized <= 0.5) {
    return interpolateColor(palette[0], palette[1], normalized * 2);
  }

  return interpolateColor(palette[1], palette[2], (normalized - 0.5) * 2);
}

export function IndicatorMap({ bounds, cells, variable, month }: IndicatorMapProps) {
  const values = useMemo(
    () =>
      cells
        .map((cell) => variable.cellValue(cell))
        .filter((value): value is number => value !== null && !Number.isNaN(value)),
    [cells, variable]
  );
  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 1;

  if (!cells.length) {
    return <div className="status info">Nessuna cella disponibile per la mappa tematica.</div>;
  }

  return (
    <div className="thematic-map-shell">
      <MapContainer center={[54, 15]} zoom={4} scrollWheelZoom className="thematic-map">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <BoundsViewport bounds={bounds} />

        <Rectangle
          bounds={[
            [bounds.minLat, bounds.minLon],
            [bounds.maxLat, bounds.maxLon]
          ]}
          pathOptions={{
            color: "#203126",
            fillOpacity: 0,
            weight: 2
          }}
        />

        {cells.map((cell, index) => {
          if (cell.latitude === null || cell.longitude === null) {
            return null;
          }

          const value = variable.cellValue(cell);
          const color = colorForValue(value, min, max, variable.palette);

          return (
            <Rectangle
              key={`${cell.month}-${cell.latitude}-${cell.longitude}-${index}`}
              bounds={[
                [cell.latitude - CELL_HALF_DEGREES, cell.longitude - CELL_HALF_DEGREES],
                [cell.latitude + CELL_HALF_DEGREES, cell.longitude + CELL_HALF_DEGREES]
              ]}
              pathOptions={{
                color,
                fillColor: color,
                fillOpacity: value === null ? 0.28 : 0.66,
                opacity: 0.7,
                weight: 0.5
              }}
            >
              <Tooltip sticky>
                <strong>{variable.label}</strong>
                <br />
                {month.slice(0, 7)}
                <br />
                lat {cell.latitude.toFixed(2)}, lon {cell.longitude.toFixed(2)}
                <br />
                {formatObservedValue(variable, value)}
              </Tooltip>
            </Rectangle>
          );
        })}
      </MapContainer>

      <div className="map-legend">
        <span>{formatObservedValue(variable, min)}</span>
        <div
          className="legend-gradient"
          style={{
            background: `linear-gradient(90deg, ${variable.palette[0]}, ${variable.palette[1]}, ${variable.palette[2]})`
          }}
        />
        <span>{formatObservedValue(variable, max)}</span>
      </div>
    </div>
  );
}
