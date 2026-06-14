import { fireEvent, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";

import { makeCall, renderWithProviders } from "@/test-utils";
import { CallDetailDrawer } from "../CallDetailDrawer";

vi.mock("@/services/api", () => ({ callsApi: { updateNotes: vi.fn() } }));

test("renders nothing when no call is selected", () => {
  const { container } = renderWithProviders(<CallDetailDrawer call={null} onClose={() => {}} />);
  expect(container.querySelector("aside")).toBeNull();
});

test("renders the call's details, label and AI summary", () => {
  const call = makeCall({
    caller_name: "María García",
    phone_number: "+34 600 000 000",
    label: "Support",
    summary: "Caller asked about billing.",
    ended_at: "2026-01-01T00:05:00",
  });
  renderWithProviders(<CallDetailDrawer call={call} onClose={() => {}} />);

  expect(screen.getByText("Call Details")).toBeTruthy();
  expect(screen.getByText("María García")).toBeTruthy();
  expect(screen.getByText("+34 600 000 000")).toBeTruthy();
  expect(screen.getByText("Support")).toBeTruthy();
  expect(screen.getByText("AI Summary")).toBeTruthy();
  expect(screen.getByText("Caller asked about billing.")).toBeTruthy();
});

test("falls back to 'Unknown' for a missing caller name", () => {
  renderWithProviders(<CallDetailDrawer call={makeCall({ caller_name: null })} onClose={() => {}} />);
  expect(screen.getByText("Unknown")).toBeTruthy();
});

test("clicking the close button invokes onClose", () => {
  const onClose = vi.fn();
  renderWithProviders(<CallDetailDrawer call={makeCall()} onClose={onClose} />);
  fireEvent.click(screen.getAllByRole("button")[0]); // the header X
  expect(onClose).toHaveBeenCalled();
});
