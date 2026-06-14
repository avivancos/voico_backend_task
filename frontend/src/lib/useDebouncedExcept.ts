import { useEffect, useRef, useState } from "react";

/**
 * Debounce changes to `value`, EXCEPT when a key outside `debounceKeys` changes — those
 * "structural" changes commit immediately and flush any pending text change along with them.
 *
 * This keeps text typing debounced (one request per pause) while sort / pagination / tab clicks stay
 * instant, and crucially avoids the stale-filter race: a structural change never issues a request
 * that carries the new structure but the old, not-yet-debounced text.
 *
 * `value` MUST be referentially stable when its contents are unchanged (memoize it), and
 * `debounceKeys` must be a stable reference (define it at module scope).
 */
export function useDebouncedExcept<T extends object>(
  value: T,
  debounceKeys: readonly (keyof T)[],
  delayMs: number,
): T {
  const [committed, setCommitted] = useState(value);
  const committedRef = useRef(committed);
  committedRef.current = committed;

  useEffect(() => {
    const prev = committedRef.current;
    if (Object.is(prev, value)) return;

    const structuralChanged = (Object.keys(value) as (keyof T)[]).some(
      (key) => !debounceKeys.includes(key) && !Object.is(prev[key], value[key]),
    );
    if (structuralChanged) {
      setCommitted(value); // apply now, with the latest text in tow
      return;
    }

    const handle = setTimeout(() => setCommitted(value), delayMs);
    return () => clearTimeout(handle);
  }, [value, debounceKeys, delayMs]);

  return committed;
}
