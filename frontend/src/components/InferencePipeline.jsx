export default function InferencePipeline({ scanStep }) {
  const steps = [
    "IMAGE NORMALIZATION",
    "FEATURE EXTRACTION",
    "38-CLASS INFERENCE",
    "DIAGNOSTIC SIGNATURE",
  ];

  return (
    <div className="pipeline-card glass">
      <div className="section-head">
        <span>02 / INFERENCE PIPELINE</span>
        <b>LIVE</b>
      </div>

      <div className="pipeline">
        {steps.map((label, i) => (
          <div
            className={`pipe-step ${
              scanStep > i ? "done" : ""
            } ${
              scanStep === i + 1 ? "active" : ""
            }`}
            key={label}
          >
            <span>
              {String(i + 1).padStart(2, "0")}
            </span>

            <div>
              <strong>{label}</strong>

              <small>
                {scanStep > i
                  ? "COMPLETE"
                  : scanStep === i + 1
                    ? "PROCESSING"
                    : "STANDBY"}
              </small>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
