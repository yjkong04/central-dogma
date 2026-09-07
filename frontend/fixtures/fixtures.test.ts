import { describe, it, expect } from "vitest";
import type { AskResponse } from "@/lib/types";
import answeredMarkers from "./answered_markers.json";
import answeredNoMarkers from "./answered_no_markers.json";
import refused from "./refused.json";

describe("fixtures", () => {
  it("answered fixtures have citations and answered status", () => {
    for (const f of [answeredMarkers, answeredNoMarkers] as AskResponse[]) {
      expect(f.status).toBe("answered");
      expect(f.citations.length).toBeGreaterThan(0);
    }
  });
  it("refused fixture has no citations", () => {
    const f = refused as AskResponse;
    expect(f.status).toBe("refused");
    expect(f.citations).toHaveLength(0);
  });
});
