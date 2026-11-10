import { useState } from "react";
import { Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { PageHeader, NoResults, EvidenceButton } from "@/components/shared";
import { journalRows, number, date, deviceLabel } from "@/lib/results";
import { downloadResults } from "@/lib/api";
import type { AppState, JournalRow } from "@/lib/types";
export function HistoryPage({
  data,
  onEvidence,
  onStart,
}: {
  data: AppState;
  onEvidence: (title: string, value: unknown) => void;
  onStart: () => void;
}) {
  const [filter, setFilter] = useState("all");
  const rows = journalRows(data);
  const shown = rows.filter((r) => filter === "all" || r.method === filter);
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="YOUR EVIDENCE"
        title="Benchmark journal."
        description="Every completed test, kept on this computer. Real prompts and synthetic benchmarks are labeled separately."
        action={
          <Button
            variant="outline"
            disabled={!rows.length}
            onClick={() => downloadResults(data)}
          >
            <Download data-icon="inline-start" />
            Export results
          </Button>
        }
      />
      <Tabs value={filter} onValueChange={(v) => setFilter(String(v))}>
        <TabsList aria-label="Filter test method" className="h-auto flex-wrap">
          <TabsTrigger value="all">
            All tests{" "}
            <span className="text-muted-foreground">{rows.length}</span>
          </TabsTrigger>
          <TabsTrigger value="prompt">Real prompts</TabsTrigger>
          <TabsTrigger value="bench">llama-bench</TabsTrigger>
          <TabsTrigger value="npu">Intel NPU</TabsTrigger>
        </TabsList>
      </Tabs>
      {!shown.length ? (
        <NoResults onStart={onStart} />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Saved measurements</CardTitle>
            <CardDescription>
              Newest first. Compare results within the same test method, model
              and settings.
            </CardDescription>
          </CardHeader>
          <CardContent className="px-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Model / test</TableHead>
                  <TableHead>Device</TableHead>
                  <TableHead className="text-right">Generation</TableHead>
                  <TableHead className="text-right">Headroom</TableHead>
                  <TableHead>Recorded</TableHead>
                  <TableHead className="pr-6 text-right">Evidence</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {shown.map((r) => (
                  <ResultRow
                    key={r.id}
                    row={r}
                    onEvidence={() => onEvidence(r.model, r.evidence)}
                  />
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      <p className="text-xs leading-relaxed text-muted-foreground">
        Generation throughput is not whole-request latency. Short prompt tests
        do not establish answer quality or long-context performance.
      </p>
    </div>
  );
}
function ResultRow({
  row: r,
  onEvidence,
}: {
  row: JournalRow;
  onEvidence: () => void;
}) {
  return (
    <TableRow>
      <TableCell className="min-w-56 max-w-sm pl-6 align-top whitespace-normal">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium">{r.model}</span>
            {r.recommended && <Badge variant="secondary">Recommended</Badge>}
          </div>
          <span className="text-xs text-muted-foreground">
            {deviceLabel(r.deviceScope)} · {r.method === "prompt"
              ? "Real prompt · automatic scan"
              : r.method === "npu" ? "OpenVINO GenAI · real prompts" : "llama-bench · synthetic tokens"}
          </span>
          <span className="block max-w-sm text-xs leading-relaxed text-muted-foreground">
            {r.note}
          </span>
          {r.prompt != null && (
            <span className="text-xs text-muted-foreground">
              Prompt processing: {number(r.prompt, 2)} tok/s
            </span>
          )}
        </div>
      </TableCell>
      <TableCell className="align-top">
        <Badge variant="outline">{r.device}</Badge>
      </TableCell>
      <TableCell className="text-right align-top">
        <span className="tabular-nums font-medium">
          {number(r.generation, 2)}
        </span>
        <span className="ml-1 text-xs text-muted-foreground">tok/s</span>
      </TableCell>
      <TableCell className="text-right align-top">
        <span className="tabular-nums">{number(r.freeRam)}</span>
        {r.freeRam != null && (
          <span className="ml-1 text-xs text-muted-foreground">GiB free</span>
        )}
      </TableCell>
      <TableCell className="whitespace-nowrap align-top text-xs text-muted-foreground">
        {date(r.finished)}
      </TableCell>
      <TableCell className="pr-6 text-right align-top">
        <EvidenceButton onClick={onEvidence} />
      </TableCell>
    </TableRow>
  );
}
