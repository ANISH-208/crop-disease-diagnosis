import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import "./App.css";

import {
  diagnoseImage,
  fetchAlerts,
} from "./services/api";

import useWebSocket from "./hooks/useWebSocket";

import Scanner from "./components/Scanner";
import SpecimenInput from "./components/SpecimenInput";
import InferencePipeline from "./components/InferencePipeline";
import DiagnosisResult from "./components/DiagnosisResult";
import MonitorGrid from "./components/MonitorGrid";
import FieldResponse from "./components/FieldResponse";

function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [socketState, setSocketState] =
    useState("connecting");

  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
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
        ].slice(0, 12));
      }

      if (type === "alert_updated") {
        setAlerts((current) =>
          current.map((alert) =>
            alert.id === data.id
              ? { ...alert, ...data }
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

  useWebSocket({
    onEvent: handleSocketEvent,
    onStatusChange: setSocketState,
  });

  /* =========================================================
     INITIAL ALERT LOAD
     ========================================================= */

  useEffect(() => {
    fetchAlerts()
      .then((data) => {
        setAlerts(data.slice(0, 12));
      })
      .catch(() => {});
  }, []);

  /* =========================================================
     FILE SELECTION
     ========================================================= */

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    if (!file.type.startsWith("image/")) {
      setError(
        "Please select a JPG or PNG crop image."
      );
      return;
    }

    if (preview) {
      URL.revokeObjectURL(preview);
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

    const timer1 = setTimeout(() => {
      setScanStep(2);
    }, 500);

    const timer2 = setTimeout(() => {
      setScanStep(3);
    }, 1100);

    try {
      const data =
        await diagnoseImage(selectedFile);

      setResult(data);
      setScanStep(4);
    } catch (err) {
      console.error(err);

      setError(
        "Unable to connect to the diagnosis server. Make sure FastAPI is running."
      );

      setScanStep(0);

      pushEvent(
        "INFERENCE ERROR",
        "FastAPI diagnosis endpoint unavailable"
      );
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setLoading(false);
    }
  };

  /* =========================================================
     RESET
     ========================================================= */

  const resetDiagnosis = () => {
    if (preview) {
      URL.revokeObjectURL(preview);
    }

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
     RENDER
     ========================================================= */

  return (
    <div className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      {/* =====================================================
          TOP BAR
          ===================================================== */}

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
            {socketState === "live"
              ? "REALTIME LINK"
              : "LINKING..."}
          </span>

          <em>V6.0</em>
        </div>
      </header>

      {/* =====================================================
          MAIN DASHBOARD
          ===================================================== */}

      <main className="dashboard">

        {/* ===================================================
            HERO
            =================================================== */}

        <section className="hero-panel">
          <div className="hero-copy">
            <div className="eyebrow">
              AI FIELD INTELLIGENCE / 038 CLASSIFIERS
            </div>

            <h1>
              See the disease.
              <br />
              <span>Stop it early.</span>
            </h1>

            <p>
              Upload a crop image and activate the V6
              vision engine. Diagnosis, confidence
              telemetry and expert escalation arrive as
              one live diagnostic stream.
            </p>

            <div className="hero-pills">
              <span>
                ● EFFICIENTNETV2-S
              </span>

              <span>
                ● 38 CLASSES
              </span>

              <span>
                ● REALTIME ALERTS
              </span>
            </div>
          </div>

          <Scanner
            preview={preview}
            loading={loading}
          />
        </section>

        {/* ===================================================
            INPUT + INFERENCE PIPELINE
            =================================================== */}

        <section className="workspace">
          <SpecimenInput
            selectedFile={selectedFile}
            error={error}
            loading={loading}
            inputRef={inputRef}
            onFileChange={handleFileChange}
            onDiagnose={diagnoseCrop}
            onReset={resetDiagnosis}
          />

          <InferencePipeline
            scanStep={scanStep}
          />
        </section>

        {/* ===================================================
            DIAGNOSIS RESULT
            =================================================== */}

        {result && (
          <DiagnosisResult
            result={result}
          />
        )}

        {/* ===================================================
            MONITOR GRID
            =================================================== */}

        <MonitorGrid
          result={result}
          socketState={socketState}
          events={events}
          alerts={alerts}
          stats={stats}
        />

        {/* ===================================================
            FIELD RESPONSE
            =================================================== */}

        <FieldResponse
          result={result}
        />
      </main>

      {/* =====================================================
          FOOTER
          ===================================================== */}

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