import { useCallback, useEffect, useRef, useState } from "react";

const REQUEST_TIMEOUT_MS = 60_000; // Render free tier cold start can take ~50s
const SLOW_AFTER_MS = 3_000; // show a "waking up" hint after this

const TIMEOUT_MSG =
  "This is taking too long — the free server may be waking up. Please try again.";

/** Turn a raw fetch error / HTTP status into a short, human message. */
export function friendlyError(err) {
  const m = String(err?.message || "");
  if (/Failed to fetch|NetworkError|ERR_NETWORK/i.test(m)) {
    return "Can't reach the server. Check your connection and try again.";
  }
  if (/HTTP 5\d\d/.test(m)) return "The server ran into a problem. Please try again in a moment.";
  if (/HTTP 404/.test(m)) return "That wasn't found — it may have been removed.";
  if (/HTTP 4(00|22)/.test(m)) return "Some values look off. Please review them and try again.";
  if (/HTTP 429/.test(m)) return "Too many requests right now. Give it a few seconds.";
  return "Something went wrong. Please try again.";
}

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

    let timedOut = false;
    const slowTimer = setTimeout(() => {
      if (alive) setState((s) => ({ ...s, slow: true }));
    }, SLOW_AFTER_MS);
    const timeoutTimer = setTimeout(() => { timedOut = true; ac.abort(); }, REQUEST_TIMEOUT_MS);

    fetch(buildUrl(path, params), { signal: ac.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => {
        if (alive) setState({ data, loading: false, error: null, slow: false });
      })
      .catch((e) => {
        if (!alive) return;
        if (e.name === "AbortError") {
          // A genuine cancellation (params changed) is silent; a timeout is not.
          if (timedOut) setState({ data: null, loading: false, error: TIMEOUT_MSG, slow: false });
          return;
        }
        setState({ data: null, loading: false, error: friendlyError(e), slow: false });
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
      let timedOut = false;
      const timeoutTimer = setTimeout(() => { timedOut = true; ac.abort(); }, REQUEST_TIMEOUT_MS);
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
        setError(timedOut ? TIMEOUT_MSG : friendlyError(e));
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
