import { unitsForSystem } from './store/unitsPreference';
import { useCalibrationStore } from './store/calibrationStore';
import type { LengthUnit } from '@gs/viewer';

function unitOptionLabel(unit: LengthUnit): string {
  switch (unit) {
    case 'mm':
      return 'mm';
    case 'cm':
      return 'cm';
    case 'm':
      return 'm';
    case 'in':
      return 'in';
    case 'ft':
      return 'ft';
    default: {
      const exhaustive: never = unit;
      return String(exhaustive);
    }
  }
}

export function UnitSelector() {
  const system = useCalibrationStore((state) => state.unitPref.system);
  const unit = useCalibrationStore((state) => state.unitPref.unit);
  const setUnitSystem = useCalibrationStore((state) => state.setUnitSystem);
  const setLengthUnit = useCalibrationStore((state) => state.setLengthUnit);
  const units = unitsForSystem(system);

  return (
    <div className="gs-units" role="group" aria-label="Sistema de unidades">
      <button
        type="button"
        className={system === 'metric' ? 'primary' : undefined}
        onClick={() => setUnitSystem('metric')}
      >
        Métrico
      </button>
      <button
        type="button"
        className={system === 'imperial' ? 'primary' : undefined}
        onClick={() => setUnitSystem('imperial')}
      >
        Imperial
      </button>
      <select
        aria-label="Unidade ativa"
        value={unit}
        onChange={(event) => setLengthUnit(event.target.value as LengthUnit)}
      >
        {units.map((item) => (
          <option key={item} value={item}>
            {unitOptionLabel(item)}
          </option>
        ))}
      </select>
    </div>
  );
}
