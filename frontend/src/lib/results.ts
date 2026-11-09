import type { AppState, JournalRow } from "./types";
const valid = (n: unknown): n is number =>
  typeof n === "number" && Number.isFinite(n) && n > 0;
export function journalRows(
  state: Pick<AppState, "history" | "scans">,
): JournalRow[] {
  const rows: JournalRow[] = state.history.map((r) => ({
    deviceScope:r.device_scope??"unverified",
    id: `bench:${r.id}`,
    model: r.model.path.split(/[\\/]/).pop() || r.model.path,
    device: r.target_requested.toUpperCase(),
    method: "bench",
    finished: r.finished_at,
    generation:
      r.metrics.find((m) => m.test === "generation")?.tokens_per_second ?? null,
    prompt:
      r.metrics.find((m) => m.test === "prompt")?.tokens_per_second ?? null,
    freeRam: null,
    recommended: false,
    note: /stories15m/i.test(r.model.path)
      ? "Tiny integration-test model. Not representative of a usable assistant."
      : "llama-bench synthetic token workload; excludes tokenization and sampling.",
    evidence: r,
  }));
  for (const scan of state.scans) {
    scan.attempts.forEach((a, i) => {
      if (
        a.status !== "completed" ||
        a.evidence !== "measured" ||
        !valid(a.generation_tokens_per_second)
      )
        return;
      rows.push({
        id: `prompt:${scan.id}:${i}`,
        deviceScope: scan.device_scope??"unverified",
        model: `${a.model.name} · ${a.model.quantization}`,
        device: a.target.toUpperCase(),
        method: "prompt",
        finished: scan.finished_at,
        generation: a.generation_tokens_per_second,
        prompt: null,
        freeRam: a.minimum_free_ram_gib,
        recommended:
          scan.device_scope === "current" && scan.recommendation?.target === a.target &&
          scan.recommendation.model.sha256 === a.model.sha256,
        note: `${a.status_label || "Measured"} · 128 output tokens × 2 · ${a.context_tokens || 4096}-token context. ${scan.cleanup.status === "deleted" ? "Temporary test files deleted; evidence retained." : "See evidence for cleanup status."}`,
        evidence: {
          scan_id: scan.id,
          scan_status: scan.status,
          hardware: scan.hardware,
          prompt: scan.prompt,
          cleanup: scan.cleanup,
          attempt: a,
        },
      });
    });
  }
  return rows.sort((a, b) => Date.parse(b.finished) - Date.parse(a.finished));
}
export const number = (n: number | null | undefined, digits = 1) =>
  n == null || !Number.isFinite(n)
    ? "—"
    : new Intl.NumberFormat(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(n);
export const date = (s: string) =>
  new Date(s).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
export const gb = (n: number) => number(n / 1e9, 2) + " GB";

export function currentRecommendation(scans: import("./types").Scan[]) { return scans.find(s=>s.device_scope==="current"&&s.recommendation); }
export const deviceLabel = (scope: import("./types").DeviceScope) => scope==="current"?"This computer":scope==="other"?"Other computer":"Device unverified";
