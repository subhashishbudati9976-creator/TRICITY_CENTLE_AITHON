import React from 'react';

interface FooterProps {
  systemStatus: string;
  lastAction: string;
}

export const Footer: React.FC<FooterProps> = ({ systemStatus, lastAction }) => {
  return (
    <footer className="air-footer">
      <div>
        <span style={{ color: 'var(--color-stone)' }}>SYSTEM: </span>
        <span>{systemStatus}</span>
      </div>
      <div>
        <span className="footer-action">{lastAction}</span>
      </div>
    </footer>
  );
};
