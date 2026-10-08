import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import "./App.css";
import "./components/Navigation.css";

import {
  diagnoseImage,
  fetchHealth,
  fetchAlerts,
} from "./services/api";

import useWebSocket from "./hooks/useWebSocket";

import Navigation from "./components/Navigation";
import { DashboardPage, ScannerPage } from "./components/MainPages";
import ExpertCenter from "./components/ExpertCenter";
import {
  AnalyticsPage,
  CropHealthPage,
  ModelIntelligencePage,
  SettingsPage,
} from "./components/OperationsPages";

function App() {
  const [page, setPage] = useState("dashboard");

  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [alertsError, setAlertsError] = useState("");
  const [backendState, setBackendState] = useState("checking");
  const [modelState, setModelState] = useState("checking");
  const [socketState, setSocketState] =
    useState("connecting");

  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [diagnosisHistory, setDiagnosisHistory] = useState([]);
  const [refreshingAlerts, setRefreshingAlerts] = useState(false);
  const [preferences, setPreferences] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("crop-doctor-preferences") || "{}");
      return {
        palette: ["canopy", "fern", "moss"].includes(stored.palette) ? stored.palette : "canopy",
        motion: typeof stored.motion === "boolean" ? stored.motion : true,
      };
    } catch {
      return { palette: "canopy", motion: true };
    }
  });
  const [scanStep, setScanStep] = useState(0);

  const inputRef = useRef(null);

  /* =========================================================
     REALTIME EVENT STREAM
     ========================================================= */

  const pushEvent = useCallback((label, detail) => {
    setEvents((current) => [
      {
        id: crypto.randomUUID(),
        time: new Date().toLocaleTimeString([], {
          hour12: false,
        }),
        label,
        detail,
      },
      ...current,
    ].slice(0, 8));
  }, []);

  const handleRealtimeEvent = useCallback(
    (type, data) => {
      pushEvent(
        type.replaceAll("_", " ").toUpperCase(),
        summarizeEvent(type, data)
      );

      if (type === "alert_created") {
        setAlerts((current) => [
          data,
          ...current.filter(
            (alert) => alert.id !== data.id
          ),
        ]);
      }

      if (type === "alert_updated") {
        setAlerts((current) =>
          current.map((alert) =>
            alert.id === (data.alert || data).id
              ? { ...alert, ...(data.alert || data) }
              : alert
          )
        );
      }
    },
    [pushEvent]
  );

  const handleSocketEvent = useCallback(
    ({ type, data }) => {
      handleRealtimeEvent(type, data);
    },
    [handleRealtimeEvent]
  );

  const handleSocketStatus = useCallback((status) => {
    setSocketState(status);
    if (status === "live") {
      fetchHealth()
        .then((data) => {
          setBackendState(data.status);
          setModelState(data.model?.status || "unknown");
        })
        .catch(() => { setBackendState("offline"); setModelState("unknown"); });
    }
  }, []);

  useWebSocket({
    onEvent: handleSocketEvent,
    onStatusChange: handleSocketStatus,
  });

  /* =========================================================
     INITIAL ALERT LOAD
     ========================================================= */

  useEffect(() => {
    fetchAlerts()
      .then((data) => {
        setAlerts(data);
        setAlertsError("");
      })
      .catch((err) => setAlertsError(err.message || "Could not load alerts."))
      .finally(() => setLoadingAlerts(false));
    fetchHealth()
      .then((data) => {
        setBackendState(data.status);
        setModelState(data.model?.status || "unknown");
      })
      .catch(() => { setBackendState("offline"); setModelState("unknown"); });
  }, []);

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  /* =========================================================
     FILE SELECTION
     ========================================================= */

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!new Set(["image/jpeg", "image/png"]).has(file.type) || !/\.(jpe?g|png)$/i.test(file.name)) {
      setError("Please select a valid JPG or PNG crop image.");
      setSelectedFile(null);
      setPreview(null);
      setResult(null);
      event.target.value = "";
      return;
    }

    if (file.size > 4 * 1024 * 1024) {
      setError("Choose an image smaller than 4 MB.");
      setSelectedFile(null);
      setPreview(null);
      setResult(null);
      event.target.value = "";
      return;
    }

    const imageUrl = URL.createObjectURL(file);

    setSelectedFile(file);
    setPreview(imageUrl);
    setResult(null);
    setError("");
    setScanStep(0);

    pushEvent(
      "IMAGE QUEUED",
      `${file.name} ready for V6 inference`
    );
  };

  /* =========================================================
     DIAGNOSIS
     ========================================================= */

  const diagnoseCrop = async () => {
    if (!selectedFile) {
      setError("Select a crop image first.");
      return;
    }

    setLoading(true);
    setResult(null);
    setError("");
    setScanStep(1);

    try {
      const data =
        await diagnoseImage(selectedFile);

      setResult(data);
      setModelState("loaded");
      setDiagnosisHistory((current) => [
        { ...data, id: `${Date.now()}`, analyzed_at: new Date().toISOString() },
        ...current,
      ].slice(0, 100));
      setScanStep(4);

    } catch (err) {
      setError(
        err.message || "Unable to connect to the diagnosis server. Make sure FastAPI is running."
      );

      setScanStep(0);

    } finally {
      setLoading(false);
    }
  };

  /* =========================================================
     RESET
     ========================================================= */

  const resetDiagnosis = () => {
    setSelectedFile(null);
    setPreview(null);
    setResult(null);
    setError("");
    setScanStep(0);

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  /* =========================================================
     ALERT STATISTICS
     ========================================================= */

  const stats = useMemo(
    () => ({
      pending: alerts.filter(
        (alert) =>
          alert.status === "pending"
      ).length,

      review: alerts.filter(
        (alert) =>
          alert.status === "in_review"
      ).length,

      resolved: alerts.filter(
        (alert) =>
          alert.status === "resolved"
      ).length,
    }),
    [alerts]
  );

  /* =========================================================
     NAVIGATION
     ========================================================= */

  const navigate = (nextPage) => {
    setPage(nextPage);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  const refreshAlerts = async () => {
    setRefreshingAlerts(true);
    try {
      const data = await fetchAlerts();
      setAlerts(data);
      setAlertsError("");
    } catch {
      setAlertsError("Could not sync alerts. Check the backend connection and retry.");
      pushEvent("SYNC ERROR", "Could not refresh the expert alert queue");
    } finally {
      setRefreshingAlerts(false);
    }
  };

  const updateAlert = (updated) => {
    setAlerts((current) => current.map((alert) => alert.id === updated.id ? { ...alert, ...updated } : alert));
  };

  const updatePreferences = (next) => {
    setPreferences(next);
    try {
      localStorage.setItem("crop-doctor-preferences", JSON.stringify(next));
    } catch {
      // Keep the selected preference for this session when storage is unavailable.
    }
  };

  /* =========================================================
     MAIN RENDER
     ========================================================= */

  return (
    <div className={`app-shell palette-${preferences.palette} ${preferences.motion ? "motion-on" : "motion-off"}`}>
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="topbar">
        <div className="brand-wrap">
          <div className="brand-mark">
            <span>✦</span>
          </div>

          <div>
            <div className="brand">
              CROP DOCTOR <b>AI</b>
            </div>

            <div className="brand-sub">
              INTELLIGENT AGRICULTURE DIAGNOSTICS
            </div>
          </div>
        </div>

        <div className="top-status">
          <span
            className={`live-dot ${
              socketState === "live"
                ? "on"
                : ""
            }`}
          />

          <span>
            {socketState === "live" ? "REALTIME LINK" : socketState === "offline" ? "RECONNECTING" : "LINKING..."}
          </span>

          <em>{modelState === "loaded" || modelState === "available" ? `MODEL ${modelState.toUpperCase()}` : modelState.toUpperCase()}</em>
        </div>
      </header>

      <Navigation
        page={page}
        onNavigate={navigate}
        stats={stats}
      />

      <main className="dashboard page-with-navigation">
        {page === "dashboard" && (
          <DashboardPage
            alerts={alerts}
            events={events}
            stats={stats}
            socketState={socketState}
            backendState={backendState}
            modelState={modelState}
            alertsError={alertsError}
            onNavigate={navigate}
            result={result}
          />
        )}

        {page === "scanner" && (
          <ScannerPage
            selectedFile={selectedFile}
            preview={preview}
            result={result}
            loading={loading}
            error={error}
            socketState={socketState}
            events={events}
            alerts={alerts}
            stats={stats}
            scanStep={scanStep}
            inputRef={inputRef}
            onFileChange={handleFileChange}
            onDiagnose={diagnoseCrop}
            onReset={resetDiagnosis}
          />
        )}

        {page === "expert" && (
          <ExpertCenter alerts={alerts} onRefresh={refreshAlerts} refreshing={refreshingAlerts} onAlertUpdated={updateAlert} loadError={alertsError} loading={loadingAlerts} />
        )}

        {page === "analytics" && (
          <AnalyticsPage alerts={alerts} history={diagnosisHistory} events={events} onNavigate={navigate} />
        )}

        {page === "crops" && <CropHealthPage onNavigate={navigate} />}

        {page === "model" && <ModelIntelligencePage history={diagnosisHistory} />}

        {page === "settings" && (
          <SettingsPage preferences={preferences} onChange={updatePreferences} socketState={socketState} onRefresh={refreshAlerts} refreshing={refreshingAlerts} alertSyncError={alertsError} />
        )}

      </main>

      <footer>
        <span>CROP DOCTOR AI</span> / V6
        INTELLIGENT AGRICULTURE SYSTEM /
        DIAGNOSTIC ASSISTANCE — NOT A REPLACEMENT
        FOR FIELD EXPERTISE
      </footer>
    </div>
  );
}

/* ===========================================================
   DASHBOARD PAGE
   =========================================================== */

/* ===========================================================
   REALTIME EVENT SUMMARY
   =========================================================== */

function summarizeEvent(type, data) {
  if (type === "connection") {
    return "Realtime diagnostic channel connected";
  }

  if (type === "diagnosis_started") {
    return "V6 inference request received";
  }

  if (type === "diagnosis_completed") {
    return `${data.crop || "Crop"} / ${
      data.diagnosis || "Diagnosis"
    } inference completed`;
  }

  if (type === "diagnosis_failed") {
    return "V6 inference request failed";
  }

  if (type === "alert_created") {
    return `${data.crop || "Crop"} / ${
      data.diagnosis || "Diagnosis"
    } alert created`;
  }

  if (type === "alert_updated") {
    return `${data.id || "Alert"} status updated`;
  }

  return "Realtime event received";
}

export default App;
