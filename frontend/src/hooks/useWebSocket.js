import { useEffect } from "react";

const WS_URL =
  import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000/ws";

export default function useWebSocket({
  onEvent,
  onStatusChange,
}) {
  useEffect(() => {
    let ws;
    let retry;
    let alive = true;

    const connect = () => {
      ws = new WebSocket(WS_URL);

      onStatusChange("connecting");

      ws.onopen = () => {
        onStatusChange("live");

        onEvent({
          type: "connection",
          data: {},
        });
      };

      ws.onmessage = (message) => {
        try {
          const payload = JSON.parse(message.data);

          onEvent({
            type: payload.type || "event",
            data:
              payload.alert ||
              payload.diagnosis ||
              payload.data ||
              {},
          });
        } catch (error) {
          console.error("Realtime event error:", error);
        }
      };

      ws.onclose = () => {
        if (!alive) return;

        onStatusChange("offline");
        retry = setTimeout(connect, 2500);
      };

      ws.onerror = () => {
        onStatusChange("offline");
      };
    };

    connect();

    return () => {
      alive = false;
      clearTimeout(retry);
      ws?.close();
    };
  }, [onEvent, onStatusChange]);
}
