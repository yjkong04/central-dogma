import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvidencePanel } from "./EvidencePanel";
import type { Citation } from "@/lib/types";

const cites: Citation[] = [
  { modality: "text", paper_id: "P", source_id: "P:c1", section: "Results", figure_label: null, image_uri: null, snippet: "alpha", score: 0.9 },
  { modality: "text", paper_id: "P", source_id: "P:c2", section: "Methods", figure_label: null, image_uri: null, snippet: "beta", score: 0.8 },
];

describe("EvidencePanel", () => {
  it("renders one card per citation", () => {
    render(<EvidencePanel citations={cites} activeSourceIds={[]} onActivate={() => {}} />);
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
  });
  it("renders nothing when there are no citations", () => {
    const { container } = render(<EvidencePanel citations={[]} activeSourceIds={[]} onActivate={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});
