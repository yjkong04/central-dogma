import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AnswerView } from "./AnswerView";
import type { Citation } from "@/lib/types";

const cites: Citation[] = [
  { modality: "figure", paper_id: "P", source_id: "P:fig3", section: "Results", figure_label: "Figure 3", image_uri: null, snippet: "c", score: 0.7 },
];

describe("AnswerView", () => {
  it("renders a resolvable marker as a button and reports its sources on click", () => {
    const onHover = vi.fn();
    render(<AnswerView answer="It plateaus [Figure 3]." citations={cites} activeSourceIds={[]} onHoverSources={onHover} />);
    const btn = screen.getByRole("button", { name: "Figure 3" });
    fireEvent.click(btn);
    expect(onHover).toHaveBeenCalledWith(["P:fig3"]);
  });
  it("shows the no-markers note when the answer has none", () => {
    render(<AnswerView answer="Plain prose." citations={cites} activeSourceIds={[]} onHoverSources={() => {}} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
    expect(screen.getByText(/inline highlighting activates/i)).toBeInTheDocument();
  });
});
