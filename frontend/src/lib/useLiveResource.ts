import { useCallback, useEffect, useRef, useState } from "react";
import { errorMessage } from "./api";

/** Retain the last successful snapshot, with an explicit stale/error state. */
export function useLiveResource<T>(load: (signal: AbortSignal) => Promise<T>) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const active = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    try {
      const next = await load(controller.signal);
      if (!controller.signal.aborted) {
        setData(next);
        setError("");
      }
    } catch (failure) {
      if (!controller.signal.aborted) setError(errorMessage(failure));
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [load]);
  useEffect(() => {
    void refresh();
    const poll = () => {
      if (document.visibilityState === "visible") void refresh();
    };
    const timer = window.setInterval(poll, 30_000);
    document.addEventListener("visibilitychange", poll);
    return () => {
      active.current?.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", poll);
    };
  }, [refresh]);
  return { data, error, loading, refresh };
}
