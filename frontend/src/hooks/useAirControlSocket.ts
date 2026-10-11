import { useEffect, useRef, useState, useCallback } from 'react';
import type { TelemetryState, CalibrationSettings } from '../types/telemetry';

const INITIAL_STATE: TelemetryState = {
  mouse_paused: true,
  camera_connected: false,
  hands_detected: 0,
  voice_mode: 'online',
  voice_busy: false,
  voice_status: 'Voice: Ready',
  recognized_text: 'No request recognized yet.',
  assistant_status: 'Ready. Built-in intents & Gemini fallback active.',
  last_action: 'Last action: None',
  system_status: 'Engine starting...',
  calibration: {
    sensitivity: 1.0,
    min_cutoff: 0.8,
    click_cooldown: 0.4,
  },
  audit_logs: [
    {
      timestamp: '00:00:00',
      source: 'SYS',
      event: 'AirControl UI Initialized',
      status: 'ONLINE',
    },
  ],
};

export function useAirControlSocket() {
  const [state, setState] = useState<TelemetryState>(INITIAL_STATE);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    // When using vite proxy, /api/ws proxies to backend
    const wsUrl = `${protocol}//${host}/api/ws`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'INIT_STATE' && data.state) {
          setState((prev) => ({
            ...prev,
            ...data.state,
          }));
        } else if (data.type === 'UPDATE' && data.state) {
          setState((prev) => {
            const nextLogs = data.new_logs && data.new_logs.length > 0
              ? [...prev.audit_logs, ...data.new_logs].slice(-100)
              : (data.state.audit_logs ?? prev.audit_logs);

            return {
              ...prev,
              ...data.state,
              audit_logs: nextLogs,
            };
          });
        }
      } catch (err) {
        console.error('WebSocket parse error:', err);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      // Reconnect after delay
      setTimeout(connect, 2000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendAction = useCallback((action: string, payload: Record<string, unknown> = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    } else {
      // Fallback to HTTP REST endpoint if WebSocket is reconnecting
      fetch(`/api/action/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).catch((err) => console.error('REST fallback error:', err));
    }
  }, []);

  const toggleMouse = useCallback(() => {
    sendAction('toggle_mouse');
  }, [sendAction]);

  const setVoiceMode = useCallback((mode: 'online' | 'offline') => {
    sendAction('set_voice_mode', { mode });
  }, [sendAction]);

  const listenVoice = useCallback(() => {
    sendAction('listen_voice');
  }, [sendAction]);

  const cancelVoice = useCallback(() => {
    sendAction('cancel_voice');
  }, [sendAction]);

  const updateCalibration = useCallback(
    (settings: Partial<CalibrationSettings>) => {
      sendAction('update_calibration', { settings });
    },
    [sendAction]
  );

  return {
    state,
    connected,
    toggleMouse,
    setVoiceMode,
    listenVoice,
    cancelVoice,
    updateCalibration,
  };
}
