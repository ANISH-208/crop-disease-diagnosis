import { translate as t, displayName } from "../i18n";
import { formatDate, isHealthy } from "../utils/reportUtils";

export default function ReportsPage({ language, reports, loading, error, onRetry, onNavigate }) {
  const text = (key) => t(language, key);
  return <section className="farmer-page page-view" aria-labelledby="reports-title">
    <div className="page-intro"><span className="eyebrow">{text("cropChecksEyebrow")}</span><h1 id="reports-title">{text("reports")}</h1><p>{text("reportDescription")}</p></div>
    {loading && !reports.length ? <div className="content-card loading-card" role="status" aria-live="polite"><span className="spinner" aria-hidden="true" />{text("loadingReports")}</div> : error && !reports.length ? <div className="content-card error-card" role="alert"><h2>{text("connectionProblem")}</h2><p>{error}</p><button className="button button-primary" onClick={onRetry}>{text("retry")}</button></div> : reports.length ? <><div className="reports-stack">{reports.map((report) => <article className="content-card report-card" key={report.id}>
      <div className={`report-glyph ${isHealthy(report) ? "healthy" : "attention"}`} aria-hidden="true">{isHealthy(report) ? "✓" : "!"}</div>
      <div className="report-body"><div className="report-topline"><span>{formatDate(report.created_at)}</span><span className={`severity-pill ${String(report.severity).toLowerCase()}`}>{text("severity")}: {displayName(report.severity)}</span></div>
        <h2>{displayName(report.crop)} · {displayName(report.diagnosis)}</h2>
        <p>{displayName(report.symptoms)}</p>
        <div className="report-facts"><span>AI confidence <strong>{Number(report.confidence).toFixed(1)}%</strong></span>{report.status && <span>{text("status")} <strong>{displayName(report.status).replaceAll("_", " ")}</strong></span>}</div>
        {report.expert_review && <p className="expert-note" role="note">{text("expertAdvice")}</p>}
        {isHealthy(report) && <p className="caveat-note">{text("healthyCaveat")}</p>}
        {Array.isArray(report.prevention) && report.prevention.length > 0 && <div className="report-next"><h3>{text("whatNext")}</h3><ol>{report.prevention.map((step, index) => <li key={`${report.id}-${index}`}>{step}</li>)}</ol></div>}
        <p className="confidence-caveat">{text("confidenceNote")}</p>
      </div>
    </article>)}</div>{error && <p className="muted-copy" role="status">Some saved reports could not be refreshed. <button className="inline-retry" onClick={onRetry}>{text("retry")}</button></p>}</> : <div className="content-card empty-reports"><span className="empty-icon" aria-hidden="true">▤</span><h2>{text("noReports")}</h2><button className="button button-primary" onClick={() => onNavigate("scanner")}>{text("startCheck")}</button></div>}
  </section>;
}
