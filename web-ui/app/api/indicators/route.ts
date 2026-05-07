import { NextResponse } from "next/server";

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
    const backendBaseUrl = process.env.PYTHON_API_BASE_URL;

    if (!body.start || !body.end) {
      return NextResponse.json({ error: "Periodo mancante." }, { status: 400 });
    }

    if (body.selectionMode === "city" && !body.city) {
      return NextResponse.json({ error: "Citta mancante." }, { status: 400 });
    }

    if (body.selectionMode === "bbox" && !body.bounds) {
      return NextResponse.json({ error: "Bounding box mancante." }, { status: 400 });
    }

    if (!backendBaseUrl) {
      return NextResponse.json(
        {
          error:
            "Backend reale non configurato: imposta PYTHON_API_BASE_URL in web-ui/.env.local e avvia FastAPI."
        },
        { status: 503 }
      );
    }

    const forwarded = await fetch(`${backendBaseUrl}/api/indicators`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(body),
      cache: "no-store"
    });

    const responseText = await forwarded.text();
    const payload = responseText ? JSON.parse(responseText) : {};
    return NextResponse.json(payload, { status: forwarded.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Errore imprevisto nel backend."
      },
      { status: 500 }
    );
  }
}
