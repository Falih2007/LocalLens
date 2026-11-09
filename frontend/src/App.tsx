import { lazy, Suspense, useEffect, useState } from "react";
import {
  Activity,
  Network,
  ArrowUpRight,
  Boxes,
  Cpu,
  Gauge,
  History,
  Monitor,
  Moon,
  RefreshCw,
  ScanLine,
  ShieldCheck,
  Sparkles,
  Sun,
  TriangleAlert,
} from "lucide-react";
import {
  Sidebar,
  SidebarProvider,
  SidebarHeader,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarGroupContent,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarInset,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  TooltipProvider,
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { EvidenceDialog, BusyIcon } from "@/components/shared";
import { OverviewPage } from "@/pages/overview";
const AutomaticPage = lazy(() =>
  import("@/pages/automatic").then((module) => ({
    default: module.AutomaticPage,
  })),
);
const ModelsPage = lazy(() =>
  import("@/pages/models").then((module) => ({ default: module.ModelsPage })),
);
const BenchmarkPage = lazy(() =>
  import("@/pages/benchmark").then((module) => ({
    default: module.BenchmarkPage,
  })),
);
import type { ManualConfig } from "@/pages/benchmark";
const HistoryPage = lazy(() =>
  import("@/pages/history").then((module) => ({ default: module.HistoryPage })),
);
import { api, useAppState } from "@/lib/api";
import { useTheme } from "@/lib/theme";
import type { Theme } from "@/lib/theme";
const ConnectPage = lazy(() =>
  import("@/pages/connect").then((module) => ({ default: module.ConnectPage })),
);
const pages = [
  { id: "overview", label: "Overview", icon: Activity },
  { id: "automatic", label: "Find my model", icon: Sparkles },
  { id: "connect", label: "Devices", icon: Network },
  { id: "models", label: "Model advisor", icon: Boxes },
  { id: "benchmark", label: "Manual benchmark", icon: Gauge },
  { id: "history", label: "Results", icon: History },
] as const;
type Page = (typeof pages)[number]["id"];
const currentPage = (): Page => {
  const value = location.hash.slice(1);
  return pages.some((p) => p.id === value) ? (value as Page) : "overview";
};
function WorkspaceNav({
  page,
  navigate,
}: {
  page: Page;
  navigate: (page: Page) => void;
}) {
  const { setOpenMobile } = useSidebar();
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="p-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <ScanLine className="size-4" />
          </div>
          <div className="group-data-[collapsible=icon]:hidden">
            <span className="font-semibold tracking-tight">LocalLens</span>
            <p className="text-[11px] text-muted-foreground">
              Your local AI workspace
            </p>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {pages.map((p) => (
                <SidebarMenuItem key={p.id}>
                  <SidebarMenuButton
                    tooltip={p.label}
                    isActive={page === p.id}
                    aria-current={page === p.id ? "page" : undefined}
                    onClick={() => {
                      navigate(p.id);
                      setOpenMobile(false);
                    }}
                  >
                    <p.icon />
                    <span>{p.label}</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>
      <SidebarFooter className="p-4">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="size-4 shrink-0" />
          <span className="group-data-[collapsible=icon]:hidden">
            Your devices. Your approval.
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground group-data-[collapsible=icon]:hidden">
          LocalLens · development preview
        </span>
      </SidebarFooter>
    </Sidebar>
  );
}
function ThemeMenu() {
  const { theme, setTheme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon" aria-label="Change appearance" />
        }
      >
        <Sun className="dark:hidden" />
        <Moon className="hidden dark:block" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <DropdownMenuLabel>Appearance</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={theme}
            onValueChange={(v) => setTheme(v as Theme)}
          >
            {[
              { value: "light", label: "Light", icon: Sun },
              { value: "dark", label: "Dark", icon: Moon },
              { value: "system", label: "System", icon: Monitor },
            ].map((t) => (
              <DropdownMenuRadioItem key={t.value} value={t.value}>
                <t.icon />
                {t.label}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
export default function App() {
  const { data, error, refresh } = useAppState();
  const [page, setPage] = useState<Page>(currentPage),
    [pending, setPending] = useState(false),
    [actionError, setActionError] = useState<string | null>(null),
    [evidence, setEvidence] = useState<{ title: string; data: unknown } | null>(
      null,
    ),
    [refreshing, setRefreshing] = useState(false);
  useEffect(() => {
    const onHash = () => {
      setPage(currentPage());
      window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  const [manualDraft, setManualDraft] = useState<ManualConfig | undefined>(
    undefined,
  );
  const navigate = (p: Page) => {
    location.hash = p;
    setPage(p);
  };
  const act = async (path: string, body: unknown) => {
    setPending(true);
    setActionError(null);
    try {
      await api(path, body);
      await refresh();
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "The action could not complete.",
      );
    } finally {
      setPending(false);
    }
  };
  const start = (mode: "quick" | "thorough" = "quick") => {
    navigate("automatic");
    void act("auto", { mode });
  };
  const cancel = () => void act("cancel", {});
  const manual = (config: ManualConfig) => void act("run", config);
  const inspect = (title: string, value: unknown) =>
    setEvidence({ title, data: value });
  const refreshHardware = async () => {
    setRefreshing(true);
    setActionError(null);
    try {
      await api("refresh", {});
      await refresh();
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Hardware detection failed.",
      );
    } finally {
      setRefreshing(false);
    }
  };
  return (
    <TooltipProvider>
      <SidebarProvider>
        <a
          href="#main-content"
          className="skip-link"
          onClick={(event) => {
            event.preventDefault();
            document.getElementById("main-content")?.focus();
          }}
        >
          Skip to content
        </a>
        <WorkspaceNav page={page} navigate={navigate} />
        <SidebarInset className="min-w-0">
          <header className="flex h-16 shrink-0 items-center justify-between gap-3 border-b px-4 md:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <SidebarTrigger aria-label="Toggle navigation" />
              <Separator orientation="vertical" className="h-4" />
              <span className="hidden text-xs text-muted-foreground sm:inline">
                Workspace
              </span>
              <span className="hidden text-muted-foreground sm:inline">/</span>
              <span className="truncate text-xs font-medium">
                {pages.find((p) => p.id === page)?.label}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="hidden sm:inline-flex">
                <span className="size-1.5 rounded-full bg-foreground" />
                {error
                  ? "Disconnected"
                  : data
                    ? "On this computer"
                    : "Connecting"}
              </Badge>
              <Tooltip>
                <TooltipTrigger
                  render={
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label="Refresh hardware"
                      disabled={refreshing || !data}
                      onClick={() => void refreshHardware()}
                    />
                  }
                >
                  {refreshing ? <BusyIcon /> : <RefreshCw />}
                </TooltipTrigger>
                <TooltipContent>Refresh detected hardware</TooltipContent>
              </Tooltip>
              <ThemeMenu />
            </div>
          </header>
          <div
            id="main-content"
            tabIndex={-1}
            className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-8 outline-none md:px-8 md:py-10"
          >
            {(error || actionError) && (
              <Alert variant="destructive">
                <TriangleAlert />
                <AlertTitle>
                  {error
                    ? "Connection unavailable"
                    : "Action could not complete"}
                </AlertTitle>
                <AlertDescription>
                  {actionError || error}
                  {error &&
                    " Keep the LocalLens launcher running. Your saved reports remain on disk."}
                </AlertDescription>
              </Alert>
            )}
            {!data ? (
              <div
                className="flex flex-col gap-6"
                role="status"
                aria-label="Loading hardware"
              >
                <Skeleton className="h-8 w-64" />
                <Skeleton className="h-4 max-w-lg" />
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                  {[1, 2, 3, 4].map((n) => (
                    <Card key={n}>
                      <CardContent className="flex flex-col gap-4 pt-4">
                        <Skeleton className="h-4 w-28" />
                        <Skeleton className="h-8 w-24" />
                      </CardContent>
                    </Card>
                  ))}
                </div>
                <p className="text-sm text-muted-foreground">
                  Connecting to your local workspace…
                </p>
              </div>
            ) : (
              <Suspense fallback={<Skeleton className="h-80 w-full" />}>
                {page === "overview" && (
                  <OverviewPage
                    data={data}
                    onScan={() => navigate("automatic")}
                    onStart={() => start()}
                    onHistory={() => navigate("history")}
                    onEvidence={inspect}
                  />
                )}{" "}
                {page === "automatic" && (
                  <AutomaticPage
                    data={data}
                    onStart={start}
                    onCancel={cancel}
                    pending={pending}
                    onEvidence={inspect}
                    onHistory={() => navigate("history")}
                  />
                )}{" "}
                {page === "connect" && (
                  <ConnectPage data={data} onEvidence={inspect} />
                )}
                {page === "models" && <ModelsPage data={data} />}{" "}
                {page === "benchmark" && (
                  <BenchmarkPage
                    data={data}
                    draft={manualDraft}
                    onDraftChange={setManualDraft}
                    onRun={manual}
                    onCancel={cancel}
                    pending={pending}
                  />
                )}{" "}
                {page === "history" && (
                  <HistoryPage
                    data={data}
                    onEvidence={inspect}
                    onStart={() => navigate("automatic")}
                  />
                )}
              </Suspense>
            )}
            <footer className="mt-8 flex flex-wrap justify-between gap-2 border-t pt-5 text-[11px] text-muted-foreground">
              <span>LocalLens</span>
              <span>Measured means measured. Estimated means estimated.</span>
            </footer>
          </div>
        </SidebarInset>
        <EvidenceDialog value={evidence} onClose={() => setEvidence(null)} />
      </SidebarProvider>
    </TooltipProvider>
  );
}
