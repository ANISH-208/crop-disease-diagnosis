export default function DiagnosisResult({ result }) {
  const topPredictions = result?.top_predictions || [];

  const confidence = Math.min(100, Math.max(0, Number(result?.confidence || 0)));

  const circumference = 2 * Math.PI * 54;

  const dash = (confidence / 100) * circumference;

  return (
    <section className="diagnosis-grid">

      {/* ===================================================
          DIAGNOSTIC SIGNATURE
          =================================================== */}

      <div className="diagnosis-card glass main-diagnosis">
        <div className="section-head">
          <span>03 / DIAGNOSTIC SIGNATURE</span>

          <b className={confidence >= 80 ? "success" : "confidence-caution"}>
            {confidence >= 80 ? "TOP CLASS PREDICTION" : "LOW CONFIDENCE · VERIFY"}
          </b>
        </div>

        <div className="diagnosis-layout">

          {/* CONFIDENCE RING */}

          <div className="confidence-ring">
            <svg viewBox="0 0 120 120">
              <circle
                className="ring-bg"
                cx="60"
                cy="60"
                r="54"
              />

              <circle
                className="ring-value"
                cx="60"
                cy="60"
                r="54"
                style={{
                  strokeDasharray: `${dash} ${circumference}`,
                }}
              />
            </svg>

            <div>
              <strong>
                {confidence.toFixed(2)}%
              </strong>

              <span>CONFIDENCE</span>
            </div>
          </div>

          {/* DIAGNOSIS INFORMATION */}

          <div className="diagnosis-copy">
            <small>
              {result.crop?.toUpperCase()}
            </small>

            <h2>{result.diagnosis || "Unclassified image"}</h2>

            <p>{result.symptoms || "Detailed symptom metadata is not available for this class."}</p>

            <div className="tag-row">
              <span>
                SEVERITY:{" "}
                {result.severity?.toUpperCase()}
              </span>

              <span>
                MODEL:{" "}
                {result.model_version || "V6"}
              </span>
              <span>{result.expert_review ? "EXPERT REVIEW ADVISED" : "NO EXPERT ESCALATION"}</span>
              {result.alert?.id && <span>ALERT: {result.alert.status || "PENDING"}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* ===================================================
          TOP INFERENCE SIGNALS
          =================================================== */}

      <div className="diagnosis-card glass top-card">
        <div className="section-head">
          <span>TOP INFERENCE SIGNALS</span>
          <b>TOP 03</b>
        </div>

        <div className="predictions">
          {topPredictions.length ? topPredictions.map((prediction, index) => {
            const pct = Number(
              prediction.confidence || 0
            );

            return (
              <div
                className="prediction"
                key={`${prediction.class}-${index}`}
              >
                <div className="pred-row">
                  <span>
                    0{index + 1}
                  </span>

                  <strong>
                    {prettyLabel(prediction.class)}
                  </strong>

                  <b>
                    {pct.toFixed(2)}%
                  </b>
                </div>

                <div className="bar">
                  <i
                    style={{
                      width: `${Math.max(
                        pct,
                        0.5
                      )}%`,
                    }}
                  />
                </div>
              </div>
            );
          }) : <p className="empty">Top prediction breakdown is unavailable for this response.</p>}
        </div>
      </div>
    </section>
  );
}

function prettyLabel(label) {
  if (!label) return "Unknown";

  const [crop, disease] =
    label.split("___");

  return `${crop || "Unknown"} / ${(disease || "")
    .replaceAll("_", " ")
    .replaceAll("(", "")
    .replaceAll(")", "")}`;
}
