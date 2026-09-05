import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { api, errorMessage } from "../lib/api";
import type { CaseRecord, IngestionReceipt } from "../lib/contracts";

const panel = "rounded-xl border border-surface-200 bg-white p-5 dark:border-surface-800 dark:bg-surface-900";
const control = "w-full rounded-lg border border-surface-300 bg-white p-3 dark:border-surface-700 dark:bg-surface-950";
const button = "rounded-lg bg-primary-600 px-4 py-3 font-medium text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-primary-400";

export function StructuredEvidence() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const caseId = params.get("caseId") || "";
  const batchId = params.get("batchId") || "";
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [search, setSearch] = useState("");
  const [caseError, setCaseError] = useState("");
  const [caseLoading, setCaseLoading] = useState(true);
  const [kind, setKind] = useState<"cdr" | "transactions">("cdr");
  const [file, setFile] = useState<File | null>(null);
  const [receipt, setReceipt] = useState<IngestionReceipt>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitLock = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  useEffect(() => {
    const controller = new AbortController();
    setCaseLoading(true);
    const timer = window.setTimeout(() => {
      void api.cases.metadata(0, 100, search, controller.signal).then(page => {
        if (!controller.signal.aborted) { setCases(page.items); setCaseError(""); }
      }).catch(failure => { if (!controller.signal.aborted) setCaseError(errorMessage(failure)); })
        .finally(() => { if (!controller.signal.aborted) setCaseLoading(false); });
    }, 250);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [search]);

  useEffect(() => {
    if (!batchId || !caseId) { setReceipt(undefined); return; }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const status = await api.ingestion.status(caseId, batchId, controller.signal);
        if (controller.signal.aborted) return;
        setReceipt(status);
        setError("");
        if (status.status !== "COMPLETED") timer = setTimeout(() => void poll(), 2000);
      } catch (failure) {
        if (!controller.signal.aborted) {
          setError(errorMessage(failure));
          timer = setTimeout(() => void poll(), 10_000);
        }
      }
    };
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [caseId, batchId]);

  const upload = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!file || !caseId || submitLock.current) return;
    if (file.size > 10 * 1024 * 1024) { setError("Choose a CSV file no larger than 10 MiB."); return; }
    submitLock.current = true;
    setBusy(true);
    setError("");
    try {
      const next = await api.ingestion.upload(caseId, kind, file);
      if (mounted.current) {
        setReceipt(next);
        setParams({ caseId, batchId: next.id });
      }
    } catch (failure) {
      if (mounted.current) setError(errorMessage(failure));
    } finally {
      submitLock.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  const matchingReceipt = receipt?.id === batchId && receipt.case_id === caseId ? receipt : undefined;
  const displayedKind = matchingReceipt?.kind ?? kind;
  return <div className="space-y-6 text-surface-900 dark:text-surface-100">
    <header><h1 className="text-2xl font-bold">Structured evidence</h1><p className="mt-2 text-sm">Import call records or financial transactions into an existing investigation.</p></header>
    <Link className="text-primary-600 underline dark:text-primary-300" to="/cases/new">Need a case first? Upload an FIR</Link>
    {caseError && <p role="alert">Case search unavailable: {caseError}</p>}
    <form aria-label="Import evidence" onSubmit={event => void upload(event)} className={`${panel} space-y-4`}>
      <label className="block">Search accessible cases<input className={`${control} mt-2`} value={search} onChange={event => setSearch(event.target.value)} placeholder="Case number or title" disabled={busy || Boolean(batchId)} /></label>
      <label className="block">Investigation<select className={`${control} mt-2`} value={caseId} disabled={busy || Boolean(batchId) || caseLoading} onChange={event => { setParams(event.target.value ? { caseId: event.target.value } : {}); setError(""); }} required>
        <option value="">{caseLoading ? "Loading cases…" : "Select a case"}</option>
        {caseId && !cases.some(item => item.id === caseId) && <option value={caseId}>{caseId}</option>}
        {cases.map(item => <option key={item.id} value={item.id}>{item.case_number} — {item.title}</option>)}
      </select></label>
      <p className="text-xs">Search covers the backend case catalogue; up to 100 matches are shown.</p>
      <label className="block">Evidence type<select className={`${control} mt-2`} value={displayedKind} onChange={event => setKind(event.target.value as "cdr" | "transactions")} disabled={busy || Boolean(batchId)}><option value="cdr">Call detail records</option><option value="transactions">Financial transactions</option></select></label>
      <p className="break-words text-sm">Required CSV columns: <code>{displayedKind === "cdr" ? "caller, receiver, timestamp, duration, tower, IMEI" : "sender, receiver, amount, UPI, timestamp, transaction_id"}</code></p>
      <p className="text-sm">UTF-8 CSV, maximum 20,000 rows / 10 MiB. Timestamps need a timezone. Amounts are INR with at most two decimal places. Optional case_id must match the selected case. CDR IDs are recommended; without them, identical call records are deduplicated by content.</p>
      {!batchId && <>
        <label className="block">CSV file<input type="file" accept=".csv,text/csv" className={`${control} mt-2`} disabled={busy} onChange={event => setFile(event.target.files?.[0] || null)} required /></label>
        <button className={button} disabled={busy || !caseId || !file || user?.role === "ANALYST"}>{busy ? "Validating and storing…" : "Import evidence"}</button>
        {user?.role === "ANALYST" && <p className="text-sm">Analysts have read-only access. An investigator or administrator must import evidence.</p>}
      </>}
    </form>
    {error && <p role="alert" className="rounded-lg border border-red-400 p-4 text-red-700 dark:text-red-300">{error}{batchId ? " Current status is unconfirmed; checking will retry automatically." : " No success has been confirmed. Retrying the same file is duplicate-safe."}</p>}
    {batchId && <section className={`${panel} space-y-3`} aria-label="Import status">
      <h2 className="text-lg font-semibold" role="status">{!matchingReceipt ? "Checking import status…" : matchingReceipt.status === "COMPLETED" ? "Evidence stored and graph synchronized" : "Evidence queued for graph synchronization"}</h2>
      <p className="break-all text-sm">Batch: {batchId}</p>
      {matchingReceipt && <>
        <p>{matchingReceipt.inserted_records} new records · {matchingReceipt.duplicate_records} duplicate records skipped</p>
        <p>Graph writes: {matchingReceipt.graph_cursor} / {matchingReceipt.graph_total}</p>
        <progress className="w-full" aria-label="Graph synchronization progress" value={matchingReceipt.graph_cursor} max={Math.max(1, matchingReceipt.graph_total)} />
        <p className="break-all text-xs">Source SHA-256: {matchingReceipt.source_sha256}</p>
        {matchingReceipt.last_error && <p role="status">Graph delivery is retrying automatically. The original evidence is safely stored.</p>}
        <p className="text-sm">Keep this URL to check progress after closing the page. Database writes and completed ingestion are recorded in the audit trail.</p>
        <div className="flex flex-wrap gap-4"><Link className="text-primary-600 underline dark:text-primary-300" to={`/case-linkage?caseId=${encodeURIComponent(caseId)}`}>Review case connections</Link><Link className="text-primary-600 underline dark:text-primary-300" to="/dashboard">View updated dashboard</Link></div>
        {matchingReceipt.status === "COMPLETED" && <button className={button} onClick={() => { setParams({ caseId }); setFile(null); setError(""); }}>Import another file</button>}
      </>}
    </section>}
  </div>;
}
