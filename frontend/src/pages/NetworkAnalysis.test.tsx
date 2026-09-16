import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { api } from "../lib/api";
import { NetworkAnalysis } from "./NetworkAnalysis";

const graphCapture = vi.hoisted(() => ({ data: null as any }));

vi.mock("react-force-graph-2d", () => ({
  default: (props: any) => {
    graphCapture.data = props.graphData;
    return <div>Network canvas</div>;
  },
}));
vi.mock("../contexts/ThemeContext", () => ({ useTheme: () => ({ theme: "light" }) }));

class ResizeObserverMock {
  constructor(private readonly callback: ResizeObserverCallback) {}
  observe(target: Element) {
    this.callback([{ target, contentRect: { width: 900, height: 600 } } as ResizeObserverEntry], this as unknown as ResizeObserver);
  }
  disconnect() {}
  unobserve() {}
}

beforeEach(() => {
  vi.stubGlobal("ResizeObserver", ResizeObserverMock);
  vi.spyOn(api.cases, "metadata").mockResolvedValue({
    total: 1,
    items: [{ id: "case-1", case_number: "FIR-1", title: "Test case", description: "", status: "OPEN", entity_count: 1, document_count: 0 }],
  });
  vi.spyOn(api.graph, "getCaseGraph").mockResolvedValue({
    nodes: [{ id: "person-1", label: "Asha Rao", type: "PERSON", confidence_score: 0.9, properties: {} }],
    edges: [],
    stats: null,
  });
  vi.spyOn(api.graph, "getCaseLinkage").mockResolvedValue({ case_id: "case-1", linked_cases: [], source: "graph" });
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  graphCapture.data = null;
});

test("shows explainable leads and sizes a matching node from centrality", async () => {
  vi.spyOn(api.graph, "getCaseInsights").mockResolvedValue({
    case_id: "case-1",
    influential_people: [{
      entity_id: "person-1",
      name: "Asha Rao",
      entity_type: "PERSON",
      centrality: { degree: 0.8, betweenness: 0.4, pagerank: 0.2 },
      explanation: "Connects several otherwise separate evidence clusters.",
    }],
    patterns: [{
      pattern_type: "REPEATED_IDENTIFIER",
      case_ids: ["case-1", "case-2"],
      confidence: 0.76,
      supporting_entity_ids: ["person-1"],
      explanation: "The same verified identifier appears in two cases.",
      disposition: "INVESTIGATIVE_LEAD_NOT_FACT",
    }],
    link_candidates: [{
      source_entity_id: "person-1",
      target_entity_id: "phone-1",
      source_name: "Asha Rao",
      target_name: "Phone ending 0198",
      confidence: 0.65,
      common_neighbor_ids: ["vehicle-1"],
      explanation: "One shared neighbour supports review of this possible link.",
      disposition: "INVESTIGATIVE_LEAD_NOT_FACT",
    }],
    status: "complete",
    warnings: [],
    disclaimer: "Review source evidence before action.",
  });

  render(<MemoryRouter initialEntries={["/network-analysis?caseId=case-1"]}><NetworkAnalysis /></MemoryRouter>);

  expect(await screen.findByText("REPEATED IDENTIFIER")).toBeVisible();
  expect(screen.getByText("The same verified identifier appears in two cases.")).toBeVisible();
  expect(screen.getByText("One shared neighbour supports review of this possible link.")).toBeVisible();
  expect(screen.getByText("Leads, not facts")).toBeVisible();
  expect(screen.getAllByText(/INVESTIGATIVE LEAD NOT FACT/).length).toBe(2);
  await waitFor(() => expect(graphCapture.data?.nodes.find((node: any) => node.id === "person-1")?.val).toBeCloseTo(12.2));
});

test("keeps the graph usable when advanced analytics are unavailable", async () => {
  vi.spyOn(api.graph, "getCaseInsights").mockRejectedValue({ status: 404, message: "Not Found" });

  render(<MemoryRouter initialEntries={["/network-analysis?caseId=case-1"]}><NetworkAnalysis /></MemoryRouter>);

  expect(await screen.findByText("Advanced analytics unavailable")).toBeVisible();
  expect(await screen.findByText("Network canvas")).toBeVisible();
});
