import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test, vi } from "vitest";
import { api } from "../lib/api";
import type { CaseRecord } from "../lib/contracts";
import { CaseLinkage } from "./CaseLinkage";

vi.mock("react-force-graph-2d", () => ({ default: () => <div>Network canvas</div> }));
vi.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light" }) }));

test("notification deep link loads a case outside the first page and shows the real shared identifier", async () => {
  const caseRecord: CaseRecord = { id: "case-alert", case_number: "DEMO-01", title: "Linked FIR", description: "Synthetic evidence", status: "OPEN", entity_count: 1, document_count: 1 };
  vi.spyOn(api.cases, "metadata").mockResolvedValue({ total: 1001, items: [] });
  vi.spyOn(api.cases, "get").mockResolvedValue(caseRecord);
  vi.spyOn(api.graph, "getCaseLinkage").mockResolvedValue({ case_id: "case-alert", source: "graph", linked_cases: [{ case_id: "case-other", link_strength: 0.8, explanation: "Matching normalized phone across two FIRs.", shared_entities: [{ entity_id: "phone-1", entity_type: "PHONE", value: "9000990189", canonical_value: "9000990189", confidence: 0.98 }] }] });
  render(<MemoryRouter initialEntries={["/case-linkage?caseId=case-alert"]}><CaseLinkage /></MemoryRouter>);
  expect(await screen.findByText("9000990189")).toBeVisible();
  expect(screen.getByText("Matching normalized phone across two FIRs.")).toBeVisible();
  expect(screen.getByText(/Candidate lead, not a finding/)).toBeVisible();
  expect(api.cases.get).toHaveBeenCalledExactlyOnceWith("case-alert");
  expect(api.graph.getCaseLinkage).toHaveBeenCalledExactlyOnceWith("case-alert");
  expect(screen.queryByText("CONFIRMED")).not.toBeInTheDocument();
});
