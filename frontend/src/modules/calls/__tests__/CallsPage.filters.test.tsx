import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { callsApi } from "@/services/api";
import type { Call, PaginatedCallsResponse } from "@/types/calls";
import { CallsPage } from "../CallsPage";

vi.mock("@/services/api", () => ({
  callsApi: { list: vi.fn(), getById: vi.fn(), updateNotes: vi.fn() },
}));

const list = vi.mocked(callsApi.list);

function makeCall(): Call {
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
  };
}

// A page with a row so the table (and its sortable headers) render.
function onePage(): PaginatedCallsResponse {
  return {
    data: [makeCall()],
    total: 1,
    page: 1,
    page_size: 20,
    total_pages: 1,
    counts: { in_progress: 0, success: 1, failed: 0 },
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <CallsPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  window.history.replaceState({}, "", "/");
  list.mockReset();
  list.mockResolvedValue(onePage());
});

afterEach(() => cleanup());

test("requests with default sort (created_at desc) and the first page", async () => {
  renderPage();
  await waitFor(() => expect(list).toHaveBeenCalled());
  expect(list).toHaveBeenCalledWith(
    expect.objectContaining({ sort_by: "created_at", sort_dir: "desc", page: 1 }),
  );
});

test("initializes filters and sort from the URL", async () => {
  window.history.replaceState({}, "", "/?label=Support&sort_by=duration_seconds&sort_dir=asc");
  renderPage();

  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(
      expect.objectContaining({ label: "Support", sort_by: "duration_seconds", sort_dir: "asc" }),
    ),
  );
  // The control reflects the URL-derived state.
  expect((screen.getByLabelText("Filter by label") as HTMLSelectElement).value).toBe("Support");
});

test("clicking a column header sorts and refetches immediately", async () => {
  renderPage();
  // Wait for the row (and therefore the sortable headers) to render before interacting.
  const durationHeader = await screen.findByRole("button", { name: /duration/i });
  list.mockClear();

  fireEvent.click(durationHeader);
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(
      expect.objectContaining({ sort_by: "duration_seconds", sort_dir: "asc" }),
    ),
  );

  fireEvent.click(screen.getByRole("button", { name: /duration/i }));
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(
      expect.objectContaining({ sort_by: "duration_seconds", sort_dir: "desc" }),
    ),
  );
});

test("changing a filter reflects in the URL immediately (shareable state)", async () => {
  renderPage();
  await waitFor(() => expect(list).toHaveBeenCalled());

  fireEvent.change(screen.getByLabelText("Filter by caller name"), { target: { value: "Zoe" } });

  await waitFor(() =>
    expect(new URLSearchParams(window.location.search).get("caller_name")).toBe("Zoe"),
  );
});

test("a typed filter reaches the API after the debounce settles", async () => {
  renderPage();
  await waitFor(() => expect(list).toHaveBeenCalled());
  list.mockClear();

  fireEvent.change(screen.getByLabelText("Filter by caller name"), { target: { value: "Zoe" } });

  // The whole point of debouncing: the value must eventually be sent to the API, not just the URL.
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ caller_name: "Zoe" })),
  );
});

test("an inverted duration range shows an inline error and is never requested", async () => {
  renderPage();
  await waitFor(() => expect(list).toHaveBeenCalled());
  list.mockClear();

  fireEvent.change(screen.getByLabelText("Min duration (seconds)"), { target: { value: "500" } });
  fireEvent.change(screen.getByLabelText("Max duration (seconds)"), { target: { value: "100" } });

  // Inline alert, NOT the full-page "Failed to load calls" error screen.
  await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());
  expect(screen.queryByText("Failed to load calls")).toBeNull();
  // The query is disabled for an invalid range, so the bad combination is never sent.
  expect(list).not.toHaveBeenCalledWith(
    expect.objectContaining({ min_duration: 500, max_duration: 100 }),
  );
});

test("changing the sort resets pagination to page 1", async () => {
  window.history.replaceState({}, "", "/?page=3");
  renderPage();
  const durationHeader = await screen.findByRole("button", { name: /duration/i });
  list.mockClear();

  fireEvent.click(durationHeader);
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(
      expect.objectContaining({ sort_by: "duration_seconds", page: 1 }),
    ),
  );
});
