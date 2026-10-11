import React from 'react';
import BlurText from './reactbits/BlurText';
import type { CalibrationSettings } from '../types/telemetry';

interface CalibCardProps {
  calibration: CalibrationSettings;
  onUpdateCalibration: (settings: Partial<CalibrationSettings>) => void;
}

export const CalibCard: React.FC<CalibCardProps> = ({
  calibration,
  onUpdateCalibration,
}) => {
  return (
    <div className="bento-card-wrapper">
      <div className="section-header">
        <div className="section-tag-group">
          <span className="section-num">[ 04 ]</span>
          <BlurText
            text="CALIBRATION & PARAMETER DESK"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <span className="section-meta">FILTERS & COOLDOWNS</span>
      </div>

      <div className="slider-group">
        {/* Sensitivity Scale */}
        <div className="slider-row">
          <span className="slider-label">Sensitivity Scale</span>
          <input
            type="range"
            min="0.4"
            max="2.5"
            step="0.05"
            value={calibration.sensitivity}
            onChange={(e) =>
              onUpdateCalibration({ sensitivity: parseFloat(e.target.value) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {calibration.sensitivity.toFixed(2)} x
          </span>
        </div>

        {/* 1€ Filter Cutoff */}
        <div className="slider-row">
          <span className="slider-label">1€ Filter Cutoff</span>
          <input
            type="range"
            min="0.2"
            max="2.5"
            step="0.05"
            value={calibration.min_cutoff}
            onChange={(e) =>
              onUpdateCalibration({ min_cutoff: parseFloat(e.target.value) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {calibration.min_cutoff.toFixed(2)} Hz
          </span>
        </div>

        {/* Click Debounce */}
        <div className="slider-row">
          <span className="slider-label">Click Debounce</span>
          <input
            type="range"
            min="0.15"
            max="0.8"
            step="0.05"
            value={calibration.click_cooldown}
            onChange={(e) =>
              onUpdateCalibration({ click_cooldown: parseFloat(e.target.value) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {calibration.click_cooldown.toFixed(2)} s
          </span>
        </div>

        {/* Gesture Hold Time */}
        <div className="slider-row">
          <span className="slider-label">Gesture Hold Time</span>
          <input
            type="range"
            min="0.25"
            max="0.8"
            step="0.05"
            value={calibration.gesture_hold_normal ?? 0.4}
            onChange={(e) =>
              onUpdateCalibration({ gesture_hold_normal: parseFloat(e.target.value) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {(calibration.gesture_hold_normal ?? 0.4).toFixed(2)} s
          </span>
        </div>

        {/* Gesture Cooldown */}
        <div className="slider-row">
          <span className="slider-label">Gesture Cooldown</span>
          <input
            type="range"
            min="0.4"
            max="2.0"
            step="0.05"
            value={calibration.gesture_cooldown ?? 0.9}
            onChange={(e) =>
              onUpdateCalibration({ gesture_cooldown: parseFloat(e.target.value) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {(calibration.gesture_cooldown ?? 0.9).toFixed(2)} s
          </span>
        </div>

        {/* Continuous Scroll Speed */}
        <div className="slider-row">
          <span className="slider-label">Scroll Speed</span>
          <input
            type="range"
            min="80"
            max="360"
            step="10"
            value={calibration.scroll_speed ?? 180}
            onChange={(e) =>
              onUpdateCalibration({ scroll_speed: parseInt(e.target.value, 10) })
            }
            className="slider-input"
          />
          <span className="slider-value">
            {calibration.scroll_speed ?? 180} px
          </span>
        </div>
      </div>
    </div>
  );
};
