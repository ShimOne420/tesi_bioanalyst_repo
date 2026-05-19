import { NextResponse } from "next/server";

export const runtime = "nodejs";

const DEFAULT_LOCAL_BACKEND_URL = "http://127.0.0.1:8000";

function getBackendBaseUrl() {
  return process.env.PYTHON_API_BASE_URL?.trim() || DEFAULT_LOCAL_BACKEND_URL;
}

type RouteContext = {
  params: {
    label: string;
  };
};

export async function GET(request: Request, context: RouteContext) {
  try {
    const { label } = context.params;
    const { searchParams } = new URL(request.url);
    const month = searchParams.get("month");

    if (!month) {
      return NextResponse.json({ error: "Parametro `month` mancante." }, { status: 400 });
    }

    const target = `${getBackendBaseUrl()}/api/cells/${label}?month=${encodeURIComponent(month)}`;
    const forwarded = await fetch(target, { method: "GET", cache: "no-store" });
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
        error: error instanceof Error ? error.message : "Errore imprevisto nel recupero celle."
      },
      { status: 500 }
    );
  }
}
