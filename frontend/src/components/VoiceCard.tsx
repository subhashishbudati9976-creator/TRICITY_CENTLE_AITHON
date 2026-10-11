import React, { useState } from 'react';
import BlurText from './reactbits/BlurText';

interface VoiceCardProps {
  voiceMode: 'online' | 'offline';
  voiceBusy: boolean;
  voiceListeningActive: boolean;
  browserSpeaking: boolean;
  voiceStatus: string;
  recognizedText: string;
  assistantStatus: string;
  speakerEnabled: boolean;
  isUnlocked: boolean;
  voices: SpeechSynthesisVoice[];
  selectedVoice: SpeechSynthesisVoice | null;
  rate: number;
  pitch: number;
  onSetVoiceMode: (mode: 'online' | 'offline') => void;
  onListenVoice: () => void;
  onStopVoice: () => void;
  onCancelVoice: () => void;
  onToggleSpeaker: () => void;
  onStopSpeaking: () => void;
  onUnlockAudio: () => void;
  onUpdateVoice: (uri: string) => void;
  onUpdateRate: (rate: number) => void;
  onUpdatePitch: (pitch: number) => void;
}

export const VoiceCard: React.FC<VoiceCardProps> = ({
  voiceMode,
  voiceBusy,
  voiceListeningActive,
  browserSpeaking,
  voiceStatus,
  recognizedText,
  assistantStatus,
  speakerEnabled,
  isUnlocked,
  voices,
  selectedVoice,
  rate,
  pitch,
  onSetVoiceMode,
  onListenVoice,
  onStopVoice,
  onCancelVoice,
  onToggleSpeaker,
  onStopSpeaking,
  onUnlockAudio,
  onUpdateVoice,
  onUpdateRate,
  onUpdatePitch,
}) => {
  const [showVoiceSettings, setShowVoiceSettings] = useState(false);

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

      {/* Listening State & Feedback Banner */}
      <div className="voice-ctrl-row" style={{ flexWrap: 'wrap', gap: '8px' }}>
        <div
          className="status-badge"
          style={{
            padding: '4px 10px',
            backgroundColor: voiceListeningActive ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
            border: voiceListeningActive ? '1px solid var(--color-sage)' : '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <span className={`status-dot ${voiceListeningActive ? 'active' : voiceBusy ? 'warn' : 'indigo'}`} />
          <span style={{ fontWeight: 700 }}>
            {voiceListeningActive ? '● LISTENING (SAY "STOP LISTENING")' : '○ WAKE STANDBY ("HEY AIRCONTROL")'}
          </span>
        </div>

        {/* Browser TTS Playing Indicator */}
        {browserSpeaking && (
          <div
            className="status-badge"
            style={{
              padding: '4px 10px',
              backgroundColor: 'rgba(99, 102, 241, 0.2)',
              border: '1px solid var(--color-indigo)',
            }}
          >
            <span className="status-dot active" />
            <span style={{ color: '#818cf8', fontWeight: 700 }}>SPEAKING (MIC MUTED)</span>
          </div>
        )}

        {/* Speaker Controls */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px' }}>
          {!isUnlocked && (
            <button
              className="btn-ghost"
              onClick={onUnlockAudio}
              style={{
                fontSize: '10px',
                padding: '3px 8px',
                color: 'var(--color-vermilion)',
                borderColor: 'var(--color-vermilion)',
              }}
            >
              ENABLE VOICE AUDIO
            </button>
          )}

          <button
            className={`btn-ghost ${speakerEnabled ? 'active' : ''}`}
            onClick={onToggleSpeaker}
            style={{ fontSize: '11px', padding: '3px 8px' }}
            title="Toggle spoken responses"
          >
            {speakerEnabled ? '🔊 SPEAKER ON' : '🔇 MUTED'}
          </button>

          {browserSpeaking && (
            <button
              className="btn-ghost"
              onClick={onStopSpeaking}
              style={{ fontSize: '11px', padding: '3px 8px', color: 'var(--color-vermilion)' }}
            >
              STOP
            </button>
          )}

          <button
            className={`btn-ghost ${showVoiceSettings ? 'active' : ''}`}
            onClick={() => setShowVoiceSettings((v) => !v)}
            style={{ fontSize: '11px', padding: '3px 8px' }}
          >
            ⚙ VOICE
          </button>
        </div>
      </div>

      {/* Voice Settings Drawer */}
      {showVoiceSettings && (
        <div
          style={{
            margin: '8px 0',
            padding: '10px 12px',
            backgroundColor: 'rgba(15, 14, 23, 0.95)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            borderRadius: '6px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            fontSize: '11px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ color: 'var(--color-stone)', width: '60px' }}>Voice:</span>
            <select
              style={{
                flex: 1,
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                color: '#f8fafc',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                borderRadius: '4px',
                padding: '4px 8px',
                fontSize: '11px',
                fontFamily: 'var(--font-sans)',
              }}
              value={selectedVoice?.voiceURI || ''}
              onChange={(e) => onUpdateVoice(e.target.value)}
            >
              {voices.map((v) => (
                <option key={v.voiceURI} value={v.voiceURI} style={{ backgroundColor: '#18181b', color: '#fff' }}>
                  {v.name} ({v.lang})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
              <span style={{ color: 'var(--color-stone)', width: '40px' }}>Rate:</span>
              <input
                type="range"
                min="0.7"
                max="1.5"
                step="0.05"
                value={rate}
                onChange={(e) => onUpdateRate(parseFloat(e.target.value))}
                style={{ flex: 1 }}
              />
              <span style={{ fontFamily: 'var(--font-mono)', width: '32px' }}>{rate.toFixed(2)}x</span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1 }}>
              <span style={{ color: 'var(--color-stone)', width: '40px' }}>Pitch:</span>
              <input
                type="range"
                min="0.8"
                max="1.3"
                step="0.05"
                value={pitch}
                onChange={(e) => onUpdatePitch(parseFloat(e.target.value))}
                style={{ flex: 1 }}
              />
              <span style={{ fontFamily: 'var(--font-mono)', width: '32px' }}>{pitch.toFixed(2)}</span>
            </div>
          </div>
        </div>
      )}

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
        {!voiceListeningActive ? (
          <button className="btn-secondary" disabled={voiceBusy} onClick={onListenVoice}>
            Start Listening
          </button>
        ) : (
          <button
            className="btn-ghost active"
            onClick={onStopVoice}
            style={{ color: 'var(--color-vermilion)', borderColor: 'var(--color-vermilion)' }}
          >
            Stop Listening
          </button>
        )}

        <button className="btn-ghost" disabled={!voiceBusy && !voiceListeningActive} onClick={onCancelVoice} style={{ height: '36px' }}>
          Cancel Task
        </button>
      </div>
    </div>
  );
};
