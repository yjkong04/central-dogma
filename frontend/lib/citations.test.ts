import { describe, it, expect } from "vitest";
import { resolveMarker, tokenizeAnswer, hasInlineMarkers } from "./citations";
import type { Citation } from "./types";

const cites: Citation[] = [
  { modality: "text", paper_id: "P", source_id: "P:c1", section: "Results", figure_label: null, image_uri: null, snippet: "a", score: 0.9 },
  { modality: "text", paper_id: "P", source_id: "P:c2", section: "Results", figure_label: null, image_uri: null, snippet: "b", score: 0.8 },
  { modality: "figure", paper_id: "P", source_id: "P:fig3", section: "Results", figure_label: "Figure 3", image_uri: null, snippet: "c", score: 0.7 },
];

describe("resolveMarker", () => {
  it("maps a figure label to its source id (case-insensitive)", () => {
    expect(resolveMarker("figure 3", cites)).toEqual(["P:fig3"]);
  });
  it("maps a section marker to ALL matching text citations", () => {
    expect(resolveMarker("Results", cites)).toEqual(["P:c1", "P:c2"]);
  });
  it("returns [] for an unknown marker", () => {
    expect(resolveMarker("Methods", cites)).toEqual([]);
  });
});

describe("tokenizeAnswer", () => {
  it("splits prose and resolvable markers in order", () => {
    const toks = tokenizeAnswer("It plateaus [Figure 3].", cites);
    expect(toks).toEqual([
      { kind: "text", text: "It plateaus " },
      { kind: "marker", label: "Figure 3", sourceIds: ["P:fig3"] },
      { kind: "text", text: "." },
    ]);
  });
  it("renders an unmatched marker as literal text", () => {
    const toks = tokenizeAnswer("See [Methods].", cites);
    expect(toks).toEqual([
      { kind: "text", text: "See " },
      { kind: "text", text: "[Methods]" },
      { kind: "text", text: "." },
    ]);
  });
  it("returns a single text token when there are no markers", () => {
    const toks = tokenizeAnswer("Plain prose.", cites);
    expect(toks).toEqual([{ kind: "text", text: "Plain prose." }]);
  });
});

describe("hasInlineMarkers", () => {
  it("is true only when a resolvable marker exists", () => {
    expect(hasInlineMarkers("x [Figure 3]", cites)).toBe(true);
    expect(hasInlineMarkers("x [Methods]", cites)).toBe(false);
    expect(hasInlineMarkers("x", cites)).toBe(false);
  });
});
