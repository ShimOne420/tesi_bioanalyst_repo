import { NextResponse } from "next/server";

import { createDemoResponse } from "../../../lib/mock-response";
import type { SelectionBounds } from "../../../lib/types";

export const runtime = "nodejs";

type RequestBody = {
  selectionMode: "city" | "bbox";
  city?: string;
  label?: string;
  bounds?: SelectionBounds;
  start: string;
  end: string;
  halfWindowDeg?: number;
  outputMode?: "area" | "cells" | "both";
  maxSteps?: number;
};

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as RequestBody;

    if (!body.start || !body.end) {
      return NextResponse.json({ error: "Periodo mancante." }, { status: 400 });
    }

    if (body.selectionMode === "city" && !body.city) {
      return NextResponse.json({ error: "Citta mancante." }, { status: 400 });
    }

    if (body.selectionMode === "bbox" && !body.bounds) {
      return NextResponse.json({ error: "Bounding box mancante." }, { status: 400 });
    }

    if (process.env.PYTHON_API_BASE_URL) {
      const forwarded = await fetch(`${process.env.PYTHON_API_BASE_URL}/api/indicators`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(body)
      });

      const payload = await forwarded.json();
      return NextResponse.json(payload, { status: forwarded.status });
    }

    const demoBounds =
      body.selectionMode === "bbox" && body.bounds
        ? body.bounds
        : {
            minLat: 44.9642,
            maxLat: 45.9642,
            minLon: 8.69,
            maxLon: 9.69
          };

    return NextResponse.json(
      createDemoResponse({
        label: body.label ?? body.city ?? "selected_area",
        selectionMode: body.selectionMode,
        bounds: demoBounds,
        startMonth: body.start.slice(0, 7),
        endMonth: body.end.slice(0, 7)
      })
    );
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Errore imprevisto nel backend."
      },
      { status: 500 }
    );
  }
}
