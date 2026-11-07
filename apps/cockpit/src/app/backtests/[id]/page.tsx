import Link from "next/link";
import { notFound } from "next/navigation";
import { getSession } from "@/lib/auth";
import { apiRequest, BackendError } from "@/lib/backend";
import { isUuid, parseJobDetail, type JobDetail } from "@/lib/backtest-contracts";
import { Shell, jobLabel } from "@/components/dashboard";
import { Login } from "@/components/login";
import { EquityCurve, Provenance, ResultMetrics, ValidationNotice } from "@/components/backtest-result";

export const dynamic = "force-dynamic";
const failures: Record<string, string> = {
  dataset_missing: "Der gebundene Datensatz ist nicht verfügbar.",
  snapshot_invalid: "Die Prüfung des eingefrorenen Datensatzes ist fehlgeschlagen.",
  configuration_mismatch: "Konfiguration und eingefrorene Version stimmen nicht überein.",
  simulation_failed: "Der Simulationslauf ist fehlgeschlagen.",
  attempts_exhausted: "Der Auftrag konnte innerhalb der erlaubten Versuche nicht abgeschlossen werden.",
};
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const session = await getSession();
  if (!session) return <Login />;
  const { id } = await params;
  if (!isUuid(id)) notFound();
  let job: JobDetail | null = null;
  try {
    const candidate = await apiRequest<unknown>(session, `/v1/jobs/${id}`);
    job = parseJobDetail(candidate, session.tenantId, id);
  } catch (error) {
    if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
    if (error instanceof BackendError && error.status === 404) notFound();
  }
  return <Shell session={session} section="backtest" connected={!!job}>
    <Link className="detail-back" href="/backtests">← Alle Forschungsaufträge</Link>
    {!job ? <section className="panel connection-error" role="status"><h2>Ergebnis nicht bestätigt</h2><p>Die geschützte Antwort ist aktuell nicht verfügbar oder entspricht nicht dem erwarteten Ergebnisformat. Es werden keine Leistungsdaten angezeigt.</p><Link className="button secondary" href={`/backtests/${id}`}>Erneut laden</Link></section> : <>
      <section className="panel"><div className="section-heading"><h2>{job.payload.symbol} · H4 · Backtest</h2><span className="badge neutral">{jobLabel(job.status)}</span></div><p className="job-identity">Auftrag <code>{job.id}</code></p>
        {job.result ? <><span className="badge warning">NICHT VALIDIERT</span><ResultMetrics result={job.result} /><p className="form-hint">Profitfaktor „nicht bestimmbar“ bedeutet: keine belastbare endliche Kennzahl. Das ist kein Profitabilitätsnachweis.</p></> : <div className="empty-state"><h3>{job.status === "FAILED" ? "Kein bestätigtes Ergebnis" : job.status === "RUNNING" ? "Simulation wird verarbeitet" : "Auftrag wartet auf Verarbeitung"}</h3><p>{job.status === "FAILED" ? failures[job.failure_code ?? ""] ?? "Der Auftrag ist fehlgeschlagen. Es wird keine Leistung abgeleitet." : "Der tatsächlich gespeicherte Workerstatus wird angezeigt. Während der Verarbeitung liegt noch keine geprüfte Leistung vor."}</p><Link href={`/backtests/${id}`} className="button secondary">Stand aktualisieren</Link></div>}
      </section>
      {job.result && <><ValidationNotice result={job.result} /><section className="panel"><div className="section-heading"><h2>Simulierte Equity nach modellierten Kosten</h2><span className="badge neutral">USDT</span></div><EquityCurve result={job.result} /></section><Provenance result={job.result} /></>}
    </>}
  </Shell>;
}
