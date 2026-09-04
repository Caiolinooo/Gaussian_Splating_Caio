import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const repoRoot = fileURLToPath(new URL('../..', import.meta.url));

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
  },
});
