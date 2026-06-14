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

test("clicking a status tab filters by that status", async () => {
  renderWithProviders(<CallsPage />);
  await screen.findByRole("button", { name: /duration/i });
  list.mockClear();

  fireEvent.click(screen.getByRole("button", { name: "Failed" }));
  await waitFor(() =>
    expect(list).toHaveBeenCalledWith(expect.objectContaining({ status: "failed" })),
  );
});
