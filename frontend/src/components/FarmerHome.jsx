import { translate as t, displayName } from "../i18n";
import { formatDate, isHealthy } from "../utils/reportUtils";

export default function FarmerHome({ language, backendState, reports, reportsLoading, reportsError, onTakePhoto, onChoosePhoto, onNavigate }) {
  const text = (key) => t(language, key);
  const latest = reports.slice(0, 3);

  return <section className="farmer-home page-view" aria-labelledby="home-title">
    <div className="home-greeting">
      <div>
        <span className="eyebrow">{text("homeEyebrow")}</span>
        <h1 id="home-title">{text("homeHeadlineFirst")}<br /><em>{text("homeHeadlineSecond")}</em></h1>
        <p>{text("photoPrompt")}</p>
      </div>
      <span className={`connection-chip ${backendState === "healthy" ? "is-ready" : backendState === "offline" ? "is-error" : ""}`} role="status">
        <i aria-hidden="true" />{backendState === "healthy" ? text("serviceReady") : backendState === "offline" || backendState === "degraded" ? text("connectionProblem") : text("checkingService")}
      </span>
    </div>

    <section className="check-card" aria-label={text("checkMyCrop")}>
      <div className="check-card-art" aria-hidden="true"><span>✳</span><i /><b /></div>
      <div className="check-card-copy">
        <span className="step-label">{text("firstStep")}</span>
        <h2>{text("checkMyCrop")}</h2>
        <p>{text("photoPrompt")}</p>
        <div className="check-actions">
          <button className="button button-primary" onClick={onTakePhoto}><span aria-hidden="true">◎</span>{text("takePhoto")}</button>
          <button className="button button-secondary" onClick={onChoosePhoto}><span aria-hidden="true">▧</span>{text("choosePhoto")}</button>
        </div>
      </div>
    </section>

    <div className="home-grid">
      <section className="content-card reports-preview" aria-labelledby="recent-title">
        <div className="card-heading"><div><span className="step-label">{text("cropChecks")}</span><h2 id="recent-title">{text("recentReports")}</h2></div><button className="text-button" onClick={() => onNavigate("reports")}>{text("viewReports")} <span aria-hidden="true">→</span></button></div>
        {reportsError && !latest.length ? <p className="inline-message" role="status">{reportsError}</p> : reportsLoading && !latest.length ? <p className="muted-copy" aria-live="polite">{text("loadingReports")}</p> : latest.length ? <><ul className="report-list">{latest.map((report) => <li key={report.id}><ReportSummary report={report} onClick={() => onNavigate("reports")} /></li>)}</ul>{reportsError && <p className="muted-copy" role="status">Some saved reports could not be refreshed.</p>}</> : <div className="empty-state"><span className="empty-icon" aria-hidden="true">▤</span><p>{text("noReports")}</p><button className="text-button" onClick={onTakePhoto}>{text("startCheck")} →</button></div>}
      </section>

      <section className="content-card photo-tips" aria-labelledby="tips-title">
        <span className="tips-symbol" aria-hidden="true">☼</span>
        <span className="step-label">{text("betterPhoto")}</span>
        <h2 id="tips-title">{text("photoTips")}</h2>
        <ul><li>{text("tipOne")}</li><li>{text("tipTwo")}</li><li>{text("tipThree")}</li></ul>
      </section>
    </div>
  </section>;
}

function ReportSummary({ report, onClick }) {
  return <button className="report-summary" onClick={onClick}>
    <span className={`report-glyph ${isHealthy(report) ? "healthy" : "attention"}`} aria-hidden="true">{isHealthy(report) ? "✓" : "!"}</span>
    <span className="report-summary-copy"><strong>{displayName(report.crop)} · {displayName(report.diagnosis)}</strong><small>{formatDate(report.created_at)} · {displayName(report.severity)} severity</small></span>
    <span className="report-chevron" aria-hidden="true">→</span>
  </button>;
}
