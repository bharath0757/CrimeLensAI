import { useCallback, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { api, errorMessage } from "../lib/api";
import { useLiveResource } from "../lib/useLiveResource";

const panel = "rounded-xl border border-surface-200 bg-white p-5 shadow-sm dark:border-surface-800 dark:bg-surface-900";
const button = "rounded-lg border border-surface-300 px-3 py-2 text-sm font-medium hover:bg-surface-100 focus-visible:outline-2 focus-visible:outline-primary-500 disabled:opacity-50 dark:border-surface-700 dark:hover:bg-surface-800";
const integer = new Intl.NumberFormat("en-IN");
const currency = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 });
const money = (value: string | null) => value === null ? "Unavailable" : currency.format(Number(value));

function BarChart({ title, values }: { title: string; values: Record<string, number> }) {
  const entries = Object.entries(values);
  const max = Math.max(1, ...entries.map(([, count]) => count));
  return <section className={panel} aria-label={title}>
    <h2 className="mb-4 font-semibold">{title}</h2>
    {entries.length === 0 ? <p className="text-sm">No records to display.</p> : <ul className="space-y-3">
      {entries.map(([label, count]) => <li key={label}>
        <div className="mb-1 flex justify-between gap-3 text-sm"><span>{label.replace(/_/g, " ")}</span><span>{integer.format(count)}</span></div>
        <div aria-hidden="true" className="h-2 rounded bg-surface-100 dark:bg-surface-800"><div className="h-2 rounded bg-primary-500" style={{ width: `${100 * count / max}%` }} /></div>
      </li>)}
    </ul>}
  </section>;
}

function ConnectionNotifications() {
  const { user } = useAuth();
  const [offset, setOffset] = useState(0);
  const load = useCallback((signal: AbortSignal) => api.dashboard.alerts(signal, offset), [offset]);
  const alerts = useLiveResource(load);
  const [acknowledging, setAcknowledging] = useState<string | null>(null);
  const busy = useRef(false);
  const [actionError, setActionError] = useState("");
  const acknowledge = async (id: string) => {
    if (busy.current) return;
    busy.current = true;
    setAcknowledging(id);
    setActionError("");
    try {
      await api.dashboard.acknowledge(id);
      await alerts.refresh();
    } catch (failure) {
      setActionError(errorMessage(failure));
    } finally {
      busy.current = false;
      setAcknowledging(null);
    }
  };
  return <section className={panel} aria-label="Connection notifications">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-semibold">Connection notifications</h2>
      <button className={button} disabled={alerts.loading} onClick={() => void alerts.refresh()}>Refresh alerts</button>
    </div>
    <p className="mt-2 text-sm text-surface-600 dark:text-surface-300">Investigative leads, not findings of guilt. Acknowledging records receipt, not confirmation of a link.</p>
    <p className="my-3 text-sm font-medium" role="status">{alerts.data ? `${alerts.data.unread} unacknowledged connections` : alerts.loading ? "Checking for connections…" : "Connection queue unavailable"}</p>
    {alerts.error && <p role="alert" className="my-3 text-sm text-red-700 dark:text-red-300">Alerts could not refresh: {alerts.error}{alerts.data ? " Showing the last successful response." : ""}</p>}
    {actionError && <p role="alert" className="my-3 text-sm text-red-700 dark:text-red-300">Acknowledgement failed: {actionError}</p>}
    {alerts.data?.items.length === 0 && <p className="py-4 text-sm">No connections on this page for your accessible cases.</p>}
    <ul className="divide-y divide-surface-200 dark:divide-surface-800">
      {alerts.data?.items.map(alert => <li key={alert.id} className="space-y-2 py-4">
        <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{alert.title}</h3><span className="rounded bg-amber-100 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">{alert.severity}</span><span className="text-xs">{alert.status === "NEW" ? "New" : "Acknowledged"}</span></div>
        <p className="break-words text-sm">{alert.explanation}</p>
        <p className="text-xs text-surface-500 dark:text-surface-400">{new Date(alert.created_at).toLocaleString()}</p>
        <div className="flex flex-wrap items-center gap-3">
          {alert.case_ids.map(caseId => <Link key={caseId} to={`/case-linkage?caseId=${encodeURIComponent(caseId)}`} className="break-all text-sm text-primary-600 underline dark:text-primary-300">Review {caseId}</Link>)}
          {alert.status === "NEW" && user?.role !== "ANALYST" && <button className={button} disabled={acknowledging !== null || alerts.loading} onClick={() => void acknowledge(alert.id)}>{acknowledging === alert.id ? "Recording…" : "Acknowledge"}</button>}
        </div>
      </li>)}
    </ul>
    {alerts.data && alerts.data.total > 20 && <div className="mt-3 flex items-center gap-3">
      <button className={button} disabled={offset === 0 || alerts.loading} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous alerts</button>
      <span className="text-sm">Page {offset / 20 + 1}</span>
      <button className={button} disabled={offset + 20 >= alerts.data.total || alerts.loading} onClick={() => setOffset(offset + 20)}>Next alerts</button>
    </div>}
  </section>;
}

export function Dashboard() {
  const overview = useLiveResource(api.dashboard.overview);
  const metrics = overview.data?.metrics;
  const cards = [
    ["Total Cases", metrics && integer.format(metrics.total_cases), "Cases you can access"],
    ["High Risk Cases", metrics && integer.format(metrics.high_risk_cases), "Marked HIGH or CRITICAL priority"],
    ["Linked Networks", metrics && integer.format(metrics.linked_networks), "Case groups sharing strong identifiers"],
    ["Money Flow", metrics && money(metrics.money_flow), "Recorded transactions in INR; not proven losses"],
    ["Active Investigations", metrics && integer.format(metrics.active_investigations), "OPEN and IN PROGRESS cases"],
  ];
  return <div className="space-y-6 text-surface-900 dark:text-surface-100">
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-2xl font-bold">Investigator Dashboard</h1><p className="mt-1 text-sm text-surface-600 dark:text-surface-300">Live evidence overview · refreshes every 30 seconds while visible</p></div>
      <button className={button} disabled={overview.loading} onClick={() => void overview.refresh()}>{overview.loading ? "Refreshing…" : "Refresh dashboard"}</button>
    </header>
    {overview.error && <p role="alert" className="rounded-lg border border-red-300 p-3 text-sm text-red-700 dark:text-red-300">Dashboard could not refresh: {overview.error}{overview.data ? " Showing the last successful snapshot; figures may be stale." : " Figures are unavailable, not zero."}</p>}
    <p role="status" className="text-xs text-surface-600 dark:text-surface-300">{overview.data ? `Snapshot: ${new Date(overview.data.generated_at).toLocaleString()} · ${overview.data.data_backend === "postgres" ? "PostgreSQL" : "In-memory demo; financial totals unavailable"}` : overview.loading ? "Loading case metrics…" : "No dashboard snapshot available"}</p>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
      {cards.map(([label, value, description]) => <section key={label} aria-label={label} className={`${panel} min-w-0`}>
        <h2 className="text-sm font-medium">{label}</h2>
        {value !== undefined ? <p className="my-3 break-words text-2xl font-bold">{value}</p> : overview.loading ? <div aria-label="Loading metric" className="my-3 h-8 animate-pulse rounded bg-surface-200 dark:bg-surface-700" /> : <p className="my-3 text-2xl">—</p>}
        <p className="text-xs text-surface-600 dark:text-surface-300">{description}</p>
      </section>)}
    </div>
    {metrics && <p className="text-sm">{integer.format(metrics.total_entities)} extracted entities · {integer.format(metrics.pending_reviews)} awaiting review. Shared identifiers suggest leads; human verification is required.</p>}
    <ConnectionNotifications />
    {overview.data && <>
      <div className="grid gap-4 md:grid-cols-3">
        <BarChart title="Cases by status" values={overview.data.statistics.cases_by_status} />
        <BarChart title="Cases by priority" values={overview.data.statistics.cases_by_priority} />
        <BarChart title="Entities by type" values={overview.data.statistics.entities_by_type} />
      </div>
      <section className={panel} aria-label="Transaction activity">
        <h2 className="font-semibold">Transaction activity</h2>
        <p className="my-2 text-xs">Most recent 30 days with recorded transactions, grouped by UTC date. Totals include all accessible recorded transactions.</p>
        {overview.data.statistics.transaction_timeline.length === 0 ? <p className="py-3 text-sm">No transaction history available.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Recorded daily transaction amounts</caption><thead><tr><th className="py-2">Date (UTC)</th><th>Transactions</th><th>Amount (INR)</th></tr></thead><tbody>{overview.data.statistics.transaction_timeline.map(day => <tr key={day.date} className="border-t border-surface-200 dark:border-surface-800"><th scope="row" className="py-2 font-normal">{day.date}</th><td>{integer.format(day.count)}</td><td>{money(day.amount)}</td></tr>)}</tbody></table></div>}
      </section>
    </>}
    <nav aria-label="Investigation tools" className="flex flex-wrap gap-4">
      <Link className={button} to="/cases/new">Upload FIR</Link><Link className={button} to="/network">Open Network Analysis</Link><Link className={button} to="/case-linkage">Explore Case Linkages</Link><Link className={button} to="/audit">Audit Trail</Link>
    </nav>
  </div>;
}
