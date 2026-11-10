import { useEffect, useRef, useState } from "react";
import { ArrowRight, Cpu, Gauge, ScanLine, TriangleAlert } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { api } from "@/lib/api";
import { gb, journalRows } from "@/lib/results";
import type { AppState, Hardware, Job } from "@/lib/types";

export type OnboardingResult =
  | { mode: "benchmark"; scanId: string }
  | { mode: "predict"; runtimeAvailable: boolean };

const choices = [
  {
    id: "benchmark",
    title: "Run a Benchmark",
    description: "Run AI models on your device to measure real-world performance.",
    label: "Most Accurate",
    icon: Gauge,
  },
  {
    id: "predict",
    title: "Scan & Predict",
    description: "Detect your hardware and estimate AI performance without running a full benchmark.",
    label: "Faster",
    icon: Cpu,
  },
] as const;
type Mode = OnboardingResult["mode"];

export function OnboardingPage({
  data, error, refresh, onBack, onComplete,
}: {
  data: AppState | null;
  error: string | null;
  refresh: () => Promise<AppState | null>;
  onBack?: () => void;
  onComplete: (result: OnboardingResult) => void;
}) {
  const [mode, setMode] = useState<Mode | null>(null);
  const [message, setMessage] = useState("");
  const [failure, setFailure] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const controller = useRef<AbortController | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const choice = choices.find((option) => option.id === mode);
  const job = jobId && data?.job.id === jobId ? data.job : null;
  const report = jobId ? data?.scans.find((scan) => scan.id === jobId) : undefined;
  const finished = Boolean(data && !data.busy && (job || report) && job?.status !== "running");
  const measured = Boolean(
    report?.status === "completed" && journalRows({ history: [], scans: [report] }).length,
  );
  let resultError: string | null = null;
  if (finished && !measured) {
    if (job?.status === "cancelled") resultError = "Benchmark cancelled.";
    else if (job?.status === "failed") resultError = job.message || "The benchmark failed.";
    else resultError = report?.attempts.find((attempt) => attempt.error)?.error
      || "The benchmark ended without a usable measurement.";
  }
  const issue = failure || resultError || error;
  const canRetry = Boolean((failure && !jobId) || resultError);
  const canCancel = mode === "predict" || Boolean(jobId && !finished);
  const plan = data?.auto_plan;
  const firstModel = plan?.candidates[0];
  const download = job?.stage === "downloading" && !cancelling ? job.download_percent : null;

  useEffect(() => { heading.current?.focus(); }, [mode]);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (jobId && finished && measured) onComplete({ mode: "benchmark", scanId: jobId });
  }, [jobId, finished, measured, onComplete]);

  const start = async (next: Mode) => {
    const request = new AbortController();
    controller.current?.abort();
    controller.current = request;
    setMode(next);
    setFailure(null);
    setJobId(null);
    setCancelling(false);
    setMessage(next === "benchmark" ? "Preparing benchmark environment…" : "Detecting CPU, GPU, and NPU…");
    try {
      if (next === "benchmark") {
        const accepted = await api<Job>("auto", { mode: "quick" }, request.signal);
        if (!accepted.id) throw new Error("The benchmark did not return a job ID.");
        if (request.signal.aborted) return;
        setJobId(accepted.id);
        setMessage(accepted.message ?? "Detecting your hardware…");
        void refresh();
        return;
      }
      const hardware = await api<Hardware>("refresh", {}, request.signal);
      if (hardware.available_gib == null) {
        throw new Error("Windows did not report available memory. Retry hardware detection to get model-fit estimates.");
      }
      setMessage("Checking the optional Intel OpenVINO runtime…");
      const runtime = await api<{ status: string }>("openvino", undefined, request.signal)
        .catch(() => null);
      if (request.signal.aborted) return;
      setMessage("Preparing your memory-fit estimates…");
      const snapshot = await refresh();
      if (request.signal.aborted) return;
      if (!snapshot?.advisor.length) throw new Error("Could not load the model-fit estimates.");
      await api("onboarding/complete", {}, request.signal);
      if (request.signal.aborted) return;
      onComplete({ mode: "predict", runtimeAvailable: runtime?.status === "available" });
    } catch (cause) {
      if (!request.signal.aborted) {
        setFailure(cause instanceof Error ? cause.message : "The operation could not complete.");
      }
    }
  };

  const chooseAgain = () => {
    controller.current?.abort();
    setMode(null);
    setFailure(null);
    setJobId(null);
    setCancelling(false);
  };

  const cancel = async () => {
    if (mode === "predict") {
      chooseAgain();
      return;
    }
    if (!jobId) return;
    setCancelling(true);
    setFailure(null);
    try {
      await api("cancel", { id: jobId });
      void refresh();
    } catch (cause) {
      setCancelling(false);
      setFailure(cause instanceof Error ? cause.message : "Could not stop the benchmark.");
      void refresh();
    }
  };

  return (
    <main className="grid min-h-dvh place-items-center px-5 py-12 sm:px-8">
      <div className="w-full max-w-3xl">
        {!choice ? (
          <div className="flex flex-col gap-8 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-300">
            <header className="flex flex-col items-center gap-3 text-center">
              <span className="grid size-11 place-items-center rounded-xl bg-primary text-primary-foreground">
                <ScanLine aria-hidden="true" className="size-5" />
              </span>
              <p className="eyebrow">LocalLens</p>
              <h1 ref={heading} tabIndex={-1} className="type-page outline-none">How would you like to test your device?</h1>
              <p className="text-sm text-muted-foreground sm:text-base">Choose how you'd like to discover your AI performance.</p>
            </header>
            <div className="grid gap-4 sm:grid-cols-2">
              {choices.map(({ id, title, description, label, icon: Icon }) => (
                <Card key={id} className="relative isolate h-full border border-transparent shadow-sm transition-[border-color,box-shadow,transform] duration-200 hover:border-ring/60 hover:shadow-md focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/50 motion-safe:hover:-translate-y-0.5">
                  <CardHeader className="flex flex-col gap-4 px-5 pt-2">
                    <span className="grid size-10 place-items-center rounded-lg bg-muted text-foreground">
                      <Icon aria-hidden="true" className="size-5" />
                    </span>
                    <CardTitle className="text-lg">
                      <button type="button" className="text-left outline-none after:absolute after:inset-0" aria-describedby={id + "-description"} onClick={() => void start(id)}>
                        {title}
                      </button>
                    </CardTitle>
                  </CardHeader>
                  <CardContent id={id + "-description"} className="px-5 leading-relaxed text-muted-foreground">
                    {description}
                  </CardContent>
                  <CardFooter className="mt-auto justify-between gap-3 px-5">
                    <Badge variant={id === "benchmark" ? "secondary" : "outline"}>{label}</Badge>
                    <ArrowRight aria-hidden="true" className="size-4 text-muted-foreground" />
                  </CardFooter>
                </Card>
              ))}
            </div>
            <p className="text-center text-xs leading-relaxed text-muted-foreground">
              {plan && firstModel ? (
                <>
                  Quick benchmark starts with {firstModel.name}. Downloads up to {gb(plan.first_download_bytes)} for the first test
                  {plan.candidates.length > 1 && ` or ${gb(plan.max_download_bytes)} if it tries smaller models`}.
                  A verified local model can reduce downloads.
                </>
              ) : plan ? (
                "No quick benchmark model fits the current memory budget."
              ) : (
                error ? "The benchmark download estimate is unavailable." : "Checking your hardware for a benchmark download estimate…"
              )}
              {" "}Scan &amp; Predict estimates RAM fit only.
            </p>
            {onBack && (
              <Button variant="ghost" className="self-center" onClick={onBack}>Back to dashboard</Button>
            )}
          </div>
        ) : (
          <div className="mx-auto flex max-w-lg flex-col gap-6 motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 motion-safe:duration-300">
            <header className="flex flex-col items-center gap-3 text-center">
              <Badge variant="secondary">Selected mode</Badge>
              <h1 ref={heading} tabIndex={-1} className="type-page outline-none">{choice.title}</h1>
            </header>
            <Card className="shadow-sm ring-primary/25">
              <CardHeader>
                <CardTitle role="status">
                  {canRetry ? "Test could not complete" : cancelling ? "Stopping and cleaning up…" : job?.message || message}
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                {!resultError && !canRetry && (
                  download != null ? (
                    <div className="flex flex-col gap-2">
                      <Progress value={download} aria-label="Current download progress" />
                      <span className="text-xs text-muted-foreground">{download}% of this download</span>
                    </div>
                  ) : (
                    <div role="progressbar" aria-label="Processing" className="h-1 overflow-hidden rounded-full bg-muted">
                      <div className="onboarding-progress h-full w-1/3 rounded-full bg-primary" />
                    </div>
                  )
                )}
                {issue && (
                  <Alert variant={job?.status === "cancelled" ? "default" : "destructive"}>
                    <TriangleAlert />
                    <AlertTitle>{job?.status === "cancelled" ? "Test stopped" : "Needs attention"}</AlertTitle>
                    <AlertDescription>{issue}</AlertDescription>
                  </Alert>
                )}
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                {canRetry && <Button onClick={() => void start(choice.id)} disabled={Boolean(data?.busy && mode === "benchmark")}>Retry</Button>}
                {error && !canRetry && <Button variant="outline" onClick={() => void refresh()}>Retry connection</Button>}
                {canRetry ? <Button variant="outline" onClick={chooseAgain}>Choose another mode</Button> :
                  canCancel && <Button variant="outline" disabled={cancelling} onClick={() => void cancel()}>Cancel</Button>}
              </CardFooter>
            </Card>
          </div>
        )}
      </div>
    </main>
  );
}
