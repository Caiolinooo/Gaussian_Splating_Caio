"""Provisioner — automação de ambiente do pipeline de Gaussian Splatting.

Componentes:
- ``detect``:  checagens somente-leitura do ambiente (GPU, WSL2, disco, RAM, ffmpeg, COLMAP, Python).
- ``install``: plano de provisionamento e rotinas de instalação (Fase 0: stubs documentados).
- ``verify``:  verificações pós-instalação (smoke tests leves; pesados planejados).
- ``health``:  agrega as detecções em um relatório de saúde consumido pela API/UI.
"""

from provisioner.detect import ComponentCheck, Status
from provisioner.health import HealthReport, run_all_checks

__all__ = ["ComponentCheck", "HealthReport", "Status", "run_all_checks"]
__version__ = "0.1.0"
