import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const repoRoot = fileURLToPath(new URL('../..', import.meta.url));
const apiProxyTarget =
  process.env.GS_API_PROXY ?? process.env.VITE_API_PROXY ?? 'http://vm.groupabz.com:2222';
const apiProxy = {
  target: apiProxyTarget,
  changeOrigin: true,
  ws: true,
};

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@gs/units': path.resolve(repoRoot, 'packages/units/src'),
      '@gs/viewer': path.resolve(repoRoot, 'packages/viewer/src'),
      '@gs/overlays': path.resolve(repoRoot, 'packages/overlays/src'),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/health': apiProxy,
      '/setup': apiProxy,
      '/jobs': apiProxy,
      '/auth': apiProxy,
      '/scenes': apiProxy,
    },
  },
});
