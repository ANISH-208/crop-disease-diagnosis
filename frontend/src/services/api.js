const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function fetchAlerts() {
  const response = await fetch(`${API_URL}/alerts`);

  if (!response.ok) {
    throw new Error("Failed to fetch alerts.");
  }

  const data = await response.json();

  return Array.isArray(data)
    ? data
    : data.alerts || [];
}

export async function diagnoseImage(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_URL}/diagnose`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("Diagnosis request failed.");
  }

  return response.json();
}
