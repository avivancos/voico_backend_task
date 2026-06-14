import { expect, test } from "vitest";

import { callsApi } from "@/services/api";

// No vi.mock here: the REAL api.ts (axios instance, the VITE_API_URL base, param serialization,
// response parsing) runs against MSW — only the network boundary is faked.

test("list() composes the base URL and serializes every filter/sort/page param", async () => {
  const res = await callsApi.list({
    status: "success",
    caller_name: "García",
    phone: "555",
    label: "Sales inquiry",
    min_duration: 60,
    max_duration: 300,
    sort_by: "duration_seconds",
    sort_dir: "asc",
    page: 2,
    page_size: 10,
  });

  // The handler echoes the query string axios actually sent.
  expect((res as unknown as { _received: Record<string, string> })._received).toEqual({
    status: "success",
    caller_name: "García",
    phone: "555",
    label: "Sales inquiry",
    min_duration: "60",
    max_duration: "300",
    sort_by: "duration_seconds",
    sort_dir: "asc",
    page: "2",
    page_size: "10",
  });
  // And the typed response is parsed through.
  expect(res.counts).toEqual({ in_progress: 0, success: 0, failed: 0 });
  expect(res.page).toBe(2);
});

test("list() omits undefined params from the query string", async () => {
  const res = await callsApi.list({ status: "failed", page: 1, page_size: 20 });
  const received = (res as unknown as { _received: Record<string, string> })._received;
  expect(received).toEqual({ status: "failed", page: "1", page_size: "20" });
  expect("caller_name" in received).toBe(false);
});

test("updateNotes() PATCHes /calls/:id/notes with a {notes} body and parses the Call back", async () => {
  const updated = await callsApi.updateNotes("abc-123", "call back Monday");
  expect(updated.id).toBe("abc-123");
  expect(updated.notes).toBe("call back Monday");
});

test("getById() fetches /calls/:id and parses the Call", async () => {
  const call = await callsApi.getById("call-42");
  expect(call.id).toBe("call-42");
  expect(call.status).toBe("success");
});
