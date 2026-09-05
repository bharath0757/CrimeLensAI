import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../lib/api";
import type { CaseRecord, ExtractionPreview } from "../lib/contracts";
import { submitIntake } from "../lib/intake";
import type { IntakeCheckpoint } from "../lib/intake";

const panel = "rounded-xl border border-surface-200 bg-white p-6 dark:border-surface-800 dark:bg-surface-900";
const input = "mt-2 w-full rounded-lg border border-surface-300 bg-white p-3 text-surface-900 focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60 dark:border-surface-700 dark:bg-surface-800 dark:text-white";
const button = "rounded-lg bg-primary-600 px-5 py-3 font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50";
const accepted = ".txt,.pdf,.docx,.csv,.json,.log";
const emptyMetadata = { title: "", firNumber: "", district: "", filedDate: "", category: "" };

export function CaseIntake() {
  const [metadata, setMetadata] = useState(emptyMetadata);
  const [firText, setFirText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<ExtractionPreview | null>(null);
  const [previewSource, setPreviewSource] = useState("");
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [visibleCount, setVisibleCount] = useState(100);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [savedCase, setSavedCase] = useState<CaseRecord | null>(null);
  const checkpoint = useRef<IntakeCheckpoint>({ documents: {}, completed: [] });
  const submitting = useRef(false);
  const previewRequest = useRef<AbortController | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const locked = busy || Boolean(checkpoint.current.caseId);
  const valid = metadata.title.trim().length >= 3 && metadata.firNumber.trim() && metadata.district.trim()
    && (firText.trim() || files.length > 0);
  // Python source offsets count Unicode code points, not JavaScript UTF-16 units.
  const previewCharacters = preview ? Array.from(preview.text) : [];

  useEffect(() => () => previewRequest.current?.abort(), []);

  function clearPreview() {
    previewRequest.current?.abort();
    previewRequest.current = null;
    setPreviewBusy(false);
    setPreview(null);
    setPreviewError("");
    setVisibleCount(100);
  }

  async function extract(file?: File) {
    clearPreview();
    const controller = new AbortController();
    previewRequest.current = controller;
    setPreviewBusy(true);
    setPreviewSource(file ? file.name : "Pasted FIR narrative");
    try {
      const result = file
        ? await api.extraction.previewFile(file, controller.signal)
        : await api.extraction.preview(firText, controller.signal);
      if (!controller.signal.aborted) setPreview(result);
    } catch (failure) {
      if (!controller.signal.aborted) setPreviewError(errorMessage(failure));
    } finally {
      if (!controller.signal.aborted) setPreviewBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!valid || submitting.current || savedCase) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    clearPreview();
    try {
      const evidence = files.map((file, index) => ({ key: `file-${index}`, file }));
      if (firText.trim()) evidence.unshift({
        key: "narrative", file: new File([firText], "fir-narrative.txt", { type: "text/plain;charset=utf-8" }),
      });
      const result = await submitIntake({
        title: metadata.title.trim(), case_number: metadata.firNumber.trim(),
        // Full text is retained in the evidence file; metadata has a 2,000-character limit.
        description: firText.trim().slice(0, 2000) || `FIR evidence uploaded for ${metadata.district.trim()}.`,
        tags: [metadata.category, `district:${metadata.district.trim()}`,
          metadata.filedDate ? `filed:${metadata.filedDate}` : ""].filter(Boolean),
      }, evidence, checkpoint.current, setProgress);
      setSavedCase(result);
      setProgress("All selected documents have completed extraction and graph synchronization.");
    } catch (failure) {
      setError(errorMessage(failure));
      setProgress("");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }

  function startAnother() {
    checkpoint.current = { documents: {}, completed: [] };
    setSavedCase(null);
    setMetadata(emptyMetadata);
    setFirText("");
    setFiles([]);
    setError("");
    setProgress("");
    clearPreview();
    if (fileInput.current) fileInput.current.value = "";
  }

  return (
    <div className="space-y-6 text-surface-900 dark:text-white">
      <header>
        <h1 className="text-2xl font-bold">Case Intake</h1>
        <p className="mt-2 text-surface-600 dark:text-surface-300">Read a new FIR, review extracted candidates, and save its evidence for cross-case analysis.</p>
      </header>
      <form onSubmit={submit} className="grid grid-cols-1 items-start gap-6 lg:grid-cols-2" aria-busy={busy}>
        <div className="min-w-0 space-y-6">
          <fieldset disabled={locked} className={`${panel} space-y-4`}>
            <legend className="sr-only">Case details</legend>
            <h2 className="text-lg font-semibold">Case details</h2>
            <label className="block" htmlFor="case-title">Case title *
              <input id="case-title" className={input} required minLength={3} maxLength={150} value={metadata.title}
                onChange={e => setMetadata({ ...metadata, title: e.target.value })} />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label htmlFor="fir-number">FIR number *
                <input id="fir-number" required maxLength={100} className={input} value={metadata.firNumber}
                  onChange={e => setMetadata({ ...metadata, firNumber: e.target.value })} />
              </label>
              <label htmlFor="district">District *
                <input id="district" required maxLength={100} className={input} value={metadata.district}
                  onChange={e => setMetadata({ ...metadata, district: e.target.value })} />
              </label>
              <label htmlFor="filed-date">Filed date
                <input id="filed-date" type="date" className={input} value={metadata.filedDate}
                  onChange={e => setMetadata({ ...metadata, filedDate: e.target.value })} />
              </label>
              <label htmlFor="category">Category
                <select id="category" className={input} value={metadata.category}
                  onChange={e => setMetadata({ ...metadata, category: e.target.value })}>
                  <option value="">Select category</option>
                  <option value="missing_person">Missing person</option>
                  <option value="financial_fraud">Financial fraud</option>
                  <option value="cyber_crime">Cyber crime</option>
                  <option value="theft">Theft</option>
                  <option value="other">Other</option>
                </select>
              </label>
            </div>
          </fieldset>
          <section className={panel}>
            <label htmlFor="fir-text" className="font-semibold">FIR narrative</label>
            <p id="narrative-help" className="mt-2 text-sm text-surface-600 dark:text-surface-300">Paste text, upload documents below, or provide both. The full narrative is retained as a source document.</p>
            <textarea id="fir-text" aria-describedby="narrative-help" className={`${input} font-mono text-sm`} rows={10}
              maxLength={500000} disabled={locked} value={firText}
              onChange={e => { setFirText(e.target.value); clearPreview(); }} />
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <span className="text-xs text-surface-500 dark:text-surface-300">{firText.length.toLocaleString()} / 500,000 characters</span>
              <button type="button" className={button} onClick={() => extract()} disabled={!firText.trim() || previewBusy || busy}>Preview narrative</button>
            </div>
          </section>
          <section className={`${panel} space-y-3`}>
            <label htmlFor="fir-files" className="font-semibold">FIR documents and supporting evidence</label>
            <p id="file-help" className="text-sm text-surface-600 dark:text-surface-300">TXT, text-based PDF, DOCX, CSV, JSON or LOG. Up to 10 files, 50 MB each. Scanned documents require OCR before upload. CSV previews extract text only; they do not create call or transfer relationships.</p>
            <input ref={fileInput} id="fir-files" aria-describedby="file-help" type="file" multiple accept={accepted}
              disabled={locked} className="w-full min-w-0 text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary-600 file:p-3 file:text-white"
              onChange={e => {
                const selected = Array.from(e.target.files || []);
                clearPreview();
                if (selected.length > 10 || selected.some(file => file.size > 50 * 1024 * 1024 || !accepted.split(",").some(ext => file.name.toLowerCase().endsWith(ext)))) {
                  setError("Choose up to 10 supported files, each no larger than 50 MB.");
                  e.target.value = "";
                  setFiles([]);
                } else { setFiles(selected); setError(""); }
              }} />
            <ul className="space-y-2">
              {files.map((file, index) => <li key={`${index}-${file.name}`} className="flex items-center justify-between gap-3 rounded-lg bg-surface-100 p-3 dark:bg-surface-800">
                <span className="min-w-0 break-all text-sm">{file.name} ({Math.ceil(file.size / 1024)} KB)</span>
                <button type="button" className="shrink-0 rounded px-3 py-2 text-primary-600 underline dark:text-primary-300 disabled:opacity-50" disabled={previewBusy || busy} onClick={() => extract(file)} aria-label={`Preview ${file.name}`}>Preview</button>
              </li>)}
            </ul>
          </section>
        </div>
        <div className="min-w-0 space-y-6">
          <section className={`${panel} space-y-4`} aria-busy={previewBusy} aria-label="Extraction preview">
            <h2 className="text-lg font-semibold">Extraction preview</h2>
            <p className="text-sm text-surface-600 dark:text-surface-300">Candidates, not findings of guilt. Confidence is a heuristic, not a probability. An officer must review identities and connections.</p>
            {previewBusy && <div role="status" className="animate-pulse rounded-lg bg-surface-100 p-8 dark:bg-surface-800">Reading and extracting entities…</div>}
            {previewError && <p role="alert" className="rounded-lg border border-red-400 p-3 text-red-700 dark:text-red-300">{previewError}</p>}
            {!preview && !previewBusy && !previewError && <p className="rounded-lg border border-dashed border-surface-400 p-8 text-center text-surface-600 dark:text-surface-300">Choose Preview to inspect a narrative or document. A preview does not save a case.</p>}
            {preview && <>
              <p role="status" className="break-words text-sm">{preview.entities.length} mentions in {previewSource}. Model: {preview.model}.</p>
              {preview.warnings.length > 0 && <ul className="rounded-lg border border-amber-400 p-3 text-sm text-amber-800 dark:text-amber-200">{preview.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}
              {preview.entities.length === 0 && <p>No entities found. You can still save this FIR for investigation.</p>}
              <ul className="max-h-[32rem] space-y-3 overflow-y-auto">
                {preview.entities.slice(0, visibleCount).map((entity, i) => <li key={`${entity.entity_id}-${i}`} className="rounded-lg border border-surface-200 p-3 dark:border-surface-700">
                  <div className="flex items-start justify-between gap-3">
                    <span className="min-w-0 break-all font-medium">{entity.value}</span>
                    <span className="shrink-0 text-sm">{Math.round(entity.confidence * 100)}%</span>
                  </div>
                  <p className="mt-1 text-xs text-surface-600 dark:text-surface-300">{entity.entity_type} · Characters {entity.start_offset}–{entity.end_offset}</p>
                  <p className="mt-2 break-words font-mono text-xs text-surface-600 dark:text-surface-300">{previewCharacters.slice(Math.max(0, entity.start_offset - 40), entity.end_offset + 40).join("")}</p>
                </li>)}
              </ul>
              {preview.entities.length > visibleCount && <button type="button" className={button} onClick={() => setVisibleCount(count => count + 100)}>Show more mentions</button>}
            </>}
          </section>
          <section className={`${panel} space-y-4`}>
            {error && <div role="alert" className="rounded-lg border border-red-400 p-4 text-red-700 dark:text-red-300">
              <p>{error}</p>
              {checkpoint.current.caseId && <p className="mt-2 break-all text-sm">Case {checkpoint.current.caseId} is saved. Keep this page open and retry to continue its unfinished documents.</p>}
            </div>}
            {progress && <p role="status" className="text-sm">{progress}</p>}
            {savedCase ? <div className="space-y-3">
              <h2 className="text-lg font-semibold">Case saved and processed</h2>
              <p>{savedCase.case_number}: {savedCase.document_count} documents, {savedCase.entity_count} extracted entities.</p>
              <p className="text-sm text-surface-600 dark:text-surface-300">Open the case in the dashboard to review candidate connections. Evidence integrity is checked separately in Audit Trail.</p>
              <div className="flex flex-wrap gap-4">
                <Link className="text-primary-600 underline dark:text-primary-300" to="/dashboard">Open dashboard</Link>
                <Link className="text-primary-600 underline dark:text-primary-300" to="/audit">Open audit trail</Link>
              </div>
              <button type="button" onClick={startAnother} className={button}>Start another case</button>
            </div> : <>
              <p className="text-sm text-surface-600 dark:text-surface-300">Saving uploads the actual documents, extracts their entities, and waits for graph synchronization. Preview results are never used as trusted evidence.</p>
              <button type="submit" className={`${button} w-full`} disabled={!valid || busy || previewBusy}>
                {busy ? "Processing evidence…" : checkpoint.current.caseId ? "Retry unfinished documents" : "Save and analyze case"}
              </button>
            </>}
          </section>
        </div>
      </form>
      <Link className="text-primary-600 underline dark:text-primary-300" to="/evidence">Import CDR or transaction CSV into an existing case</Link>
    </div>
  );
}
