import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableHeader,
  TableHead,
  TableRow,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import { Info } from "lucide-react";
import { PageHeader } from "@/components/shared";
import { number } from "@/lib/results";
import type { AppState } from "@/lib/types";
export function ModelsPage({ data }: { data: AppState }) {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="A STARTING POINT"
        title="Models that might fit."
        description="Quick memory estimates, separate from measured speed. These are CPU RAM budgets, not GPU capacity guarantees."
      />
      <Alert>
        <Info />
        <AlertTitle>Estimated, not benchmarked</AlertTitle>
        <AlertDescription>
          Q4-class weights at roughly 0.60 bytes per parameter, 15% runtime
          overhead and 2 GiB workspace. “Likely fits” leaves a 20% free-memory
          margin. Context and architecture can change requirements.
        </AlertDescription>
      </Alert>
      <Card>
        <CardHeader>
          <CardTitle>Memory compatibility advisor</CardTitle>
          <CardDescription>
            {number(data.hardware.available_gib)} GiB available at last hardware
            detection.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="pl-6">Model family</TableHead>
                <TableHead>Parameters</TableHead>
                <TableHead>Approx. budget</TableHead>
                <TableHead>Memory assessment</TableHead>
                <TableHead className="pr-6">Evidence</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.advisor.map((m) => (
                <TableRow key={m.name}>
                  <TableCell className="pl-6 font-medium">{m.name}</TableCell>
                  <TableCell>{m.parameters_b}B</TableCell>
                  <TableCell className="tabular-nums">
                    {number(m.required_gib)} GiB
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={
                        m.status === "Likely fits" ? "secondary" : "outline"
                      }
                    >
                      {m.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="pr-6 text-muted-foreground">
                    Estimated
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="text-xs leading-relaxed text-muted-foreground">
        A different GGUF, quantization or context setting can behave
        differently. Use the automatic scan or a manual benchmark to measure
        actual performance.
      </p>
    </div>
  );
}
