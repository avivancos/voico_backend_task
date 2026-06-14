import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";

import type { Call, PaginatedCallsResponse } from "@/types/calls";

/** Canonical Call factory for tests — one source of truth (replaces the per-file copies). */
export function makeCall(overrides: Partial<Call> = {}): Call {
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

/** Build a paginated response with counts derived from the rows. */
export function pageOf(
  calls: Call[] = [],
  overrides: Partial<PaginatedCallsResponse> = {},
): PaginatedCallsResponse {
  const counts = { in_progress: 0, success: 0, failed: 0 };
  for (const c of calls) counts[c.status] += 1;
  return {
    data: calls,
    total: calls.length,
    page: 1,
    page_size: 20,
    total_pages: 1,
    counts,
    ...overrides,
  };
}

/** Render under a fresh QueryClient (retries off, no cache carry-over between tests). */
export function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  };
}
