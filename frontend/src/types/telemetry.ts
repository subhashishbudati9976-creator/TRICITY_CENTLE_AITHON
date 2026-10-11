export interface CalibrationSettings {
  sensitivity: number;
  min_cutoff: number;
  click_cooldown: number;
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
  voice_mode: 'online' | 'offline';
  voice_busy: boolean;
  voice_status: string;
  recognized_text: string;
  assistant_status: string;
  last_action: string;
  system_status: string;
  calibration: CalibrationSettings;
  audit_logs: AuditLogEntry[];
}
