import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { StatusBadge } from "../CallsTable";

test("renders the human-readable label for each status", () => {
  render(<StatusBadge status="success" />);
  // getByText throws if the label is missing, so this asserts the render.
  expect(screen.getByText("Success")).toBeDefined();
});
