import React from 'react';
import TechText from './reactbits/TechText';

interface HeaderProps {
  mousePaused: boolean;
  cameraConnected: boolean;
  controlMode: 'cursor' | 'gesture';
  gestureKeysEnabled: boolean;
  onToggleMouse: () => void;
  onToggleControlMode: () => void;
  onToggleGestureKeys: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  mousePaused,
  cameraConnected,
  controlMode,
  gestureKeysEnabled,
  onToggleMouse,
  onToggleControlMode,
  onToggleGestureKeys,
}) => {
  return (
    <header className="air-header">
      <div className="header-brand">
        <div className="header-wordmark-wrapper">
          <TechText
            text="AIRCONTROL"
            fontWeight={800}
            fontSize={36}
            reveal="letter"
            specks={15}
            color="#f8fafc"
            accentColor="#e64522"
            fontFamily="Space Grotesk, sans-serif"
            style={{ width: '260px', height: '42px', position: 'relative' }}
          />
        </div>
        <span className="header-subtitle">
          Touch-Free Desktop Interaction System | Precision Instrument
        </span>
      </div>

      <div className="header-badges">
        {/* Mode Toggle & Badge */}
        <div
          className="status-badge"
          style={{
            cursor: 'pointer',
            border: controlMode === 'gesture' ? '1px solid var(--color-vermilion)' : '1px solid rgba(99, 102, 241, 0.4)',
          }}
          onClick={onToggleControlMode}
          title="Click to toggle between Cursor Mode and Gesture-Key Mode"
        >
          <span className={`status-dot ${controlMode === 'gesture' ? 'warn' : 'active'}`} />
          <span>{controlMode === 'gesture' ? 'MODE: GESTURE KEYS' : 'MODE: CURSOR CONTROL'}</span>
        </div>

        <button
          className="btn-ghost"
          onClick={onToggleControlMode}
          style={{ padding: '4px 10px', fontSize: '11px', height: '32px' }}
          title="Switch active interaction mode"
        >
          Switch to {controlMode === 'cursor' ? 'Gesture Keys' : 'Cursor Mode'}
        </button>

        {controlMode === 'gesture' && (
          <button
            className={`btn-ghost ${gestureKeysEnabled ? 'active' : ''}`}
            onClick={onToggleGestureKeys}
            style={{
              padding: '4px 8px',
              fontSize: '11px',
              height: '32px',
              color: gestureKeysEnabled ? 'var(--color-sage)' : 'var(--color-stone)',
            }}
            title="Enable or disable gesture shortcuts"
          >
            Keys: {gestureKeysEnabled ? 'ON' : 'OFF'}
          </button>
        )}

        <div className="status-badge">
          <span className={`status-dot ${!mousePaused ? 'active' : ''}`} />
          <span>{!mousePaused ? 'ENGINE ACTIVE' : 'ENGINE STANDBY'}</span>
        </div>

        <div className="status-badge">
          <span className={`status-dot ${cameraConnected ? 'active' : 'warn'}`} />
          <span>{cameraConnected ? 'SENSOR ONLINE' : 'SENSOR INIT'}</span>
        </div>

        <button
          className="btn-primary"
          onClick={onToggleMouse}
          style={{
            backgroundColor: mousePaused ? 'var(--color-vermilion)' : 'var(--color-indigo)',
          }}
        >
          {mousePaused ? 'Enable Control' : 'Pause Control'}
        </button>
      </div>
    </header>
  );
};
