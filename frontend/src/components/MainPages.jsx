import Scanner from "./Scanner";
import SpecimenInput from "./SpecimenInput";
import InferencePipeline from "./InferencePipeline";
import DiagnosisResult from "./DiagnosisResult";
import MonitorGrid from "./MonitorGrid";
import FieldResponse from "./FieldResponse";

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
  socketState,
  events,
  alerts,
  stats,
  scanStep,
  inputRef,
  onFileChange,
  onDiagnose,
  onReset,
}) {
  return (
    <section className="page-view">
      <div className="scanner-page-heading">
        <div>
          <div className="eyebrow">
            COMPUTER VISION / CROP HEALTH
          </div>

          <h1>
            Diagnose the
            <br />
            <span>unknown.</span>
          </h1>

          <p>
            Upload a crop image and activate the V6
            vision engine. The complete diagnostic pipeline
            remains synchronized with the backend in real time.
          </p>
        </div>

        <div className="scanner-page-status">
          <span
            className={`live-dot ${
              socketState === "live"
                ? "on"
                : ""
            }`}
          />

          {socketState === "live"
            ? "BACKEND LINK ACTIVE"
            : "CONNECTING TO BACKEND"}
        </div>
      </div>

      <section className="hero-panel scanner-hero">
        <div className="hero-copy">
          <div className="hero-pills">
            <span>● EFFICIENTNETV2-S</span>
            <span>● 38 CLASSES</span>
            <span>● REALTIME ALERTS</span>
          </div>
        </div>

        <Scanner
          preview={preview}
          loading={loading}
        />
      </section>

      <section className="workspace">
        <SpecimenInput
          selectedFile={selectedFile}
          error={error}
          loading={loading}
          inputRef={inputRef}
          onFileChange={onFileChange}
          onDiagnose={onDiagnose}
          onReset={onReset}
        />

        <InferencePipeline
          scanStep={scanStep}
          result={result}
          loading={loading}
        />
      </section>

      {result && (
        <DiagnosisResult
          result={result}
        />
      )}

      <MonitorGrid
        result={result}
        socketState={socketState}
        events={events}
        alerts={alerts}
        stats={stats}
      />

      <FieldResponse
        result={result}
      />
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
