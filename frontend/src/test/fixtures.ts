import scanJson from "../../../tests/fixtures/qwen3-4b-scan.json";
import manualJson from "../../../tests/fixtures/llama-bench-result.json";
import type { AppState, Scan, ManualResult, Plan } from "@/lib/types";
export const scan = {...scanJson,device_scope:"current"} as unknown as Scan;
export const manual = {...manualJson,device_scope:"current"} as unknown as ManualResult;
export function fixture(): AppState {
  return {
    hardware: scan.hardware,
    busy: false,
    job: { status: "idle" },
    history: [manual],
    scans: [scan],
    advisor: [],
    auto_plan: scanJson.plan as unknown as Plan,
    thorough_plan: { ...scanJson.plan, mode: "thorough" } as unknown as Plan,
  };
}
