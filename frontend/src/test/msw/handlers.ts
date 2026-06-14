import { http, HttpResponse } from "msw";

// api.ts composes `${VITE_API_URL ?? "http://localhost:8000"}/api`; tests have no VITE_API_URL.
const BASE = "http://localhost:8000/api";

export const handlers = [
  // Echo the received query params back so a test can prove axios serialized them correctly, plus a
  // canned (empty) page so the response shape is real.
  http.get(`${BASE}/calls`, ({ request }) => {
    const params = Object.fromEntries(new URL(request.url).searchParams.entries());
    return HttpResponse.json({
      data: [],
      total: 0,
      page: Number(params.page ?? 1),
      page_size: Number(params.page_size ?? 20),
      total_pages: 1,
      counts: { in_progress: 0, success: 0, failed: 0 },
      _received: params, // test-only echo of the serialized query string
    });
  }),

  http.get(`${BASE}/calls/:id`, ({ params }) => {
    return HttpResponse.json({
      id: params.id,
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
    });
  }),

  http.patch(`${BASE}/calls/:id/notes`, async ({ request, params }) => {
    const body = (await request.json()) as { notes: string | null };
    return HttpResponse.json({
      id: params.id,
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
      notes: body.notes,
    });
  }),
];
