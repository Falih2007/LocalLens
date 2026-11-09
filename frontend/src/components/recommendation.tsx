import { Check, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";
import { number, date } from "@/lib/results";
import type { Scan } from "@/lib/types";
export function RecommendationCard({
  scan,
  onEvidence,
  onHistory,
}: {
  scan: Scan;
  onEvidence: () => void;
  onHistory?: () => void;
}) {
  const r = scan.recommendation;
  if (!r || scan.device_scope !== "current") return null;
  return (
    <Card>
      <CardHeader>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <Badge variant="secondary">
            <Check data-icon="inline-start" />
            Measured recommendation
          </Badge>
          <span className="text-xs text-muted-foreground">
            {date(scan.finished_at)}
          </span>
        </div>
        <CardTitle>
          {r.model.name}{" "}
          <span className="font-normal text-muted-foreground">
            / {r.model.quantization}
          </span>
        </CardTitle>
        <CardDescription>
          A comfortable fit on {r.target.toUpperCase()} in this scan.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <p className="metric-number">
              {number(r.generation_tokens_per_second, 2)}
              <span className="ml-1.5 text-sm font-normal text-muted-foreground">
                tok/s
              </span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Measured generation · 2 prompt tests
            </p>
          </div>
          <div>
            <p className="metric-number">
              {number(r.minimum_free_ram_gib)}
              <span className="ml-1.5 text-sm font-normal text-muted-foreground">
                GiB free
              </span>
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Lowest system-memory headroom
            </p>
          </div>
        </div>
        <Separator />
        <p className="text-sm leading-relaxed text-muted-foreground">
          {r.reason}
        </p>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {r.scope}
        </p>
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" />
          {scan.cleanup.status === "deleted"
            ? "Test downloads removed. Saved results are retained; existing models are preserved."
            : scan.cleanup.status === "failed"
              ? `Cleanup needs attention: ${scan.cleanup.path}`
              : "No cleanup was needed."}
        </div>
      </CardContent>
      <CardFooter className="flex flex-wrap gap-2">
        <Button variant="outline" onClick={onEvidence}>
          Inspect evidence
        </Button>
        {onHistory && (
          <Button variant="ghost" onClick={onHistory}>
            View benchmark journal
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
