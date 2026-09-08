"""Provisioner — automação de ambiente do pipeline de Gaussian Splatting.

Componentes:
- ``detect``:  checagens somente-leitura do ambiente (GPU, WSL2, disco, RAM, ffmpeg, COLMAP, Python).
- ``install``: ffmpeg/PyTorch/gsplat reais no Linux+GPU; COLMAP só é localizado (nunca compilado).
- ``verify``:  smoke tests de ffmpeg, COLMAP do usuário, Python, torch e gsplat.
- ``health``:  agrega as detecções em um relatório de saúde consumido pela API/UI.
"""

from provisioner.detect import ComponentCheck, Status
from provisioner.health import HealthReport, run_all_checks

__all__ = ["ComponentCheck", "HealthReport", "Status", "run_all_checks"]
__version__ = "0.2.0"
