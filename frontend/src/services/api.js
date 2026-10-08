export const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/+$/, "");
export const WS_URL = import.meta.env.VITE_WS_URL || `${API_URL.replace(/^http/, "ws")}/ws`;

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
