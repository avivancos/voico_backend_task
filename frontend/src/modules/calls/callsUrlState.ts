import {
  CALL_LABELS,
  CALL_SORT_FIELDS,
  type CallLabel,
  type CallSortField,
  type CallStatus,
  type CallsFilters,
  type CallsSort,
} from "@/types/calls";

export interface CallsUrlState {
  filters: CallsFilters;
  sort: CallsSort;
  status?: CallStatus;
  page: number;
}

export const DEFAULT_SORT: CallsSort = { sort_by: "created_at", sort_dir: "desc" };

const STATUSES: CallStatus[] = ["in_progress", "success", "failed"];

function parsePositiveInt(raw: string | null): number | undefined {
  if (raw === null || raw.trim() === "") return undefined;
  const n = Number(raw);
  return Number.isInteger(n) && n >= 0 ? n : undefined;
}

/** Parse the URL query string into the dashboard's filter/sort/status/page state. Unknown or
 * malformed values fall back to defaults rather than throwing — the URL is untrusted input. */
export function parseCallsUrlState(search: string): CallsUrlState {
  const p = new URLSearchParams(search);

  const filters: CallsFilters = {};
  const caller = p.get("caller_name")?.trim();
  if (caller) filters.caller_name = caller;
  const phone = p.get("phone")?.trim();
  if (phone) filters.phone = phone;
  const label = p.get("label");
  if (label && (CALL_LABELS as readonly string[]).includes(label)) {
    filters.label = label as CallLabel;
  }
  const min = parsePositiveInt(p.get("min_duration"));
  if (min !== undefined) filters.min_duration = min;
  const max = parsePositiveInt(p.get("max_duration"));
  if (max !== undefined) filters.max_duration = max;

  const sortBy = p.get("sort_by");
  const sortDir = p.get("sort_dir");
  const sort: CallsSort = {
    sort_by: (CALL_SORT_FIELDS as readonly string[]).includes(sortBy ?? "")
      ? (sortBy as CallSortField)
      : DEFAULT_SORT.sort_by,
    sort_dir: sortDir === "asc" ? "asc" : "desc",
  };

  const statusRaw = p.get("status");
  const status = STATUSES.includes(statusRaw as CallStatus)
    ? (statusRaw as CallStatus)
    : undefined;

  const page = parsePositiveInt(p.get("page"));

  return { filters, sort, status, page: page && page >= 1 ? page : 1 };
}

// Query params this view owns. Anything else in the URL is preserved untouched.
const OWNED_KEYS = [
  "caller_name",
  "phone",
  "label",
  "min_duration",
  "max_duration",
  "status",
  "sort_by",
  "sort_dir",
  "page",
];

/** Serialize state back to a query string, omitting defaults so shared URLs stay clean. Merges onto
 * `baseSearch` so unrelated query params are preserved; only the keys this view owns are rewritten. */
export function buildCallsSearch(state: CallsUrlState, baseSearch = ""): string {
  const p = new URLSearchParams(baseSearch);
  OWNED_KEYS.forEach((k) => p.delete(k));
  if (state.filters.caller_name) p.set("caller_name", state.filters.caller_name);
  if (state.filters.phone) p.set("phone", state.filters.phone);
  if (state.filters.label) p.set("label", state.filters.label);
  if (state.filters.min_duration !== undefined) {
    p.set("min_duration", String(state.filters.min_duration));
  }
  if (state.filters.max_duration !== undefined) {
    p.set("max_duration", String(state.filters.max_duration));
  }
  if (state.status) p.set("status", state.status);
  if (state.sort.sort_by !== DEFAULT_SORT.sort_by || state.sort.sort_dir !== DEFAULT_SORT.sort_dir) {
    p.set("sort_by", state.sort.sort_by);
    p.set("sort_dir", state.sort.sort_dir);
  }
  if (state.page > 1) p.set("page", String(state.page));

  const qs = p.toString();
  return qs ? `?${qs}` : "";
}
