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

export class ApiError extends Error {
  constructor(message, { status = 0, code = "request_error", payload = null, cause } = {}) {
    super(message, { cause });
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

async function readPayload(response) {
  return response.json().catch(() => ({}));
}

function responseError(response, payload, fallbackMessage) {
  const message = typeof payload.message === "string"
    ? payload.message
    : typeof payload.detail === "string"
      ? payload.detail
      : fallbackMessage;
  return new ApiError(message || fallbackMessage, {
    status: response.status,
    code: typeof payload.status === "string" ? payload.status : "request_error",
    payload,
  });
}

async function readResponse(response, fallbackMessage) {
  const payload = await readPayload(response);
  if (!response.ok) {
    throw responseError(response, payload, fallbackMessage);
  }
  return payload;
}

async function request(url, options = {}, timeoutMs = 20000, externalSignal) {
  const controller = new AbortController();
  let timedOut = false;
  const timeout = globalThis.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const abortFromCaller = () => controller.abort();
  if (externalSignal?.aborted) controller.abort();
  else externalSignal?.addEventListener("abort", abortFromCaller, { once: true });
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (error) {
    if (error.name === "AbortError") {
      throw new ApiError(timedOut
        ? "The request took too long. Your photo is still here; try again when your connection is steady."
        : "The request was cancelled.", { code: timedOut ? "timeout" : "cancelled", cause: error });
    }
    if (error instanceof TypeError) {
      throw new ApiError("Connection problem. Check your internet connection and try again.", { code: "network_error", cause: error });
    }
    throw error;
  } finally {
    globalThis.clearTimeout(timeout);
    externalSignal?.removeEventListener("abort", abortFromCaller);
  }
}

export async function fetchHealth() {
  const response = await request(`${API_URL}/health`);
  const data = await readResponse(response, "Could not reach the diagnosis service.");
  if (!["healthy", "degraded"].includes(data.status) || !data.model || !data.suitability) {
    throw new ApiError("The diagnosis service returned an incomplete status.", { code: "invalid_response", payload: data });
  }
  return data;
}

export async function fetchAlerts(expertKey) {
  const headers = expertKey ? { "X-Expert-Key": expertKey } : {};
  const response = await request(`${API_URL}/alerts`, { headers });

  const data = await readResponse(response, "Failed to fetch alerts.");

  const alerts = Array.isArray(data) ? data : data.alerts;
  if (!Array.isArray(alerts)) throw new ApiError("The alert service returned an invalid response.", { code: "invalid_response", payload: data });
  return alerts;
}

export async function fetchReports() {
  const response = await request(`${API_URL}/reports`, { headers: { "X-Report-Key": getReportKey() } });
  const data = await readResponse(response, "Could not load crop reports.");
  if (!Array.isArray(data.reports)) throw new ApiError("The reports service returned an invalid response.", { code: "invalid_response", payload: data });
  return data.reports;
}

export async function fetchDiseases() {
  const response = await request(`${API_URL}/diseases`);
  const data = await readResponse(response, "Could not load crop disease reference data.");
  if (!Array.isArray(data.classes)) throw new ApiError("The crop guide returned an invalid response.", { code: "invalid_response", payload: data });
  return data.classes;
}

export async function diagnoseImage(file, { signal } = {}) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await request(`${API_URL}/diagnose`, {
    method: "POST",
    body: formData,
    headers: { "X-Report-Key": getReportKey() },
  }, 90000, signal);
  const payload = await readPayload(response);
  const resultStates = new Set(["possible_disease_detected", "healthy_class_predicted", "uncertain", "not_plant", "invalid_image", "validation_unavailable"]);
  if (resultStates.has(payload.status) && typeof payload.message === "string") return payload;
  if (!response.ok) throw responseError(response, payload, "The crop photo could not be checked.");
  throw new ApiError("The diagnosis service returned an incomplete result.", { status: response.status, code: "invalid_response", payload });
}
