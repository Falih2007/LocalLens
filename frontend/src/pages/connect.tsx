import { useCallback, useEffect, useState } from "react";
import {
  ArrowLeftRight,
  BookOpen,
  Download,
  Info,
  Laptop,
  Search,
  ShieldCheck,
  Smartphone,
  Unplug,
  Wifi,
} from "lucide-react";
import { api, downloadCompanion } from "@/lib/api";
import type { AppState } from "@/lib/types";
import { number } from "@/lib/results";
import { PageHeader, BusyIcon } from "@/components/shared";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyDescription,
} from "@/components/ui/empty";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  FieldGroup,
  Field,
  FieldLabel,
  FieldDescription,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableHeader,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
} from "@/components/ui/table";

type WorkerHardware = {
  name: string;
  device_type: string;
  os: string;
  cpu: string;
  gpu: string;
  npu: string;
  physical_ram_gib: number | null;
  available_gib: number | null;
  swap_gib: number | null;
  runtime: { status: string; backend: string };
  inference_participation: string;
  battery_percent?: number;
  sharing_enabled?: boolean;
};
export type Peer = {
  id: string;
  name: string;
  fingerprint: string;
  status: string;
  protocol?: string;
  platform?: string;
  remembered?: boolean;
  verification_code?: string;
  verified?: boolean;
  last_seen?: number;
  message?: string;
  hardware?: WorkerHardware | null;
  connection_benchmark?: {
    median_roundtrip_ms: number;
    roundtrip_payload_mib_s: number;
  };
  traffic?: {
    bytes_to_phone: number;
    bytes_from_phone: number;
    interruptions: number;
  };
};
export type ClusterState = {
  devices: Peer[];
  message: string;
  scanning: boolean;
  discovery_error?: string | null;
  trust_error?: string | null;
  summary: {
    connected_workers: number;
    total_reported_physical_gib: number | null;
    local_model_budget_gib: number | null;
    actual_usable_cluster_capacity_gib: number | null;
    capacity_note: string;
  };
  backends: { id: string; name: string; status: string; reason: string }[];
  reports: { kind: string; finished_at?: number; [key: string]: unknown }[];
};
const memoryFit = (
  required: number,
  physical: number | null,
  available: number | null,
  phone = false,
) => {
  if (physical == null || available == null) return "Unknown";
  const room = Math.max(
    0,
    Math.min(physical, available) - Math.max(phone ? 2 : 4, physical * 0.2),
  );
  return required <= room ? "May fit · estimate" : "Exceeds reserved budget";
};

export function ConnectPage({
  data,
  onEvidence,
}: {
  data: AppState;
  onEvidence: (title: string, value: unknown) => void;
}) {
  const [cluster, setCluster] = useState<ClusterState | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pairing, setPairing] = useState<Peer | null>(null);
  const [code, setCode] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [manualHost, setManualHost] = useState("");
  const [manualPort, setManualPort] = useState("45460");
  const [executable, setExecutable] = useState("");
  const [model, setModel] = useState("");
  const [layers, setLayers] = useState(8);
  const load = useCallback(async () => {
    setCluster(await api<ClusterState>("connect/state"));
  }, []);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    const poll = async () => {
      controller = new AbortController();
      try {
        await api("connect/refresh", {}, controller.signal);
        const next = await api<ClusterState>(
          "connect/state",
          undefined,
          controller.signal,
        );
        if (active) setCluster(next);
      } catch (e) {
        if (active)
          setError(
            e instanceof Error ? e.message : "Companion status unavailable.",
          );
      } finally {
        if (active) timer = setTimeout(poll, 5000);
      }
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
      controller?.abort();
    };
  }, []);
  const act = async (action: string, body: unknown = {}) => {
    setBusy(action);
    setError(null);
    try {
      const result = await api(`connect/${action}`, body);
      await load();
      return result;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection action failed.");
      return null;
    } finally {
      setBusy(null);
    }
  };
  const guide = async () => {
    setError(null);
    try {
      const result = await api<{ text: string }>("connect/guide");
      onEvidence("Connect Devices · setup and experiment guide", result.text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Setup guide unavailable.");
    }
  };
  const connected =
    cluster?.devices.filter((p) => p.status === "connected") || [];
  const computePeer = connected.find((peer) => peer.hardware?.runtime.status === "ready");
  const livePair = cluster?.devices.find((p) => p.id === pairing?.id) || pairing;
  useEffect(() => {
    if (livePair?.status === "connected") setPairing(null);
  }, [livePair?.status]);
  const exportResults = () => {
    const url = URL.createObjectURL(
      new Blob(
        [
          JSON.stringify(
            { schema_version: "1.0", cluster_reports: cluster?.reports || [] },
            null,
            2,
          ),
        ],
        { type: "application/json" },
      ),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "locallens-connections.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="BETTER, TOGETHER"
        title="Your devices. Together."
        description="Find a companion on your Wi-Fi. Pair with permission. Explore what your devices can do together."
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => { void downloadCompanion(true).catch((e) => setError(String(e))); }}><Download data-icon="inline-start" />Android app</Button>
            <Button variant="outline" onClick={() => void guide()}>
              <BookOpen data-icon="inline-start" />
              Phone setup
            </Button>
            <Button disabled={!!busy} onClick={() => void act("scan")}>
              {busy === "scan" ? (
                <BusyIcon />
              ) : (
                <Search data-icon="inline-start" />
              )}
              Add device
            </Button>
          </div>
        }
      />
      {error && (
        <Alert variant="destructive" role="alert">
          <Info />
          <AlertTitle>Connection needs attention</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {(cluster?.discovery_error || cluster?.trust_error) && (
        <Alert><Info /><AlertTitle>Device setup needs attention</AlertTitle>
          <AlertDescription>{cluster.discovery_error || cluster.trust_error}</AlertDescription>
        </Alert>
      )}
      <p className="text-sm text-muted-foreground" role="status">
        {cluster?.scanning ? "Scanning your Wi-Fi…" : "Nearby devices refresh automatically. Enable discovery in the phone companion."}
      </p>
      <Card>
        <CardHeader>
          <CardTitle>Your compute circle</CardTitle>
          <CardDescription>
            Connection status is live. Model-parallel inference remains
            experimental.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <div
            className="flex flex-wrap items-center justify-center gap-6 py-4"
            aria-label="Cluster connection diagram"
          >
            <div className="flex flex-col items-center gap-2">
              <Laptop className="size-10" />
              <span className="text-sm font-medium">This computer</span>
              <Badge variant="secondary">Primary · online</Badge>
            </div>
            <div className="flex flex-col items-center gap-2 text-muted-foreground">
              <ArrowLeftRight className="size-6" />
              <span className="text-xs">
                {connected.length ? "Encrypted Wi-Fi" : "No paired connection"}
              </span>
            </div>
            <div className="flex flex-col items-center gap-2">
              <Smartphone className="size-10" />
              <span className="text-sm font-medium">
                {connected.length
                  ? connected[0].hardware?.name || connected[0].name
                  : "Your companion"}
              </span>
              <Badge variant="outline">
                {connected.length
                  ? `${connected.length} connected · inference unverified`
                  : "Waiting for pairing"}
              </Badge>
            </div>
          </div>
          <Separator />
          <dl className="grid gap-5 sm:grid-cols-3">
            <div>
              <dt className="text-xs text-muted-foreground">
                Connected workers
              </dt>
              <dd className="mt-1 text-2xl font-medium tabular-nums">
                {connected.length}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                Reported physical memory
              </dt>
              <dd className="mt-1 text-2xl font-medium tabular-nums">
                {cluster
                  ? number(cluster.summary.total_reported_physical_gib)
                  : "—"}
                <span className="ml-1 text-sm text-muted-foreground">GiB</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-muted-foreground">
                Usable model capacity
              </dt>
              <dd className="mt-1 text-lg font-medium">Not verified</dd>
            </div>
          </dl>
          <p className="text-xs leading-relaxed text-muted-foreground">
            {cluster?.summary.capacity_note ||
              "Physical RAM is not pooled model capacity. Phone virtual RAM expansion is excluded."}
          </p>
        </CardContent>
      </Card>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold tracking-tight">
          Available devices
        </h2>
        <Badge variant="outline">
          <ShieldCheck />
          Approval required
        </Badge>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Laptop className="size-5" />
              This computer
            </CardTitle>
            <CardDescription>
              {data.hardware.os} · Primary device
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <dt className="text-muted-foreground">CPU</dt>
              <dd>{data.hardware.cpu}</dd>
              <dt className="text-muted-foreground">Graphics</dt>
              <dd>
                {data.hardware.gpus.map((g) => g.Name).join(", ") ||
                  "Not detected"}
              </dd>
              <dt className="text-muted-foreground">Neural processor</dt>
              <dd>
                {data.hardware.npus.map((n) => n.FriendlyName).join(", ") ||
                  "Not detected"}
              </dd>
              <dt className="text-muted-foreground">Physical / available</dt>
              <dd>
                {number(data.hardware.ram_gib)} /{" "}
                {number(data.hardware.available_gib)} GiB
              </dd>
            </dl>
          </CardContent>
          <CardFooter>
            <Badge variant="secondary">Local hardware · detected</Badge>
          </CardFooter>
        </Card>
        {cluster?.devices.map((peer) => (
          <Card key={peer.id}>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="size-5" />
                {peer.hardware?.name || peer.name}
              </CardTitle>
              <CardDescription>
                {peer.hardware
                  ? `${peer.hardware.os} · ${peer.hardware.device_type}`
                  : `${peer.platform || "Nearby companion"} · ${peer.remembered ? "Remembered device" : "Approval required"}`}
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Badge
                variant={peer.status === "connected" ? "secondary" : "outline"}
              >
                {peer.status === "pending" ? "Approve on phone" : peer.status}
              </Badge>
              {peer.hardware && (
                <dl className="grid grid-cols-2 gap-3 text-sm">
                  <dt className="text-muted-foreground">CPU</dt>
                  <dd>{peer.hardware.cpu}</dd>
                  <dt className="text-muted-foreground">GPU / NPU</dt>
                  <dd>
                    {peer.hardware.gpu} / {peer.hardware.npu}
                  </dd>
                  <dt className="text-muted-foreground">
                    Physical / available
                  </dt>
                  <dd>
                    {number(peer.hardware.physical_ram_gib)} /{" "}
                    {number(peer.hardware.available_gib)} GiB
                  </dd>
                  <dt className="text-muted-foreground">Swap (excluded)</dt>
                  <dd>{number(peer.hardware.swap_gib)} GiB</dd>
                  <dt className="text-muted-foreground">Runtime</dt>
                  <dd>
                    {peer.hardware.runtime.backend} ·{" "}
                    {peer.hardware.runtime.status}
                  </dd>
                  <dt className="text-muted-foreground">Compute sharing</dt>
                  <dd>{peer.hardware.sharing_enabled === true ? "Enabled on phone" : peer.protocol === "locallens-companion/2" ? "Unavailable in pairing preview" : "Controlled in Termux"}</dd>
                  {peer.hardware.battery_percent != null && <><dt className="text-muted-foreground">Battery</dt><dd>{peer.hardware.battery_percent}%</dd></>}
                </dl>
              )}
              <p className="text-xs text-muted-foreground">
                {peer.message ||
                  "Discovered over LAN. No inference capability is assumed."}
              </p>
              {peer.status !== "connected" && peer.last_seen && <p className="text-xs text-muted-foreground">Hardware last reported {new Date(peer.last_seen * 1000).toLocaleString()}.</p>}
              <p className="text-xs text-muted-foreground">
                {peer.connection_benchmark
                  ? `${peer.connection_benchmark.median_roundtrip_ms} ms TLS request round trip · measured`
                  : "Network latency not measured"}
              </p>
              {peer.traffic && (
                <p className="text-xs text-muted-foreground">
                  RPC payload:{" "}
                  {number(
                    (peer.traffic.bytes_to_phone +
                      peer.traffic.bytes_from_phone) /
                      1024 ** 2,
                    2,
                  )}{" "}
                  MiB · {peer.traffic.interruptions} interruptions
                </p>
              )}
            </CardContent>
            <CardFooter className="flex flex-wrap gap-2">
              {peer.status === "available" ? (
                <Button
                  disabled={!!busy}
                  onClick={async () => {
                    if (peer.protocol === "locallens-companion/2" && !(await act("pair", { device_id: peer.id }))) return;
                    setPairing(peer);
                    setCode("");
                    setConfirmed(false);
                  }}
                >
                  <ShieldCheck data-icon="inline-start" />
                  Connect
                </Button>
              ) : (
                <Button
                  variant="outline"
                  disabled={!!busy}
                  onClick={() => void act("disconnect", { device_id: peer.id })}
                >
                  <Unplug data-icon="inline-start" />
                  {peer.protocol === "locallens-companion/2" ? "Disconnect" : "Disconnect & revoke"}
                </Button>
              )}
              {peer.status === "pending" && peer.protocol === "locallens-companion/2" && (
                <Button disabled={!!busy} onClick={() => { setPairing(peer); setConfirmed(false); }}>Verify code</Button>
              )}
              {peer.remembered && peer.status !== "connected" && (
                <Button disabled={!!busy} onClick={() => void act("resume", { device_id: peer.id })}>Reconnect</Button>
              )}
              {peer.protocol === "locallens-companion/2" && peer.status !== "available" && (
                <Button variant="ghost" disabled={!!busy} onClick={() => void act("forget", { device_id: peer.id })}>Forget device</Button>
              )}
              {peer.status === "connected" && (
                <Button
                  variant="outline"
                  disabled={!!busy}
                  onClick={() => void act("benchmark", { device_id: peer.id })}
                >
                  {busy === "benchmark" ? (
                    <BusyIcon />
                  ) : (
                    <Wifi data-icon="inline-start" />
                  )}
                  Benchmark connection
                </Button>
              )}
            </CardFooter>
          </Card>
        ))}
      </div>
      {cluster && cluster.devices.length === 0 && (
        <Empty className="border">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Wifi />
            </EmptyMedia>
            <EmptyTitle>No companion discovered yet</EmptyTitle>
            <EmptyDescription>{cluster.message}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
      <details>
        <summary className="cursor-pointer text-sm text-muted-foreground">Advanced: connect by address</summary>
        <form className="mt-4 max-w-md" onSubmit={(event) => { event.preventDefault(); void act("manual", { host: manualHost, port: Number(manualPort) }); }}>
          <FieldGroup>
            <Field><FieldLabel htmlFor="manual-host">Phone Wi-Fi address</FieldLabel><Input id="manual-host" value={manualHost} onChange={(event) => setManualHost(event.target.value)} placeholder="192.168.1.20" required /><FieldDescription>Use the address shown in the native companion when mDNS is blocked. Pairing approval is still required.</FieldDescription></Field>
            <Field><FieldLabel htmlFor="manual-port">Companion port</FieldLabel><Input id="manual-port" type="number" min={1024} max={65535} value={manualPort} onChange={(event) => setManualPort(event.target.value)} required /></Field>
            <Button disabled={!!busy} type="submit">Find at address</Button>
          </FieldGroup>
        </form>
      </details>
      <Alert>
        <Info />
        <AlertTitle>Pairing is the first step</AlertTitle>
        <AlertDescription>
          Exo currently has no verified Windows–Android path for this setup. The
          experimental llama.cpp adapter can split work between laptop CPU and
          phone CPU. Intel Arc and AI Boost NPU are not part of this first
          experiment. A connected phone is not yet a verified compute
          contributor.
        </AlertDescription>
      </Alert>
      <Card>
        <CardHeader>
          <CardTitle>Plan with room to breathe</CardTitle>
          <CardDescription>
            Memory estimates only. A phone needs its own reserve; virtual
            expansion never increases physical capacity.
          </CardDescription>
        </CardHeader>
        <CardContent className="px-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Model</TableHead>
                  <TableHead>Laptop alone</TableHead>
                  <TableHead>Phone alone</TableHead>
                  <TableHead className="pr-6">Together</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.advisor.slice(0, 4).map((m) => (
                  <TableRow key={m.name}>
                    <TableCell className="pl-6">{m.name}</TableCell>
                    <TableCell>
                      {memoryFit(
                        m.required_gib,
                        data.hardware.ram_gib,
                        data.hardware.available_gib,
                      )}
                    </TableCell>
                    <TableCell>
                      {connected[0]?.hardware
                        ? memoryFit(
                            m.required_gib,
                            connected[0].hardware.physical_ram_gib,
                            connected[0].hardware.available_gib,
                            true,
                          )
                        : "Pair a phone first"}
                    </TableCell>
                    <TableCell className="pr-6">
                      Requires verified split
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>One model. Two devices.</CardTitle>
          <CardDescription>
            Experimental comparison: laptop CPU, phone RPC, then a partial layer
            split. No benchmark has run merely by opening this page.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            First build the matching runtimes using Phone setup. Use a small
            GGUF under 2 GiB. Results include real prompt and generation
            timings, loading time, memory samples, RPC payload counts and
            participation evidence. Phone-only retains a laptop coordinator.
          </p>
          <Button
            variant="outline"
            onClick={() => {
              void downloadCompanion().catch((e) => setError(String(e)));
            }}
          >
            <Download data-icon="inline-start" />
            Download Termux fallback
          </Button>
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Advanced experiment setup
            </summary>
            <form
              className="mt-5"
              onSubmit={(event) => {
                event.preventDefault();
                if (computePeer)
                  void act("experiment", {
                    device_id: computePeer.id,
                    executable,
                    model,
                    remote_layers: layers,
                  });
              }}
            >
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="rpc-engine">
                    RPC-enabled llama-server executable
                  </FieldLabel>
                  <Input
                    id="rpc-engine"
                    value={executable}
                    onChange={(e) => setExecutable(e.target.value)}
                    required
                    placeholder="Choose the trusted build described in setup"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="rpc-model">
                    Small GGUF model path
                  </FieldLabel>
                  <Input
                    id="rpc-model"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    required
                  />
                  <FieldDescription>
                    Your existing model is preserved. This experiment does not
                    download or delete it.
                  </FieldDescription>
                </Field>
                <Field>
                  <FieldLabel htmlFor="remote-layers">
                    Layers to send to phone in the combined test
                  </FieldLabel>
                  <Input
                    id="remote-layers"
                    type="number"
                    min={1}
                    max={16}
                    value={layers}
                    onChange={(e) => setLayers(Number(e.target.value))}
                    required
                  />
                </Field>
                <Button
                  type="submit"
                  disabled={!!busy || data.busy || !computePeer}
                >
                  {busy === "experiment" ? (
                    <BusyIcon />
                  ) : (
                    <ArrowLeftRight data-icon="inline-start" />
                  )}
                  Run real comparison
                </Button>
              </FieldGroup>
            </form>
          </details>
          {data.job.kind === "distributed" && (
            <div role="status" className="flex flex-col gap-2">
              <Badge variant="outline">{data.job.status}</Badge>
              <p className="text-sm">{data.job.message}</p>
              {data.busy && (
                <Button
                  variant="outline"
                  onClick={() => {
                    void api("cancel", {}).catch((e) => setError(String(e)));
                  }}
                >
                  Stop experiment
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        {cluster?.backends.map((b) => (
          <Card key={b.id}>
            <CardHeader>
              <CardTitle>{b.name}</CardTitle>
              <CardDescription>{b.status}</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{b.reason}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Connection & experiment journal</CardTitle>
          <CardDescription>
            Saved evidence stays local and separate from single-device
            recommendations.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {cluster?.reports.length ? (
            cluster.reports.map((r, i) => (
              <div
                key={i}
                className="flex flex-wrap items-center justify-between gap-3"
              >
                <span className="text-sm">
                  {r.kind === "connection"
                    ? "Measured TLS connection test"
                    : "Experimental inference comparison"}
                  {r.finished_at
                    ? ` · ${new Date(r.finished_at * 1000).toLocaleString()}`
                    : ""}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    onEvidence("Connection and inference evidence", r)
                  }
                >
                  Inspect evidence
                </Button>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              No connection or distributed benchmark has been recorded.
            </p>
          )}
        </CardContent>
        <CardFooter>
          <Button
            variant="outline"
            disabled={!cluster?.reports.length}
            onClick={exportResults}
          >
            <Download data-icon="inline-start" />
            Export evidence
          </Button>
        </CardFooter>
      </Card>
      <Dialog
        open={!!pairing}
        onOpenChange={(open) => {
          if (!open) setPairing(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Pair with {pairing?.name}</DialogTitle>
            <DialogDescription>
              {pairing?.protocol === "locallens-companion/2"
                ? "Compare the verification code on both screens. Approve on the phone, then confirm here. Requests expire after two minutes."
                : "Compare this complete fingerprint with the phone companion. Then enter its pairing code and approve the request on the phone."}
            </DialogDescription>
          </DialogHeader>
          {pairing?.protocol === "locallens-companion/2" ? (
            <FieldGroup>
              <Field><FieldLabel>Verification code</FieldLabel>
                <p className="rounded-md bg-muted p-4 font-mono text-2xl tracking-wide">{livePair?.verification_code || "Waiting for request…"}</p>
                <FieldDescription>This code identifies this pairing request. Only confirm if the code in the phone approval dialog matches.</FieldDescription>
              </Field>
              <details><summary className="cursor-pointer text-sm">Full certificate fingerprint</summary><p className="mt-2 break-all font-mono text-xs">{pairing.fingerprint}</p></details>
              <Field orientation="horizontal"><Checkbox id="native-code-match" checked={confirmed} onCheckedChange={(value) => setConfirmed(value === true)} /><FieldLabel htmlFor="native-code-match">The codes match on both screens</FieldLabel></Field>
              <p className="text-sm text-muted-foreground" role="status">{livePair?.message}</p>
              <DialogFooter>
                <Button variant="outline" disabled={!!busy} onClick={async () => { await act("forget", { device_id: pairing.id }); setPairing(null); }}>Cancel pairing</Button>
                <Button disabled={!confirmed || !!busy || !livePair?.verification_code || livePair?.status !== "pending" || livePair?.verified === true} onClick={() => void act("confirm", { device_id: pairing.id })}>{livePair?.verified ? "Waiting for phone approval…" : "Confirm matching code"}</Button>
              </DialogFooter>
            </FieldGroup>
          ) : <form
            onSubmit={async (event) => {
              event.preventDefault();
              if (
                pairing &&
                (await act("pair", {
                  device_id: pairing.id,
                  code,
                  fingerprint_confirmed: confirmed,
                }))
              )
                setPairing(null);
            }}
          >
            <FieldGroup>
              <Field>
                <FieldLabel>Certificate SHA-256</FieldLabel>
                <p className="break-all rounded-md bg-muted p-3 font-mono text-xs">
                  {pairing?.fingerprint}
                </p>
              </Field>
              <Field orientation="horizontal">
                <Checkbox
                  id="fingerprint-match"
                  checked={confirmed}
                  onCheckedChange={(value) => setConfirmed(value === true)}
                />
                <FieldLabel htmlFor="fingerprint-match">
                  The full fingerprint matches my phone
                </FieldLabel>
              </Field>
              <Field>
                <FieldLabel htmlFor="pair-code">Phone pairing code</FieldLabel>
                <Input
                  id="pair-code"
                  autoComplete="off"
                  value={code}
                  maxLength={10}
                  onChange={(e) => setCode(e.target.value.toUpperCase())}
                  required
                />
                <FieldDescription>
                  Pairings last only while both apps are running. You can
                  disconnect and revoke at any time.
                </FieldDescription>
              </Field>
              <DialogFooter>
                <Button
                  type="submit"
                  disabled={!confirmed || code.length !== 10 || !!busy}
                >
                  Request phone approval
                </Button>
              </DialogFooter>
            </FieldGroup>
          </form>}
        </DialogContent>
      </Dialog>
    </div>
  );
}
