import React, { useRef, useEffect } from 'react';
import BlurText from './reactbits/BlurText';
import type { AuditLogEntry } from '../types/telemetry';

interface AuditLogCardProps {
  logs: AuditLogEntry[];
}

export const AuditLogCard: React.FC<AuditLogCardProps> = ({ logs }) => {
  const listRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest log entry
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="bento-card-wrapper">
      <div className="section-header">
        <div className="section-tag-group">
          <span className="section-num">[ 03 ]</span>
          <BlurText
            text="CHRONOLOGICAL INSTRUMENT AUDIT LOG"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <span className="section-meta">LIVE AUDIT LEDGER</span>
      </div>

      <div className="audit-log-container">
        <div className="audit-log-header">
          <div className="audit-log-item">
            <span>TIMESTAMP</span>
            <span>SOURCE</span>
            <span>TELEMETRY EVENT</span>
            <span style={{ textAlign: 'right' }}>STATUS</span>
          </div>
        </div>

        <div ref={listRef} className="audit-log-list">
          {logs.map((item, index) => (
            <div key={`${item.timestamp}-${index}`} className="audit-log-item">
              <span className="log-time">[{item.timestamp}]</span>
              <span className="log-source">[{item.source}]</span>
              <span className="log-event">{item.event}</span>
              <span className={`log-status ${item.status}`}>[{item.status}]</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
