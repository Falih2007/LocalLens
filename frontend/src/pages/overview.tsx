import {
  Cpu,
  MemoryStick,
  CircuitBoard,
  Activity,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader, MetricCard, SectionCard } from "@/components/shared";
import { RecommendationCard } from "@/components/recommendation";
import { journalRows, number, gb, currentRecommendation } from "@/lib/results";
import type { AppState } from "@/lib/types";
export function OverviewPage({
  data,
  onScan,
  onHistory,
  onStart,
  onEvidence,
}: {
  data: AppState;
  onScan: () => void;
  onHistory: () => void;
  onStart: () => void;
  onEvidence: (title: string, data: unknown) => void;
}) {
  const h = data.hardware,
    latest = currentRecommendation(data.scans),
    count = journalRows(data).filter(r=>r.deviceScope==="current").length;
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="LOCAL AI WORKSPACE"
        title="Your computer, understood."
        description="Know what fits. Measure what works. Find an everyday model with room to spare."
        action={
          <Button
            onClick={onStart}
            disabled={data.busy || !data.auto_plan.candidates.length}
          >
            Find my best model
            <ArrowUpRight data-icon="inline-end" />
          </Button>
        }
      />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="System memory"
          value={number(h.ram_gib)}
          unit="GiB"
          detail={`${number(h.available_gib)} GiB available at last detection`}
          icon={<MemoryStick className="size-4" />}
        />
        <MetricCard
          label="Graphics"
          value={String(h.gpus.length)}
          unit={h.gpus.length === 1 ? "adapter" : "adapters"}
          detail={
            h.gpus.map((g) => g.Name).join(", ") ||
            "No graphics adapter reported"
          }
          icon={<CircuitBoard className="size-4" />}
        />
        <MetricCard
          label="Neural processor"
          value={h.npus.length ? "Detected" : "Not detected"}
          detail={
            h.npus.map((n) => n.FriendlyName).join(", ") ||
            "Runtime support is checked separately"
          }
          icon={<Cpu className="size-4" />}
        />
        <MetricCard
          label="Measured tests"
          value={String(count)}
          detail="Verified measurements from this computer"
          icon={<Activity className="size-4" />}
        />
      </div>
      <div className="grid items-start gap-6 lg:grid-cols-2">
        {latest ? (
          <RecommendationCard
            scan={latest}
            onEvidence={() =>
              onEvidence("Recommended model · saved evidence", latest)
            }
            onHistory={onHistory}
          />
        ) : (
          <Card>
            <CardHeader>
              <Badge variant="secondary" className="w-fit">
                Ready when you are
              </Badge>
              <CardTitle>Meet your everyday model.</CardTitle>
              <CardDescription>
                One automatic scan downloads, measures and cleans up. No file
                paths required.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed text-muted-foreground">
                The quick scan starts with the largest eligible model up to 4B.
                A recommendation requires two real prompt tests at 15 tok/s or
                better, plus generous free-memory headroom.
              </p>
            </CardContent>
            <CardFooter>
              <Button onClick={onScan}>
                Explore the automatic scan
                <ArrowUpRight data-icon="inline-end" />
              </Button>
            </CardFooter>
          </Card>
        )}
        <div className="flex flex-col gap-6">
          <SectionCard
            title={h.cpu}
            description={`${h.threads} logical processors`}
          >
            <dl className="detail-list">
              <div>
                <dt>System</dt>
                <dd>{h.os}</dd>
              </div>
              <div>
                <dt>GPU driver</dt>
                <dd>
                  {h.gpus.map((g) => g.DriverVersion).join(", ") ||
                    "Unavailable"}
                </dd>
              </div>
              <div>
                <dt>Memory reserve</dt>
                <dd>
                  {number(data.auto_plan.reserve_gib)} GiB minimum during
                  automatic tests
                </dd>
              </div>
            </dl>
          </SectionCard>
          <Card>
            <CardHeader>
              <CardTitle>Evidence over guesswork.</CardTitle>
              <CardDescription>
                Memory estimates and actual test results always stay distinct.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-start gap-3">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                <p className="text-sm leading-relaxed text-muted-foreground">
                  Inference stays on this computer. The automatic scan uses
                  public downloads from GitHub and Hugging Face, then removes
                  its test files.
                </p>
              </div>
            </CardContent>
            <CardFooter>
              <Button variant="outline" onClick={onScan}>
                Scan details · from {gb(data.auto_plan.first_download_bytes)}
              </Button>
            </CardFooter>
          </Card>
        </div>
      </div>
      <SectionCard
        title="Detection notes"
        description="Hardware visibility is not a guarantee of inference support."
      >
        <ul className="flex list-disc flex-col gap-2 pl-4 text-xs leading-relaxed text-muted-foreground">
          {h.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      </SectionCard>
    </div>
  );
}
