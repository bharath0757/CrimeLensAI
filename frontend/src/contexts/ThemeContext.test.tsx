import { render, screen } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { ThemeProvider, useTheme } from "./ThemeContext";

function ThemeReader() { return <span>{useTheme().theme}</span>; }

test("legacy dark preference cannot restore the dark investigator interface", () => {
  localStorage.setItem("crimelens-theme", "dark");
  document.documentElement.classList.add("dark");
  render(<ThemeProvider><ThemeReader /></ThemeProvider>);
  expect(screen.getByText("light")).toBeInTheDocument();
  expect(document.documentElement).not.toHaveClass("dark");
  expect(document.documentElement.style.colorScheme).toBe("light");
  expect(localStorage.getItem("crimelens-theme")).toBeNull();
});

test("disabled browser storage does not prevent rendering", () => {
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("Storage disabled"); });
  render(<ThemeProvider><ThemeReader /></ThemeProvider>);
  expect(screen.getByText("light")).toBeInTheDocument();
});
