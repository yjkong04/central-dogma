import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RootLayout from "./layout";

describe("RootLayout", () => {
  it("renders its children", () => {
    render(<RootLayout>{<p>hello</p>}</RootLayout>);
    expect(screen.getByText("hello")).toBeInTheDocument();
  });
});
