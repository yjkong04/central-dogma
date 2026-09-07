import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CitationCard } from "./CitationCard";
import type { Citation } from "@/lib/types";

const figure = (uri: string | null): Citation => ({
  modality: "figure", paper_id: "P", source_id: "P:fig3", section: "Results",
  figure_label: "Figure 3", image_uri: uri, snippet: "Dose-response curve.", score: 0.79,
});

describe("CitationCard", () => {
  it("renders an <img> for an http image_uri", () => {
    render(<CitationCard citation={figure("https://cdn.example.org/f.jpg")} active={false} onActivate={() => {}} />);
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
  it("renders caption-only for a demo:// uri (no img)", () => {
    render(<CitationCard citation={figure("demo://x")} active={false} onActivate={() => {}} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("Dose-response curve.")).toBeInTheDocument();
  });
  it("falls back to caption-only when the image errors", () => {
    render(<CitationCard citation={figure("https://cdn.example.org/f.jpg")} active={false} onActivate={() => {}} />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
  it("calls onActivate with its source id when clicked", () => {
    const onActivate = vi.fn();
    render(<CitationCard citation={figure(null)} active={false} onActivate={onActivate} />);
    fireEvent.click(screen.getByText("Dose-response curve."));
    expect(onActivate).toHaveBeenCalledWith("P:fig3");
  });
});
