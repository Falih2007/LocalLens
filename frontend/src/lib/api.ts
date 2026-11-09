import { useCallback, useEffect, useState } from "react";
import type { AppState } from "./types";
export async function api<T = unknown>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const token =
    document.querySelector<HTMLMetaElement>("meta[name=session-token]")
      ?.content || "";
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json", "X-LocalLens-Token": token },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || `Request failed (${response.status})`);
  return result as T;
}
export function useAppState() {
  const [data, setData] = useState<AppState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    try {
      const next = await api<AppState>("state");
      setData(next);
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Cannot reach the local engine.",
      );
    }
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    const poll = async () => {
      controller = new AbortController();
      try {
        const next = await api<AppState>("state", undefined, controller.signal);
        if (active) {
          setData(next);
          setError(null);
        }
      } catch (e) {
        if (active)
          setError(e instanceof Error ? e.message : "Connection unavailable.");
      } finally {
        if (active) timer = setTimeout(poll, 2500);
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
    };
  }, []);
  return { data, error, refresh };
}
export function downloadResults(data: AppState) {
  const blob = new Blob(
    [
      JSON.stringify(
        {
          schema_version: "1.0",
          results: data.history,
          automatic_scans: data.scans,
        },
        null,
        2,
      ),
    ],
    { type: "application/json" },
  );
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "locallens-results.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function downloadCompanion(native = false) {
  const token =
    document.querySelector<HTMLMetaElement>("meta[name=session-token]")
      ?.content || "";
  const response = await fetch(native ? "/api/connect/apk" : "/api/connect/companion", {
    headers: { "X-LocalLens-Token": token },
  });
  if (!response.ok)
    throw new Error(
      "Companion download unavailable. Keep the LocalLens launcher running.",
    );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = native ? "LocalLens-Companion-debug.apk" : "LocalLens-Android-Companion.zip";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
