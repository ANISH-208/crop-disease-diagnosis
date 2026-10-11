import { translate as t, displayName } from "../i18n";
import { formatDate, isHealthy } from "../utils/reportUtils";

export default function FarmerHome({ language, backendState, diagnosisAvailable, diagnosisUnavailableReason, reports, reportsLoading, reportsError, onTakePhoto, onChoosePhoto, onNavigate }) {
  const text = (key) => t(language, key);
  const latest = reports.slice(0, 3);

  return <section className="farmer-home page-view" aria-labelledby="home-title">
    <section className="field-hero" aria-label={text("checkMyCrop")}>
      <div className="field-hero-copy">
        <span className="field-badge"><i aria-hidden="true">✳</i>{text("homeEyebrow")}</span>
        <h1 id="home-title">{text("homeHeadlineFirst")}<br /><em>{text("homeHeadlineSecond")}</em></h1>
        <p>{text("photoPrompt")}</p>
        <div className="field-hero-actions">
          <button className="button button-primary" onClick={onTakePhoto}>
            <CameraIcon />{text("takePhoto")}
          </button>
          <button className="button button-secondary" onClick={onChoosePhoto}>
            <GalleryIcon />{text("choosePhoto")}
          </button>
        </div>
        {!diagnosisAvailable && diagnosisUnavailableReason && <p className="photo-check-unavailable" role="status">{diagnosisUnavailableReason}</p>}
        <p className="field-hero-note"><ShieldIcon />{text("photoSentOnlyOnAction")}</p>
      </div>
      <BotanicalArtwork backendState={backendState} diagnosisAvailable={diagnosisAvailable} text={text} />
    </section>

    <section className="field-process" aria-labelledby="process-title">
      <div className="field-section-heading">
        <div><span className="step-label">{text("processEyebrow")}</span><h2 id="process-title">{text("processTitle")}</h2></div>
        <p>{text("processNote")}</p>
      </div>
      <div className="process-cards">
        <ProcessCard number="01" title={text("stepPhotoTitle")} detail={text("stepPhotoDetail")} />
        <ProcessCard number="02" title={text("stepCheckTitle")} detail={text("stepCheckDetail")} />
        <ProcessCard number="03" title={text("stepNextTitle")} detail={text("stepNextDetail")} />
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

function ProcessCard({ number, title, detail }) {
  return <article className="process-card">
    <span className="process-number">{number}</span>
    <div><h3>{title}</h3><p>{detail}</p></div>
    <span className="process-arrow" aria-hidden="true">↗</span>
  </article>;
}

function BotanicalArtwork({ backendState, diagnosisAvailable, text }) {
  const isUnavailable = backendState === "offline" || backendState === "degraded";
  const status = diagnosisAvailable
    ? text("serviceReady")
    : isUnavailable
      ? text("connectionProblem")
      : text("checkingService");
  const statusClass = diagnosisAvailable ? "is-ready" : isUnavailable ? "is-offline" : "is-checking";

  return <div className={`field-hero-art ${statusClass}`} aria-hidden="true">
    <svg className="leaf-illustration" viewBox="0 0 520 430" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="field-glow" cx="0" cy="0" r="1" gradientTransform="translate(270 206) rotate(90) scale(192 200)" gradientUnits="userSpaceOnUse">
          <stop stopColor="#DAECA5" stopOpacity=".22" />
          <stop offset="1" stopColor="#DAECA5" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="leaf-lime" x1="173" y1="108" x2="324" y2="307" gradientUnits="userSpaceOnUse">
          <stop stopColor="#E5F0B7" />
          <stop offset="1" stopColor="#8BBE79" />
        </linearGradient>
        <linearGradient id="leaf-sage" x1="151" y1="179" x2="348" y2="339" gradientUnits="userSpaceOnUse">
          <stop stopColor="#C7DDA1" />
          <stop offset="1" stopColor="#6A9D75" />
        </linearGradient>
        <filter id="leaf-shadow" x="100" y="76" width="331" height="320" colorInterpolationFilters="sRGB" filterUnits="userSpaceOnUse">
          <feGaussianBlur stdDeviation="13" />
        </filter>
      </defs>
      <circle cx="268" cy="211" r="193" fill="url(#field-glow)" />
      <circle className="art-orbit art-orbit-one" cx="270" cy="210" r="160" stroke="#D8E9A2" strokeOpacity=".54" />
      <circle className="art-orbit art-orbit-two" cx="270" cy="210" r="132" stroke="#F9FFE7" strokeOpacity=".36" strokeDasharray="3 9" />
      <path d="M265 355C270 299 274 238 266 161" stroke="#DDEBAF" strokeWidth="4" strokeLinecap="round" />
      <path className="leaf-shape leaf-shape-one" d="M265 264C202 253 167 213 173 149C228 158 267 199 265 264Z" fill="url(#leaf-lime)" />
      <path className="leaf-shape leaf-shape-two" d="M268 227C275 157 317 116 380 120C367 177 330 218 268 227Z" fill="#91BD79" />
      <path className="leaf-shape leaf-shape-three" d="M271 317C207 327 159 301 143 248C197 237 244 261 271 317Z" fill="url(#leaf-sage)" />
      <path className="leaf-shape leaf-shape-four" d="M274 292C315 240 369 225 415 252C383 298 333 317 274 292Z" fill="#DCEAA7" />
      <path className="leaf-shape leaf-shape-five" d="M266 178C249 117 267 71 309 48C336 95 326 141 266 178Z" fill="#C4DF8C" />
      <g stroke="#F4F8E9" strokeOpacity=".58" strokeWidth="2" strokeLinecap="round">
        <path d="M265 263L202 178M265 263L235 191M269 226L355 137M269 226L324 157M271 316L166 266M271 316L211 273M275 292L388 262M275 292L343 260M267 178L294 91" />
      </g>
      <circle className="art-spark art-spark-one" cx="114" cy="123" r="5" fill="#DAECA5" />
      <circle className="art-spark art-spark-two" cx="408" cy="156" r="4" fill="#F5F8E9" />
      <circle className="art-spark art-spark-three" cx="361" cy="353" r="5" fill="#DAECA5" />
      <path d="M86 210h19M95.5 200.5v19M431 311h16M439 303v16" stroke="#DCEAA7" strokeOpacity=".72" strokeLinecap="round" />
    </svg>
    <div className="art-coordinate art-coordinate-top"><span>FIELD SCAN</span><b>01</b></div>
    <div className="art-ready-card">
      <span className="art-ready-icon"><i /></span>
      <span><small>{text("photoCheckLabel")}</small><strong>{status}</strong></span>
      <span className="art-ready-check">{diagnosisAvailable ? "✓" : isUnavailable ? "!" : "…"}</span>
    </div>
    <div className="art-coordinate art-coordinate-bottom"><span>ONE CLEAR LEAF</span><i /></div>
  </div>;
}

function CameraIcon() {
  return <svg className="action-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M3 6.5h3l1.3-2h5.4l1.3 2h3v9H3v-9Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/><circle cx="10" cy="10.8" r="2.8" stroke="currentColor" strokeWidth="1.6" /></svg>;
}

function GalleryIcon() {
  return <svg className="action-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3" y="3.5" width="14" height="13" rx="2" stroke="currentColor" strokeWidth="1.6"/><circle cx="7.2" cy="7.5" r="1.2" fill="currentColor"/><path d="m4.5 14 3.7-3.3 2.2 1.7 2.7-3 2.4 2.4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

function ShieldIcon() {
  return <svg viewBox="0 0 18 18" fill="none" aria-hidden="true"><path d="M9 2.2 14.4 4v4.1c0 3.4-2.2 5.8-5.4 7.5-3.2-1.7-5.4-4.1-5.4-7.5V4L9 2.2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/><path d="m6.5 8.8 1.7 1.7 3.5-3.7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>;
}

function ReportSummary({ report, onClick }) {
  return <button className="report-summary" onClick={onClick}>
    <span className={`report-glyph ${isHealthy(report) ? "healthy" : "attention"}`} aria-hidden="true">{isHealthy(report) ? "✓" : "!"}</span>
    <span className="report-summary-copy"><strong>{displayName(report.crop)} · {displayName(report.diagnosis)}</strong><small>{formatDate(report.created_at)} · {displayName(report.severity)} severity</small></span>
    <span className="report-chevron" aria-hidden="true">→</span>
  </button>;
}
