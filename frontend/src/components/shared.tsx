import type { ReactNode } from "react";
import { FileJson, History, LoaderCircle } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
  EmptyContent,
} from "@/components/ui/empty";
import { Button } from "@/components/ui/button";
export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-5">
      <div className="flex max-w-2xl flex-col gap-2">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="type-page">{title}</h1>
        <p className="text-sm leading-relaxed text-muted-foreground">
          {description}
        </p>
      </div>
      {action}
    </div>
  );
}
export function MetricCard({
  label,
  value,
  unit,
  detail,
  icon,
}: {
  label: string;
  value: string;
  unit?: string;
  detail: string;
  icon?: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription className="flex items-center justify-between gap-2">
          {label}
          {icon}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="metric-number">
          {value}
          <span className="ml-1.5 text-sm font-normal text-muted-foreground">
            {unit}
          </span>
        </p>
        <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
          {detail}
        </p>
      </CardContent>
    </Card>
  );
}
export function BusyIcon() {
  return (
    <LoaderCircle
      data-icon="inline-start"
      className="motion-safe:animate-spin"
      aria-hidden="true"
    />
  );
}
export function EvidenceDialog({
  value,
  onClose,
}: {
  value: { title: string; data: unknown } | null;
  onClose: () => void;
}) {
  return (
    <Dialog
      open={!!value}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="max-h-[85svh] sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>{value?.title || "Saved evidence"}</DialogTitle>
          <DialogDescription>
            {typeof value?.data === "string"
              ? "Setup instructions and hardware-testing steps."
              : "Original measurements, test settings and engine output. Temporary model cleanup does not remove this record."}
          </DialogDescription>
        </DialogHeader>
        <pre
          className="max-h-[60svh] overflow-auto rounded-lg bg-muted p-4 text-xs leading-relaxed whitespace-pre-wrap wrap-anywhere"
          tabIndex={0}
        >
          {typeof value?.data === "string"
            ? value.data
            : JSON.stringify(value?.data, null, 2)}
        </pre>
      </DialogContent>
    </Dialog>
  );
}
export function NoResults({ onStart }: { onStart?: () => void }) {
  return (
    <Empty className="min-h-64 border">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <History />
        </EmptyMedia>
        <EmptyTitle>A clean slate.</EmptyTitle>
        <EmptyDescription>
          Successful prompt tests and manual benchmarks will appear here.
          Estimates are never displayed as measured scores.
        </EmptyDescription>
      </EmptyHeader>
      {onStart && (
        <EmptyContent>
          <Button onClick={onStart}>Find my model</Button>
        </EmptyContent>
      )}
    </Empty>
  );
}
export function EvidenceButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick}>
      <FileJson data-icon="inline-start" />
      Evidence
    </Button>
  );
}
export function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
