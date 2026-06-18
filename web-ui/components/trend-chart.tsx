"use client";

import type { IndicatorRow } from "../lib/types";
import type { ObservedVariable } from "../lib/observed-variables";
import { formatObservedValue } from "../lib/observed-variables";

type TrendChartProps = {
  rows: IndicatorRow[];
  variable: ObservedVariable;
};

const CHART_WIDTH = 720;
const CHART_HEIGHT = 280;
const PADDING = {
  top: 18,
  right: 22,
  bottom: 42,
  left: 64
};

function monthLabel(value: string) {
  return value.slice(0, 7);
}

export function TrendChart({ rows, variable }: TrendChartProps) {
  const points = rows
    .map((row) => ({
      month: row.month,
      value: variable.monthlyValue(row)
    }))
    .filter((point): point is { month: string; value: number } => point.value !== null && !Number.isNaN(point.value));

  if (!points.length) {
    return <div className="status info">Nessun dato disponibile per il trend di {variable.label}.</div>;
  }

  const values = points.map((point) => point.value);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const span = maxValue - minValue || 1;
  const yMin = minValue === maxValue ? minValue - span * 0.5 : minValue;
  const yMax = minValue === maxValue ? maxValue + span * 0.5 : maxValue;
  const ySpan = yMax - yMin || 1;
  const innerWidth = CHART_WIDTH - PADDING.left - PADDING.right;
  const innerHeight = CHART_HEIGHT - PADDING.top - PADDING.bottom;

  const toX = (index: number) =>
    PADDING.left + (points.length === 1 ? innerWidth / 2 : (index / (points.length - 1)) * innerWidth);
  const toY = (value: number) => PADDING.top + (1 - (value - yMin) / ySpan) * innerHeight;

  const path = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${toX(index).toFixed(2)} ${toY(point.value).toFixed(2)}`)
    .join(" ");
  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];
  const yTicks = [yMax, yMin + ySpan / 2, yMin];

  return (
    <div className="chart-shell">
      <div className="chart-summary">
        <div>
          <span>Primo mese</span>
          <strong>{formatObservedValue(variable, firstPoint.value)}</strong>
        </div>
        <div>
          <span>Ultimo mese</span>
          <strong>{formatObservedValue(variable, lastPoint.value)}</strong>
        </div>
        <div>
          <span>Delta</span>
          <strong>{formatObservedValue(variable, lastPoint.value - firstPoint.value)}</strong>
        </div>
      </div>

      <svg className="trend-svg" viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img">
        <title>{`Trend ${variable.label}`}</title>
        <line
          x1={PADDING.left}
          y1={CHART_HEIGHT - PADDING.bottom}
          x2={CHART_WIDTH - PADDING.right}
          y2={CHART_HEIGHT - PADDING.bottom}
          className="chart-axis"
        />
        <line
          x1={PADDING.left}
          y1={PADDING.top}
          x2={PADDING.left}
          y2={CHART_HEIGHT - PADDING.bottom}
          className="chart-axis"
        />

        {yTicks.map((tick) => {
          const y = toY(tick);
          return (
            <g key={tick}>
              <line x1={PADDING.left} y1={y} x2={CHART_WIDTH - PADDING.right} y2={y} className="chart-grid" />
              <text x={PADDING.left - 10} y={y + 4} textAnchor="end" className="chart-label">
                {tick.toFixed(variable.decimals)}
              </text>
            </g>
          );
        })}

        <path d={path} className="trend-line" />
        {points.map((point, index) => (
          <g key={point.month}>
            <circle cx={toX(index)} cy={toY(point.value)} r="4.5" className="trend-point" />
            <title>{`${monthLabel(point.month)}: ${formatObservedValue(variable, point.value)}`}</title>
          </g>
        ))}

        <text x={PADDING.left} y={CHART_HEIGHT - 14} className="chart-label">
          {monthLabel(firstPoint.month)}
        </text>
        <text x={CHART_WIDTH - PADDING.right} y={CHART_HEIGHT - 14} textAnchor="end" className="chart-label">
          {monthLabel(lastPoint.month)}
        </text>
      </svg>
    </div>
  );
}
