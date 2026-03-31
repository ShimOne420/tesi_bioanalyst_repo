import { NextResponse } from "next/server";

import { CITY_OPTIONS } from "../../../lib/cities";

export const runtime = "nodejs";

export async function GET() {
  try {
    if (process.env.PYTHON_API_BASE_URL) {
      const forwarded = await fetch(`${process.env.PYTHON_API_BASE_URL}/api/metadata`, {
        method: "GET",
        cache: "no-store"
      });

      const payload = await forwarded.json();
      return NextResponse.json(payload, { status: forwarded.status });
    }

    return NextResponse.json({
      period: {
        minMonth: "2000-01",
        maxMonth: "2020-06"
      },
      cities: CITY_OPTIONS,
      note: "Modalita demo: metadata locale non disponibile, sto usando un range predefinito."
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Errore imprevisto nel recupero dei metadati."
      },
      { status: 500 }
    );
  }
}
