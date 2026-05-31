import { useCallback, useEffect, useRef, useState } from "react";

const REQUEST_TIMEOUT_MS = 60_000; // Render free tier cold start can take ~50s
const SLOW_AFTER_MS = 3_000; // show a "waking up" hint after this

export function buildUrl(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (Array.isArray(v)) {
      v.forEach((x) => x != null && x !== "" && url.searchParams.append(k, x));
    } else if (v !== "" && v !== null && v !== undefined) {
      url.searchParams.set(k, v);
    }
  });
  return url.toString();
}

/**
 * Data fetching hook with three properties the old version lacked:
 *  - AbortController per request: stale responses (rapid filter/keystroke/page
 *    changes) are cancelled, so the UI never shows data that doesn't match the
 *    current params, and there's no setState-after-unmount.
 *  - Timeout: a hung request aborts instead of spinning forever.
 *  - `slow` flag: true once a request has been pending past SLOW_AFTER_MS, so
 *    callers can surface a cold-start message.
 */
export function useApi(path, params = {}, deps = []) {
  const [state, setState] = useState({
    data: null,
    loading: true,
    error: null,
    slow: false,
  });
  const [nonce, setNonce] = useState(0);
  const key = JSON.stringify(params);

  useEffect(() => {
    const ac = new AbortController();
    let alive = true;
    setState((s) => ({ ...s, loading: true, error: null, slow: false }));

    const slowTimer = setTimeout(() => {
      if (alive) setState((s) => ({ ...s, slow: true }));
    }, SLOW_AFTER_MS);
    const timeoutTimer = setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS);

    fetch(buildUrl(path, params), { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (alive) setState({ data, loading: false, error: null, slow: false });
      })
      .catch((e) => {
        if (alive && e.name !== "AbortError") {
          setState({ data: null, loading: false, error: e.message, slow: false });
        }
      })
      .finally(() => {
        clearTimeout(slowTimer);
        clearTimeout(timeoutTimer);
      });

    return () => {
      alive = false;
      clearTimeout(slowTimer);
      clearTimeout(timeoutTimer);
      ac.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, key, nonce, ...deps]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { ...state, reload };
}

export function usePut(path) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const put = useCallback(
    async (body) => {
      setSaving(true);
      setError(null);
      const ac = new AbortController();
      const timeoutTimer = setTimeout(() => ac.abort(), REQUEST_TIMEOUT_MS);
      try {
        const r = await fetch(path, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: ac.signal,
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return await r.json();
      } catch (e) {
        setError(e.message);
        return null;
      } finally {
        clearTimeout(timeoutTimer);
        setSaving(false);
      }
    },
    [path]
  );

  return { put, saving, error };
}

/** Debounce a fast-changing value (e.g. a search box) before it drives a fetch. */
export function useDebouncedValue(value, delay = 300) {
  const [debounced, setDebounced] = useState(value);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      setDebounced(value);
      return;
    }
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}
