import { NextResponse } from "next/server";

export const runtime = "nodejs";

type RouteContext = {
  params: {
    label: string;
    format: string;
  };
};

export async function GET(_request: Request, context: RouteContext) {
  try {
    if (!process.env.PYTHON_API_BASE_URL) {
      return NextResponse.json(
        { error: "Download non disponibile senza backend Python configurato." },
        { status: 503 }
      );
    }

    const { label, format } = context.params;
    const target = `${process.env.PYTHON_API_BASE_URL}/api/download/${label}/${format}`;
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
