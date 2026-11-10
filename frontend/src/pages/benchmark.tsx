import { useState } from "react";
import type { FormEvent } from "react";
import { Cpu, CircuitBoard, Play, Square, Info } from "lucide-react";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import {
  Field,
  FieldGroup,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { PageHeader, BusyIcon } from "@/components/shared";
import { api } from "@/lib/api";
import { number } from "@/lib/results";
import type { AppState } from "@/lib/types";
export type ManualConfig = {
  executable: string;
  model: string;
  target: "cpu" | "gpu";
  threads: number;
};
export function BenchmarkPage({
  data,
  onRun,
  onRunNpu,
  onCancel,
  pending,
  draft,
  onDraftChange,
}: {
  data: AppState;
  onRun: (config: ManualConfig) => void;
  onRunNpu: (model: string) => void;
  onCancel: () => void;
  pending: boolean;
  draft?: ManualConfig;
  onDraftChange?: (draft: ManualConfig) => void;
}) {
  const [localDraft, setLocalDraft] = useState<ManualConfig>({
    executable: "",
    model: "",
    target: "cpu",
    threads: Math.min(data.hardware.threads || 4, 16),
  });
  const { executable, model, target, threads } = draft ?? localDraft;
  const updateDraft = (patch: Partial<ManualConfig>) => {
    const next = { ...(draft ?? localDraft), ...patch };
    setLocalDraft(next);
    onDraftChange?.(next);
  };
  const [npuModel, setNpuModel] = useState("");
  const [probe, setProbe] = useState<{
      status: string;
      message: string;
      devices?: string[];
    } | null>(null),
    [probing, setProbing] = useState(false);
  const busy = data.busy || pending;
  const npuResult = data.npu_results?.find((result) => result.id === data.job.id);
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    onRun({
      executable: executable.trim().replace(/^"|"$/g, ""),
      model: model.trim().replace(/^"|"$/g, ""),
      target,
      threads,
    });
  };
  const check = async () => {
    setProbing(true);
    try {
      setProbe(await api("openvino"));
    } catch (e) {
      setProbe({
        status: "unavailable",
        message: e instanceof Error ? e.message : "Runtime check failed.",
      });
    } finally {
      setProbing(false);
    }
  };
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="ADVANCED TESTING"
        title="Bring your own model."
        description="Run a repeatable llama-bench test with local files. For automatic downloads and a recommendation, use Find my model."
      />
      <div className="grid items-start gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Manual benchmark</CardTitle>
            <CardDescription>
              128 prompt tokens · 32 generated tokens · 3 repetitions
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form id="manual-form" onSubmit={submit}>
              <FieldGroup>
                <Field data-disabled={busy}>
                  <FieldLabel htmlFor="engine-path">
                    llama-bench executable
                  </FieldLabel>
                  <Input
                    id="engine-path"
                    value={executable}
                    onChange={(e) =>
                      updateDraft({ executable: e.target.value })
                    }
                    placeholder="C:\AI\llama.cpp\llama-bench.exe"
                    required
                    disabled={busy}
                  />
                  <FieldDescription>
                    Keep the build's DLL files beside its executable.
                  </FieldDescription>
                </Field>
                <Field data-disabled={busy}>
                  <FieldLabel htmlFor="model-path">GGUF model file</FieldLabel>
                  <Input
                    id="model-path"
                    value={model}
                    onChange={(e) => updateDraft({ model: e.target.value })}
                    placeholder="C:\AI\models\your-model.gguf"
                    required
                    disabled={busy}
                  />
                </Field>
                <Field data-disabled={busy}>
                  <FieldLabel id="target-label">Compute target</FieldLabel>
                  <ToggleGroup
                    aria-labelledby="target-label"
                    value={[target]}
                    onValueChange={(v) => {
                      if (v[0] === "cpu" || v[0] === "gpu")
                        updateDraft({ target: v[0] });
                    }}
                    variant="outline"
                    disabled={busy}
                  >
                    <ToggleGroupItem value="cpu">
                      <Cpu />
                      CPU
                    </ToggleGroupItem>
                    <ToggleGroupItem value="gpu">
                      <CircuitBoard />
                      GPU offload
                    </ToggleGroupItem>
                  </ToggleGroup>
                  <FieldDescription>
                    GPU requires a compatible Vulkan, CUDA or other GPU build.
                    Offload may be partial.
                  </FieldDescription>
                </Field>
                <Field data-disabled={busy}>
                  <FieldLabel htmlFor="threads">CPU threads</FieldLabel>
                  <Input
                    id="threads"
                    type="number"
                    min={1}
                    max={256}
                    required
                    value={threads}
                    onChange={(e) =>
                      updateDraft({ threads: Number(e.target.value) })
                    }
                    disabled={busy}
                    className="max-w-36"
                  />
                </Field>
              </FieldGroup>
            </form>
          </CardContent>
          <CardFooter className="flex gap-2">
            <Button type="submit" form="manual-form" disabled={busy}>
              {pending ? <BusyIcon /> : <Play data-icon="inline-start" />}Start
              benchmark
            </Button>
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={!data.busy || Boolean(data.job.kind) || pending}
            >
              <Square data-icon="inline-start" />
              Cancel
            </Button>
          </CardFooter>
        </Card>
        <Card>
          <CardHeader>
            <Badge variant="outline" className="w-fit">
              {data.job.status === "idle" ? "Ready" : data.job.status}
            </Badge>
            <CardTitle>A real measurement.</CardTitle>
            <CardDescription>
              Prompt processing and text generation are measured separately.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p
              role="status"
              aria-live="polite"
              className="text-sm leading-relaxed text-muted-foreground"
            >
              {!data.job.kind && data.job.message
                ? data.job.message
                : "Choose a trusted engine and a local model. No scores appear until the engine returns valid measurements."}
            </p>
          </CardContent>
          <CardFooter>
            <p className="text-xs leading-relaxed text-muted-foreground">
              The command, hardware snapshot and original engine output are kept
              with every successful result. Failures and cancellations never
              create a score.
            </p>
          </CardFooter>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Intel NPU runtime</CardTitle>
            <Badge variant="outline">{data.hardware.npus.length ? "Detected by Windows" : "Check runtime"}</Badge>
          </div>
          <CardDescription>
            Test an exported OpenVINO text model on Intel AI Boost using the optional OpenVINO GenAI runtime.
            This test targets the NPU explicitly.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {probe ? (
            <Alert>
              <Info />
              <AlertTitle>{probe.status}</AlertTitle>
              <AlertDescription>
                {probe.message} Devices: {probe.devices?.join(", ") || "none"}.
              </AlertDescription>
            </Alert>
          ) : (
            <p className="text-sm text-muted-foreground">
              Detecting Intel AI Boost does not prove that a model can execute
              on it. A compatible driver, runtime and exported model are
              required.
            </p>
          )}
          <form id="npu-form" onSubmit={(event) => {
            event.preventDefault();
            onRunNpu(npuModel.trim().replace(/^"|"$/g, ""));
          }}>
            <FieldGroup>
              <Field data-disabled={busy}>
                <FieldLabel htmlFor="npu-model">OpenVINO model folder</FieldLabel>
                <Input id="npu-model" value={npuModel} onChange={(event) => setNpuModel(event.target.value)}
                  placeholder="C:\AI\models\your-openvino-model" required disabled={busy} />
                <FieldDescription>
                  Choose a trusted local folder with exported XML/BIN model and tokenizer files. GGUF files use the CPU/GPU test.
                </FieldDescription>
              </Field>
            </FieldGroup>
          </form>
          {data.job.kind === "npu" && (
            <p role="status" className="text-sm text-muted-foreground">{data.job.message}</p>
          )}
          {npuResult && (
            <p className="text-sm">
              <strong>{npuResult.model.name}</strong> · {number(npuResult.generation_tokens_per_second, 2)} tok/s · {number(npuResult.time_to_first_token_ms)} ms to first token
            </p>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap gap-2">
          <Button type="submit" form="npu-form" disabled={busy || !npuModel.trim()}>
            <Play data-icon="inline-start" />Run NPU benchmark
          </Button>
          {data.busy && data.job.kind === "npu" && (
            <Button variant="outline" onClick={onCancel} disabled={pending || data.job.status !== "running"}>
              <Square data-icon="inline-start" />Stop NPU test
            </Button>
          )}
          <Button
            variant="outline"
            onClick={() => void check()}
            disabled={probing}
          >
            {probing && <BusyIcon />}Check OpenVINO runtime
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
