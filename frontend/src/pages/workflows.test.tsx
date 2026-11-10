import { describe, it, expect, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HistoryPage } from "./history";
import { AutomaticPage } from "./automatic";
import { BenchmarkPage } from "./benchmark";
import { fixture } from "@/test/fixtures";
import { api } from "@/lib/api";
vi.mock("@/lib/api", () => ({ api: vi.fn(), downloadResults: vi.fn() }));
describe("preserved frontend workflows", () => {
  it("shows saved 4B tests, filters methods, and opens their original evidence", async () => {
    const user = userEvent.setup();
    const onEvidence = vi.fn();
    render(
      <HistoryPage
        data={fixture()}
        onEvidence={onEvidence}
        onStart={vi.fn()}
      />,
    );
    expect(screen.getByText("19.46")).toBeVisible();
    expect(screen.getByText("9.80")).toBeVisible();
    await user.click(screen.getAllByRole("button", { name: "Evidence" })[0]);
    expect(onEvidence).toHaveBeenCalledWith(
      "Qwen3 4B · Q4_K_M",
      expect.objectContaining({
        scan_id: expect.any(String),
        attempt: expect.objectContaining({ target: "gpu" }),
      }),
    );
    await user.click(screen.getByRole("tab", { name: "llama-bench" }));
    expect(screen.queryByText("19.46")).not.toBeInTheDocument();
    expect(screen.getByText("stories15M-q4_0.gguf")).toBeVisible();
  });
  it("starts a quick scan with one click and a broader scan only when selected", async () => {
    const user = userEvent.setup();
    const onStart = vi.fn();
    render(
      <AutomaticPage
        data={fixture()}
        pending={false}
        onStart={onStart}
        onCancel={vi.fn()}
        onEvidence={vi.fn()}
        onHistory={vi.fn()}
      />,
    );
    await user.click(
      screen.getByRole("button", { name: "Find my best model" }),
    );
    expect(onStart).toHaveBeenLastCalledWith("quick");
    await user.click(screen.getByRole("checkbox", { name: "Also test 8B" }));
    await user.click(
      screen.getByRole("button", { name: "Find my best model" }),
    );
    expect(onStart).toHaveBeenLastCalledWith("thorough");
  });
  it("disables new scans while running and preserves Stop", async () => {
    const s = fixture();
    s.busy = true;
    s.job = {
      kind: "automatic",
      status: "running",
      stage: "downloading",
      message: "Downloading verified engine",
      download_percent: 25,
    };
    const onCancel = vi.fn();
    render(
      <AutomaticPage
        data={s}
        pending={false}
        onStart={vi.fn()}
        onCancel={onCancel}
        onEvidence={vi.fn()}
        onHistory={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Find my best model" }),
    ).toBeDisabled();
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "25",
    );
    await userEvent.click(screen.getByRole("button", { name: "Stop test" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
  it("submits the original manual benchmark fields and target", async () => {
    const user = userEvent.setup();
    const onRun = vi.fn();
    render(
      <BenchmarkPage
        data={fixture()}
        pending={false}
        onRun={onRun}
        onRunNpu={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await user.type(
      screen.getByLabelText("llama-bench executable"),
      "C:\\AI\\llama-bench.exe",
    );
    await user.type(
      screen.getByLabelText("GGUF model file"),
      "C:\\AI\\model.gguf",
    );
    await user.click(screen.getByRole("button", { name: "GPU offload" }));
    await user.clear(screen.getByLabelText("CPU threads"));
    await user.type(screen.getByLabelText("CPU threads"), "8");
    await user.click(screen.getByRole("button", { name: "Start benchmark" }));
    expect(onRun).toHaveBeenCalledWith({
      executable: "C:\\AI\\llama-bench.exe",
      model: "C:\\AI\\model.gguf",
      target: "gpu",
      threads: 8,
    });
  });
  it("submits an OpenVINO folder through the separate NPU action", async () => {
    const onRun = vi.fn();
    const onRunNpu = vi.fn();
    render(
      <BenchmarkPage
        data={fixture()}
        pending={false}
        onRun={onRun}
        onRunNpu={onRunNpu}
        onCancel={vi.fn()}
      />,
    );
    const folder = "C:\\AI\\OpenVINO model";
    await userEvent.type(screen.getByLabelText("OpenVINO model folder"), folder);
    await userEvent.click(screen.getByRole("button", { name: "Run NPU benchmark" }));
    expect(onRunNpu).toHaveBeenCalledWith(folder);
    expect(onRun).not.toHaveBeenCalled();
  });
  it("reports the NPU runtime as unavailable without inventing a score", async () => {
    vi.mocked(api).mockResolvedValue({
      status: "unavailable",
      message: "No module named 'openvino'",
      devices: [],
    });
    render(
      <BenchmarkPage
        data={fixture()}
        pending={false}
        onRun={vi.fn()}
        onRunNpu={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Check OpenVINO runtime" }),
    );
    await waitFor(() => expect(screen.getByText("unavailable")).toBeVisible());
    expect(screen.getByText(/No module named/)).toBeVisible();
    expect(api).toHaveBeenCalledWith("openvino");
  });
});
