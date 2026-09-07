import { NextResponse } from "next/server";

const API_BASE = process.env.API_BASE ?? "http://localhost:8000";

export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const question = (body as { question?: unknown } | null)?.question;
  if (typeof question !== "string" || question.trim().length < 3) {
    return NextResponse.json({ error: "question must be at least 3 characters" }, { status: 400 });
  }
  try {
    const upstream = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await upstream.text();
    if (!upstream.ok) {
      return NextResponse.json({ error: `backend error (${upstream.status})` }, { status: 502 });
    }
    return new NextResponse(text, { status: 200, headers: { "content-type": "application/json" } });
  } catch {
    return NextResponse.json(
      { error: `couldn't reach the API — is uvicorn running on ${API_BASE}?` },
      { status: 502 }
    );
  }
}
