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

async function readResponse(response, fallbackMessage) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof payload.detail === "string" ? payload.detail : fallbackMessage;
    throw new Error(detail || fallbackMessage);
  }
  return payload;
}

export async function fetchHealth() {
  const response = await fetch(`${API_URL}/health`);
  return readResponse(response, "Could not reach the diagnosis service.");
}

export async function fetchAlerts() {
  const response = await fetch(`${API_URL}/alerts`);

  const data = await readResponse(response, "Failed to fetch alerts.");

  return Array.isArray(data)
    ? data
    : Array.isArray(data.alerts)
      ? data.alerts
      : [];
}

export async function fetchDiseases() {
  const response = await fetch(`${API_URL}/diseases`);
  const data = await readResponse(response, "Could not load crop disease reference data.");
  return Array.isArray(data.classes) ? data.classes : [];
}

export async function diagnoseImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/diagnose`, {
    method: "POST",
    body: formData,
  });

  return readResponse(response, "Diagnosis request failed.");
}
