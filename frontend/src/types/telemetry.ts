export interface CalibrationSettings {
  sensitivity: number;
  min_cutoff: number;
  click_cooldown: number;
  gesture_hold_normal?: number;
  gesture_hold_dangerous?: number;
  gesture_cooldown?: number;
  scroll_speed?: number;
}

export interface AuditLogEntry {
  timestamp: string;
  source: string;
  event: string;
  status: string;
}

export interface TelemetryState {
  mouse_paused: boolean;
  camera_connected: boolean;
  hands_detected: number;
  control_mode: 'cursor' | 'gesture';
  gesture_keys_enabled: boolean;
  detected_gesture: string;
  gesture_action: string;
  gesture_progress: number;
  voice_mode: 'online' | 'offline';
  voice_busy: boolean;
  voice_listening_active: boolean;
  browser_speaking: boolean;
  voice_status: string;
  recognized_text: string;
  assistant_status: string;
  last_action: string;
  system_status: string;
  calibration: CalibrationSettings;
  audit_logs: AuditLogEntry[];
}
