import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// A UI chama a API local diretamente (CORS liberado no backend para esta origem).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
});
