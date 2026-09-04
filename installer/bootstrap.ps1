# ============================================================================
# installer/bootstrap.ps1 — STUB (Fase 0)
#
# Papel planejado (Fases seguintes): ponto de entrada do instalador da
# aplicação desktop. O instalador Tauri (MSI/NSIS) cuidará da experiência
# "instala e abre"; este script existirá como caminho de recuperação /
# bootstrap manual avançado, orquestrando o Provisioner (pipeline/provisioner)
# fora do app quando necessário.
#
# O que ele FARÁ quando implementado (não executar agora):
#   1. Verificar pré-requisitos mínimos (Windows 10/11, WebView2, espaço).
#   2. Garantir WSL2 habilitado (wsl --install --no-distribution) — requer
#      reinício; o fluxo de UI guiará o usuário.
#   3. Delegar ao Provisioner (Python) a instalação de ffmpeg, COLMAP,
#      PyTorch+CUDA e gsplat — com logs enviados à UI de Setup.
#
# Referências oficiais planejadas:
#   - WSL:    https://learn.microsoft.com/pt-br/windows/wsl/install
#   - FFmpeg: https://www.gyan.dev/ffmpeg/builds/ (builds Windows)
#   - COLMAP: https://github.com/colmap/colmap/releases
#   - gsplat: https://docs.gsplat.studio/ (wheels pré-compiladas)
#
# ⚠️  NÃO EXECUTAR: este arquivo é um placeholder documentado da Fase 0.
# ============================================================================

Write-Host "bootstrap.ps1 é um stub da Fase 0 — a instalação real será implementada junto ao Provisioner."
Write-Host "Acompanhe o progresso pela UI de Setup (apps/web) consumindo a API (apps/api)."
