const PIPELINE_STEPS = [
  "IMAGE REQUEST",
  "SERVER INFERENCE",
  "DIAGNOSTIC REPORT",
  "EXPERT ROUTING",
];

export default function InferencePipeline({ scanStep, result, loading }) {
  return (
    <div className="pipeline-card glass" aria-live="polite">
      <div className="section-head">
        <span>02 / DIAGNOSIS WORKFLOW</span>
        <b>{result ? "RESPONSE RECEIVED" : loading ? "REQUEST IN FLIGHT" : "READY"}</b>
      </div>

      <div className="pipeline">
        {PIPELINE_STEPS.map((label, index) => {
          const step = index + 1;
          const complete = Boolean(result) || scanStep > step;
          const active = !result && loading && scanStep === step;
          const routing = step === 4;
          const routingText = !result
            ? "AWAITING RESULT"
            : result.alert_created
              ? "ALERT CREATED"
              : result.expert_review
                ? "REVIEW ADVISED"
                : "NOT REQUIRED";
          const status = routing && result
            ? routingText
            : complete
              ? "COMPLETE"
              : active
                ? "WAITING ON API"
                : loading
                  ? "AWAITING RESPONSE"
                  : "READY";

          return (
            <div
              className={`pipe-step ${complete ? "done" : ""} ${active ? "active" : ""}`}
              key={label}
            >
              <span>{String(step).padStart(2, "0")}</span>
              <div>
                <strong>{label}</strong>
                <small>{status}</small>
              </div>
            </div>
          );
        })}
      </div>
      <p className="pipeline-note">The API returns a result when inference finishes; individual model internals are not streamed as progress events.</p>
    </div>
  );
}
