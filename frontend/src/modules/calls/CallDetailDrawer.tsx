import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { format } from "date-fns";
import { X, Phone, User, Clock, Calendar, FileText, Sparkles, StickyNote, Pencil, Loader2 } from "lucide-react";
import { StatusBadge } from "./CallsTable";
import { callsApi } from "@/services/api";
import type { Call, PaginatedCallsResponse } from "@/types/calls";

interface CallDetailDrawerProps {
  call: Call | null;
  onClose: () => void;
}

function DetailRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-3 py-3 border-b border-border last:border-0">
      <div className="mt-0.5 text-muted-foreground">{icon}</div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <div className="text-sm font-medium text-foreground break-words">{value}</div>
      </div>
    </div>
  );
}

function formatDuration(seconds: number | null): string {
  if (seconds === null) return "Not available";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m} min ${s} sec` : `${s} sec`;
}

/**
 * Inline-editable notes. Saving updates the UI immediately (optimistic) and rolls back if the
 * request fails; the calls list cache is patched on success so the table stays in sync.
 */
export function NotesSection({ call }: { call: Call }) {
  const queryClient = useQueryClient();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(call.notes ?? "");
  const [displayNotes, setDisplayNotes] = useState<string | null>(call.notes);

  // When a different call is opened (or its note changes upstream), resync the editor.
  useEffect(() => {
    setDisplayNotes(call.notes);
    setDraft(call.notes ?? "");
    setIsEditing(false);
  }, [call.id, call.notes]);

  const mutation = useMutation({
    mutationFn: (notes: string) => callsApi.updateNotes(call.id, notes),
  });

  // Optimistic update with rollback, kept in the handler so the mutation's rejection is always
  // awaited and handled here (no lifecycle callbacks → no stray unhandled rejection in tests).
  async function save() {
    const previous = displayNotes;
    const optimistic = draft.trim() ? draft.trim() : null;
    setDisplayNotes(optimistic);
    setIsEditing(false);
    try {
      const updated = await mutation.mutateAsync(draft);
      setDisplayNotes(updated.notes);
      // Patch the list cache so the table reflects the change, then resync from the server.
      queryClient.setQueriesData<PaginatedCallsResponse>({ queryKey: ["calls"] }, (old) =>
        old ? { ...old, data: old.data.map((c) => (c.id === updated.id ? updated : c)) } : old,
      );
      queryClient.invalidateQueries({ queryKey: ["calls"] });
    } catch {
      setDisplayNotes(previous); // rollback
    }
  }

  function cancel() {
    setDraft(displayNotes ?? "");
    setIsEditing(false);
    mutation.reset();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      cancel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      save();
    }
  }

  return (
    <div className="px-6 py-4 border-t border-border">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <StickyNote className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Notes</h3>
        </div>
        {!isEditing && (
          <button
            type="button"
            onClick={() => setIsEditing(true)}
            aria-label="Edit notes"
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <Pencil className="h-3.5 w-3.5" />
          </button>
        )}
      </div>

      {isEditing ? (
        <div>
          <textarea
            aria-label="Call notes"
            autoFocus
            maxLength={2000}
            rows={4}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Add a note…"
            className="w-full rounded-md border border-border bg-white p-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-[#FDDF5C]"
          />
          <div className="mt-2 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={cancel}
              disabled={mutation.isPending}
              className="rounded-md px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={mutation.isPending}
              aria-label="Save notes"
              className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors disabled:opacity-60"
              style={{ backgroundColor: "#FDDF5C", color: "#4a3800" }}
            >
              {mutation.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
              Save
            </button>
          </div>
        </div>
      ) : displayNotes ? (
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          className="block w-full text-left text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap break-words rounded-md px-1 -mx-1 py-0.5 hover:bg-muted/50 transition-colors"
        >
          {displayNotes}
        </button>
      ) : (
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          className="text-sm italic text-muted-foreground/70 hover:text-foreground transition-colors"
        >
          Add a note…
        </button>
      )}

      {mutation.isError && (
        <p className="mt-2 text-xs text-red-500">Couldn’t save — your note was reverted.</p>
      )}
    </div>
  );
}

export function CallDetailDrawer({ call, onClose }: CallDetailDrawerProps) {
  if (!call) return null;

  return (
    <>
      <div
        className="fixed inset-0 bg-black/20 z-40 transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className="fixed right-0 top-0 h-full w-full max-w-md bg-white shadow-2xl z-50 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="text-base font-semibold text-foreground">Call Details</h2>
            <p className="text-xs text-muted-foreground font-mono mt-0.5">#{call.id.slice(0, 8)}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Status banner */}
        <div className="px-6 py-3 bg-muted/50 border-b border-border flex items-center justify-between">
          <StatusBadge status={call.status} />
          {call.label && (
            <span className="inline-flex items-center rounded-md px-2 py-1 text-xs font-medium border border-border bg-white text-foreground">
              {call.label}
            </span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          <DetailRow
            icon={<Phone className="h-4 w-4" />}
            label="Phone Number"
            value={<span className="font-mono">{call.phone_number}</span>}
          />
          <DetailRow
            icon={<User className="h-4 w-4" />}
            label="Caller Name"
            value={call.caller_name ?? "Unknown"}
          />
          <DetailRow
            icon={<Clock className="h-4 w-4" />}
            label="Duration"
            value={formatDuration(call.duration_seconds)}
          />
          <DetailRow
            icon={<Calendar className="h-4 w-4" />}
            label="Started At"
            value={format(new Date(call.started_at), "PPpp")}
          />
          {call.ended_at && (
            <DetailRow
              icon={<Calendar className="h-4 w-4" />}
              label="Ended At"
              value={format(new Date(call.ended_at), "PPpp")}
            />
          )}
        </div>

        <NotesSection call={call} />

        {/* AI Summary */}
        {call.summary && (
          <div className="px-6 py-4 border-t border-border">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="h-4 w-4" style={{ color: "#FDDF5C" }} />
              <h3 className="text-sm font-semibold text-foreground">AI Summary</h3>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{call.summary}</p>
          </div>
        )}

        {/* Transcript */}
        {call.raw_transcript && (
          <div className="px-6 py-4 border-t border-border">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">Transcript</h3>
            </div>
            <div className="bg-muted rounded-lg p-3 max-h-48 overflow-y-auto">
              <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                {call.raw_transcript}
              </pre>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="px-6 py-3 border-t border-border bg-muted/30">
          <p className="text-xs text-muted-foreground">
            Created {format(new Date(call.created_at), "PPpp")}
          </p>
        </div>
      </aside>
    </>
  );
}
