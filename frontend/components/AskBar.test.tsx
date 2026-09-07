import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { AskBar } from "./AskBar";

describe("AskBar", () => {
  it("submits the trimmed question", () => {
    const onAsk = vi.fn();
    render(<AskBar onAsk={onAsk} disabled={false} />);
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "  hello world  " } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
    expect(onAsk).toHaveBeenCalledWith("hello world");
  });
  it("does not submit a too-short question", () => {
    const onAsk = vi.fn();
    render(<AskBar onAsk={onAsk} disabled={false} />);
    fireEvent.change(screen.getByLabelText("question"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));
    expect(onAsk).not.toHaveBeenCalled();
  });
});
