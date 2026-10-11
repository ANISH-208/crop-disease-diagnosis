import { translate as t, displayName } from "../i18n";

const messages = {
  not_plant: {
    title: "This doesn’t look like a crop photo",
    detail: "Choose a clear photo of a crop leaf. No disease result was produced.",
    icon: "↺",
  },
  uncertain: {
    title: "We couldn’t confirm a crop condition",
    detail: "Try a clear, close photo of one leaf. Ask a local crop expert if the plant is getting worse.",
    icon: "?",
  },
  validation_unavailable: {
    title: "Photo checks are temporarily unavailable",
    detail: "The crop photo safety check could not run, so no disease result was produced.",
    icon: "…",
  },
  invalid_image: {
    title: "This photo couldn’t be opened",
    detail: "Choose a valid JPG or PNG photo, then try again.",
    icon: "↺",
  },
};

export default function DiagnosisResult({ result, language = "en", onCheckAnother }) {
  const healthy = result?.status === "healthy_class_predicted";
  const rejected = messages[result?.status];
  const steps = Array.isArray(result?.prevention) ? result.prevention : [];
  const text = (key) => t(language, key);

  if (rejected) {
    return <section className={`diagnosis-result result-rejected result-${result.status}`} aria-labelledby="result-title" aria-live="polite">
      <div className="result-banner">
        <span className="result-icon" aria-hidden="true">{rejected.icon}</span>
        <div><span className="step-label">PHOTO CHECK</span><h2 id="result-title">{rejected.title}</h2><p>{result.message || rejected.detail}</p></div>
      </div>
      <p className="result-disclaimer">No crop disease was identified from this photo.</p>
      <button className="button button-primary" onClick={onCheckAnother}>{text("startCheck")}</button>
    </section>;
  }

  const uncertain = result?.status === "uncertain";
  return <section className={`diagnosis-result ${uncertain ? "result-uncertain" : ""}`} aria-labelledby="result-title" aria-live="polite">
    <div className="result-banner">
      <span className={`result-icon ${healthy ? "healthy" : "attention"}`} aria-hidden="true">{healthy ? "✓" : "!"}</span>
      <div><span className="step-label">{text("checkComplete")}</span><h2 id="result-title">{uncertain ? "We couldn’t confirm a crop condition" : healthy ? "Possible healthy match" : text("possibleDetected")}</h2>
        <p>{uncertain ? result.message : `${displayName(result.crop)} · ${displayName(result.diagnosis)}`}</p></div>
    </div>
    {result.expert_review && !uncertain && <p className="expert-note" role="note">{text("expertAdvice")}</p>}
    {healthy && <p className="caveat-note">A healthy-class match does not guarantee that the plant is healthy. Watch for changes and consult a local expert if symptoms appear.</p>}
    {!uncertain && <div className="result-details">
      <article><span className="step-label">{text("whatNoticed")}</span><p>{result.symptoms || text("resultUnavailable")}</p></article>
      <article><span className="step-label">{text("severity").toUpperCase()}</span><p className={`severity-text ${String(result.severity).toLowerCase()}`}>{displayName(result.severity) || "Not provided"}</p></article>
      <article><span className="step-label">MODEL SCORE</span><p>{Number(result.confidence).toFixed(1)}%</p><small>This score is not a guarantee of correctness.</small></article>
    </div>}
    {!uncertain && <div className="result-next"><h3>{text("whatNext")}</h3>{steps.length ? <ol>{steps.map((step, index) => <li key={`${result.job_id || "result"}-${index}`}>{step}</li>)}</ol> : <p>{text("followUpExpert")}</p>}</div>}
    {uncertain && <div className="result-next"><h3>What to do next</h3><ol><li>Take a close, well-lit photo of one leaf.</li><li>Compare symptoms with a trusted local crop guide.</li><li>Ask an agricultural expert if the crop continues to decline.</li></ol></div>}
    <p className="result-disclaimer">AI photo checks can miss unfamiliar crops, diseases, or field conditions. Use this as guidance, not a confirmed diagnosis.</p>
    {result.created_at && <p className="saved-report-note" role="status">✓ {text("reportSaved")}</p>}
    <button className="button button-primary" onClick={onCheckAnother}>{text("startCheck")}</button>
  </section>;
}
