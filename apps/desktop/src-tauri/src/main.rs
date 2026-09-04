// Shell desktop Tauri v2 — Fase 0: janela nativa apontando para o dev server do apps/web.
// Próximas fases: sidecar do Provisioner, supervisão do backend local (processos filhos)
// e auto-update (tauri-plugin-updater).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("falha ao iniciar o app desktop (Tauri)");
}
