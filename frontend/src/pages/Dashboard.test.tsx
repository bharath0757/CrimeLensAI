import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { api } from "../lib/api";
import type { ConnectionAlert, DashboardOverview } from "../lib/contracts";
import { Dashboard } from "./Dashboard";

vi.mock("../contexts/AuthContext", () => ({ useAuth: () => ({ user: { role: "INVESTIGATOR" } }) }));

const overview: DashboardOverview = {
  generated_at: "2026-09-04T12:00:00Z", data_backend: "postgres",
  metrics: { total_cases: 225, high_risk_cases: 17, active_investigations: 103, linked_networks: 8, money_flow: "149.75", currency: "INR", total_entities: 1000, total_relationships: 30, pending_reviews: 19 },
  statistics: { cases_by_status: { OPEN: 103, CLOSED: 122 }, cases_by_priority: { HIGH: 17 }, entities_by_type: { PHONE: 88 }, transaction_timeline: [{ date: "2026-09-03", amount: "149.75", count: 2 }] },
};
const alert: ConnectionAlert = { id: "alert-1", case_ids: ["case-a", "case-b"], title: "Shared phone across cases", explanation: "The same phone occurs in two FIRs; verify source documents.", severity: "HIGH", status: "NEW", created_at: "2026-09-04T12:00:00Z" };
const open = () => render(<MemoryRouter><Dashboard /></MemoryRouter>);

beforeEach(() => {
  vi.spyOn(api.dashboard, "overview").mockResolvedValue(structuredClone(overview));
  vi.spyOn(api.dashboard, "alerts").mockResolvedValue({ total: 1, unread: 1, items: [alert] });
});

test("renders all five real measures, live charts and source case links", async () => {
  open();
  expect(await within(screen.getByRole("region", { name: "Total Cases" })).findByText("225")).toBeVisible();
  expect(within(screen.getByRole("region", { name: "High Risk Cases" })).getByText("17")).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Linked Networks" })).getByText("8")).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Money Flow" })).getByText("₹149.75")).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Active Investigations" })).getByText("103")).toBeVisible();
  expect(screen.getByRole("region", { name: "Cases by status" })).toHaveTextContent("CLOSED122");
  expect(await screen.findByRole("link", { name: "Review case-a" })).toHaveAttribute("href", "/case-linkage?caseId=case-a");
});

test("graph outage cannot erase valid database metrics or masquerade as no alerts", async () => {
  vi.mocked(api.dashboard.alerts).mockRejectedValue(new Error("Graph unavailable"));
  open();
  expect(await screen.findByText(/Alerts could not refresh: Graph unavailable/)).toBeVisible();
  expect(within(screen.getByRole("region", { name: "Total Cases" })).getByText("225")).toBeVisible();
  expect(screen.queryByText(/No connections on this page/)).not.toBeInTheDocument();
});

test("failed refresh retains a visibly stale snapshot then recovers", async () => {
  open();
  await screen.findByText("225");
  vi.mocked(api.dashboard.overview).mockRejectedValueOnce(new Error("Database unavailable"));
  fireEvent.click(screen.getByRole("button", { name: "Refresh dashboard" }));
  expect(await screen.findByText(/figures may be stale/)).toBeVisible();
  expect(screen.getByText("225")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Refresh dashboard" }));
  await waitFor(() => expect(screen.queryByText(/figures may be stale/)).not.toBeInTheDocument());
});

test("acknowledgement waits for the server and refreshes the persisted queue", async () => {
  vi.spyOn(api.dashboard, "acknowledge").mockResolvedValue({ ...alert, status: "ACKNOWLEDGED" });
  open();
  const acknowledge = await screen.findByRole("button", { name: "Acknowledge" });
  vi.mocked(api.dashboard.alerts).mockResolvedValue({ total: 1, unread: 0, items: [{ ...alert, status: "ACKNOWLEDGED" }] });
  fireEvent.click(acknowledge);
  await screen.findByText("Acknowledged");
  expect(api.dashboard.acknowledge).toHaveBeenCalledExactlyOnceWith("alert-1");
  expect(screen.queryByRole("button", { name: "Acknowledge" })).not.toBeInTheDocument();
  expect(screen.getByText("0 unacknowledged connections")).toBeVisible();
});

test("initial database failure does not render false zero metrics", async () => {
  vi.mocked(api.dashboard.overview).mockRejectedValue(new Error("Database unavailable"));
  open();
  await screen.findByText(/Figures are unavailable, not zero/);
  expect(within(screen.getByRole("region", { name: "Total Cases" })).getByText("—")).toBeVisible();
  expect(screen.queryByRole("region", { name: "Cases by status" })).not.toBeInTheDocument();
});
