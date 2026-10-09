import DiagnosisResult from "./DiagnosisResult";
import { translate as t } from "../i18n";

export function DashboardPage({
  alerts,
  events,
  stats,
  socketState,
  backendState,
  modelState,
  alertsError,
  onNavigate,
  result,
}) {
  const latestAlerts = alerts.slice(0, 4);

  return (
    <section className="page-view">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            AI FIELD OPERATIONS / COMMAND CENTER
          </div>

          <h1>
            Crop intelligence,
            <br />
            <span>at a glance.</span>
          </h1>

          <p>
            Monitor diagnosis activity, expert escalation,
            and the live AI diagnostic network from one
            control surface.
          </p>
        </div>

        <button
          className="dashboard-launch"
          onClick={() => onNavigate("scanner")}
        >
          OPEN AI SCANNER
          <span>→</span>
        </button>
      </div>

      <div className="overview-grid">
        <OverviewCard
          label="PENDING ALERTS"
          value={stats.pending}
          detail="Awaiting expert review"
          icon="!"
          accent="warning"
        />

        <OverviewCard
          label="IN REVIEW"
          value={stats.review}
          detail="Currently being verified"
          icon="◌"
          accent="active"
        />

        <OverviewCard
          label="RESOLVED"
          value={stats.resolved}
          detail="Completed expert cases"
          icon="✓"
          accent="healthy"
        />

        <OverviewCard
          label="EVENTS"
          value={events.length}
          detail="Live telemetry received"
          icon="⌁"
          accent="live"
        />
      </div>

      <div className="dashboard-main-grid">
        <div className="dashboard-feature glass">
          <div className="section-head">
            <span>01 / DIAGNOSTIC ENGINE</span>
            <b>{modelState === "checking" ? "CHECKING MODEL" : `MODEL ${modelState.toUpperCase()}`}</b>
          </div>

          <div className="engine-display">
            <div className="engine-orbit orbit-a" />
            <div className="engine-orbit orbit-b" />

            <div className="engine-core">
              <span>✦</span>
              <strong>V6</strong>
              <small>VISION ENGINE</small>
            </div>

            <div className="engine-readout">
              <span>MODEL</span>
              <strong>EfficientNetV2-S</strong>
            </div>

            <div className="engine-readout right">
              <span>CLASSES</span>
              <strong>38</strong>
            </div>
          </div>

          <div className="engine-footer">
            <div>
              <span>INPUT</span>
              <strong>224 × 224 RGB</strong>
            </div>

            <div>
              <span>BENCHMARK</span>
              <strong>99.04% ACCURACY</strong>
            </div>

            <div>
              <span>CHANNEL</span>
              <strong>
                {socketState.toUpperCase()} / API {backendState.toUpperCase()}
              </strong>
            </div>
          </div>
        </div>

        <div className="dashboard-feed glass">
          <div className="section-head">
            <span>02 / LIVE ACTIVITY</span>
            <b>{events.length} EVENTS</b>
          </div>

          <div className="dashboard-event-list">
            {events.length ? (
              events.map((event) => (
                <div
                  className="dashboard-event"
                  key={event.id}
                >
                  <time>{event.time}</time>

                  <div>
                    <strong>{event.label}</strong>
                    <span>{event.detail}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty">
                Waiting for realtime events…
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="dashboard-alerts glass">
        <div className="section-head">
          <span>03 / EXPERT ESCALATION</span>
          <button
            className="section-link"
            onClick={() => onNavigate("expert")}
          >
            OPEN CENTER →
          </button>
        </div>

        {alertsError && <div className="error-line" role="status">ALERT SYNC: {alertsError}</div>}

        {latestAlerts.length ? (
          <div className="dashboard-alert-list">
            {latestAlerts.map((alert) => (
              <div
                className="dashboard-alert-row"
                key={alert.id}
              >
                <span
                  className={`priority ${
                    alert.priority || "normal"
                  }`}
                />

                <div>
                  <strong>
                    {alert.crop} / {alert.diagnosis}
                  </strong>

                  <small>
                    {alert.status?.replaceAll(
                      "_",
                      " "
                    )}{" "}
                    •{" "}
                    {Number(
                      alert.confidence || 0
                    ).toFixed(1)}
                    %
                  </small>
                </div>

                <span className="alert-arrow">
                  →
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="dashboard-empty">
            <strong>No active expert alerts</strong>
            <span>
              New escalations will appear here in real time.
            </span>
          </div>
        )}
      </div>

      {result && (
        <div className="dashboard-result-strip glass">
          <div>
            <span>LAST DIAGNOSIS</span>
            <strong>
              {result.crop} / {result.diagnosis}
            </strong>
          </div>

          <div>
            <span>CONFIDENCE</span>
            <strong>{result.confidence}%</strong>
          </div>

          <button
            onClick={() => onNavigate("scanner")}
          >
            VIEW DIAGNOSIS →
          </button>
        </div>
      )}
    </section>
  );
}

/* ===========================================================
   AI SCANNER PAGE
   =========================================================== */

export function ScannerPage({
  selectedFile,
  preview,
  result,
  loading,
  error,
  backendState,
  language,
  onTakePhoto,
  onChoosePhoto,
  onDiagnose,
  onReset,
  onRetryConnection,
}) {
  const text = (key) => t(language, key);
  return (
    <section className="farmer-page scan-page page-view" aria-labelledby="scan-title">
      <div className="page-intro"><span className="eyebrow">{text("stepPhoto")}</span><h1 id="scan-title">{text("scanTitle")}</h1><p>{text("scanIntro")}</p><span className={`connection-chip ${backendState === "healthy" ? "is-ready" : backendState === "offline" || backendState === "degraded" ? "is-error" : ""}`} role="status"><i aria-hidden="true" />{backendState === "healthy" ? text("serviceReady") : backendState === "offline" || backendState === "degraded" ? text("connectionProblem") : text("checkingService")}</span></div>
      <section className="content-card photo-review" aria-label="Crop photo review">
        <div className={`photo-preview ${preview ? "has-photo" : ""}`}>
          {preview ? <img src={preview} alt="Preview of the crop photo you selected" /> : <div className="photo-placeholder"><span aria-hidden="true">◎</span><strong>{text("oneLeaf")}</strong><small>{text("supportedPhoto")}</small></div>}
        </div>
        {selectedFile && <p className="selected-photo-name">{selectedFile.name} · {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>}
        {!selectedFile ? <div className="photo-actions"><button className="button button-primary" onClick={onTakePhoto}><span aria-hidden="true">◎</span>{text("takePhoto")}</button><button className="button button-secondary" onClick={onChoosePhoto}><span aria-hidden="true">▧</span>{text("choosePhoto")}</button></div> : <div className="photo-actions"><button className="button button-secondary" onClick={onTakePhoto} disabled={loading}>{text("retake")}</button><button className="button button-secondary" onClick={onChoosePhoto} disabled={loading}>{text("chooseAnother")}</button></div>}
        {error && <div className="inline-message" role="alert">{error}</div>}
        {selectedFile && !result && <button className="button button-primary analyze-button" disabled={loading || backendState !== "healthy"} onClick={onDiagnose}>{loading ? <><span className="spinner" aria-hidden="true" />{text("checking")}</> : text("photoReview")}</button>}
        {(backendState === "offline" || backendState === "degraded") && <div className="offline-hint" role="status">{text("photoStillHere")} <button type="button" className="inline-retry" onClick={onRetryConnection}>{text("retry")}</button></div>}
        <p className="photo-consent">{text("photoSentOnlyOnAction")}</p>
      </section>
      <aside className="quick-tips content-card"><strong>{text("photoTips")}</strong><ul><li>{text("tipOne")}</li><li>{text("tipThree")}</li></ul></aside>
      {result && <DiagnosisResult result={result} language={language} onCheckAnother={onReset} />}
    </section>
  );
}

/* ===========================================================
   DASHBOARD COMPONENT
   =========================================================== */

function OverviewCard({
  label,
  value,
  detail,
  icon,
  accent,
}) {
  return (
    <div className={`overview-card glass ${accent}`}>
      <div className="overview-card-icon">
        {icon}
      </div>

      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{detail}</small>
      </div>
    </div>
  );
}
