import { SPLAT_QUALITY_RANGE, type SplatQuality } from '@gs/viewer';

import { useViewerRuntime } from '../runtime/ViewerRuntimeContext';

/**
 * Controles de nitidez (C0 — anti-smearing).
 *
 * Os três primeiros são os que realmente matam o smearing:
 * - **Suavização** (`blurAmount`): 0.3 é o default do Spark e serve para cenas
 *   treinadas SEM anti-aliasing; 0.0 é o correto para as treinadas com o tweak.
 * - **Foco** (`focalAdjustment`): 2.0 reproduz o PlayCanvas/SuperSplat.
 * - **Alcance** (`maxStdDev`): √5≈2.24 encurta as caudas; √8≈2.83 é o default.
 */
export function SharpnessControls({ quality }: { quality: SplatQuality }) {
  const controller = useViewerRuntime();

  return (
    <div className="gs-sharpness" aria-label="Controles de nitidez">
      <Slider
        label="Suavização"
        title="blurAmount — 0 deixa o splat nítido; 0.3 (default do Spark) infla ~0,5px"
        value={quality.blurAmount}
        range={SPLAT_QUALITY_RANGE.blurAmount}
        onChange={(value) => controller?.setQuality({ blurAmount: value })}
      />
      <Slider
        label="Foco"
        title="focalAdjustment — 2.0 reproduz o PlayCanvas/SuperSplat"
        value={quality.focalAdjustment}
        range={SPLAT_QUALITY_RANGE.focalAdjustment}
        onChange={(value) => controller?.setQuality({ focalAdjustment: value })}
      />
      <Slider
        label="Alcance"
        title="maxStdDev — desvios-padrão renderizados; menor encurta as caudas"
        value={quality.maxStdDev}
        range={SPLAT_QUALITY_RANGE.maxStdDev}
        onChange={(value) => controller?.setQuality({ maxStdDev: value })}
      />
      <Slider
        label="Decaimento"
        title="falloff — 1 = kernel gaussiano normal; 0 = chapado"
        value={quality.falloff}
        range={SPLAT_QUALITY_RANGE.falloff}
        onChange={(value) => controller?.setQuality({ falloff: value })}
      />
      <button
        type="button"
        onClick={() => controller?.resetSharpness()}
        title="Voltar aos valores padrão anti-smearing"
      >
        Padrão nítido
      </button>
    </div>
  );
}

interface SliderProps {
  label: string;
  title: string;
  value: number;
  range: { min: number; max: number; step: number };
  onChange: (value: number) => void;
}

function Slider({ label, title, value, range, onChange }: SliderProps) {
  return (
    <label className="gs-relight" title={title}>
      {label}
      <input
        type="range"
        min={0}
        max={1000}
        value={Math.round(((value - range.min) / (range.max - range.min)) * 1000)}
        aria-label={label}
        onChange={(event) => {
          const ratio = Number(event.target.value) / 1000;
          onChange(range.min + ratio * (range.max - range.min));
        }}
      />
      <span>{value.toFixed(2)}</span>
    </label>
  );
}
