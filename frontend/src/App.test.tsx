import { beforeEach, it, expect, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { api } from "@/lib/api";
import type { AppState } from "@/lib/types";
import { fixture, scan } from "@/test/fixtures";

let state: AppState;
const refresh = vi.fn(async () => state);
vi.mock("@/lib/api", () => ({
  api: vi.fn(),
  downloadResults: vi.fn(),
  useAppState: () => ({ data: state, error: null, refresh }),
}));

beforeEach(() => {
  location.hash = "";
  state = {
    ...fixture(),
    history: fixture().history.map((result) => ({ ...result, device_scope: "unverified" })),
    scans: [{ ...scan, device_scope: "unverified" }],
    advisor: [{
      name: "Example model", parameters_b: 4, weights_gib: 2.2, required_gib: 4.5,
      status: "Likely fits", evidence: "estimated", assumption: "CPU memory only",
    }],
  };
  vi.mocked(api).mockReset().mockImplementation(async (path) => {
    if (path === "refresh") return state.hardware;
    if (path === "openvino") return { status: "unavailable" };
    if (path === "auto") return { id: "onboarding-run", status: "running" };
  });
});

async function choosePrediction() {
  await userEvent.click(screen.getByRole("button", { name: "Scan & Predict" }));
  await screen.findByRole("heading", { name: "Models that might fit." });
}

it("preserves manual file paths across navigation and uses one main landmark", async () => {
  const user = userEvent.setup();
  render(<App />);
  await choosePrediction();
  await user.click(screen.getByRole("button", { name: /^Manual benchmark$/ }));
  const input = await screen.findByLabelText("llama-bench executable");
  await user.type(input, "C:\\AI\\llama-bench.exe");
  await user.type(
    screen.getByLabelText("GGUF model file"),
    "C:\\AI\\model.gguf",
  );
  await user.click(screen.getByRole("button", { name: /^Results$/ }));
  await screen.findByRole("heading", { name: "Benchmark journal." }, { timeout: 3000 });
  await user.click(screen.getByRole("button", { name: /^Manual benchmark$/ }));
  expect(await screen.findByLabelText("llama-bench executable")).toHaveValue(
    "C:\\AI\\llama-bench.exe",
  );
  expect(screen.getByLabelText("GGUF model file")).toHaveValue(
    "C:\\AI\\model.gguf",
  );
  expect(screen.getAllByRole("main")).toHaveLength(1);
});

it("opens actual saved evidence in the controlled dialog", async () => {
  render(<App />);
  await choosePrediction();
  await userEvent.click(screen.getByRole("button", { name: /^Results$/ }));
  await screen.findByRole("heading", { name: "Benchmark journal." }, { timeout: 3000 });
  await userEvent.click(screen.getAllByRole("button", { name: "Evidence" })[0]);
  expect(await screen.findByRole("dialog")).toBeVisible();
  expect(screen.getByRole("dialog")).toHaveTextContent("Original measurements");
});

it("skip-to-content preserves the current route", async () => {
  render(<App />);
  await choosePrediction();
  await userEvent.click(screen.getByRole("button", { name: /^Results$/ }));
  await screen.findByRole("heading", { name: "Benchmark journal." }, { timeout: 3000 });
  await userEvent.click(screen.getByRole("link", { name: "Skip to content" }));
  expect(location.hash).toBe("#history");
  expect(document.getElementById("main-content")).toHaveFocus();
});

it("gates a deep link until prediction finishes and can return to mode selection", async () => {
  location.hash = "history";
  render(<App />);
  expect(screen.getByRole("heading", { name: "How would you like to test your device?" })).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Benchmark journal." })).not.toBeInTheDocument();
  await choosePrediction();
  expect(screen.getByText("Example model")).toBeVisible();
  expect(screen.getByText(/Intel OpenVINO NPU runtime unavailable/)).toBeVisible();
  expect(vi.mocked(api).mock.calls.map(([path]) => path)).toEqual(["refresh", "openvino", "onboarding/complete"]);
  await userEvent.click(screen.getByRole("button", { name: "Test modes" }));
  expect(screen.getByRole("button", { name: "Run a Benchmark" })).toBeVisible();
  expect(state.scans).toEqual([{ ...scan, device_scope: "unverified" }]);
});

it("follows only its own benchmark and shows saved measurements on completion", async () => {
  const { rerender } = render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Run a Benchmark" }));
  await waitFor(() => expect(api).toHaveBeenCalledWith("auto", { mode: "quick" }, expect.any(AbortSignal)));
  expect(screen.queryByRole("heading", { name: "Find your everyday model." })).not.toBeInTheDocument();
  state = { ...state, busy: true, job: {
    id: "onboarding-run", status: "running", stage: "downloading", download_percent: 40,
  } };
  rerender(<App />);
  expect(await screen.findByRole("progressbar", { name: "Current download progress" })).toHaveAttribute("aria-valuenow", "40");
  state = { ...state, busy: false, job: { id: "onboarding-run", status: "completed" },
    scans: [scan, { ...scan, id: "onboarding-run", recommendation: null }],
  };
  rerender(<App />);
  const comparison = await screen.findByRole("heading", { name: "Latest scan · device comparison" });
  expect(comparison).toBeVisible();
  expect(screen.queryByRole("heading", { name: "Your best tested model" })).not.toBeInTheDocument();
  expect(within(screen.getByRole("table")).getAllByText(/tok\/s/).length).toBeGreaterThan(0);
});

it("waits for cancellation cleanup and offers retry without entering the dashboard", async () => {
  const { rerender } = render(<App />);
  await userEvent.click(screen.getByRole("button", { name: "Run a Benchmark" }));
  await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
  expect(api).toHaveBeenCalledWith("cancel", { id: "onboarding-run" });
  state = { ...state, busy: true, job: { id: "onboarding-run", status: "cancelled" } };
  rerender(<App />);
  expect(screen.getByText("Stopping and cleaning up…")).toBeVisible();
  state = { ...state, busy: false };
  rerender(<App />);
  expect(await screen.findByText("Benchmark cancelled.")).toBeVisible();
  expect(screen.getByRole("button", { name: "Retry" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Test modes" })).not.toBeInTheDocument();
});

it("opens the dashboard without rerunning tests for returning users", async () => {
  state = { ...state, onboarding_complete: true, history: [], scans: [] };
  const first = render(<App />);
  expect(await screen.findByRole("heading", { name: "Your computer, understood." })).toBeVisible();
  expect(api).not.toHaveBeenCalled();
  first.unmount();

  state = { ...state, onboarding_complete: false, scans: [scan] };
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Your best tested model" })).toBeVisible();
  expect(api).not.toHaveBeenCalled();
});
