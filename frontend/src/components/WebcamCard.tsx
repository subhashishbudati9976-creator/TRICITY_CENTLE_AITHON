import React, { useRef, useState, useEffect, useCallback } from 'react';
import BlurText from './reactbits/BlurText';

interface WebcamCardProps {
  cameraConnected: boolean;
  handsDetected: number;
  mousePaused: boolean;
  onFullscreenChange?: (isFullscreen: boolean) => void;
}

export const WebcamCard: React.FC<WebcamCardProps> = ({
  cameraConnected,
  handsDetected,
  mousePaused,
  onFullscreenChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

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
            text="OPTICAL SENSOR & LANDMARK MATRIX"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <span className="section-meta">640x480 @ 30FPS</span>
          <button className="btn-ghost" onClick={toggleFullscreen}>
            {isFullscreen ? 'EXIT FULLSCREEN' : 'FULLSCREEN'}
          </button>
        </div>
      </div>

      {/* Video Viewport Container (Target of Fullscreen API) */}
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
            // Reconnect attempt on camera drop
            const target = e.currentTarget;
            setTimeout(() => {
              target.src = `/api/stream?t=${Date.now()}`;
            }, 1000);
          }}
        />

        {/* Dynamic landmark alignment overlay canvas */}
        <canvas ref={canvasRef} className="webcam-overlay-canvas" />

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
        <span style={{ fontWeight: 700, color: mousePaused ? 'var(--color-stone)' : 'var(--color-sage)' }}>
          Mouse control: {mousePaused ? 'DISABLED' : 'ACTIVE'}
        </span>
        <span style={{ color: 'var(--color-sage)' }}>FAILSAFE: CORNER ARMED</span>
        <button className="btn-ghost" onClick={toggleFullscreen} style={{ padding: '3px 8px', fontSize: '10px' }}>
          EXPAND
        </button>
      </div>

      {/* Protocol Quick Reference Matrix */}
      <div className="protocol-card">
        <div className="protocol-column gesture">
          <h4>[ GESTURE PROTOCOL ]</h4>
          <ul>
            <li><strong>POSITION:</strong> 1.5–3 ft from lens</li>
            <li><strong>MOVE:</strong> Index finger tip (1€ Filter)</li>
            <li><strong>CLICK:</strong> Pinch thumb + index</li>
            <li><strong>FAIL-SAFE:</strong> Throw mouse to top-left</li>
          </ul>
        </div>
        <div className="protocol-column voice">
          <h4>[ VOICE PROTOCOL ]</h4>
          <ul>
            <li><strong>APPS:</strong> 'Open Chrome' | 'Launch Notepad'</li>
            <li><strong>WEB:</strong> 'Open LinkedIn / GitHub / YouTube'</li>
            <li><strong>ACTIONS:</strong> 'Click' | 'Scroll Up/Down'</li>
            <li><strong>AUDIO:</strong> 'Volume Up/Down' | 'Mute'</li>
          </ul>
        </div>
      </div>
    </div>
  );
};
