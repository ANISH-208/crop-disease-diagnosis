import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./App.css";
import "./components/Navigation.css";

import { diagnoseImage, fetchAlerts, fetchHealth, fetchReports } from "./services/api";
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
  const [alertsError, setAlertsError] = useState("");
  const [reportsError, setReportsError] = useState("");
  const [backendState, setBackendState] = useState("checking");
  const [modelState, setModelState] = useState("checking");
  const [socketState, setSocketState] = useState("connecting");
  const [events, setEvents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [reports, setReports] = useState([]);
  const [loadingAlerts, setLoadingAlerts] = useState(true);
  const [loadingReports, setLoadingReports] = useState(true);
  const [diagnosisHistory, setDiagnosisHistory] = useState([]);
  const [refreshingAlerts, setRefreshingAlerts] = useState(false);
  const [language, setLanguage] = useState(() => {
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
      setModelState(data.model?.status || "unknown");
    } catch {
      setBackendState("offline");
      setModelState("unknown");
    }
  }, []);

  const refreshAlerts = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setRefreshingAlerts(true);
    try {
      const data = await fetchAlerts();
      setAlerts(data);
      setAlertsError("");
    } catch (requestError) {
      setAlertsError(requestError.message || "Could not load crop reports. Check your connection and retry.");
    } finally {
      setLoadingAlerts(false);
      if (!quiet) setRefreshingAlerts(false);
    }
  }, []);

  const handleRealtimeEvent = useCallback((type, data) => {
    pushEvent(type.replaceAll("_", " ").toUpperCase(), summarizeEvent(type, data));
    if (type === "alert_created") setAlerts((current) => [data, ...current.filter((alert) => alert.id !== data.id)]);
    if (type === "alert_updated") setAlerts((current) => current.map((alert) => alert.id === (data.alert || data).id ? { ...alert, ...(data.alert || data) } : alert));
    if (type === "diagnosis_completed" && data) {
      const report = data.diagnosis || data;
      setReports((current) => [report, ...current.filter((item) => item.id !== (report.id || report.job_id))]);
    }
  }, [pushEvent]);

  const handleSocketEvent = useCallback(({ type, data }) => handleRealtimeEvent(type, data), [handleRealtimeEvent]);
  const handleSocketStatus = useCallback((status) => setSocketState(status), []);
  useWebSocket({ onEvent: handleSocketEvent, onStatusChange: handleSocketStatus });

  useEffect(() => {
    let active = true;
    fetchHealth().then((data) => {
      if (!active) return;
      setBackendState(data.status === "healthy" ? "healthy" : "degraded");
      setModelState(data.model?.status || "unknown");
    }).catch(() => {
      if (!active) return;
      setBackendState("offline");
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
    fetchAlerts().then((data) => {
      if (active) setAlerts(data);
    }).catch((requestError) => {
      if (active) setAlertsError(requestError.message || "Could not load crop reports. Check your connection and retry.");
    }).finally(() => {
      if (active) setLoadingAlerts(false);
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    document.documentElement.lang = language;
    try { localStorage.setItem("crop-doctor-language", language); } catch { /* Session-only preference is fine. */ }
  }, [language]);

  useEffect(() => () => {
    if (preview?.startsWith("blob:")) URL.revokeObjectURL(preview);
  }, [preview]);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const supportedType = new Set(["image/jpeg", "image/png"]).has(file.type);
    const supportedName = /\.(jpe?g|png)$/i.test(file.name);
    if (!supportedType || !supportedName) {
      setError("Choose a JPG or PNG photo. Photos in other formats are not supported yet.");
      setPage("scanner");
      return;
    }
    if (file.size > 4 * 1024 * 1024) {
      setError("This photo is larger than 4 MB. Choose a smaller JPG or PNG photo.");
      setPage("scanner");
      return;
    }
    setSelectedFile(file);
    setPreview(URL.createObjectURL(file));
    setResult(null);
    setError("");
    setPage("scanner");
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
    if (!selectedFile || loading) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const data = await diagnoseImage(selectedFile);
      setResult(data);
      setModelState(data.model_version || "available");
      setDiagnosisHistory((current) => [{ ...data, id: data.job_id, analyzed_at: data.created_at || new Date().toISOString() }, ...current].slice(0, 100));
      const sessionReport = { ...data, id: data.job_id, created_at: data.created_at || new Date().toISOString() };
      sessionReportsRef.current = [sessionReport, ...sessionReportsRef.current.filter((item) => item.id !== sessionReport.id)];
      setReports((current) => [sessionReport, ...current.filter((item) => item.id !== sessionReport.id)]);
      pushEvent("PHOTO CHECKED", `${data.crop || "Crop"} · ${data.diagnosis || "Result ready"}`);
      void refreshReports({ quiet: true });
      void refreshAlerts({ quiet: true });
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
      <button className="brand-button" aria-label="Crop Doctor AI home" onClick={() => navigate("home")}><span className="brand-mark" aria-hidden="true">✳</span><span><strong>Crop Doctor AI</strong><small>{text("brandTagline")}</small></span></button>
      <div className="header-tools">
        <span className={`header-status ${backendState === "healthy" ? "ready" : backendState === "offline" || backendState === "degraded" ? "offline" : ""}`} role="status"><i aria-hidden="true" />{backendState === "healthy" ? text("serviceReady") : backendState === "offline" || backendState === "degraded" ? text("connectionProblem") : text("checkingService")}</span>
        <label className="language-picker"><span>{"Language"}</span><select aria-label="Language" value={language} onChange={(event) => setLanguage(event.target.value)}><option value="en">English</option></select></label>
      </div>
    </header>

    <input ref={cameraInputRef} className="visually-hidden" tabIndex={-1} type="file" accept="image/*" capture="environment" onChange={handleFileChange} aria-label="Take a crop photo" />
    <input ref={galleryInputRef} className="visually-hidden" tabIndex={-1} type="file" accept="image/jpeg,image/png,.jpg,.jpeg,.png" onChange={handleFileChange} aria-label="Choose a JPG or PNG photo from gallery" />

    <Navigation page={page} onNavigate={navigate} language={language} />
    <main id="main-content" className="farmer-main">
      {page === "home" && <FarmerHome language={language} backendState={backendState} reports={reports} reportsLoading={loadingReports} reportsError={reportsError} onTakePhoto={requestCamera} onChoosePhoto={requestGallery} onNavigate={navigate} />}
      {page === "scanner" && <ScannerPage selectedFile={selectedFile} preview={preview} result={result} loading={loading} error={error} backendState={backendState} language={language} onTakePhoto={requestCamera} onChoosePhoto={requestGallery} onDiagnose={diagnoseCrop} onReset={resetDiagnosis} onRetryConnection={refreshHealth} />}
      {page === "reports" && <ReportsPage language={language} reports={reports} loading={loadingReports} error={reportsError} onRetry={() => void refreshReports()} onNavigate={navigate} />}
      {page === "help" && <HelpPage language={language} onNavigate={navigate} />}
      {page === "dashboard" && <DashboardPage alerts={alerts} events={events} stats={stats} socketState={socketState} backendState={backendState} modelState={modelState} alertsError={alertsError} onNavigate={navigate} result={result} />}
      {page === "expert" && <ExpertCenter alerts={alerts} onRefresh={() => void refreshAlerts()} refreshing={refreshingAlerts} onAlertUpdated={updateAlert} loadError={alertsError} loading={loadingAlerts} />}
      {page === "analytics" && <AnalyticsPage alerts={alerts} history={diagnosisHistory} events={events} onNavigate={navigate} />}
      {page === "crops" && <CropHealthPage onNavigate={navigate} />}
      {page === "model" && <ModelIntelligencePage history={diagnosisHistory} />}
      {page === "settings" && <SettingsPage preferences={preferences} onChange={updatePreferences} socketState={socketState} onRefresh={() => void refreshAlerts()} refreshing={refreshingAlerts} alertSyncError={alertsError} />}
    </main>
    <footer className="farmer-footer"><span>Crop Doctor AI</span><span>{text("farmerFooter")}</span></footer>
  </div>;
}

function summarizeEvent(type, data) {
  if (type === "connection") return "Service connection is active";
  if (type === "diagnosis_started") return "Your crop photo is being checked";
  if (type === "diagnosis_completed") return `${data.crop || "Crop"} · result ready`;
  if (type === "diagnosis_failed") return "The crop photo could not be checked";
  if (type === "alert_created") return `${data.crop || "Crop"} needs an expert review`;
  if (type === "alert_updated") return "An expert review was updated";
  return "Crop report updated";
}

export default App;
