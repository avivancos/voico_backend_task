import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import type { Call } from "@/types/calls";
import { CallsTable } from "../CallsTable";

afterEach(() => cleanup());

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    phone_number: "+1 (555) 000-0000",
    caller_name: "Sarah",
    duration_seconds: 60,
    status: "success",
    summary: null,
    label: "Support",
    started_at: "2026-01-01T00:00:00",
    ended_at: null,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    raw_transcript: null,
    notes: null,
    ...overrides,
  };
}

test("clicking a column header requests sorting by that field", () => {
  const onSortChange = vi.fn();
  render(
    <CallsTable
      calls={[makeCall()]}
      onRowClick={() => {}}
      sort={{ sort_by: "created_at", sort_dir: "desc" }}
      onSortChange={onSortChange}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: /duration/i }));
  expect(onSortChange).toHaveBeenCalledWith("duration_seconds");

  fireEvent.click(screen.getByRole("button", { name: /caller/i }));
  expect(onSortChange).toHaveBeenCalledWith("caller_name");
});

test("the active sort column exposes its direction via aria-sort", () => {
  render(
    <CallsTable
      calls={[makeCall()]}
      onRowClick={() => {}}
      sort={{ sort_by: "duration_seconds", sort_dir: "asc" }}
      onSortChange={() => {}}
    />,
  );

  expect(screen.getByRole("columnheader", { name: /duration/i }).getAttribute("aria-sort")).toBe(
    "ascending",
  );
  // A column that is not the active sort is not marked.
  expect(screen.getByRole("columnheader", { name: /caller/i }).getAttribute("aria-sort")).toBe(
    "none",
  );
});
