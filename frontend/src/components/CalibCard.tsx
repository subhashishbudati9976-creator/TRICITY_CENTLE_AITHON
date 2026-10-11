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
            text="CALIBRATION & FILTER PARAMETERS"
            className="section-title"
            animateBy="words"
            direction="top"
            delay={80}
          />
        </div>
        <span className="section-meta">1€ FILTER DESK</span>
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
      </div>
    </div>
  );
};
