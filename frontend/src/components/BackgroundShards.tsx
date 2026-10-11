import React, { useState, useEffect } from 'react';
import AeroShards from './reactbits/AeroShards';

interface BackgroundShardsProps {
  isFullscreen: boolean;
}

export const BackgroundShards: React.FC<BackgroundShardsProps> = ({ isFullscreen }) => {
  const [hasWebGpu, setHasWebGpu] = useState(true);

  useEffect(() => {
    // Check if navigator.gpu exists
    if (typeof navigator === 'undefined' || !('gpu' in navigator)) {
      setHasWebGpu(false);
    }
  }, []);

  return (
    <div className={`background-canvas-container ${isFullscreen ? 'fullscreen-active' : ''}`}>
      {hasWebGpu ? (
        <AeroShards
          placement="full"
          backgroundColor="#09080d"
          shardColor="#6366f1"
          accentColor="#e64522"
          detail="balanced"
          flow="stream"
          material="pearl"
          speed={0.8}
          density={1.2}
          glow={0.8}
          bloom={0.4}
          holdToGather={false}
          style={{ width: '100%', height: '100%', position: 'absolute', inset: 0 }}
          onError={() => setHasWebGpu(false)}
        />
      ) : (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(circle at 50% 20%, rgba(99, 102, 241, 0.12) 0%, rgba(14, 13, 20, 0.8) 50%, #09080d 100%)',
          }}
        />
      )}
    </div>
  );
};
