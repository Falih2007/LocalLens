import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConnectPage, type ClusterState, type Peer } from "./connect";
import { fixture } from "@/test/fixtures";
import { api } from "@/lib/api";
vi.mock("@/lib/api", () => ({ api: vi.fn() }));

const empty = (): ClusterState => ({
  devices: [],
  message: "Open the companion on the same Wi-Fi.",
  scanning: false,
  summary: {
    connected_workers: 0,
    total_reported_physical_gib: 32,
    local_model_budget_gib: 12,
    actual_usable_cluster_capacity_gib: null,
    capacity_note: "Physical memory is inventory, not pooled model capacity.",
  },
  backends: [],
  reports: [],
});
let state: ClusterState;
beforeEach(() => {
  state = empty();
  vi.mocked(api)
    .mockReset()
    .mockImplementation(async (path) =>
      path === "connect/state" ? structuredClone(state) : { status: "pending" },
    );
});
describe("Connect Devices trust and evidence", () => {
  it("starts empty, never invents an OPPO or benchmark, and allows a manual rescan", async () => {
    const user = userEvent.setup();
    render(<ConnectPage data={fixture()} onEvidence={vi.fn()} />);
    await screen.findByText("No companion discovered yet");
    expect(screen.queryByText("OPPO A77")).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "No connection or distributed benchmark has been recorded.",
      ),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Run real comparison" }),
    ).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Add device" }));
    await waitFor(() => expect(api).toHaveBeenCalledWith("connect/scan", {}));
  });
  it("requires matching fingerprint and code before requesting separate phone approval", async () => {
    const user = userEvent.setup();
    const peer: Peer = {
      id: "test",
      name: "Test companion fixture",
      fingerprint: "a".repeat(64),
      status: "available",
    };
    state.devices = [peer];
    render(<ConnectPage data={fixture()} onEvidence={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Connect" }));
    const request = screen.getByRole("button", {
      name: "Request phone approval",
    });
    expect(request).toBeDisabled();
    await user.type(screen.getByLabelText("Phone pairing code"), "AB12345678");
    expect(request).toBeDisabled();
    await user.click(
      screen.getByRole("checkbox", {
        name: "The full fingerprint matches my phone",
      }),
    );
    await user.click(request);
    await waitFor(() =>
      expect(api).toHaveBeenCalledWith("connect/pair", {
        device_id: "test",
        code: "AB12345678",
        fingerprint_confirmed: true,
      }),
    );
    expect(
      screen.queryByText("Test companion fixture · contributing"),
    ).not.toBeInTheDocument();
  });
  it("reports action failures and leaves measurements absent", async () => {
    const user = userEvent.setup();
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "connect/scan")
        throw new Error("Wi-Fi discovery unavailable");
      return path === "connect/state" ? state : {};
    });
    render(<ConnectPage data={fixture()} onEvidence={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Add device" }));
    expect(
      await screen.findByText("Wi-Fi discovery unavailable"),
    ).toBeVisible();
    expect(
      screen.getByText(
        "No connection or distributed benchmark has been recorded.",
      ),
    ).toBeVisible();
  });
  it("native pairing sends a request then requires code comparison before confirmation", async () => {
    const user = userEvent.setup();
    state.devices = [{ id: "native", name: "Native fixture", fingerprint: "a".repeat(64), protocol: "locallens-companion/2", status: "available" }];
    vi.mocked(api).mockImplementation(async (path) => {
      if (path === "connect/pair") state.devices[0] = { ...state.devices[0], status: "pending", verification_code: "AAAA AAAA AAAA AAAA" };
      return path === "connect/state" ? structuredClone(state) : { status: "pending" };
    });
    render(<ConnectPage data={fixture()} onEvidence={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Connect" }));
    expect(api).toHaveBeenCalledWith("connect/pair", { device_id: "native" });
    expect(await screen.findByText("AAAA AAAA AAAA AAAA")).toBeVisible();
    const confirm = screen.getByRole("button", { name: "Confirm matching code" });
    expect(confirm).toBeDisabled();
    expect(screen.queryByLabelText("Phone pairing code")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "The codes match on both screens" }));
    await user.click(confirm);
    expect(api).toHaveBeenCalledWith("connect/confirm", { device_id: "native" });
  });
  it("remembered devices can reconnect or be forgotten", async () => {
    const user = userEvent.setup();
    state.devices = [{ id: "native", name: "Remembered fixture", fingerprint: "a".repeat(64), protocol: "locallens-companion/2", status: "disconnected", remembered: true }];
    render(<ConnectPage data={fixture()} onEvidence={vi.fn()} />);
    await user.click(await screen.findByRole("button", { name: "Reconnect" }));
    expect(api).toHaveBeenCalledWith("connect/resume", { device_id: "native" });
    await user.click(screen.getByRole("button", { name: "Forget device" }));
    expect(api).toHaveBeenCalledWith("connect/forget", { device_id: "native" });
  });
});
