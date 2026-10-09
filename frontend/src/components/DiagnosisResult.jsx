import { translate as t, displayName } from "../i18n";

export default function DiagnosisResult({ result, language = "en", onCheckAnother }) {
  const healthy = String(result?.diagnosis || "").toLowerCase() === "healthy";
  const steps = Array.isArray(result?.prevention) ? result.prevention : [];
  const text = (key) => t(language, key);

  return <section className="diagnosis-result" aria-labelledby="result-title" aria-live="polite">
    <div className="result-banner">
      <span className={`result-icon ${healthy ? "healthy" : "attention"}`} aria-hidden="true">{healthy ? "✓" : "!"}</span>
      <div><span className="step-label">{text("checkComplete")}</span><h2 id="result-title">{healthy ? text("noDiseaseDetected") : text("possibleDetected")}</h2><p>{displayName(result.crop)} · {displayName(result.diagnosis)}</p></div>
    </div>
    {result.expert_review && <p className="expert-note" role="note">{text("expertAdvice")}</p>}
    {healthy && <p className="caveat-note">{text("healthyCaveat")}</p>}
    <div className="result-details">
      <article><span className="step-label">{text("whatNoticed")}</span><p>{result.symptoms || text("resultUnavailable")}</p></article>
      <article><span className="step-label">{text("severity").toUpperCase()}</span><p className={`severity-text ${String(result.severity).toLowerCase()}`}>{displayName(result.severity) || "Not provided"}</p></article>
      <article><span className="step-label">{text("aiConfidence")}</span><p>{Number(result.confidence).toFixed(1)}%</p><small>{text("confidenceNote")}</small></article>
    </div>
    <div className="result-next"><h3>{text("whatNext")}</h3>{steps.length ? <ol>{steps.map((step, index) => <li key={`${result.job_id || "result"}-${index}`}>{step}</li>)}</ol> : <p>{text("followUpExpert")}</p>}</div>
    <p className="result-disclaimer">{text("resultHelp")}</p>
    {result.created_at && <p className="saved-report-note" role="status">✓ {text("reportSaved")}</p>}
    <button className="button button-primary" onClick={onCheckAnother}>{text("startCheck")}</button>
  </section>;
}
