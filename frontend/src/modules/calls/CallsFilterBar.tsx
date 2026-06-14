import { useLayoutEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { CALL_LABELS, type CallLabel, type CallsFilters } from "@/types/calls";

interface CallsFilterBarProps {
  filters: CallsFilters;
  onChange: (next: CallsFilters) => void;
}

const INPUT_CLASS =
  "h-9 rounded-md border border-border bg-white px-3 text-sm text-foreground " +
  "placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-[#FDDF5C]";

/** Set a key to a value, or drop it entirely when the value is empty/undefined, so we never send
 * an empty string to the API (which would otherwise be a no-op filter that clutters the URL). */
function withFilter<K extends keyof CallsFilters>(
  filters: CallsFilters,
  key: K,
  value: CallsFilters[K] | undefined,
): CallsFilters {
  const next = { ...filters };
  if (value === undefined || value === "") delete next[key];
  else next[key] = value;
  return next;
}

/** Coerce a duration field to a non-negative integer; reject negatives, decimals, and junk so they
 * never reach the API (which would 422 on a negative bound or a non-integer). */
function parseDuration(raw: string): number | undefined {
  if (raw.trim() === "") return undefined;
  const n = Math.floor(Number(raw));
  return Number.isFinite(n) && n >= 0 ? n : undefined;
}

const CHIP_LABELS: Record<keyof CallsFilters, string> = {
  caller_name: "Caller name",
  phone: "Phone",
  label: "Label",
  min_duration: "Min duration",
  max_duration: "Max duration",
};

function chipText(key: keyof CallsFilters, value: string | number): string {
  if (key === "min_duration") return `≥ ${value}s`;
  if (key === "max_duration") return `≤ ${value}s`;
  if (key === "caller_name") return `Name: ${value}`;
  if (key === "phone") return `Phone: ${value}`;
  if (key === "label") return `Label: ${value}`;
  return String(value);
}

export function CallsFilterBar({ filters, onChange }: CallsFilterBarProps) {
  const callerRef = useRef<HTMLInputElement>(null);
  const clearAllRef = useRef<HTMLButtonElement>(null);
  const pendingFocus = useRef(false);
  const [announcement, setAnnouncement] = useState("");

  const activeKeys = (Object.keys(filters) as (keyof CallsFilters)[]).filter(
    (k) => filters[k] !== undefined && filters[k] !== "",
  );

  // After a chip is removed its button unmounts; move focus to a stable anchor (the "Clear all"
  // button if any chips remain, otherwise the first filter input) so keyboard users aren't dropped
  // to the top of the document.
  useLayoutEffect(() => {
    if (!pendingFocus.current) return;
    pendingFocus.current = false;
    (clearAllRef.current ?? callerRef.current)?.focus();
  }, [filters]);

  function removeFilter(key: keyof CallsFilters) {
    pendingFocus.current = true;
    setAnnouncement(`${CHIP_LABELS[key]} filter removed`);
    onChange(withFilter(filters, key, undefined));
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <input
          ref={callerRef}
          type="text"
          aria-label="Filter by caller name"
          placeholder="Caller name"
          value={filters.caller_name ?? ""}
          onChange={(e) => onChange(withFilter(filters, "caller_name", e.target.value))}
          className={`${INPUT_CLASS} w-40`}
        />
        <input
          type="text"
          inputMode="tel"
          aria-label="Filter by phone"
          placeholder="Phone"
          value={filters.phone ?? ""}
          onChange={(e) => onChange(withFilter(filters, "phone", e.target.value))}
          className={`${INPUT_CLASS} w-36`}
        />
        <select
          aria-label="Filter by label"
          value={filters.label ?? ""}
          onChange={(e) =>
            onChange(withFilter(filters, "label", (e.target.value || undefined) as CallLabel))
          }
          className={`${INPUT_CLASS} w-40`}
        >
          <option value="">All labels</option>
          {CALL_LABELS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        <input
          type="number"
          min={0}
          step={1}
          aria-label="Min duration (seconds)"
          placeholder="Min sec"
          value={filters.min_duration ?? ""}
          onChange={(e) => onChange(withFilter(filters, "min_duration", parseDuration(e.target.value)))}
          className={`${INPUT_CLASS} w-24`}
        />
        <input
          type="number"
          min={0}
          step={1}
          aria-label="Max duration (seconds)"
          placeholder="Max sec"
          value={filters.max_duration ?? ""}
          onChange={(e) => onChange(withFilter(filters, "max_duration", parseDuration(e.target.value)))}
          className={`${INPUT_CLASS} w-24`}
        />
      </div>

      {activeKeys.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          {activeKeys.map((key) => (
            <span
              key={key}
              className="inline-flex items-center gap-1 rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground"
            >
              {chipText(key, filters[key] as string | number)}
              <button
                type="button"
                aria-label={`Remove ${CHIP_LABELS[key]} filter`}
                onClick={() => removeFilter(key)}
                className="rounded-full p-0.5 text-muted-foreground hover:bg-black/10 hover:text-foreground"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <button
            ref={clearAllRef}
            type="button"
            onClick={() => onChange({})}
            className="text-xs font-medium text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          >
            Clear all
          </button>
        </div>
      )}

      <span role="status" aria-live="polite" className="sr-only">
        {announcement}
      </span>
    </div>
  );
}
