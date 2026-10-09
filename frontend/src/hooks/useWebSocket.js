import { useEffect } from "react";
import { WS_URL } from "../services/api";

export default function useWebSocket({
  onEvent,
  onStatusChange,
}) {
  useEffect(() => {
    if (!WS_URL) {
      onStatusChange("rest");
      return undefined;
    }

    let ws;
    let retryTimer;
    let alive = true;
    let retryCount = 0;

    const connect = () => {
      if (!alive) return;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        scheduleReconnect();
        return;
      }

      onStatusChange("connecting");

      ws.onopen = () => {
        retryCount = 0;
        onStatusChange("live");
      };

      ws.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);
          const eventType = payload.type || "event";
          let data = payload.data ?? payload.alert ?? payload.diagnosis ?? {};
          if (eventType === "alert_created" || eventType === "alert_updated") {
            data = data.alert ?? data;
          } else if (eventType === "diagnosis_completed") {
            data = data.diagnosis
              ? { ...data.diagnosis, job_id: data.job_id }
              : data;
          }

          onEvent({
            type: eventType,
            data,
          });
        } catch {
          onEvent({ type: "protocol_error", data: { message: "Could not read a realtime event." } });
        }
      };

      ws.onclose = () => {
        if (!alive) return;

        onStatusChange("offline");
        scheduleReconnect();
      };

      ws.onerror = () => {
        onStatusChange("offline");
        ws?.close();
      };
    };

    const scheduleReconnect = () => {
      if (!alive || retryTimer) return;
      const delay = Math.min(1000 * 2 ** retryCount, 30000);
      retryCount += 1;
      retryTimer = setTimeout(() => {
        retryTimer = null;
        connect();
      }, delay);
    };

    connect();

    return () => {
      alive = false;
      clearTimeout(retryTimer);
      ws?.close();
    };
  }, [onEvent, onStatusChange]);
}
