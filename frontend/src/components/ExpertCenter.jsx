import { useMemo, useState } from "react";
import "./ExpertCenter.css";
import { API_URL } from "../services/api";

const FILTERS = [
  { id: "all", label: "All Alerts" },
  { id: "pending", label: "Pending" },
  { id: "in_review", label: "In Review" },
  { id: "resolved", label: "Resolved" },
  { id: "high_priority", label: "High Priority" },
];

function ExpertCenter({
  alerts = [],
  onRefresh,
  refreshing = false,
  onAlertUpdated,
  loadError = "",
  loading = false,
}) {
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [updatingId, setUpdatingId] = useState(null);
  const [selectedAlertId, setSelectedAlertId] = useState(null);
  const [error, setError] = useState("");

  const counts = useMemo(
    () => ({
      all: alerts.length,
      pending: alerts.filter((a) => a.status === "pending").length,
      in_review: alerts.filter((a) => a.status === "in_review").length,
      resolved: alerts.filter((a) => a.status === "resolved").length,
      high_priority: alerts.filter((a) => ["high", "critical"].includes(String(a.priority || "").toLowerCase())).length,
    }),
    [alerts]
  );

  const visibleAlerts = useMemo(() => {
    const normalized = search.trim().toLowerCase();
    return alerts.filter((alert) => {
      const statusMatches = filter === "all"
        || (filter === "high_priority" ? ["high", "critical"].includes(String(alert.priority || "").toLowerCase()) : alert.status === filter);
      const queryMatches = !normalized || [alert.crop, alert.diagnosis, alert.id, alert.severity]
        .some((value) => String(value || "").toLowerCase().includes(normalized));
      return statusMatches && queryMatches;
    });
  }, [alerts, filter, search]);
  const selectedAlert = alerts.find((alert) => alert.id === selectedAlertId) || null;

  const updateStatus = async (id, status) => {
    setUpdatingId(id);
    setError("");

    try {
      const response = await fetch(`${API_URL}/alerts/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status }),
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(typeof payload.detail === "string" ? payload.detail : "Unable to update alert.");
      }
      const updated = payload.alert || payload;

      onAlertUpdated?.(updated);

      setSelectedAlertId(id);
    } catch (err) {
      setError(err.message || "Unable to update alert.");
    } finally {
      setUpdatingId(null);
    }
  };

  return (
    <section className="expert-center">
      <div className="expert-header">
        <div>
          <span className="expert-eyebrow">
            03 / EXPERT REVIEW NETWORK
          </span>

          <h1>Expert Center</h1>

          <p>
            Review AI-generated crop disease alerts and coordinate
            agricultural verification.
          </p>
        </div>

        <button
          className="expert-refresh"
          onClick={onRefresh}
          disabled={refreshing}
        >
          <span className={refreshing ? "refresh-spin" : ""}>↻</span>
          {refreshing ? "SYNCING" : "SYNC ALERTS"}
        </button>
      </div>

      <div className="expert-command-strip">
        <div className="expert-live-state">
          <span className="expert-live-dot" />
          <div>
            <strong>REALTIME ALERT NETWORK</strong>
            <small>Connected to V6 diagnostic backend</small>
          </div>
        </div>

        <div className="expert-sync-label">
          <span>ALERT STREAM</span>
          <strong>{alerts.length.toString().padStart(2, "0")}</strong>
        </div>
      </div>

      <div className="expert-stats">
        <StatCard
          label="TOTAL ALERTS"
          value={counts.all}
          marker="01"
        />

        <StatCard
          label="PENDING REVIEW"
          value={counts.pending}
          marker="02"
          active={counts.pending > 0}
        />

        <StatCard
          label="IN REVIEW"
          value={counts.in_review}
          marker="03"
        />

        <StatCard
          label="RESOLVED"
          value={counts.resolved}
          marker="04"
        />

        <StatCard label="HIGH PRIORITY" value={counts.high_priority} marker="05" active={counts.high_priority > 0} />
      </div>

      <div className="expert-toolbar">
        <label className="expert-search">
          <span>⌕</span>
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search crop, diagnosis, severity, or alert ID" aria-label="Search expert alerts" />
        </label>

        <div className="expert-filters">
          {FILTERS.map((item) => (
            <button
              key={item.id}
              className={filter === item.id ? "active" : ""}
              onClick={() => setFilter(item.id)}
            >
              {item.label}
              <span>{counts[item.id]}</span>
            </button>
          ))}
        </div>

        <span className="expert-result-count">
          SHOWING {visibleAlerts.length} ALERT
          {visibleAlerts.length === 1 ? "" : "S"}
        </span>
      </div>

      {(error || loadError) && (
        <div className="expert-error">
          <span>!</span>
          {error || loadError}
        </div>
      )}

      <div className="expert-layout">
        <div className="expert-alerts">
          {visibleAlerts.length === 0 ? (
            loading
              ? <div className="expert-empty" role="status"><div className="empty-orbit"><span/><span/><span/></div><strong>SYNCING ALERT QUEUE</strong><p>Loading saved cases from the diagnosis service.</p></div>
              : <EmptyState filter={filter} />
          ) : (
            visibleAlerts.map((alert, index) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                index={index}
                selected={selectedAlert?.id === alert.id}
                updating={updatingId === alert.id}
                onSelect={() => setSelectedAlertId(alert.id)}
                onStatusChange={updateStatus}
              />
            ))
          )}
        </div>

        <aside className="expert-detail">
          {selectedAlert ? (
            <AlertDetail
              alert={selectedAlert}
              updating={updatingId === selectedAlert.id}
              onStatusChange={updateStatus}
            />
          ) : (
            <div className="detail-empty">
              <div className="detail-crosshair">
                <span />
                <span />
              </div>

              <strong>SELECT AN ALERT</strong>
              <p>
                Choose an alert from the queue to inspect its
                diagnostic intelligence.
              </p>
            </div>
          )}
        </aside>
      </div>
    </section>
  );
}

function StatCard({ label, value, marker, active = false }) {
  return (
    <div className={`expert-stat ${active ? "active" : ""}`}>
      <div className="expert-stat-top">
        <span>{marker}</span>
        <i />
      </div>

      <strong>{value.toString().padStart(2, "0")}</strong>
      <small>{label}</small>
    </div>
  );
}

function AlertCard({
  alert,
  index,
  selected,
  updating,
  onSelect,
  onStatusChange,
}) {
  const priority = (alert.priority || "normal").toLowerCase();
  const status = alert.status || "pending";

  return (
    <article
      className={`expert-alert-card ${
        selected ? "selected" : ""
      }`}
    >
      <div className="alert-index">
        {(index + 1).toString().padStart(2, "0")}
      </div>

      <div className={`alert-priority ${priority}`}>
        <span />
        {priority.toUpperCase()}
      </div>

      <div className="alert-main">
        <div className="alert-title-row">
          <div>
            <span className="alert-crop">
              {alert.crop || "Unknown Crop"}
            </span>

            <h3>{alert.diagnosis || "Unknown Diagnosis"}</h3>
          </div>

          <div className="alert-confidence">
            <strong>
              {Number(alert.confidence || 0).toFixed(1)}%
            </strong>
            <span>AI CONFIDENCE</span>
          </div>
        </div>

        <div className="alert-meta">
          <span>
            <b>SEVERITY</b>
            {alert.severity || "Unknown"}
          </span>

          <span>
            <b>STATUS</b>
            {status.replaceAll("_", " ")}
          </span>

          <span>
            <b>MODEL</b>
            {alert.model_version || "V6 ENGINE"}
          </span>

          <span>
            <b>RECEIVED</b>
            {alert.created_at ? new Date(alert.created_at).toLocaleString() : "Time unavailable"}
          </span>
        </div>

        <div className="alert-actions">
          {status === "pending" && (
            <button
              onClick={(event) => {
                event.stopPropagation();
                onStatusChange(alert.id, "in_review");
              }}
              disabled={updating}
            >
              {updating ? "UPDATING..." : "START REVIEW"}
            </button>
          )}

          {status === "in_review" && (
            <button
              onClick={(event) => {
                event.stopPropagation();
                onStatusChange(alert.id, "resolved");
              }}
              disabled={updating}
            >
              {updating ? "UPDATING..." : "MARK RESOLVED"}
            </button>
          )}

          {status === "resolved" && (
            <span className="resolved-label">
              ✓ REVIEW COMPLETED
            </span>
          )}

          <button className="inspect-label" onClick={(event) => { event.stopPropagation(); onSelect(); }}>INSPECT →</button>
        </div>
      </div>
    </article>
  );
}

function AlertDetail({ alert, updating, onStatusChange }) {
  const status = alert.status || "pending";

  return (
    <div className="detail-panel">
      <div className="detail-header">
        <div>
          <span>ALERT IDENTIFIER</span>
          <strong>#{alert.id}</strong>
        </div>

        <div className={`detail-status ${status}`}>
          {status.replaceAll("_", " ").toUpperCase()}
        </div>
      </div>

      <div className="detail-diagnosis">
        <span>{alert.crop || "UNKNOWN CROP"}</span>
        <h2>{alert.diagnosis || "Unknown Diagnosis"}</h2>
      </div>

      {alert.symptoms && (
        <div className="detail-symptoms">
          <span>REPORTED SYMPTOMS</span>
          <p>{alert.symptoms}</p>
        </div>
      )}

      <div className="detail-confidence">
        <div className="confidence-track">
          <span
            style={{
              width: `${Math.min(
                Number(alert.confidence || 0),
                100
              )}%`,
            }}
          />
        </div>

        <div>
          <span>MODEL CONFIDENCE</span>
          <strong>
            {Number(alert.confidence || 0).toFixed(2)}%
          </strong>
        </div>
      </div>

      <div className="detail-grid">
        <DetailMetric
          label="SEVERITY"
          value={alert.severity || "Unknown"}
        />

        <DetailMetric
          label="PRIORITY"
          value={(alert.priority || "normal").toUpperCase()}
        />

        <DetailMetric
          label="MODEL"
          value={alert.model_version || "V6"}
        />

        <DetailMetric
          label="STATUS"
          value={status.replaceAll("_", " ").toUpperCase()}
        />

        <DetailMetric label="IMAGE FILE" value={alert.image_filename || "Not attached"} />
      </div>

      <div className="detail-note">
        <span>EXPERT PROTOCOL</span>
        <p>
          AI output should be treated as diagnostic assistance.
          Field verification is recommended before applying
          disease-control measures.
        </p>
      </div>


      <div className="detail-actions">
        {status === "pending" && (
          <button
            onClick={() => onStatusChange(alert.id, "in_review")}
            disabled={updating}
          >
            {updating ? "UPDATING..." : "BEGIN EXPERT REVIEW"}
          </button>
        )}

        {status === "in_review" && (
          <button
            onClick={() => onStatusChange(alert.id, "resolved")}
            disabled={updating}
          >
            {updating ? "UPDATING..." : "RESOLVE ALERT"}
          </button>
        )}

        {status === "resolved" && (
          <div className="detail-resolved">
            <span>✓</span>
            ALERT RESOLVED
          </div>
        )}
      </div>
    </div>
  );
}

function DetailMetric({ label, value }) {
  return (
    <div className="detail-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function EmptyState({ filter }) {
  return (
    <div className="expert-empty">
      <div className="empty-orbit">
        <span />
        <span />
        <span />
      </div>

      <strong>
        {filter === "all"
          ? "NO ALERTS DETECTED"
          : `NO ${filter.replaceAll("_", " ").toUpperCase()} ALERTS`}
      </strong>

      <p>
        The expert queue is clear. New AI escalations will
        appear here automatically.
      </p>
    </div>
  );
}

export default ExpertCenter;
