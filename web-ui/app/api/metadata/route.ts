import { NextResponse } from "next/server";

export const runtime = "nodejs";

const DEFAULT_LOCAL_BACKEND_URL = "http://127.0.0.1:8000";

function getBackendBaseUrl() {
  return process.env.PYTHON_API_BASE_URL?.trim() || DEFAULT_LOCAL_BACKEND_URL;
}

export async function GET() {
  try {
    const backendBaseUrl = getBackendBaseUrl();

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
