import { describe, it, expect, vi, afterEach } from "vitest";
import { ask } from "./api";

afterEach(() => vi.restoreAllMocks());

function mockFetch(body: unknown, ok = true, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: ok ? status : status }))
  );
}

describe("ask", () => {
  it("returns the parsed AskResponse on success", async () => {
    mockFetch({ answer: "hi", citations: [], status: "answered", backend: "demo", confidence: 0.5, sections_covered: 0 });
    const res = await ask({ question: "what is up" });
    expect(res.answer).toBe("hi");
    expect(res.status).toBe("answered");
  });
  it("throws the server error message on non-ok", async () => {
    mockFetch({ error: "couldn't reach the API" }, false, 502);
    await expect(ask({ question: "what is up" })).rejects.toThrow("couldn't reach the API");
  });
});
