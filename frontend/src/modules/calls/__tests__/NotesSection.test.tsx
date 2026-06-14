import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { callsApi } from "@/services/api";
import type { Call } from "@/types/calls";
import { NotesSection } from "../CallDetailDrawer";

vi.mock("@/services/api", () => ({
  callsApi: { updateNotes: vi.fn() },
}));

const updateNotes = vi.mocked(callsApi.updateNotes);

function makeCall(overrides: Partial<Call> = {}): Call {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    phone_number: "+1 (555) 000-0000",
    caller_name: "Sarah",
    duration_seconds: 60,
    status: "success",
    summary: null,
    label: null,
    started_at: "2026-01-01T00:00:00",
    ended_at: null,
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
    raw_transcript: null,
    notes: null,
    ...overrides,
  };
}

function renderSection(call: Call) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotesSection call={call} />
    </QueryClientProvider>,
  );
}

// NOTE: no `beforeEach(mockReset)` — it interacts badly with vitest 2.1.9's per-test
// unhandled-rejection tracking and would falsely fail the rollback test. Each test sets its own
// mock implementation, and assertions are keyed to distinct values, so a reset isn't needed.
afterEach(() => cleanup());

test("optimistically shows the new note and calls the API with the typed value", async () => {
  const call = makeCall({ notes: null });
  updateNotes.mockResolvedValue(makeCall({ notes: "Call back Monday" }));
  renderSection(call);

  fireEvent.click(screen.getByLabelText("Edit notes"));
  fireEvent.change(screen.getByLabelText("Call notes"), {
    target: { value: "Call back Monday" },
  });
  fireEvent.click(screen.getByLabelText("Save notes"));

  // Called with what the user typed; the new value is shown without waiting for a refetch.
  await waitFor(() => expect(updateNotes).toHaveBeenCalledWith(call.id, "Call back Monday"));
  await waitFor(() => expect(screen.getByText("Call back Monday")).toBeDefined());
});

test("rolls back to the previous note when the save fails", async () => {
  const call = makeCall({ notes: "Original note" });
  // A deferred promise we control and explicitly observe, so the rejection is never "unhandled".
  let rejectUpdate!: (error: Error) => void;
  const pending = new Promise<Call>((_resolve, reject) => {
    rejectUpdate = reject;
  });
  updateNotes.mockReturnValue(pending);
  renderSection(call);

  fireEvent.click(screen.getByLabelText("Edit notes"));
  fireEvent.change(screen.getByLabelText("Call notes"), {
    target: { value: "Broken update" },
  });
  fireEvent.click(screen.getByLabelText("Save notes"));

  // While the request is in flight, the optimistic value is shown.
  await waitFor(() => expect(screen.getByText("Broken update")).toBeDefined());

  // Fail the request; observe the rejection here too so it is fully handled.
  rejectUpdate(new Error("network down"));
  await pending.catch(() => {});

  await waitFor(() => expect(screen.getByText(/Couldn.t save/i)).toBeDefined());
  // The displayed note reverted to the original; the failed value was not committed.
  expect(screen.getByText("Original note")).toBeDefined();
  expect(screen.queryByText("Broken update")).toBeNull();
});

test("Cancel discards an unsaved edit and never calls the API", async () => {
  updateNotes.mockClear();
  const call = makeCall({ notes: "Original note" });
  renderSection(call);

  fireEvent.click(screen.getByLabelText("Edit notes"));
  fireEvent.change(screen.getByLabelText("Call notes"), { target: { value: "scratch text" } });
  fireEvent.click(screen.getByText("Cancel"));

  // Back to read mode showing the original; the scratch edit and the API call are discarded.
  expect(screen.getByText("Original note")).toBeDefined();
  expect(screen.queryByLabelText("Call notes")).toBeNull();
  expect(updateNotes).not.toHaveBeenCalled();
});

test("Esc discards the edit and restores the original note", async () => {
  updateNotes.mockClear();
  const call = makeCall({ notes: "Original note" });
  renderSection(call);

  fireEvent.click(screen.getByLabelText("Edit notes"));
  const textarea = screen.getByLabelText("Call notes");
  fireEvent.change(textarea, { target: { value: "scratch text" } });
  fireEvent.keyDown(textarea, { key: "Escape" });

  expect(screen.getByText("Original note")).toBeDefined();
  expect(screen.queryByLabelText("Call notes")).toBeNull();
  expect(updateNotes).not.toHaveBeenCalled();
});

test("Cmd/Ctrl+Enter saves the raw draft via the endpoint", async () => {
  updateNotes.mockClear();
  const call = makeCall({ notes: null });
  updateNotes.mockResolvedValue(makeCall({ notes: "via keyboard" }));
  renderSection(call);

  fireEvent.click(screen.getByLabelText("Edit notes"));
  const textarea = screen.getByLabelText("Call notes");
  fireEvent.change(textarea, { target: { value: "  via keyboard  " } });
  fireEvent.keyDown(textarea, { key: "Enter", ctrlKey: true });

  // We send the raw draft (the server normalizes) — pin that the client does not pre-trim.
  await waitFor(() => expect(updateNotes).toHaveBeenCalledWith(call.id, "  via keyboard  "));
});

test("renders a note as inert text, not executable HTML (XSS-at-render)", () => {
  const xss = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
  const { container } = renderSection(makeCall({ notes: xss }));

  // React escapes interpolated text: the payload shows as literal text, with no live element.
  expect(container.textContent).toContain(xss);
  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("script")).toBeNull();
});
