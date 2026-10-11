import React from 'react';
import BlurText from './reactbits/BlurText';

interface VoiceCardProps {
  voiceMode: 'online' | 'offline';
  voiceBusy: boolean;
  voiceStatus: string;
  recognizedText: string;
  assistantStatus: string;
  onSetVoiceMode: (mode: 'online' | 'offline') => void;
  onListenVoice: () => void;
  onCancelVoice: () => void;
}

export const VoiceCard: React.FC<VoiceCardProps> = ({
  voiceMode,
  voiceBusy,
  voiceStatus,
  recognizedText,
  assistantStatus,
  onSetVoiceMode,
  onListenVoice,
  onCancelVoice,
}) => {
  return (
    <div className="bento-card-wrapper">
      <div className="section-header">
        <div className="section-tag-group">
          <span className="section-num">[ 02 ]</span>
          <BlurText
            text="ACOUSTIC COMMAND TRANSLATOR"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <div className="mode-selector">
          <button
            className={`mode-btn ${voiceMode === 'online' ? 'active' : ''}`}
            onClick={() => onSetVoiceMode('online')}
          >
            Online
          </button>
          <button
            className={`mode-btn ${voiceMode === 'offline' ? 'active' : ''}`}
            onClick={() => onSetVoiceMode('offline')}
          >
            Offline
          </button>
        </div>
      </div>

      <div className="voice-ctrl-row">
        <div className="status-badge" style={{ padding: '4px 10px' }}>
          <span className={`status-dot ${voiceBusy ? 'warn' : 'indigo'}`} />
          <span>{voiceBusy ? '● RECORDING...' : '● MIC STANDBY'}</span>
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-stone)' }}>
          Mode: {voiceMode.toUpperCase()}
        </span>
      </div>

      <div className="readout-box">
        <span className="readout-label">LIVE READOUT:</span>
        <span className="readout-text">{voiceStatus}</span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '11px', color: 'var(--color-stone)' }}>
          {recognizedText}
        </span>
      </div>

      <div className="intent-box">
        <strong>ASSISTANT INTENT: </strong>
        <span>{assistantStatus}</span>
      </div>

      <div className="voice-actions-row">
        <button
          className="btn-secondary"
          disabled={voiceBusy}
          onClick={onListenVoice}
        >
          {voiceBusy ? 'Listening...' : 'Listen for Command'}
        </button>
        <button
          className="btn-ghost"
          disabled={!voiceBusy}
          onClick={onCancelVoice}
          style={{ height: '36px' }}
        >
          Cancel Task
        </button>
      </div>
    </div>
  );
};
