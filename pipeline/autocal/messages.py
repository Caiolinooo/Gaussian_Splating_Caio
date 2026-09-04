"""User-facing auto-calibration warnings (pt-BR, actionable).

Code, identifiers and docstrings stay in English. These strings are the only
copy shown to the end user when auto-height calibration is weak or impossible.
The live tape measure in the viewer is always the fallback (tasks.md §7).
"""

from __future__ import annotations

WARN_NO_PERSON = (
    "Nenhuma pessoa foi detectada nos frames. Use a trena no viewer para calibrar manualmente."
)
WARN_PARTIAL_BODY = (
    "O corpo aparece só em parte na maioria dos frames. "
    "A confiança está baixa — confirme a escala com a trena."
)
WARN_MULTI_PERSON = (
    "Várias pessoas aparecem nos frames. "
    "A escala pode estar errada se a altura informada não for da pessoa principal."
)
WARN_FEW_FRAMES = (
    "Poucos frames válidos para auto-calibração. Confirme a escala com a trena no viewer."
)
WARN_HIGH_VARIANCE = (
    "A altura estimada varia muito entre os frames. Confirme a escala com a trena."
)
WARN_NO_DEPTH = (
    "Sem profundidade do SfM: não foi possível converter pixels em unidades da cena. "
    "Prefira a trena no viewer."
)
WARN_HEURISTIC_DEPTH = (
    "A profundidade usada é heurística (sem mapa de profundidade do COLMAP). "
    "Trate o fator de escala como preliminar e confirme com a trena."
)
WARN_LOW_VISIBILITY = (
    "Muitos pontos do esqueleto estão oclusos. A auto-calibração pode falhar — use a trena."
)
WARN_NO_BACKEND = (
    "Nenhum backend de pose está disponível neste ambiente. "
    "A calibração automática foi ignorada; use a trena no viewer."
)
WARN_BAD_POSTURE = (
    "A pessoa não está de pé na maioria dos frames. "
    "A altura em pixels fica encurtada — use a trena."
)
WARN_NO_SCALE = (
    "Não foi possível estimar um fator de escala. Defina a referência com a trena no viewer."
)
WARN_HEIGHT_RANGE = (
    "A altura informada está fora da faixa humana típica (0,40–2,70 m). "
    "Verifique se o valor está em metros."
)
WARN_NO_FRAMES = (
    "Nenhum frame foi enviado para a auto-calibração. Use a trena no viewer."
)

#: Below this many inlier frames we surface WARN_FEW_FRAMES.
FEW_FRAMES_THRESHOLD: int = 4

#: Coefficient of variation of inlier scene heights that triggers WARN_HIGH_VARIANCE.
HIGH_VARIANCE_CV: float = 0.12

#: Fraction of frames with >1 person that triggers WARN_MULTI_PERSON.
MULTI_PERSON_RATIO_THRESHOLD: float = 0.25

#: Typical adult stature used only for a sanity warning (metres).
TYPICAL_HEIGHT_M: tuple[float, float] = (0.40, 2.70)
