import { NextResponse } from "next/server";

export const runtime = "nodejs";

const DEFAULT_LOCAL_BACKEND_URL = "http://127.0.0.1:8000";

function getBackendBaseUrl() {
  return process.env.PYTHON_API_BASE_URL?.trim() || DEFAULT_LOCAL_BACKEND_URL;
}

type RouteContext = {
  params: {
    label: string;
    format: string;
  };
};

export async function GET(_request: Request, context: RouteContext) {
  try {
    const { label, format } = context.params;
    const target = `${getBackendBaseUrl()}/api/download/${label}/${format}`;
    const forwarded = await fetch(target, { method: "GET", cache: "no-store" });

    if (!forwarded.ok) {
      const errorText = await forwarded.text();
      return new NextResponse(errorText, { status: forwarded.status });
    }

    const contentType = forwarded.headers.get("content-type") ?? "application/octet-stream";
    const disposition =
      forwarded.headers.get("content-disposition") ?? `attachment; filename="${label}.${format}"`;
    const buffer = await forwarded.arrayBuffer();

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Content-Disposition": disposition
      }
    });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Errore imprevisto durante il download."
      },
      { status: 500 }
    );
  }
}
