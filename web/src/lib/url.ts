import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";

/**
 * One piece of page state kept in the query string (Vercel guidelines: the URL reflects state),
 * so a selected unit, prospect or player survives a reload and can be shared as a link.
 * Updates replace the history entry, so Back still leaves the page instead of undoing clicks.
 */
export function useUrlParam(key: string): [string | null, (value: string | null) => void] {
  const [params, setParams] = useSearchParams();
  const value = params.get(key);
  const set = useCallback(
    (next: string | null) =>
      setParams(
        (cur) => {
          const p = new URLSearchParams(cur);
          if (next == null || next === "") p.delete(key);
          else p.set(key, next);
          return p;
        },
        { replace: true },
      ),
    [key, setParams],
  );
  return [value, set];
}
