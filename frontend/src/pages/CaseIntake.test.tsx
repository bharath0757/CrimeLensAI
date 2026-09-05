import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, expect, test, vi } from "vitest";
import { api } from "../lib/api";
import type { ExtractionPreview } from "../lib/contracts";
import { CaseIntake } from "./CaseIntake";

const saved = { id: "case-1", case_number: "FIR-NEW-1", title: "New FIR", description: "Narrative", status: "OPEN", entity_count: 1, document_count: 1 };
const result: ExtractionPreview = {
  text: "Phone: 9123456789", model: "test-contract", warnings: ["Heuristic confidence"], document_sha256: null,
  entities: [{ entity_id: "mention-1", entity_type: "PHONE", value: "9123456789", normalized_value: "+919123456789", confidence: .98, start_offset: 7, end_offset: 17, source_field: "document_text" }],
};

beforeEach(() => {
  vi.spyOn(api.cases, "create").mockResolvedValue(saved);
  vi.spyOn(api.cases, "get").mockResolvedValue(saved);
  vi.spyOn(api.documents, "upload").mockResolvedValue({ id: "doc-1", case_id: "case-1", original_filename: "fir.txt", processing_status: "PENDING", extracted_entity_count: 0, error_message: null });
  vi.spyOn(api.documents, "process").mockResolvedValue({ success: true, case_id: "case-1", document_id: "doc-1", message: "Completed" });
  vi.spyOn(api.extraction, "preview").mockResolvedValue(result);
  vi.spyOn(api.extraction, "previewFile").mockResolvedValue(result);
});

function openForm() {
  render(<MemoryRouter><CaseIntake /></MemoryRouter>);
  fireEvent.change(screen.getByLabelText(/Case title/), { target: { value: "New FIR" } });
  fireEvent.change(screen.getByLabelText(/FIR number/), { target: { value: "FIR-NEW-1" } });
  fireEvent.change(screen.getByLabelText(/District/), { target: { value: "Lucknow" } });
}

test("narrative preview displays confidence and source offsets without saving", async () => {
  openForm();
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: result.text } });
  fireEvent.click(screen.getByRole("button", { name: "Preview narrative" }));
  expect(await screen.findByText("98%")).toBeInTheDocument();
  expect(screen.getByText(/Characters 7–17/)).toBeInTheDocument();
  expect(screen.getByText("Heuristic confidence")).toBeInTheDocument();
  expect(api.cases.create).not.toHaveBeenCalled();
});

test("file-only FIR saves the actual selected file and waits for processing", async () => {
  openForm();
  const file = new File([result.text], "random-fir.txt", { type: "text/plain" });
  await userEvent.upload(screen.getByLabelText("FIR documents and supporting evidence"), file);
  fireEvent.click(screen.getByRole("button", { name: "Preview random-fir.txt" }));
  expect(await screen.findByText("98%")).toBeInTheDocument();
  expect(api.extraction.previewFile).toHaveBeenCalledWith(file, expect.any(AbortSignal));
  fireEvent.click(screen.getByRole("button", { name: "Save and analyze case" }));
  expect(await screen.findByText("Case saved and processed")).toBeInTheDocument();
  expect(api.documents.upload).toHaveBeenCalledWith("case-1", file);
  expect(api.documents.process).toHaveBeenCalledWith("doc-1");
  expect(api.cases.create).toHaveBeenCalledWith(expect.objectContaining({ case_number: "FIR-NEW-1" }));
});

test("long narrative is retained in an uploaded file while metadata stays bounded", async () => {
  openForm();
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: "Witness statement. ".repeat(300) } });
  fireEvent.click(screen.getByRole("button", { name: "Save and analyze case" }));
  await screen.findByText("Case saved and processed");
  const file = vi.mocked(api.documents.upload).mock.calls[0][1];
  expect(file.size).toBeGreaterThan(2000);
  expect(file.name).toBe("fir-narrative.txt");
  expect(vi.mocked(api.cases.create).mock.calls[0][0].description).toHaveLength(2000);
});

test("processing failure retries the acknowledged document without duplicate case or upload", async () => {
  vi.mocked(api.documents.process).mockRejectedValueOnce(new Error("Graph unavailable"));
  openForm();
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: result.text } });
  fireEvent.click(screen.getByRole("button", { name: "Save and analyze case" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Graph unavailable");
  expect(screen.queryByText("Case saved and processed")).not.toBeInTheDocument();
  expect(screen.getByLabelText("FIR narrative")).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Retry unfinished documents" }));
  await screen.findByText("Case saved and processed");
  expect(api.cases.create).toHaveBeenCalledTimes(1);
  expect(api.documents.upload).toHaveBeenCalledTimes(1);
  expect(api.documents.process).toHaveBeenCalledTimes(2);
});

test("changed narrative discards an in-flight stale preview", async () => {
  let resolve!: (value: ExtractionPreview) => void;
  vi.mocked(api.extraction.preview).mockReturnValue(new Promise(done => { resolve = done; }));
  openForm();
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: result.text } });
  fireEvent.click(screen.getByRole("button", { name: "Preview narrative" }));
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: "Another FIR" } });
  resolve(result);
  await waitFor(() => expect(screen.queryByText("98%")).not.toBeInTheDocument());
  expect(vi.mocked(api.extraction.preview).mock.calls[0][1]?.aborted).toBe(true);
});

test("empty extraction is an honest empty state", async () => {
  vi.mocked(api.extraction.preview).mockResolvedValue({ ...result, entities: [] });
  openForm();
  fireEvent.change(screen.getByLabelText("FIR narrative"), { target: { value: "A complaint without identifiers." } });
  fireEvent.click(screen.getByRole("button", { name: "Preview narrative" }));
  expect(await screen.findByText(/No entities found/)).toBeInTheDocument();
});
