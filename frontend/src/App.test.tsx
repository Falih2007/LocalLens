import { it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { fixture } from "@/test/fixtures";
vi.mock("@/lib/api", () => ({
  api: vi.fn(),
  downloadResults: vi.fn(),
  useAppState: () => ({ data: fixture(), error: null, refresh: vi.fn() }),
}));
it("preserves manual file paths across navigation and uses one main landmark", async () => {
  location.hash = "benchmark";
  const user = userEvent.setup();
  render(<App />);
  const input = await screen.findByLabelText("llama-bench executable");
  await user.type(input, "C:\\AI\\llama-bench.exe");
  await user.type(
    screen.getByLabelText("GGUF model file"),
    "C:\\AI\\model.gguf",
  );
  await user.click(screen.getByRole("button", { name: /^Results$/ }));
  await screen.findByRole("heading", { name: "Benchmark journal." });
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
  location.hash = "history";
  render(<App />);
  await screen.findByRole("heading", { name: "Benchmark journal." });
  await userEvent.click(screen.getAllByRole("button", { name: "Evidence" })[0]);
  expect(await screen.findByRole("dialog")).toBeVisible();
  expect(screen.getByRole("dialog")).toHaveTextContent("Original measurements");
});

it("skip-to-content preserves the current route", async () => {
  location.hash = "history";
  render(<App />);
  await screen.findByRole("heading", { name: "Benchmark journal." });
  await userEvent.click(screen.getByRole("link", { name: "Skip to content" }));
  expect(location.hash).toBe("#history");
  expect(document.getElementById("main-content")).toHaveFocus();
});
