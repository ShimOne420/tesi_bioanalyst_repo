import { NextResponse } from "next/server";

export const runtime = "nodejs";

export async function GET() {
  try {
    const backendBaseUrl = process.env.PYTHON_API_BASE_URL;

    if (!backendBaseUrl) {
      return NextResponse.json(
        {
          error:
            "Backend reale non configurato: imposta PYTHON_API_BASE_URL in web-ui/.env.local e avvia FastAPI."
        },
        { status: 503 }
      );
    }

    const forwarded = await fetch(`${backendBaseUrl}/api/metadata`, {
      method: "GET",
      cache: "no-store"
    });

    const responseText = await forwarded.text();
    let payload: unknown = {};
    try {
      payload = responseText ? JSON.parse(responseText) : {};
    } catch {
      payload = { error: responseText || "Il backend non ha restituito una risposta JSON." };
    }
    return NextResponse.json(payload, { status: forwarded.status });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Errore imprevisto nel recupero dei metadati."
      },
      { status: 500 }
    );
  }
}
