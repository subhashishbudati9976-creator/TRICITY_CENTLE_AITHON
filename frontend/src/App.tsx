import { useState, useEffect, useRef, useCallback } from 'react';
import GlowCursor from './components/reactbits/GlowCursor';
import { ParticleCard } from './components/reactbits/MagicBento';
import { BackgroundShards } from './components/BackgroundShards';
import { Header } from './components/Header';
import { WebcamCard } from './components/WebcamCard';
import { VoiceCard } from './components/VoiceCard';
import { AuditLogCard } from './components/AuditLogCard';
import { CalibCard } from './components/CalibCard';
import { Footer } from './components/Footer';
import { useAirControlSocket } from './hooks/useAirControlSocket';
import { useBrowserSpeech } from './hooks/useBrowserSpeech';

export default function App() {
  const speechRef = useRef<{ speakText: (text: string) => void }>({ speakText: () => {} });

  const {
    state,
    toggleMouse,
    setControlMode,
    toggleControlMode,
    toggleGestureKeys,
    setVoiceMode,
    listenVoice,
    stopVoice,
    cancelVoice,
    sendSpeechState,
    updateCalibration,
  } = useAirControlSocket({
    onSpeak: (text) => {
      speechRef.current.speakText(text);
    },
  });

  const handleSpeakingChange = useCallback(
    (speaking: boolean) => {
      sendSpeechState(speaking);
    },
    [sendSpeechState]
  );

  const {
    voices,
    selectedVoice,
    rate,
    pitch,
    speakerEnabled,
    isUnlocked,
    isSpeaking,
    speakText,
    stopSpeaking,
    toggleSpeaker,
    unlockAudio,
    updateVoice,
    updateRate,
    updatePitch,
  } = useBrowserSpeech(handleSpeakingChange);

  useEffect(() => {
    speechRef.current.speakText = speakText;
  }, [speakText]);

  const [isFullscreen, setIsFullscreen] = useState(false);
  const [cursorQuality, setCursorQuality] = useState<'high' | 'medium' | 'low'>('high');

  // Dynamic FPS monitor to step down cursor quality if frame rate drops
  const frameTimesRef = useRef<number[]>([]);
  useEffect(() => {
    let animId: number;
    let lastTime = performance.now();

    const checkFps = (time: number) => {
      const delta = time - lastTime;
      lastTime = time;
      if (delta > 0) {
        frameTimesRef.current.push(1000 / delta);
        if (frameTimesRef.current.length > 60) {
          frameTimesRef.current.shift();
          const avgFps =
            frameTimesRef.current.reduce((a, b) => a + b, 0) /
            frameTimesRef.current.length;

          if (avgFps < 28 && cursorQuality !== 'low') {
            setCursorQuality('low');
          } else if (avgFps < 45 && cursorQuality === 'high') {
            setCursorQuality('medium');
          }
        }
      }
      animId = requestAnimationFrame(checkFps);
    };

    animId = requestAnimationFrame(checkFps);
    return () => cancelAnimationFrame(animId);
  }, [cursorQuality]);

  return (
    <GlowCursor
      theme="dark"
      clickBurst={true}
      quality={cursorQuality}
      color="#6366f1"
      secondaryColor="#e64522"
      intensity={0.8}
      glow={0.7}
      style={{ minHeight: '100vh', width: '100%' }}
    >
      {/* Background Wind Sculpture (AeroShards) */}
      <BackgroundShards isFullscreen={isFullscreen} />

      <div className="app-container">
        {/* Top Header with TechText */}
        <Header
          mousePaused={state.mouse_paused}
          cameraConnected={state.camera_connected}
          controlMode={state.control_mode}
          gestureKeysEnabled={state.gesture_keys_enabled}
          onToggleMouse={toggleMouse}
          onToggleControlMode={toggleControlMode}
          onToggleGestureKeys={toggleGestureKeys}
        />

        {/* Dashboard Bento Workspace */}
        <main className="dashboard-grid">
          {/* Left Column: Optical Sensor Matrix */}
          <section className="panel-col">
            <ParticleCard
              enableTilt={false}
              enableMagnetism={false}
              clickEffect={false}
              glowColor="99, 102, 241"
              style={{ display: 'flex', flexDirection: 'column', flex: 1, padding: 0 }}
            >
              <WebcamCard
                cameraConnected={state.camera_connected}
                handsDetected={state.hands_detected}
                mousePaused={state.mouse_paused}
                controlMode={state.control_mode}
                detectedGesture={state.detected_gesture}
                gestureAction={state.gesture_action}
                gestureProgress={state.gesture_progress}
                onFullscreenChange={setIsFullscreen}
              />
            </ParticleCard>
          </section>

          {/* Right Column: Voice Translator, Audit Log, Calibration Parameters */}
          <section className="panel-col">
            {/* Section 02: Acoustic Command Translator */}
            <ParticleCard
              enableTilt={true}
              enableMagnetism={false}
              clickEffect={true}
              glowColor="99, 102, 241"
              style={{ padding: 0 }}
            >
              <VoiceCard
                voiceMode={state.voice_mode}
                voiceBusy={state.voice_busy}
                voiceListeningActive={state.voice_listening_active}
                browserSpeaking={isSpeaking || state.browser_speaking}
                voiceStatus={state.voice_status}
                recognizedText={state.recognized_text}
                assistantStatus={state.assistant_status}
                speakerEnabled={speakerEnabled}
                isUnlocked={isUnlocked}
                voices={voices}
                selectedVoice={selectedVoice}
                rate={rate}
                pitch={pitch}
                onSetVoiceMode={setVoiceMode}
                onListenVoice={listenVoice}
                onStopVoice={stopVoice}
                onCancelVoice={cancelVoice}
                onToggleSpeaker={toggleSpeaker}
                onStopSpeaking={stopSpeaking}
                onUnlockAudio={unlockAudio}
                onUpdateVoice={updateVoice}
                onUpdateRate={updateRate}
                onUpdatePitch={updatePitch}
              />
            </ParticleCard>

            {/* Section 03: Chronological Audit Log */}
            <ParticleCard
              enableTilt={true}
              enableMagnetism={false}
              clickEffect={true}
              glowColor="132, 0, 255"
              style={{ padding: 0 }}
            >
              <AuditLogCard logs={state.audit_logs} />
            </ParticleCard>

            {/* Section 04: Calibration Desk */}
            <ParticleCard
              enableTilt={true}
              enableMagnetism={false}
              clickEffect={true}
              glowColor="99, 102, 241"
              style={{ padding: 0 }}
            >
              <CalibCard
                calibration={state.calibration}
                onUpdateCalibration={updateCalibration}
              />
            </ParticleCard>
          </section>
        </main>

        {/* Bottom Status Strip */}
        <Footer
          systemStatus={state.system_status}
          lastAction={state.last_action}
        />
      </div>
    </GlowCursor>
  );
}
