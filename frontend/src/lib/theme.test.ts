import { it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useTheme } from "./theme";
it("applies and persists appearance without page-specific color patches", () => {
  const { result } = renderHook(() => useTheme());
  act(() => result.current.setTheme("dark"));
  expect(document.documentElement).toHaveClass("dark");
  expect(localStorage.getItem("locallens-theme")).toBe("dark");
  act(() => result.current.setTheme("light"));
  expect(document.documentElement).not.toHaveClass("dark");
  act(() => result.current.setTheme("system"));
  expect(document.documentElement).not.toHaveClass("dark");
});
