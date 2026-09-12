import type { ApiError, AskRequest, AskResponse } from "./types";

export async function ask(req: AskRequest): Promise<AskResponse> {
  const base = process.env.NEXT_PUBLIC_API_URL;
  const url = base ? `${base.replace(/\/$/, "")}/ask` : "/api/ask";
  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
  const data = (await res.json()) as AskResponse | ApiError;
  if (!res.ok || "error" in data) {
    const msg = "error" in data ? data.error : `request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}
