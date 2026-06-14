import { useState } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { CallsFilters } from "@/types/calls";
import { CallsFilterBar } from "../CallsFilterBar";

afterEach(() => cleanup());

function setup(filters: CallsFilters = {}) {
  const onChange = vi.fn();
  render(<CallsFilterBar filters={filters} onChange={onChange} />);
  return { onChange };
}

// A real stateful host so onChange actually re-renders with the new filters — needed to exercise
// the focus-management effect, which only runs when the `filters` prop changes.
function Controlled({ initial }: { initial: CallsFilters }) {
  const [filters, setFilters] = useState<CallsFilters>(initial);
  return <CallsFilterBar filters={filters} onChange={setFilters} />;
}

test("typing a caller name emits the updated filters", () => {
  const { onChange } = setup();
  fireEvent.change(screen.getByLabelText("Filter by caller name"), {
    target: { value: "García" },
  });
  expect(onChange).toHaveBeenCalledWith({ caller_name: "García" });
});

test("selecting a label emits the chosen label value", () => {
  const { onChange } = setup();
  fireEvent.change(screen.getByLabelText("Filter by label"), {
    target: { value: "Sales inquiry" },
  });
  expect(onChange).toHaveBeenCalledWith({ label: "Sales inquiry" });
});

test("the min duration input emits a numeric bound", () => {
  const { onChange } = setup();
  fireEvent.change(screen.getByLabelText("Min duration (seconds)"), { target: { value: "60" } });
  expect(onChange).toHaveBeenCalledWith({ min_duration: 60 });
});

test("the max duration input emits a numeric bound alongside an existing min", () => {
  const { onChange } = setup({ min_duration: 60 });
  fireEvent.change(screen.getByLabelText("Max duration (seconds)"), { target: { value: "300" } });
  expect(onChange).toHaveBeenCalledWith({ min_duration: 60, max_duration: 300 });
});

test("duration inputs reject negatives and decimals (never reach the API)", () => {
  const { onChange } = setup();
  const min = screen.getByLabelText("Min duration (seconds)");

  fireEvent.change(min, { target: { value: "-5" } });
  expect(onChange).toHaveBeenLastCalledWith({}); // negative dropped, not emitted

  fireEvent.change(min, { target: { value: "2.5" } });
  expect(onChange).toHaveBeenLastCalledWith({ min_duration: 2 }); // floored to an integer
});

test("clearing a text field removes that key (does not send an empty string)", () => {
  const { onChange } = setup({ caller_name: "abc" });
  fireEvent.change(screen.getByLabelText("Filter by caller name"), { target: { value: "" } });
  expect(onChange).toHaveBeenCalledWith({});
});

test("each active filter shows a chip; removing it emits filters without that key", () => {
  const { onChange } = setup({ caller_name: "García", label: "Support", min_duration: 60 });

  // A chip per active filter (status lives in the tabs, not here).
  expect(screen.getByText("Name: García")).toBeDefined();
  expect(screen.getByText("Label: Support")).toBeDefined();

  fireEvent.click(screen.getByLabelText("Remove Caller name filter"));
  expect(onChange).toHaveBeenCalledWith({ label: "Support", min_duration: 60 });
});

test("'Clear all' removes every filter at once", () => {
  const { onChange } = setup({ caller_name: "García", label: "Support", min_duration: 60 });
  fireEvent.click(screen.getByText("Clear all"));
  expect(onChange).toHaveBeenCalledWith({});
});

test("removing a chip keeps keyboard focus on a stable element (not the document body)", () => {
  // Two active filters: removing one leaves the chip row (and 'Clear all') mounted.
  render(<Controlled initial={{ caller_name: "García", label: "Support" }} />);
  fireEvent.click(screen.getByLabelText("Remove Caller name filter"));
  // Focus must not be lost to <body>; it lands on the persistent 'Clear all' control.
  expect(document.activeElement).toBe(screen.getByText("Clear all"));
});

test("removing the last chip moves focus to the caller-name input", () => {
  render(<Controlled initial={{ label: "Support" }} />);
  fireEvent.click(screen.getByLabelText("Remove Label filter"));
  expect(document.activeElement).toBe(screen.getByLabelText("Filter by caller name"));
});

test("no chips render when there are no active filters", () => {
  setup({});
  expect(screen.queryByLabelText(/remove .* filter/i)).toBeNull();
});
