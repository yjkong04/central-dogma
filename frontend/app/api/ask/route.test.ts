// @vitest-environment node
import { describe, it, expect, vi, afterEach } from "vitest";
import { POST } from "./route";

afterEach(() => vi.restoreAllMocks());

function req(body: unknown): Request {
  return new Request("http://localhost/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/ask", () => {
  it("rejects a too-short question with 400", async () => {
    const res = await POST(req({ question: "hi" }));
    expect(res.status).toBe(400);
  });

  it("forwards a valid question and passes the backend JSON through", async () => {
    const backend = { answer: "ok", citations: [], status: "answered", backend: "demo", confidence: 0.5, sections_covered: 0 };
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify(backend), { status: 200 })));
    const res = await POST(req({ question: "what does the figure show" }));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual(backend);
  });

  it("maps a network failure to a 502 error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("ECONNREFUSED"); }));
    const res = await POST(req({ question: "what does the figure show" }));
    expect(res.status).toBe(502);
    expect((await res.json()).error).toMatch(/reach the API/);
  });
});
