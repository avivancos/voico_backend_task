import { useEffect, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { RefreshCw, Phone } from "lucide-react";
import { callsApi } from "@/services/api";
import type {
  Call,
  CallSortField,
  CallStatus,
  CallsFilters,
  CallsQueryParams,
} from "@/types/calls";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useDebouncedExcept } from "@/lib/useDebouncedExcept";
import { CallsTable } from "./CallsTable";
import { CallsFilterBar } from "./CallsFilterBar";
import { CallDetailDrawer } from "./CallDetailDrawer";
import { buildCallsSearch, parseCallsUrlState, type CallsUrlState } from "./callsUrlState";

type TabValue = "all" | CallStatus;

const TABS: { label: string; value: TabValue }[] = [
  { label: "All", value: "all" },
  { label: "In Progress", value: "in_progress" },
  { label: "Success", value: "success" },
  { label: "Failed", value: "failed" },
];

const PAGE_SIZE = 20;

// Only the free-text inputs are debounced; sort/status/page/label/duration apply immediately.
const DEBOUNCE_KEYS = ["caller_name", "phone"] as const;

export function CallsPage() {
  const [state, setState] = useState<CallsUrlState>(() =>
    parseCallsUrlState(window.location.search),
  );
  const [selectedCall, setSelectedCall] = useState<Call | null>(null);
  const { filters, sort, status, page } = state;

  // The URL is the single source of truth: reflect every state change so the view is shareable
  // and survives reload/back. We merge onto the existing query string so unrelated params and the
  // hash fragment are preserved, not clobbered.
  useEffect(() => {
    const search = buildCallsSearch(state, window.location.search);
    const url = `${window.location.pathname}${search}${window.location.hash}`;
    window.history.replaceState(window.history.state, "", url);
  }, [state]);

  // Stable identity so the debounce effect only fires on real value changes.
  const queryParams = useMemo<CallsQueryParams>(
    () => ({
      status,
      caller_name: filters.caller_name,
      phone: filters.phone,
      label: filters.label,
      min_duration: filters.min_duration,
      max_duration: filters.max_duration,
      sort_by: sort.sort_by,
      sort_dir: sort.sort_dir,
      page,
      page_size: PAGE_SIZE,
    }),
    [status, filters, sort, page],
  );
  const debouncedParams = useDebouncedExcept(queryParams, DEBOUNCE_KEYS, 300);

  // An inverted range (min > max) is the one filter combination the API rejects with 422. Guard it
  // client-side so a normal typo never triggers the full-page error state — show an inline hint and
  // keep the current results until the range is valid again.
  const invalidRange =
    filters.min_duration != null &&
    filters.max_duration != null &&
    filters.min_duration > filters.max_duration;

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ["calls", debouncedParams],
    queryFn: () => callsApi.list(debouncedParams),
    refetchInterval: 5000,
    enabled: !invalidRange,
    // Keep showing the current rows while a new filter/sort/page loads — no spinner flash.
    placeholderData: keepPreviousData,
  });

  function handleTabChange(tab: TabValue) {
    setState((s) => ({ ...s, status: tab === "all" ? undefined : tab, page: 1 }));
  }

  function handleFiltersChange(next: CallsFilters) {
    setState((s) => ({ ...s, filters: next, page: 1 }));
  }

  function handleSort(field: CallSortField) {
    setState((s) => {
      const sort_dir =
        s.sort.sort_by === field && s.sort.sort_dir === "asc" ? "desc" : "asc";
      return { ...s, sort: { sort_by: field, sort_dir }, page: 1 };
    });
  }

  function gotoPage(next: number) {
    setState((s) => ({ ...s, page: next }));
  }

  const activeTab: TabValue = status ?? "all";

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-white border-b-2 shadow-sm" style={{ borderBottomColor: "#FDDF5C" }}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-3">
              <div
                className="w-9 h-9 rounded-xl flex items-center justify-center font-bold text-base shadow"
                style={{ backgroundColor: "#FDDF5C" }}
              >
                <span style={{ color: "#7A6000" }}>V</span>
              </div>
              <span className="font-bold text-xl tracking-tight text-gray-900">VOICO</span>
              <span className="hidden sm:block text-sm text-gray-400 font-normal pl-3 border-l border-gray-200">
                Calls Dashboard
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-gray-500">
                <span
                  className={`inline-block w-2 h-2 rounded-full ${isFetching ? "animate-pulse" : ""}`}
                  style={{ backgroundColor: isFetching ? "#FDDF5C" : "#86efac" }}
                />
                {isFetching ? "Syncing..." : "Live"}
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-gray-400 hover:text-gray-700"
                onClick={() => refetch()}
              >
                <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats row */}
        {data && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
            {[
              { label: "Total Calls", value: data.total },
              { label: "In Progress", value: data.counts?.in_progress ?? "—" },
              { label: "Successful", value: data.counts?.success ?? "—" },
              { label: "Failed", value: data.counts?.failed ?? "—" },
            ].map((stat) => (
              <div key={stat.label} className="rounded-xl border border-border bg-white p-4 shadow-sm">
                <p className="text-xs text-muted-foreground mb-1 font-medium">{stat.label}</p>
                <p className="text-2xl font-bold text-foreground">{stat.value}</p>
              </div>
            ))}
          </div>
        )}

        <Card className="bg-white">
          <div className="flex flex-col gap-4 px-6 pt-5 pb-4 border-b border-border">
            <div className="flex items-center">
              <div className="flex gap-1 bg-muted rounded-lg p-1 w-fit">
                {TABS.map((tab) => (
                  <button
                    key={tab.value}
                    onClick={() => handleTabChange(tab.value)}
                    className="px-3 py-1.5 rounded-md text-sm font-medium transition-all"
                    style={
                      activeTab === tab.value
                        ? { backgroundColor: "#FDDF5C", color: "#4a3800", boxShadow: "0 1px 3px rgba(0,0,0,0.10)" }
                        : { color: "var(--muted-foreground)" }
                    }
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
            <CallsFilterBar filters={filters} onChange={handleFiltersChange} />
            {invalidRange && (
              <p role="alert" className="text-xs font-medium text-red-600">
                Min duration can’t be greater than max duration.
              </p>
            )}
          </div>

          <CardContent className="p-0">
            {isError ? (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-3">
                  <Phone className="h-5 w-5 text-red-500" />
                </div>
                <p className="text-sm font-medium text-foreground">Failed to load calls</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Make sure the backend is running at localhost:8000
                </p>
                <Button variant="outline" size="sm" onClick={() => refetch()} className="mt-3">
                  Retry
                </Button>
              </div>
            ) : isLoading ? (
              <div className="flex items-center justify-center py-20">
                <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <CallsTable
                calls={data?.data ?? []}
                onRowClick={setSelectedCall}
                sort={sort}
                onSortChange={handleSort}
              />
            )}
          </CardContent>

          {/* Pagination */}
          {data && data.total_pages > 1 && (
            <div className="flex items-center justify-between px-6 py-4 border-t border-border">
              <p className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}{" "}
                <span className="opacity-60">({data.total} total)</span>
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => gotoPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => gotoPage(Math.min(data.total_pages, page + 1))}
                  disabled={page === data.total_pages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>

      <CallDetailDrawer call={selectedCall} onClose={() => setSelectedCall(null)} />
    </div>
  );
}
