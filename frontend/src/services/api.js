// The Vercel frontend and API are deployed together. Keep production calls on
// this origin so an old VITE_API_URL value cannot send requests back to Render.
export const API_URL = (import.meta.env.PROD
  ? "/api"
  : import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");

function websocketUrl() {
  // Vercel Functions do not provide persistent WebSocket connections.
  if (import.meta.env.PROD) return "";
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const url = new URL(`${API_URL}/ws`, window.location.origin);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export const WS_URL = websocketUrl();
let sessionReportKey;

function getReportKey() {
  if (sessionReportKey) return sessionReportKey;
  try {
    sessionReportKey = localStorage.getItem("crop-doctor-report-key");
  } catch {
    // Continue with a session-only key when browser storage is unavailable.
  }
  if (!sessionReportKey) {
    if (!globalThis.crypto?.getRandomValues) throw new Error("Secure browser storage is unavailable. Open this app over HTTPS and try again.");
    const bytes = globalThis.crypto.getRandomValues(new Uint8Array(32));
    sessionReportKey = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    try { localStorage.setItem("crop-doctor-report-key", sessionReportKey); } catch { /* Keep the key for this app session. */ }
  }
  return sessionReportKey;
}

async function readResponse(response, fallbackMessage) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : fallbackMessage;
    throw new Error(detail || fallbackMessage);
  }
  return payload;
}

async function request(url, options = {}, timeoutMs = 20000) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("The request took too long. Your photo is still here; try again when your connection is steady.", { cause: error });
    }
    if (error instanceof TypeError) {
      throw new Error("Connection problem. Check your internet connection and try again.", { cause: error });
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function fetchHealth() {
  const response = await request(`${API_URL}/health`);
  return readResponse(response, "Could not reach the diagnosis service.");
}

export async function fetchAlerts() {
  const response = await request(`${API_URL}/alerts`);

  const data = await readResponse(response, "Failed to fetch alerts.");

  return Array.isArray(data)
    ? data
    : Array.isArray(data.alerts)
      ? data.alerts
      : [];
}

export async function fetchReports() {
  const response = await request(`${API_URL}/reports`, { headers: { "X-Report-Key": getReportKey() } });
  const data = await readResponse(response, "Could not load crop reports.");
  return Array.isArray(data.reports) ? data.reports : [];
}

export async function fetchDiseases() {
  const response = await request(`${API_URL}/diseases`);
  const data = await readResponse(response, "Could not load crop disease reference data.");
  return Array.isArray(data.classes) ? data.classes : [];
}

export async function diagnoseImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await request(`${API_URL}/diagnose`, {
    method: "POST",
    body: formData,
    headers: { "X-Report-Key": getReportKey() },
  }, 90000);

  return readResponse(response, "Diagnosis request failed.");
}
