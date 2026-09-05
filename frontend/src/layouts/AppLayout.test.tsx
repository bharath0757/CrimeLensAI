import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { AppLayout } from "./AppLayout";

const { logout } = vi.hoisted(() => ({ logout: vi.fn().mockResolvedValue(undefined) }));
vi.mock("../contexts/AuthContext", () => ({
  useAuth: () => ({ user: { full_name: "Test Officer", role: "INVESTIGATOR" }, logout }),
}));

function openShell() {
  return render(<MemoryRouter initialEntries={["/dashboard"]}><Routes>
    <Route element={<AppLayout />}>
      <Route path="/dashboard" element={<h1>Dashboard content</h1>} />
      <Route path="/cases/new" element={<h1>Case intake content</h1>} />
    </Route>
    <Route path="/login" element={<h1>Signed out</h1>} />
  </Routes></MemoryRouter>);
}

test("navigation has an active state, officer identity and no dark mode control", () => {
  openShell();
  expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByText("Test Officer")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /dark mode/i })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Skip to workspace" })).toHaveAttribute("href", "#workspace");
});

test("mobile navigation opens, Escape closes it and restores focus", () => {
  openShell();
  fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(screen.getByRole("button", { name: "Close navigation" })).toHaveAttribute("aria-expanded", "true");
  expect(document.querySelector(".workspace-body")).toHaveAttribute("inert");
  fireEvent.keyDown(window, { key: "Escape" });
  expect(screen.getByRole("button", { name: "Open navigation" })).toHaveFocus();
  expect(document.querySelector(".workspace-body")).not.toHaveAttribute("inert");
});

test("selecting an investigation route closes the mobile menu", () => {
  openShell();
  fireEvent.click(screen.getByRole("button", { name: "Open navigation" }));
  fireEvent.click(screen.getByRole("link", { name: "Case Intake" }));
  expect(screen.getByRole("heading", { name: "Case intake content" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open navigation" })).toHaveAttribute("aria-expanded", "false");
});

test("sign out keeps the real authentication callback", async () => {
  openShell();
  fireEvent.click(screen.getByRole("button", { name: "Logout" }));
  await waitFor(() => expect(screen.getByRole("heading", { name: "Signed out" })).toBeInTheDocument());
  expect(logout).toHaveBeenCalledTimes(1);
});
