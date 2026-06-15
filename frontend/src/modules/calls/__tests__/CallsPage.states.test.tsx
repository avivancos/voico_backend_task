import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";

import { callsApi } from "@/services/api";
import { makeCall, pageOf, renderWithProviders } from "@/test-utils";
import { CallsPage } from "../CallsPage";

vi.mock("@/services/api", () => ({
  callsApi: { list: vi.fn(), getById: vi.fn(), updateNotes: vi.fn() },
}));

const list = vi.mocked(callsApi.list);

beforeEach(() => {
  window.history.replaceState({}, "", "/");
  list.mockReset();
  list.mockResolvedValue(pageOf([makeCall()]));
});

test("shows the error state when the list request fails", async () => {
  list.mockReset();
  list.mockRejectedValue(new Error("network down"));
  renderWithProviders(<CallsPage />);
  expect(await screen.findByText("Failed to load calls")).toBeTruthy();
});

test("renders stat cards from the response counts", async () => {
  list.mockReset();
  list.mockResolvedValue(
    pageOf([makeCall()], { total: 42, counts: { in_progress: 5, success: 30, failed: 7 } }),
  );
  renderWithProviders(<CallsPage />);
  expect(await screen.findByText("Total Calls")).toBeTruthy();
  expect(await screen.findByText("42")).toBeTruthy();
});

test("paginates with the Next button", async () => {
  list.mockReset();
  list.mockResolvedValue(pageOf([makeCall()], { total: 45, total_pages: 3, page: 1 }));
  renderWithProviders(<CallsPage />);

  fireEvent.click(await screen.findByRole("button", { name: /next/i }));
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ page: 2 })),
  );
});

test("keeps an open drawer live when polling returns an updated call", async () => {
  const call = makeCall({ summary: null, updated_at: "2026-01-01T00:00:00" });
  list.mockReset();
  list.mockResolvedValue(pageOf([call]));
  renderWithProviders(<CallsPage />);

  // Open the drawer from the row; no AI summary yet.
  fireEvent.click(await screen.findByText(call.phone_number));
  expect(await screen.findByText("Call Details")).toBeTruthy();
  expect(screen.queryByText("AI Summary")).toBeNull();

  // The next poll/refresh brings an enriched version of the same call.
  list.mockResolvedValue(
    pageOf([{ ...call, summary: "Caller upgraded their plan.", updated_at: "2026-01-01T00:05:00" }]),
  );
  fireEvent.click(screen.getByLabelText("Refresh"));

  // The open drawer reflects the upstream change without being reopened.
  expect(await screen.findByText("Caller upgraded their plan.")).toBeTruthy();
});

test("clicking a status tab filters by that status", async () => {
  renderWithProviders(<CallsPage />);
  await screen.findByRole("button", { name: /duration/i });
  list.mockClear();

  fireEvent.click(screen.getByRole("button", { name: "Failed" }));
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ status: "failed" })),
  );
});
