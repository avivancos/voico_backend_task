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

test("renders the raw transcript when present", () => {
  const call = makeCall({
    raw_transcript: "Agent: How can I help?\nCaller: I need support.",
  });
  renderWithProviders(<CallDetailDrawer call={call} onClose={() => {}} />);

  expect(screen.getByText("Transcript")).toBeTruthy();
  expect(screen.getByText(/I need support\./)).toBeTruthy();
});

test("omits the AI summary and transcript sections when those fields are null", () => {
  renderWithProviders(
    <CallDetailDrawer call={makeCall({ summary: null, raw_transcript: null })} onClose={() => {}} />,
  );
  expect(screen.queryByText("AI Summary")).toBeNull();
  expect(screen.queryByText("Transcript")).toBeNull();
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

test("closing with unsaved note edits prompts and stays open when cancelled", () => {
  const onClose = vi.fn();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
  renderWithProviders(<CallDetailDrawer call={makeCall({ notes: null })} onClose={onClose} />);

  fireEvent.click(screen.getByText("Add a note…"));
  fireEvent.change(screen.getByLabelText("Call notes"), { target: { value: "work in progress" } });
  fireEvent.click(screen.getByLabelText("Close details"));

  expect(confirmSpy).toHaveBeenCalled();
  expect(onClose).not.toHaveBeenCalled(); // the user kept editing
  confirmSpy.mockRestore();
});

test("closing with unsaved note edits proceeds when confirmed", () => {
  const onClose = vi.fn();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderWithProviders(<CallDetailDrawer call={makeCall({ notes: null })} onClose={onClose} />);

  fireEvent.click(screen.getByText("Add a note…"));
  fireEvent.change(screen.getByLabelText("Call notes"), { target: { value: "work in progress" } });
  fireEvent.click(screen.getByLabelText("Close details"));

  expect(onClose).toHaveBeenCalled();
  confirmSpy.mockRestore();
});

test("closing without unsaved edits never prompts", () => {
  const onClose = vi.fn();
  const confirmSpy = vi.spyOn(window, "confirm");
  renderWithProviders(<CallDetailDrawer call={makeCall()} onClose={onClose} />);

  fireEvent.click(screen.getByLabelText("Close details"));

  expect(confirmSpy).not.toHaveBeenCalled();
  expect(onClose).toHaveBeenCalled();
  confirmSpy.mockRestore();
});
