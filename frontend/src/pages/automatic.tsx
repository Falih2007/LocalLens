import { useState } from "react";
import {
  ArrowUpRight,
  Download,
  MessageSquare,
  Trash2,
  Square,
  Check,
  Info,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
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
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldLabel, FieldDescription } from "@/components/ui/field";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { PageHeader, BusyIcon, EvidenceButton } from "@/components/shared";
import { RecommendationCard } from "@/components/recommendation";
import { number, gb, currentRecommendation } from "@/lib/results";
import type { AppState } from "@/lib/types";
export function AutomaticPage({
  data,
  selectedScanId,
  onStart,
  onCancel,
  onEvidence,
  onHistory,
  pending,
}: {
  data: AppState;
  selectedScanId?: string;
  onStart: (mode: "quick" | "thorough") => void;
  onCancel: () => void;
  onEvidence: (title: string, value: unknown) => void;
  onHistory: () => void;
  pending: boolean;
}) {
  const [thorough, setThorough] = useState(false);
  const p = thorough ? data.thorough_plan : data.auto_plan,
    j = data.job,
    running = data.busy && j.kind === "automatic",
    selected = selectedScanId ? data.scans.find((scan) => scan.id === selectedScanId) : undefined,
    latest = selected ?? data.scans.find((scan) => scan.device_scope === "current"),
    recommended = selected ? (selected.recommendation ? selected : undefined) : currentRecommendation(data.scans);
  const message =
    j.kind === "automatic"
      ? j.status === "cancelled" && recommended
        ? "This attempt stopped. Your previous measured recommendation is kept below."
        : j.message
      : "No file paths. No manual setup.";
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="ONE CLICK. REAL ANSWERS."
        title="Find your everyday model."
        description="A real prompt, a measured pace, and enough memory left for the rest of your day."
      />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <CardTitle>Automatic model scan</CardTitle>
            <Badge variant="outline">
              {running
                ? j.stage || "Running"
                : j.kind === "automatic"
                  ? j.status
                  : "Ready"}
            </Badge>
          </div>
          <CardDescription>
            Test GPU and CPU, compare their generation speed, and remove
            temporary downloads.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div className="grid gap-5 md:grid-cols-3">
            {[
              {
                icon: Download,
                title: "Download & verify",
                text: "A pinned engine and an eligible model. Existing supported Ollama models can be copied instead.",
              },
              {
                icon: MessageSquare,
                title: "Measure a real prompt",
                text: "Two uncached 128-token tests per backend, after warmup. No invented scores.",
              },
              {
                icon: Trash2,
                title: "Clean up & recommend",
                text: "Test files are removed. Only small reports, generated samples and logs remain.",
              },
            ].map(({ icon: Icon, title, text }) => (
              <div className="flex flex-col gap-2" key={title}>
                <Icon className="size-5 text-muted-foreground" />
                <h3 className="text-sm font-medium">{title}</h3>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {text}
                </p>
              </div>
            ))}
          </div>
          <Separator />
          <Field orientation="horizontal" data-disabled={data.busy || pending}>
            <Checkbox
              id="thorough"
              checked={thorough}
              onCheckedChange={(v) => setThorough(v === true)}
              disabled={data.busy || pending}
            />
            <div>
              <FieldLabel htmlFor="thorough">Also test 8B</FieldLabel>
              <FieldDescription>
                Quick mode tests up to 4B. Include 8B for a broader scan and a
                larger download.
              </FieldDescription>
            </div>
          </Field>
          <div className="grid gap-3 text-xs text-muted-foreground sm:grid-cols-3">
            <p>
              <span className="block text-foreground">
                {p.candidates[0]?.name || "No eligible model"}
              </span>
              First memory-safe candidate
            </p>
            <p>
              <span className="block text-foreground">
                {gb(p.first_download_bytes)} first · {gb(p.max_download_bytes)}{" "}
                maximum
              </span>
              Potential downloads; reuse can reduce this
            </p>
            <p>
              <span className="block text-foreground">
                {number(p.reserve_gib)} GiB memory reserve
              </span>
              Both tests must reach 15 tok/s
            </p>
          </div>
          <div
            className="rounded-lg border bg-muted/30 p-4"
            role="status"
            aria-live="polite"
          >
            <div className="flex items-center gap-2 text-sm">
              {running && <BusyIcon />}
              {message}
            </div>
            {running && j.download_percent != null && (
              <div className="mt-3 flex flex-col gap-2">
                <Progress
                  value={j.download_percent}
                  aria-label="Download progress"
                />
                <span className="text-xs text-muted-foreground">
                  {number(j.download_percent)}% of this download
                </span>
              </div>
            )}
          </div>
          {!p.candidates.length && (
            <Alert>
              <Info />
              <AlertTitle>More free memory is needed</AlertTitle>
              <AlertDescription>
                Close other apps, refresh hardware and try again. No model is
                loaded without the memory reserve.
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
        <CardFooter className="flex flex-wrap gap-2">
          <Button
            size="lg"
            onClick={() => onStart(thorough ? "thorough" : "quick")}
            disabled={data.busy || pending || !p.candidates.length}
          >
            {pending ? <BusyIcon /> : <ArrowUpRight data-icon="inline-start" />}
            Find my best model
          </Button>
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={!running || j.status === "cancelled" || pending}
          >
            <Square data-icon="inline-start" />
            Stop test
          </Button>
        </CardFooter>
      </Card>
      {recommended && (
        <RecommendationCard
          scan={recommended}
          onEvidence={() =>
            onEvidence("Automatic scan · full evidence", recommended)
          }
          onHistory={onHistory}
        />
      )}{" "}
      {latest && latest.attempts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Latest scan · device comparison</CardTitle>
            <CardDescription>
              Successful measurements and unavailable backends are both kept in
              the record.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Model</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead>Generation</TableHead>
                  <TableHead>Assessment</TableHead>
                  <TableHead className="pr-6 text-right">Evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {latest.attempts.map((a, i) => (
                  <TableRow key={i}>
                    <TableCell className="pl-6">{a.model.name}</TableCell>
                    <TableCell>{a.target.toUpperCase()}</TableCell>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {a.status === "completed"
                        ? number(a.generation_tokens_per_second, 2) + " tok/s"
                        : "Unavailable"}
                    </TableCell>
                    <TableCell>
                      {a.comfortable ? (
                        <Badge variant="secondary">
                          <Check />
                          Comfortable
                        </Badge>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {a.error || a.status_label || a.status}
                        </span>
                      )}
                    </TableCell>
                    <TableCell className="pr-6 text-right">
                      <EvidenceButton
                        onClick={() =>
                          onEvidence(
                            `${a.model.name} · ${a.target.toUpperCase()}`,
                            a,
                          )
                        }
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">
        This is a short fixed workload with 4096-token context capacity. It
        measures comfort within this small Qwen3 catalogue, not answer quality
        or the best model in the world. NPU execution is not part of this scan.
      </p>
    </div>
  );
}
