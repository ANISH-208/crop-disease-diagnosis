export default function MonitorGrid({
  result,
  socketState,
  events,
  alerts,
  stats,
}) {
  return (
    <section className="monitor-grid">

      {/* ===================================================
          MODEL TELEMETRY
          =================================================== */}

      <div className="monitor-card glass">
        <div className="section-head">
          <span>04 / MODEL TELEMETRY</span>
          <b>ONLINE</b>
        </div>

        <div className="telemetry">
          <Metric
            label="ENGINE"
            value={
              result?.model_version ||
              "v6-efficientnetv2s"
            }
          />

          <Metric
            label="INPUT"
            value="224 × 224 RGB"
          />

          <Metric
            label="OUTPUT"
            value="38 CLASSES"
          />

          <Metric
            label="CHANNEL"
            value={
              socketState === "live"
                ? "WEBSOCKET LIVE"
                : "RECONNECTING"
            }
          />
        </div>
      </div>

      {/* ===================================================
          LIVE EVENT STREAM
          =================================================== */}

      <div className="monitor-card glass">
        <div className="section-head">
          <span>05 / LIVE EVENT STREAM</span>

          <b>
            {events.length
              .toString()
              .padStart(2, "0")}{" "}
            EVENTS
          </b>
        </div>

        <div className="event-list">
          {events.length ? (
            events.map((event) => (
              <div
                className="event"
                key={event.id}
              >
                <time>{event.time}</time>

                <div>
                  <strong>
                    {event.label}
                  </strong>

                  <span>
                    {event.detail}
                  </span>
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

      {/* ===================================================
          EXPERT CENTER
          =================================================== */}

      <div className="monitor-card glass expert-card">
        <div className="section-head">
          <span>06 / EXPERT CENTER</span>

          <b>
            {stats.pending} PENDING
          </b>
        </div>

        <div className="expert-stats">
          <div>
            <strong>{stats.pending}</strong>
            <span>PENDING</span>
          </div>

          <div>
            <strong>{stats.review}</strong>
            <span>IN REVIEW</span>
          </div>

          <div>
            <strong>{stats.resolved}</strong>
            <span>RESOLVED</span>
          </div>
        </div>

        <div className="alert-list">
          {alerts.slice(0, 3).map((alert) => (
            <div
              className="alert-row"
              key={alert.id}
            >
              <span
                className={`priority ${
                  alert.priority || "normal"
                }`}
              />

              <div>
                <strong>
                  {alert.crop} /{" "}
                  {alert.diagnosis}
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
            </div>
          ))}

          {!alerts.length && (
            <div className="empty">
              No active alerts.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

/* ===========================================================
   METRIC
   =========================================================== */

function Metric({ label, value }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
