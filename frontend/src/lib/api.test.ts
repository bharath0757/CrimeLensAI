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
