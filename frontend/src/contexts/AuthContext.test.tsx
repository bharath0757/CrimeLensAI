import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { ProtectedRoute } from "../components/ProtectedRoute";
import { api } from "../lib/api";
import { SESSION_EXPIRED_EVENT } from "../lib/auth-events";
import type { UserProfile } from "../lib/contracts";
import { Login } from "../pages/Login";
import { AuthProvider, useAuth } from "./AuthContext";

const officer: UserProfile = { id: "officer-1", email: "officer@example.test", full_name: "Test Officer", is_active: true, role: "INVESTIGATOR" };

function PrivatePage() {
  const { user, logout } = useAuth();
  return <div>Private case for {user?.full_name}<button onClick={() => void logout()}>Log out</button></div>;
}

function openApp(path = "/cases/new") {
  render(<AuthProvider><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/login" element={<Login />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/cases/new" element={<PrivatePage />} />
      <Route path="/dashboard" element={<PrivatePage />} />
    </Route>
  </Routes></MemoryRouter></AuthProvider>);
}

test("unauthenticated direct URL cannot render private cases", async () => {
  const me = vi.spyOn(api.auth, "me");
  openApp();
  expect(await screen.findByRole("button", { name: "Sign In" })).toBeInTheDocument();
  expect(screen.queryByText(/Private case/)).not.toBeInTheDocument();
  expect(me).not.toHaveBeenCalled();
});

test("expired stored token never creates a fake investigator", async () => {
  localStorage.setItem("crimelens_auth_token", "expired");
  vi.spyOn(api.auth, "me").mockRejectedValue({ status: 401 });
  openApp();
  await screen.findByRole("button", { name: "Sign In" });
  expect(localStorage.getItem("crimelens_auth_token")).toBeNull();
  expect(screen.queryByText(/Private case/)).not.toBeInTheDocument();
});

test("login waits for verified officer profile, then logout removes access", async () => {
  vi.spyOn(api.auth, "login").mockResolvedValue({ access_token: "new-test-token", token_type: "bearer", user: officer });
  vi.spyOn(api.auth, "me").mockResolvedValue(officer);
  openApp("/login");
  fireEvent.change(screen.getByLabelText("Username"), { target: { value: officer.email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Test-password-1!" } });
  fireEvent.click(screen.getByRole("button", { name: "Sign In" }));
  expect(await screen.findByText(/Private case for Test Officer/)).toBeInTheDocument();
  expect(api.auth.me).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole("button", { name: "Log out" }));
  await screen.findByRole("button", { name: "Sign In" });
  expect(localStorage.getItem("crimelens_auth_token")).toBeNull();
});

test("revoked API session clears private UI immediately", async () => {
  localStorage.setItem("crimelens_auth_token", "valid-test-token");
  vi.spyOn(api.auth, "me").mockResolvedValue(officer);
  openApp();
  await screen.findByText(/Private case for Test Officer/);
  fireEvent(window, new Event(SESSION_EXPIRED_EVENT));
  await screen.findByRole("button", { name: "Sign In" });
  await waitFor(() => expect(localStorage.getItem("crimelens_auth_token")).toBeNull());
});

test("disabled officer profile is not accepted as an authenticated session", async () => {
  localStorage.setItem("crimelens_auth_token", "disabled-test-token");
  vi.spyOn(api.auth, "me").mockResolvedValue({ ...officer, is_active: false });
  openApp();
  await screen.findByRole("button", { name: "Sign In" });
  expect(screen.queryByText(/Private case/)).not.toBeInTheDocument();
});
