import { afterEach, expect, test, vi } from "vitest";
import { api } from "./api";

afterEach(() => vi.unstubAllGlobals());

test("multipart evidence sends real file bytes without a JSON content type", async () => {
  localStorage.setItem("crimelens_auth_token", "test-token");
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "document-1" }), { status: 201 }));
  vi.stubGlobal("fetch", fetchMock);
  const file = new File(["FIR evidence"], "fir.txt", { type: "text/plain" });
  await api.documents.upload("case-1", file);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/v1/cases/case-1/documents");
  expect(options.body).toBeInstanceOf(FormData);
  expect(options.body.get("file")).toBe(file);
  expect(options.headers.has("Content-Type")).toBe(false);
  expect(options.headers.get("Authorization")).toBe("Bearer test-token");
});

test("successful delete accepts an empty 204 response", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
  await expect(api.cases.delete("case-1")).resolves.toBeUndefined();
});

test("validation errors name the invalid input", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "title"], msg: "Too short" }] }), { status: 422 })));
  await expect(api.cases.create({ title: "x", description: "test" })).rejects.toMatchObject({ status: 422, message: "title: Too short" });
});

test("dashboard adapts the deployed split endpoints when overview is unavailable", async () => {
  const responses = [
    new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }),
    new Response(JSON.stringify({ total_cases: 2, total_entities: 5, cross_case_links: 1, pending_reviews: 3 })),
    new Response(JSON.stringify({ active_cases: 2, total_relationships: 4 })),
    new Response(JSON.stringify({ cases_by_status: { OPEN: 2 }, cases_by_priority: { HIGH: 1, CRITICAL: 1 }, entities_by_type: { PERSON: 5 } })),
  ];
  vi.stubGlobal("fetch", vi.fn().mockImplementation(() => Promise.resolve(responses.shift())));
  const overview = await api.dashboard.overview();
  expect(overview.metrics).toMatchObject({ total_cases: 2, high_risk_cases: 2, linked_networks: 1, active_investigations: 2 });
  expect(overview.statistics.cases_by_status).toEqual({ OPEN: 2 });
});

test("dashboard marks unavailable legacy alerts without fabricating connections", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 })));
  await expect(api.dashboard.alerts()).resolves.toEqual({ total: 0, unread: 0, items: [], available: false });
});

test("preview passes text and cancellation to the real gateway path", async () => {
  const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ entities: [] })));
  vi.stubGlobal("fetch", fetchMock);
  const controller = new AbortController();
  await api.extraction.preview("Phone: 9123456789", controller.signal);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toBe("/api/v1/extraction/preview");
  expect(JSON.parse(options.body)).toEqual({ text: "Phone: 9123456789" });
  expect(options.signal).toBe(controller.signal);
});
