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
    const seenEventIds = new Set();

    const connect = () => {
      if (!alive) return;
      try {
        ws = new WebSocket(WS_URL);
      } catch {
        onStatusChange("offline");
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
          const eventId = payload.event_id;
          if (eventId && seenEventIds.has(eventId)) return;
          if (eventId) {
            seenEventIds.add(eventId);
            if (seenEventIds.size > 100) seenEventIds.delete(seenEventIds.values().next().value);
          }
          onEvent({ type: eventType, eventId, data: payload.data ?? payload.alert ?? payload.diagnosis ?? {} });
        } catch {
          onEvent({ type: "protocol_error", eventId: null, data: { message: "Could not read a realtime event." } });
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
