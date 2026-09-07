import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import Page from "./page";
import * as api from "@/lib/api";
import answeredMarkers from "@/fixtures/answered_markers.json";
import refused from "@/fixtures/refused.json";
import type { AskResponse } from "@/lib/types";

beforeEach(() => vi.restoreAllMocks());

function ask(q: string) {
  fireEvent.change(screen.getByLabelText("question"), { target: { value: q } });
  fireEvent.click(screen.getByRole("button", { name: /ask/i }));
}

describe("Page", () => {
  it("shows seeded example questions before any ask", () => {
    render(<Page />);
    expect(screen.getByText(/what does the figure show/i)).toBeInTheDocument();
  });
  it("renders the answer and evidence panel on success", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(answeredMarkers as AskResponse);
    render(<Page />);
    ask("what does the figure show about dose");
    await waitFor(() => expect(screen.getByRole("button", { name: "Results" })).toBeInTheDocument());
    expect(screen.getByLabelText("evidence")).toBeInTheDocument();
  });
  it("shows the refusal banner when refused", async () => {
    vi.spyOn(api, "ask").mockResolvedValue(refused as AskResponse);
    render(<Page />);
    ask("what is the airspeed of a swallow");
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/won't guess/i));
  });
  it("shows an error banner when the client throws", async () => {
    vi.spyOn(api, "ask").mockRejectedValue(new Error("couldn't reach the API"));
    render(<Page />);
    ask("what does the figure show about dose");
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("couldn't reach the API"));
  });
});
