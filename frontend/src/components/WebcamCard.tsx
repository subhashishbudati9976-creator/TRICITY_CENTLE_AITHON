import React, { useRef, useState, useEffect, useCallback } from 'react';
import BlurText from './reactbits/BlurText';

interface WebcamCardProps {
  cameraConnected: boolean;
  handsDetected: number;
  mousePaused: boolean;
  controlMode: 'cursor' | 'gesture';
  detectedGesture: string;
  gestureAction: string;
  gestureProgress: number;
  onFullscreenChange?: (isFullscreen: boolean) => void;
}

const CHEAT_SHEET_SHORTCUTS = [
  { fingers: 'Thumb + Index', key: 'Right Arrow', desc: 'Navigate forward / right', danger: false },
  { fingers: 'Thumb + Index + Pinky', key: 'Left Arrow', desc: 'Navigate back / left', danger: false },
  { fingers: 'Index only', key: 'Space', desc: 'Pause/Play / Page Scroll', danger: false },
  { fingers: 'Middle only', key: "'z'", desc: 'Undo / Key Z', danger: false },
  { fingers: 'Thumb + Index + Middle', key: "'m'", desc: 'Mute / Key M', danger: false },
  { fingers: 'Thumb only', key: 'Enter', desc: 'Submit / Confirm', danger: false },
  { fingers: 'Index + Middle', key: 'Up Arrow', desc: 'Navigate Up', danger: false },
  { fingers: 'Index + Pinky', key: 'Down Arrow', desc: 'Navigate Down', danger: false },
  { fingers: 'Index + Middle + Ring', key: 'Ctrl + F4', desc: 'Close Tab / Document (800ms hold)', danger: true },
  { fingers: 'Pinky only', key: 'Ctrl + T', desc: 'New Browser Tab', danger: false },
  { fingers: 'Thumb + Index + Middle + Ring', key: 'Ctrl + Win + Right', desc: 'Switch Desktop (800ms hold)', danger: true },
  { fingers: 'Index + Middle + Ring + Pinky', key: 'Ctrl + Alt + W', desc: 'Close Windows (800ms hold)', danger: true },
  { fingers: 'Thumb + Middle + Ring + Pinky', key: 'Esc', desc: 'Dismiss / Cancel', danger: false },
  { fingers: 'Thumb + Pinky', key: 'F5', desc: 'Reload / Refresh', danger: false },
  { fingers: 'Thumb + Middle + Pinky', key: 'Right-Click', desc: 'Context Menu', danger: false },
];

const CONTINUOUS_GESTURES = [
  { fingers: 'Open Palm (5 fingers)', action: 'Continuous Scroll', desc: 'Move hand UP / DOWN to scroll smoothly' },
  { fingers: 'Fist (0 fingers)', action: 'Continuous Zoom', desc: 'Move hand UP (Zoom in) / DOWN (Zoom out)' },
];

export const WebcamCard: React.FC<WebcamCardProps> = ({
  cameraConnected,
  handsDetected,
  mousePaused,
  controlMode,
  detectedGesture,
  gestureAction,
  gestureProgress,
  onFullscreenChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showCheatSheet, setShowCheatSheet] = useState(false);

  // Synchronize canvas dimensions with actual rendered video size
  const updateCanvasDimensions = useCallback(() => {
    if (!videoRef.current || !canvasRef.current) return;
    const rect = videoRef.current.getBoundingClientRect();
    canvasRef.current.width = rect.width;
    canvasRef.current.height = rect.height;
  }, []);

  useEffect(() => {
    const handleResize = () => updateCanvasDimensions();
    window.addEventListener('resize', handleResize);

    const resizeObserver = new ResizeObserver(() => {
      updateCanvasDimensions();
    });

    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      resizeObserver.disconnect();
    };
  }, [updateCanvasDimensions]);

  // Fullscreen toggle using native Fullscreen API
  const toggleFullscreen = useCallback(async () => {
    if (!containerRef.current) return;

    try {
      if (!document.fullscreenElement) {
        await containerRef.current.requestFullscreen();
        setIsFullscreen(true);
        onFullscreenChange?.(true);
      } else {
        await document.exitFullscreen();
        setIsFullscreen(false);
        onFullscreenChange?.(false);
      }
    } catch (err) {
      console.error('Fullscreen request failed:', err);
    }
  }, [onFullscreenChange]);

  const exitFullscreen = useCallback(async () => {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      setIsFullscreen(false);
      onFullscreenChange?.(false);
    }
  }, [onFullscreenChange]);

  useEffect(() => {
    const onFsChange = () => {
      const active = Boolean(document.fullscreenElement);
      setIsFullscreen(active);
      onFullscreenChange?.(active);
      setTimeout(updateCanvasDimensions, 100);
    };

    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, [onFullscreenChange, updateCanvasDimensions]);

  return (
    <div className="bento-card-wrapper" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      <div className="section-header">
        <div className="section-tag-group">
          <span className="section-num">[ 01 ]</span>
          <BlurText
            text="OPTICAL SENSOR & GESTURE MATRIX"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            className={`btn-ghost ${showCheatSheet ? 'active' : ''}`}
            onClick={() => setShowCheatSheet((v) => !v)}
            style={{ padding: '3px 9px', fontSize: '11px' }}
          >
            {showCheatSheet ? 'HIDE CHEAT SHEET' : 'GESTURE CHEAT SHEET'}
          </button>
          <button className="btn-ghost" onClick={toggleFullscreen} style={{ padding: '3px 9px', fontSize: '11px' }}>
            {isFullscreen ? 'EXIT FULLSCREEN' : 'FULLSCREEN'}
          </button>
        </div>
      </div>

      {/* Video Viewport Container */}
      <div ref={containerRef} className="webcam-viewport-container">
        {isFullscreen && (
          <button className="fullscreen-exit-btn" onClick={exitFullscreen}>
            ✕ EXIT FULLSCREEN (ESC)
          </button>
        )}

        <img
          ref={videoRef}
          src="/api/stream"
          alt="AirControl Live Optical Tracking Stream"
          className="webcam-video-element"
          onLoad={updateCanvasDimensions}
          onError={(e) => {
            const target = e.currentTarget;
            setTimeout(() => {
              target.src = `/api/stream?t=${Date.now()}`;
            }, 1000);
          }}
        />

        {/* Dynamic landmark alignment overlay canvas */}
        <canvas ref={canvasRef} className="webcam-overlay-canvas" />

        {/* Live Active Gesture Floating Badge & Progress Ring */}
        {detectedGesture !== 'None' && (
          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              backgroundColor: 'rgba(15, 14, 23, 0.88)',
              backdropFilter: 'blur(8px)',
              border: '1px solid rgba(99, 102, 241, 0.4)',
              borderRadius: '8px',
              padding: '6px 12px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              boxShadow: '0 4px 14px rgba(0,0,0,0.4)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <span style={{ fontSize: '10px', color: 'var(--color-stone)', fontFamily: 'var(--font-mono)' }}>
                DETECTED: {detectedGesture.toUpperCase()}
              </span>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#f8fafc' }}>
                ➜ {gestureAction}
              </span>
            </div>
            {controlMode === 'gesture' && gestureProgress > 0 && (
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <svg width="32" height="32" viewBox="0 0 32 32">
                  <circle cx="16" cy="16" r="13" stroke="rgba(255,255,255,0.15)" strokeWidth="3" fill="none" />
                  <circle
                    cx="16"
                    cy="16"
                    r="13"
                    stroke={gestureProgress >= 1 ? 'var(--color-sage)' : 'var(--color-indigo)'}
                    strokeWidth="3"
                    fill="none"
                    strokeDasharray="81.68"
                    strokeDashoffset={81.68 * (1 - gestureProgress)}
                    transform="rotate(-90 16 16)"
                    style={{ transition: 'stroke-dashoffset 0.05s linear' }}
                  />
                </svg>
                <span style={{ position: 'absolute', fontSize: '9px', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                  {Math.round(gestureProgress * 100)}%
                </span>
              </div>
            )}
          </div>
        )}

        {!cameraConnected && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'rgba(9, 8, 13, 0.92)',
              gap: '12px',
              fontFamily: 'var(--font-mono)',
              fontSize: '12px',
              color: 'var(--color-stone)',
              textAlign: 'center',
              padding: '20px',
            }}
          >
            <span style={{ color: 'var(--color-vermilion)', fontWeight: 700 }}>
              ACQUIRING OPTICAL SENSOR FEED...
            </span>
            <span>PLACE HAND IN VIEW TO ENGAGE 21-LANDMARK MATRIX</span>
          </div>
        )}
      </div>

      {/* Live Telemetry Mini-Bar */}
      <div className="telemetry-bar">
        <span>Hands detected: {handsDetected}</span>
        <span
          style={{
            fontWeight: 700,
            color: controlMode === 'gesture' ? 'var(--color-vermilion)' : 'var(--color-indigo)',
          }}
        >
          Active Mode: {controlMode === 'gesture' ? 'GESTURE KEYS' : 'CURSOR & PINCH'}
        </span>
        <span style={{ color: 'var(--color-sage)' }}>FAILSAFE: CORNER ARMED</span>
      </div>

      {/* Collapsible Gesture Cheat Sheet */}
      {showCheatSheet && (
        <div
          style={{
            margin: '8px 0',
            padding: '12px',
            backgroundColor: 'rgba(15, 14, 23, 0.95)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            borderRadius: '8px',
            maxHeight: '260px',
            overflowY: 'auto',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', color: 'var(--color-indigo)' }}>
              COMPLETE GESTURE CHEAT SHEET (15 KEY SHORTCUTS + SCROLL & ZOOM)
            </span>
            <span style={{ fontSize: '10px', color: 'var(--color-stone)' }}>Hold 400ms (800ms for safety)</span>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
              gap: '6px',
              fontSize: '11px',
            }}
          >
            {CHEAT_SHEET_SHORTCUTS.map((g, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '4px 8px',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  borderRadius: '4px',
                  borderLeft: g.danger ? '2px solid var(--color-vermilion)' : '2px solid var(--color-indigo)',
                }}
              >
                <div>
                  <strong style={{ color: '#f8fafc' }}>{g.fingers}</strong>
                  <span style={{ marginLeft: '6px', color: 'var(--color-stone)', fontSize: '10px' }}>
                    ({g.desc})
                  </span>
                </div>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    backgroundColor: g.danger ? 'rgba(230, 69, 34, 0.2)' : 'rgba(99, 102, 241, 0.2)',
                    color: g.danger ? 'var(--color-vermilion)' : '#818cf8',
                    fontWeight: 700,
                  }}
                >
                  {g.key}
                </span>
              </div>
            ))}

            {CONTINUOUS_GESTURES.map((cg, idx) => (
              <div
                key={`cg-${idx}`}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '4px 8px',
                  backgroundColor: 'rgba(16, 185, 129, 0.05)',
                  borderRadius: '4px',
                  borderLeft: '2px solid var(--color-sage)',
                }}
              >
                <div>
                  <strong style={{ color: '#f8fafc' }}>{cg.fingers}</strong>
                  <span style={{ marginLeft: '6px', color: 'var(--color-stone)', fontSize: '10px' }}>
                    ({cg.desc})
                  </span>
                </div>
                <span
                  style={{
                    fontFamily: 'var(--font-mono)',
                    padding: '2px 6px',
                    borderRadius: '3px',
                    backgroundColor: 'rgba(16, 185, 129, 0.2)',
                    color: 'var(--color-sage)',
                    fontWeight: 700,
                  }}
                >
                  {cg.action}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Protocol Quick Reference Matrix */}
      <div className="protocol-card">
        <div className="protocol-column gesture">
          <h4>[ GESTURE PROTOCOL ]</h4>
          <ul>
            <li><strong>CURSOR MODE:</strong> Index tip moves cursor | Pinch clicks</li>
            <li><strong>GESTURE MODE:</strong> 15 Shortcut keys active | Cursor frozen</li>
            <li><strong>CONTINUOUS SCROLL:</strong> Hold Open Palm & move hand up/down</li>
            <li><strong>CONTINUOUS ZOOM:</strong> Hold Fist & move hand up/down</li>
          </ul>
        </div>
        <div className="protocol-column voice">
          <h4>[ VOICE PROTOCOL ]</h4>
          <ul>
            <li><strong>WAKE PHRASES:</strong> 'Hey AirControl, start listening' | 'Stop listening'</li>
            <li><strong>MODES:</strong> 'Switch to gesture mode' | 'Cursor mode'</li>
            <li><strong>ZOOM / SCROLL:</strong> 'Zoom in the page' | 'Scroll page down'</li>
            <li><strong>APPS & WEB:</strong> 'Open Chrome' | 'Search YouTube for ...'</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
