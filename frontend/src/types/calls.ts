export type CallStatus = "in_progress" | "success" | "failed";

// Label values are the public API contract (the enum *value*, e.g. "Sales inquiry"), which is also
// exactly what the API returns on each row — so a row's `label` round-trips as a filter unchanged.
export const CALL_LABELS = [
  "Sales inquiry",
  "Support",
  "Complaint",
  "Appointment",
  "Follow-up",
  "Other",
] as const;
export type CallLabel = (typeof CALL_LABELS)[number];

// Whitelisted sort fields — mirrors the backend CallSortField enum.
export const CALL_SORT_FIELDS = [
  "created_at",
  "started_at",
  "duration_seconds",
  "caller_name",
  "phone_number",
  "status",
  "label",
] as const;
export type CallSortField = (typeof CALL_SORT_FIELDS)[number];

export type SortDir = "asc" | "desc";

export interface Call {
  id: string;
  phone_number: string;
  caller_name: string | null;
  duration_seconds: number | null;
  status: CallStatus;
  summary: string | null;
  label: string | null;
  started_at: string;
  ended_at: string | null;
  created_at: string;
  updated_at: string;
  raw_transcript: string | null;
  notes: string | null;
}

export interface CallCounts {
  in_progress: number;
  success: number;
  failed: number;
}

export interface PaginatedCallsResponse {
  data: Call[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  counts: CallCounts;
}

export interface CallsQueryParams {
  status?: CallStatus;
  caller_name?: string;
  phone?: string;
  label?: CallLabel;
  min_duration?: number;
  max_duration?: number;
  sort_by?: CallSortField;
  sort_dir?: SortDir;
  page?: number;
  page_size?: number;
}

// The content filters surfaced in the filter bar (status lives in the tabs, sort in the headers).
export interface CallsFilters {
  caller_name?: string;
  phone?: string;
  label?: CallLabel;
  min_duration?: number;
  max_duration?: number;
}

export interface CallsSort {
  sort_by: CallSortField;
  sort_dir: SortDir;
}
