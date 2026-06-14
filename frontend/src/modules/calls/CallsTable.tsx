import { format } from "date-fns";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Phone,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Call, CallSortField, CallStatus, CallsSort } from "@/types/calls";

interface StatusBadgeProps {
  status: CallStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  if (status === "in_progress") {
    return (
      <Badge variant="in_progress">
        <Loader2 className="h-3 w-3 animate-spin" />
        In Progress
      </Badge>
    );
  }
  if (status === "success") {
    return (
      <Badge variant="success">
        <CheckCircle2 className="h-3 w-3" />
        Success
      </Badge>
    );
  }
  return (
    <Badge variant="failed">
      <XCircle className="h-3 w-3" />
      Failed
    </Badge>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

const SORTABLE_COLUMNS: { label: string; field: CallSortField }[] = [
  { label: "Phone", field: "phone_number" },
  { label: "Caller", field: "caller_name" },
  { label: "Status", field: "status" },
  { label: "Label", field: "label" },
  { label: "Duration", field: "duration_seconds" },
  { label: "Started At", field: "started_at" },
];

interface SortableHeaderProps {
  label: string;
  field: CallSortField;
  sort?: CallsSort;
  onSortChange?: (field: CallSortField) => void;
}

function SortableHeader({ label, field, sort, onSortChange }: SortableHeaderProps) {
  const active = sort?.sort_by === field;
  const ariaSort = !active ? "none" : sort?.sort_dir === "asc" ? "ascending" : "descending";

  if (!onSortChange) {
    return (
      <th className="text-left py-3 px-4 text-xs font-medium text-muted-foreground">{label}</th>
    );
  }

  return (
    <th aria-sort={ariaSort} className="text-left py-3 px-4">
      <button
        type="button"
        onClick={() => onSortChange(field)}
        className={`inline-flex items-center gap-1 text-xs font-medium transition-colors ${
          active ? "text-foreground" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {label}
        {!active ? (
          <ChevronsUpDown className="h-3 w-3 opacity-40" aria-hidden="true" />
        ) : sort?.sort_dir === "asc" ? (
          <ChevronUp className="h-3 w-3" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-3 w-3" aria-hidden="true" />
        )}
      </button>
    </th>
  );
}

interface CallsTableProps {
  calls: Call[];
  onRowClick: (call: Call) => void;
  sort?: CallsSort;
  onSortChange?: (field: CallSortField) => void;
}

export function CallsTable({ calls, onRowClick, sort, onSortChange }: CallsTableProps) {
  const COLUMN_COUNT = SORTABLE_COLUMNS.length + 1; // sortable columns + the chevron column

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {SORTABLE_COLUMNS.map((col) => (
              <SortableHeader
                key={col.field}
                label={col.label}
                field={col.field}
                sort={sort}
                onSortChange={onSortChange}
              />
            ))}
            <th className="py-3 px-4" />
          </tr>
        </thead>
        {calls.length === 0 ? (
          // Keep the headers (and their sort controls) mounted on an empty result set.
          <tbody>
            <tr>
              <td colSpan={COLUMN_COUNT}>
                <div className="flex flex-col items-center justify-center py-20 text-center">
                  <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-4">
                    <Phone className="h-7 w-7 text-muted-foreground" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-1">No calls found</h3>
                  <p className="text-sm text-muted-foreground max-w-xs">
                    No calls match your current filters. Try adjusting them or run the seed script to
                    generate test data.
                  </p>
                </div>
              </td>
            </tr>
          </tbody>
        ) : (
        <tbody className="divide-y divide-border">
          {calls.map((call) => (
            <tr
              key={call.id}
              onClick={() => onRowClick(call)}
              className="group hover:bg-muted/50 transition-colors cursor-pointer"
            >
              <td className="py-3 px-4 font-mono text-xs text-foreground">{call.phone_number}</td>
              <td className="py-3 px-4 text-foreground">{call.caller_name ?? "—"}</td>
              <td className="py-3 px-4">
                <StatusBadge status={call.status} />
              </td>
              <td className="py-3 px-4">
                {call.label ? (
                  <span className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium border border-border bg-muted text-foreground">
                    {call.label}
                  </span>
                ) : (
                  <span className="text-muted-foreground text-xs">—</span>
                )}
              </td>
              <td className="py-3 px-4 tabular-nums text-muted-foreground">
                {formatDuration(call.duration_seconds)}
              </td>
              <td className="py-3 px-4 tabular-nums text-muted-foreground">
                {format(new Date(call.started_at), "MMM d, HH:mm:ss")}
              </td>
              <td className="py-3 px-4">
                <ChevronRight className="h-4 w-4 text-muted-foreground group-hover:text-foreground transition-colors" />
              </td>
            </tr>
          ))}
        </tbody>
        )}
      </table>
    </div>
  );
}
