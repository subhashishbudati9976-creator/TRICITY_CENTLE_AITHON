import React from 'react';
import TechText from './reactbits/TechText';

interface HeaderProps {
  mousePaused: boolean;
  cameraConnected: boolean;
  onToggleMouse: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  mousePaused,
  cameraConnected,
  onToggleMouse,
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
          {mousePaused ? 'Enable Mouse Control' : 'Pause Mouse Control'}
        </button>
      </div>
    </header>
  );
};
