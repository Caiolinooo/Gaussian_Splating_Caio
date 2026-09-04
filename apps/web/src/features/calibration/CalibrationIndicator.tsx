import { hudCalibrationLabel, isCalibrated } from './math/scaleFactor';
import { useCalibrationStore } from './store/calibrationStore';

export function CalibrationIndicator() {
  const calibration = useCalibrationStore((state) => state.calibration);
  const extras = useCalibrationStore((state) => state.extras);
  const label = hudCalibrationLabel(calibration);
  const ok = isCalibrated(calibration);
  const title = [
    extras.framesUsed != null ? `${extras.framesUsed} frames` : null,
    extras.errorEstimate != null ? `erro est. ${extras.errorEstimate}` : null,
    extras.warnings?.join('; '),
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <span className={ok ? 'gs-cal-ok' : 'gs-cal-warn'} title={title || label}>
      {label}
    </span>
  );
}
