import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import "./components/Navigation.css";

import { diagnoseImage, fetchAlerts, fetchHealth, fetchReports } from "./services/api";
import { validatePhotoFile } from "./services/photoInput";
import useWebSocket from "./hooks/useWebSocket";
import Navigation from "./components/Navigation";
import { DashboardPage, ScannerPage } from "./components/MainPages";
import FarmerHome from "./components/FarmerHome";
import ReportsPage from "./components/ReportsPage";
import HelpPage from "./components/HelpPage";
import ExpertCenter from "./components/ExpertCenter";
import { AnalyticsPage, CropHealthPage, ModelIntelligencePage, SettingsPage } from "./components/OperationsPages";
import { translate as t } from "./i18n";

function App() {
  const [page, setPage] = useState("home");
  const [selectedFile, setSelectedFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expertAccessKey, setExpertAccessKey] = useState(() => {
    try { return sessionStorage.getItem("crop-doctor-expert-key") || ""; } catch { return ""; }
  });
  const [alertsError, setAlertsError] = useState(() => expertAccessKey ? "" : "Enter the expert access key in Settings to load the alert queue.");
  const [reportsError, setReportsError] = useState("");
  const [backendState, setBackendState] = useState("checking");
  const [diagnosisAvailable, setDiagnosisAvailable] = useState(false);
  const [diagnosisUnavailableReason, setDiagnosisUnavailableReason] = useState("");
  const [modelState, setModelState] = useState("checking");
  const [socketState, setSocketState] = useState("connecting");
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [reports, setReports] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(Boolean(expertAccessKey));
  const [loadingReports, setLoadingReports] = useState(true);
  const [diagnosisHistory, setDiagnosisHistory] = useState([]);
  const [refreshingAlerts, setRefreshingAlerts] = useState(false);
  const [language] = useState(() => {
    try { return localStorage.getItem("crop-doctor-language") || "en"; } catch { return "en"; }
  });
  const text = (key) => t(language, key);
  const [preferences, setPreferences] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("crop-doctor-preferences") || "{}");
      return {
        palette: ["canopy", "fern", "moss"].includes(stored.palette) ? stored.palette : "canopy",
        motion: typeof stored.motion === "boolean" ? stored.motion : true,
      };
    } catch { return { palette: "canopy", motion: true }; }
  });
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const sessionReportsRef = useRef([]);

  const pushEvent = useCallback((label, detail) => {
    setEvents((current) => [{ id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`, time: new Date().toLocaleTimeString([], { hour12: false }), label, detail }, ...current].slice(0, 8));
  }, []);

  const refreshReports = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setLoadingReports(true);
    try {
      const data = await fetchReports();
      setReports((current) => {
        const combined = new Map([...current, ...sessionReportsRef.current, ...data].map((report) => [report.id || report.job_id, report]));
        return [...combined.values()].sort((left, right) => new Date(right.created_at || 0) - new Date(left.created_at || 0));
      });
      setReportsError("");
    } catch (requestError) {
      setReportsError(requestError.message || "Reports could not be loaded. Check your connection and try again.");
    } finally {
      if (!quiet) setLoadingReports(false);
    }
  }, []);

  const refreshHealth = useCallback(async () => {
    try {
      const data = await fetchHealth();
      setBackendState(data.status === "healthy" ? "healthy" : "degraded");
      setDiagnosisAvailable(Boolean(data.diagnosis_ready));
      setDiagnosisUnavailableReason(getDiagnosisUnavailableReason(data));
      setModelState(data.model?.status || "unknown");
    } catch {
      setBackendState("offline");
      setDiagnosisAvailable(false);
      setDiagnosisUnavailableReason("Could not reach the crop photo service.");
      setModelState("unknown");
    }
  }, []);

  const refreshAlerts = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setRefreshingAlerts(true);
    if (!expertAccessKey) {
      setAlerts([]);
      setAlertsError("Enter the expert access key in Settings to load the alert queue.");
      setLoadingAlerts(false);
      if (!quiet) setRefreshingAlerts(false);
      return;
    }
    try {
      const data = await fetchAlerts(expertAccessKey);
      setAlerts(data);
      setAlertsError("");
    } catch (requestError) {
      setAlertsError(requestError.message || "Could not load crop reports. Check your connection and retry.");
    } finally {
      setLoadingAlerts(false);
      if (!quiet) setRefreshingAlerts(false);
    }
  }, [expertAccessKey]);

  const handleRealtimeEvent = useCallback((type, data = {}) => {
    pushEvent(type.replaceAll("_", " ").toUpperCase(), summarizeEvent(type));
    if (expertAccessKey && (type === "alert_created" || type === "alert_updated")) {
      const incoming = data.alert || data;
      if (incoming?.id) {
        setAlerts((current) => type === "alert_created"
          ? [incoming, ...current.filter((item) => item.id !== incoming.id)]
          : current.map((item) => item.id === incoming.id ? { ...item, ...incoming } : item));
        if (type === "alert_updated" && !alerts.some((item) => item.id === incoming.id)) void refreshAlerts({ quiet: true });
      } else {
        void refreshAlerts({ quiet: true });
      }
    }
  }, [alerts, expertAccessKey, pushEvent, refreshAlerts]);

  const handleSocketEvent = useCallback(({ type, data }) => handleRealtimeEvent(type, data), [handleRealtimeEvent]);
  const handleSocketStatus = useCallback((status) => setSocketState(status), []);
  useWebSocket({ onEvent: handleSocketEvent, onStatusChange: handleSocketStatus });

  useEffect(() => {
    let active = true;
    fetchHealth().then((data) => {
      if (!active) return;
      setBackendState(data.status === "healthy" ? "healthy" : "degraded");
      setDiagnosisAvailable(Boolean(data.diagnosis_ready));
      setDiagnosisUnavailableReason(getDiagnosisUnavailableReason(data));
      setModelState(data.model?.status || "unknown");
    }).catch(() => {
      if (!active) return;
      setBackendState("offline");
      setDiagnosisAvailable(false);
      setDiagnosisUnavailableReason("Could not reach the crop photo service.");
      setModelState("unknown");
    });
    fetchReports().then((data) => {
      if (!active) return;
      setReports(data);
      setReportsError("");
    }).catch((requestError) => {
      if (active) setReportsError(requestError.message || "Reports could not be loaded. Check your connection and try again.");
    }).finally(() => {
      if (active) setLoadingReports(false);
    });
    if (expertAccessKey) {
      fetchAlerts(expertAccessKey).then((data) => {
        if (active) {
          setAlerts(data);
          setAlertsError("");
        }
      }).catch((requestError) => {
        if (active) setAlertsError(requestError.message || "Could not load crop reports. Check your connection and retry.");
      }).finally(() => {
        if (active) setLoadingAlerts(false);
      });
    }
    return () => { active = false; };
  }, [expertAccessKey]);

  useEffect(() => {
    document.documentElement.lang = language;
    try { localStorage.setItem("crop-doctor-language", language); } catch { /* Session-only preference is fine. */ }
  }, [language]);

  useEffect(() => () => {
    if (preview?.startsWith("blob:")) URL.revokeObjectURL(preview);
  }, [preview]);

  const handleFileChange = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setPage("scanner");
    try {
      const normalizedFile = await validatePhotoFile(file);
      setSelectedFile(normalizedFile);
      setPreview(URL.createObjectURL(normalizedFile));
      setResult(null);
      setError("");
    } catch (validationError) {
      setError(validationError.message);
      setSelectedFile(null);
      setPreview(null);
      setResult(null);
    }
  };

  const requestCamera = () => {
    setPage("scanner");
    setError("");
    cameraInputRef.current?.click();
  };
  const requestGallery = () => {
    setPage("scanner");
    setError("");
    galleryInputRef.current?.click();
  };

  const diagnoseCrop = async () => {
    if (!selectedFile || loading || !diagnosisAvailable) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const data = await diagnoseImage(selectedFile);
      setResult(data);
      if (["possible_disease_detected", "healthy_class_predicted"].includes(data.status)) {
        setModelState(data.model_version || "available");
        setDiagnosisHistory((current) => [{ ...data, id: data.job_id, analyzed_at: data.created_at || new Date().toISOString() }, ...current].slice(0, 100));
        const sessionReport = { ...data, id: data.job_id, created_at: data.created_at || new Date().toISOString() };
        sessionReportsRef.current = [sessionReport, ...sessionReportsRef.current.filter((item) => item.id !== sessionReport.id)];
        setReports((current) => [sessionReport, ...current.filter((item) => item.id !== sessionReport.id)]);
        void refreshReports({ quiet: true });
        if (expertAccessKey) void refreshAlerts({ quiet: true });
      }
      pushEvent("PHOTO CHECKED", data.message || "The photo check is complete.");
    } catch (requestError) {
      setError(requestError.message || "Connection problem. Check your internet and try again.");
      void refreshHealth();
    } finally {
      setLoading(false);
    }
  };

  const resetDiagnosis = () => {
    setSelectedFile(null);
    setPreview(null);
    setResult(null);
    setError("");
  };
  const navigate = (nextPage) => {
    setPage(nextPage);
    window.scrollTo({ top: 0, behavior: preferences.motion ? "smooth" : "instant" });
  };
  const updateAlert = (updated) => setAlerts((current) => current.map((alert) => alert.id === updated.id ? { ...alert, ...updated } : alert));
  const updateExpertKey = (nextKey) => {
    const normalizedKey = nextKey.trim();
    setExpertAccessKey(normalizedKey);
    setAlerts([]);
    setAlertsError(normalizedKey ? "" : "Enter the expert access key in Settings to load the alert queue.");
    setLoadingAlerts(Boolean(normalizedKey));
    try {
      if (normalizedKey) sessionStorage.setItem("crop-doctor-expert-key", normalizedKey);
      else sessionStorage.removeItem("crop-doctor-expert-key");
    } catch { /* Keep the key in memory for this app session. */ }
  };
  const updatePreferences = (next) => {
    setPreferences(next);
    try { localStorage.setItem("crop-doctor-preferences", JSON.stringify(next)); } catch { /* Session-only preference is fine. */ }
  };

  const stats = useMemo(() => ({
    pending: alerts.filter((alert) => alert.status === "pending").length,
    review: alerts.filter((alert) => alert.status === "in_review").length,
    resolved: alerts.filter((alert) => alert.status === "resolved").length,
  }), [alerts]);

  return <div className={`app-shell palette-${preferences.palette} ${preferences.motion ? "motion-on" : "motion-off"}`}>
    <a className="skip-link" href="#main-content">Skip to main content</a>
    <header className="farmer-header">
      <button className="brand-button" aria-label="FieldLeaf AI home" onClick={() => navigate("home")}><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none"><path d="M16.2 24.9c-7.4-.8-11.2-5-10.3-12.3 6.8 1.1 10.4 5.1 10.3 12.3Z" fill="currentColor"/><path d="M16.6 22.4c.7-7.2 4.9-11 12.1-10.2-1 6.8-5 10.5-12.1 10.2Z" fill="currentColor" opacity=".72"/><path d="M16.1 25.7c.2-5.8.4-10.5.1-16.2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg></span><span><strong>FieldLeaf AI</strong><small>{text("brandTagline")}</small></span></button>
      <div className="header-tools">
        <span className={`header-status ${backendState === "healthy" ? "ready" : backendState === "offline" || backendState === "degraded" ? "offline" : ""}`} role="status"><i aria-hidden="true" />{backendState === "healthy" ? text("serviceReady") : backendState === "offline" || backendState === "degraded" ? text("connectionProblem") : text("checkingService")}</span>
      </div>
    </header>

    <input ref={cameraInputRef} className="visually-hidden" tabIndex={-1} type="file" accept="image/*" capture="environment" onChange={handleFileChange} aria-label="Take a crop photo" />
    <input ref={galleryInputRef} className="visually-hidden" tabIndex={-1} type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" onChange={handleFileChange} aria-label="Choose a JPG or PNG photo from gallery" />

    <Navigation page={page} onNavigate={navigate} language={language} />
    <main id="main-content" className="farmer-main">
      {page === "home" && <FarmerHome language={language} backendState={backendState} diagnosisAvailable={diagnosisAvailable} diagnosisUnavailableReason={diagnosisUnavailableReason} reports={reports} reportsLoading={loadingReports} reportsError={reportsError} onTakePhoto={requestCamera} onChoosePhoto={requestGallery} onNavigate={navigate} />}
      {page === "scanner" && <ScannerPage selectedFile={selectedFile} preview={preview} result={result} loading={loading} error={error} backendState={backendState} diagnosisAvailable={diagnosisAvailable} diagnosisUnavailableReason={diagnosisUnavailableReason} language={language} onTakePhoto={requestCamera} onChoosePhoto={requestGallery} onDiagnose={diagnoseCrop} onReset={resetDiagnosis} onRetryConnection={refreshHealth} />}
      {page === "reports" && <ReportsPage language={language} reports={reports} loading={loadingReports} error={reportsError} onRetry={() => void refreshReports()} onNavigate={navigate} />}
      {page === "help" && <HelpPage language={language} onNavigate={navigate} />}
      {page === "dashboard" && <DashboardPage alerts={alerts} events={events} stats={stats} socketState={socketState} backendState={backendState} modelState={modelState} alertsError={alertsError} onNavigate={navigate} result={result} />}
      {page === "expert" && <ExpertCenter alerts={alerts} expertAccessKey={expertAccessKey} backendState={backendState} socketState={socketState} onRefresh={() => void refreshAlerts()} refreshing={refreshingAlerts} onAlertUpdated={updateAlert} loadError={alertsError} loading={loadingAlerts} />}
      {page === "analytics" && <AnalyticsPage alerts={alerts} history={diagnosisHistory} events={events} onNavigate={navigate} />}
      {page === "crops" && <CropHealthPage onNavigate={navigate} />}
      {page === "model" && <ModelIntelligencePage history={diagnosisHistory} />}
      {page === "settings" && <SettingsPage preferences={preferences} onChange={updatePreferences} socketState={socketState} onRefresh={() => void refreshAlerts()} refreshing={refreshingAlerts} alertSyncError={alertsError} expertAccessKey={expertAccessKey} onExpertKeyChange={updateExpertKey} />}
    </main>
    <footer className="farmer-footer"><span>FieldLeaf AI</span><span>{text("farmerFooter")}</span></footer>
  </div>;
}

function summarizeEvent(type) {
  if (type === "connection") return "Service connection is active";
  if (type === "diagnosis_started") return "Your crop photo is being checked";
  if (type === "diagnosis_completed") return "A crop photo check is complete";
  if (type === "diagnosis_failed") return "The crop photo could not be checked";
  if (type === "alert_created") return "An expert review was requested";
  if (type === "alert_updated") return "An expert review status changed";
  return "Crop report updated";
}

function getDiagnosisUnavailableReason(data) {
  if (data.diagnosis_ready) return "";
  if (!data.suitability?.ready) return "Crop photo checks are not ready yet. Please try again later.";
  if (!data.model?.ready) return "The crop photo service is not available at the moment.";
  if (!data.disease_policy?.ready) return "Disease results are not ready yet. Please try again later.";
  return "Crop photo checks are not ready yet. Please try again later.";
}

export default App;
