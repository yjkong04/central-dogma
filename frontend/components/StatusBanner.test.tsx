import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBanner } from "./StatusBanner";
import type { AskResponse } from "@/lib/types";

const answered: AskResponse = { answer: "a", citations: [], status: "answered", backend: "pgvector", confidence: 0.82, sections_covered: 2 };
const refused: AskResponse = { answer: "no", citations: [], status: "refused", backend: "demo", confidence: null, sections_covered: 0 };

describe("StatusBanner", () => {
  it("shows an error alert when error is set", () => {
    render(<StatusBanner response={null} error="couldn't reach the API" />);
    expect(screen.getByRole("alert")).toHaveTextContent("couldn't reach the API");
  });
  it("shows the refusal as a status when refused", () => {
    render(<StatusBanner response={refused} error={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(/won't guess/i);
  });
  it("shows backend, confidence and sections when answered", () => {
    render(<StatusBanner response={answered} error={null} />);
    const banner = screen.getByRole("status");
    expect(banner).toHaveTextContent("pgvector");
    expect(banner).toHaveTextContent("0.820");
    expect(banner).toHaveTextContent("2");
  });
});
