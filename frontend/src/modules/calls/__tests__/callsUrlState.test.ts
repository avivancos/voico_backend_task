import { expect, test } from "vitest";

import type { CallLabel } from "@/types/calls";
import { buildCallsSearch, DEFAULT_SORT, parseCallsUrlState } from "../callsUrlState";

test("round-trips a fully populated query string", () => {
  const search =
    "?caller_name=García&phone=555&label=Support&min_duration=60&max_duration=300" +
    "&status=success&sort_by=duration_seconds&sort_dir=asc&page=2";
  const parsed = parseCallsUrlState(search);
  // Rebuild then re-parse — the state must survive the trip unchanged.
  expect(parseCallsUrlState(buildCallsSearch(parsed))).toEqual(parsed);
});

test("an empty query string yields defaults, and defaults serialize to an empty string", () => {
  expect(parseCallsUrlState("")).toEqual({
    filters: {},
    sort: DEFAULT_SORT,
    status: undefined,
    page: 1,
  });
  expect(buildCallsSearch({ filters: {}, sort: DEFAULT_SORT, page: 1 })).toBe("");
});

test("malformed / out-of-range values fall back to safe defaults (URL is untrusted)", () => {
  const p = parseCallsUrlState(
    "?min_duration=-5&max_duration=2.5&label=Nope&status=bogus" +
      "&sort_by=raw_transcript&sort_dir=sideways&page=0",
  );
  expect(p.filters.min_duration).toBeUndefined(); // negative rejected
  expect(p.filters.max_duration).toBeUndefined(); // non-integer rejected
  expect(p.filters.label).toBeUndefined(); // unknown label rejected
  expect(p.status).toBeUndefined(); // unknown status rejected
  expect(p.sort).toEqual(DEFAULT_SORT); // non-whitelisted sort field -> default
  expect(p.page).toBe(1); // page 0 -> 1
});

test("serializing preserves unrelated query params and rewrites owned keys from state", () => {
  const state = { filters: { label: "Support" as CallLabel }, sort: DEFAULT_SORT, page: 1 };
  const out = buildCallsSearch(state, "?token=abc&label=Other");
  const params = new URLSearchParams(out);
  expect(params.get("token")).toBe("abc"); // unrelated param survives
  expect(params.get("label")).toBe("Support"); // owned key reflects state, not the stale URL value
});
