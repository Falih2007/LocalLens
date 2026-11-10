export type DeviceScope = "current" | "other" | "unverified";
export type Hardware = {
  device_id?: string | null;
  cpu: string;
  threads: number;
  os: string;
  ram_gib: number | null;
  available_gib: number | null;
  gpus: { Name: string; DriverVersion: string }[];
  npus: { FriendlyName: string; Status: string }[];
  warnings: string[];
  detected_at: string;
};
export type Model = {
  name: string;
  parameters_b: number;
  quantization: string;
  sha256: string;
  filename: string;
  bytes: number;
  source?: string;
};
export type Sample = {
  predicted_per_second: number;
  predicted_n: number;
  prompt_per_second?: number;
  prompt_n?: number;
  [key: string]: unknown;
};
export type Attempt = {
  model: Model;
  target: string;
  status: string;
  evidence: string;
  generation_tokens_per_second?: number;
  slowest_tokens_per_second?: number;
  minimum_free_ram_gib: number | null;
  comfortable?: boolean;
  status_label?: string;
  samples: Sample[];
  error?: string;
  context_tokens: number;
  gpu_layers_offloaded?: number;
  model_layers?: number;
  [key: string]: unknown;
};
export type Recommendation = {
  model: Model;
  target: string;
  generation_tokens_per_second: number;
  slowest_tokens_per_second: number;
  minimum_free_ram_gib: number;
  reason: string;
  scope: string;
};
export type Scan = {
  device_scope?: DeviceScope;
  id: string;
  status: string;
  finished_at: string;
  hardware: Hardware;
  prompt: string;
  attempts: Attempt[];
  recommendation: Recommendation | null;
  cleanup: { status: string; message?: string; path?: string };
  outcome?: string;
  [key: string]: unknown;
};
export type ManualResult = {
  device_scope?: DeviceScope;
  id: string;
  finished_at: string;
  target_requested: string;
  model: { path: string };
  metrics: { test: string; tokens_per_second: number; stddev: number | null }[];
  [key: string]: unknown;
};
export type Plan = {
  mode: string;
  candidates: Model[];
  reserve_gib: number;
  first_download_bytes: number;
  max_download_bytes: number;
  prompt: string;
  minimum_tokens_per_second: number;
};
export type Job = {
  status: string;
  kind?: string;
  stage?: string;
  message?: string;
  download_percent?: number | null;
  id?: string;
};
export type Advisor = {
  name: string;
  parameters_b: number;
  weights_gib: number;
  required_gib: number;
  status: string;
  evidence: string;
  assumption: string;
};
export type NpuResult = {
  id: string;
  device_scope?: DeviceScope;
  finished_at: string;
  evidence: "measured";
  model: { path: string; name: string };
  generation_tokens_per_second: number;
  time_to_first_token_ms: number;
};
export type AppState = {
  onboarding_complete?: boolean;
  hardware: Hardware;
  busy: boolean;
  job: Job;
  history: ManualResult[];
  npu_results?: NpuResult[];
  scans: Scan[];
  advisor: Advisor[];
  auto_plan: Plan;
  thorough_plan: Plan;
};
export type JournalRow = {
  deviceScope: DeviceScope;
  id: string;
  model: string;
  device: string;
  method: "prompt" | "bench" | "npu";
  finished: string;
  generation: number | null;
  prompt: number | null;
  freeRam: number | null;
  recommended: boolean;
  note: string;
  evidence: unknown;
};
