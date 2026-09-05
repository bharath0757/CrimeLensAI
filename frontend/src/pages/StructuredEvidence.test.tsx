import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { api } from "../lib/api";
import type { CaseRecord, IngestionReceipt } from "../lib/contracts";
import { StructuredEvidence } from "./StructuredEvidence";

const auth = vi.hoisted(() => ({ role: "INVESTIGATOR" }));
vi.mock("../contexts/AuthContext", () => ({ useAuth: () => ({ user: auth }) }));
const batch: IngestionReceipt = {
  id: "batch-1", case_id: "case-1", document_id: "doc-1", kind: "transactions",
  source_sha256: "a".repeat(64), record_count: 2, inserted_records: 2, duplicate_records: 0,
  status: "PENDING", graph_cursor: 0, graph_total: 5,
  created_at: "2026-09-04T12:00:00Z", completed_at: null, last_error: null,
};
const completed = { ...batch, status: "COMPLETED" as const, graph_cursor: 5, completed_at: "2026-09-04T12:00:01Z" };
function Location() { return <span aria-label="Current URL">{useLocation().search}</span>; }
const open = (url = "/evidence?caseId=case-1") => render(<MemoryRouter initialEntries={[url]}><StructuredEvidence /><Location /></MemoryRouter>);

beforeEach(() => {
  auth.role = "INVESTIGATOR";
  vi.spyOn(api.cases, "metadata").mockResolvedValue({ items: [{ id: "case-1", case_number: "FIR-001", title: "Synthetic evidence" } as CaseRecord], total: 1 });
  vi.spyOn(api.ingestion, "upload").mockResolvedValue(batch);
  vi.spyOn(api.ingestion, "status").mockResolvedValue(batch);
});
afterEach(() => vi.useRealTimers());

test("uploads the selected file and retains a reloadable batch URL until graph completion", async () => {
  vi.useFakeTimers();
  open();
  const file = new File(["sender,receiver,amount\n"], "transfers.csv", { type: "text/csv" });
  fireEvent.change(screen.getByLabelText("Evidence type"), { target: { value: "transactions" } });
  fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [file] } });
  await act(async () => { fireEvent.submit(screen.getByRole("form", { name: "Import evidence" })); });
  expect(api.ingestion.upload).toHaveBeenCalledExactlyOnceWith("case-1", "transactions", file);
  expect(screen.getByLabelText("Current URL")).toHaveTextContent("caseId=case-1&batchId=batch-1");
  expect(screen.getByRole("status")).toHaveTextContent("Evidence queued for graph synchronization");
  expect(screen.queryByText("Evidence stored and graph synchronized")).not.toBeInTheDocument();
  vi.mocked(api.ingestion.status).mockResolvedValue(completed);
  await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
  expect(screen.getByRole("status")).toHaveTextContent("Evidence stored and graph synchronized");
  expect(screen.getByLabelText("Graph synchronization progress")).toHaveValue(5);
  expect(screen.getByRole("link", { name: "Review case connections" })).toHaveAttribute("href", "/case-linkage?caseId=case-1");
});

test("restores server status and correct evidence type without repeating an upload", async () => {
  vi.mocked(api.ingestion.status).mockResolvedValue(completed);
  open("/evidence?caseId=case-1&batchId=batch-1");
  await screen.findByText("Evidence stored and graph synchronized");
  expect(screen.getByLabelText("Evidence type")).toHaveValue("transactions");
  expect(screen.queryByLabelText("CSV file")).not.toBeInTheDocument();
  expect(api.ingestion.upload).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Import another file" }));
  expect(screen.getByLabelText("CSV file")).toBeVisible();
  expect(screen.getByLabelText("Current URL")).not.toHaveTextContent("batchId");
});

test("failed status lookup does not claim a nonexistent batch was saved", async () => {
  vi.mocked(api.ingestion.status).mockRejectedValue(new Error("Import not found"));
  open("/evidence?caseId=case-1&batchId=wrong-id");
  await screen.findByRole("alert");
  expect(screen.getByRole("status")).toHaveTextContent("Checking import status");
  expect(screen.getByRole("alert")).toHaveTextContent("Current status is unconfirmed");
  expect(screen.queryByText(/Evidence queued/)).not.toBeInTheDocument();
});

test("validation failure permits duplicate-safe retry without a false receipt", async () => {
  vi.mocked(api.ingestion.upload).mockRejectedValueOnce(new Error("Row 2: transaction_id must not be blank"));
  open();
  fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [new File(["bad"], "evidence.csv")] } });
  fireEvent.submit(screen.getByRole("form", { name: "Import evidence" }));
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("transaction_id must not be blank");
  expect(screen.queryByRole("region", { name: "Import status" })).not.toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("button", { name: "Import evidence" })).toBeEnabled());
});

test("analysts cannot submit evidence", () => {
  auth.role = "ANALYST";
  open();
  fireEvent.change(screen.getByLabelText("CSV file"), { target: { files: [new File(["source"], "evidence.csv")] } });
  expect(screen.getByRole("button", { name: "Import evidence" })).toBeDisabled();
  expect(screen.getByText(/Analysts have read-only access/)).toBeVisible();
  expect(api.ingestion.upload).not.toHaveBeenCalled();
});
