import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const webRoot = fileURLToPath(new URL('../../../../', import.meta.url));

export default defineConfig({
  root: webRoot,
  resolve: {
    alias: {
      '@gs/units': path.resolve(webRoot, '../../packages/units/src/index.ts'),
    },
  },
  test: {
    environment: 'node',
    include: ['src/features/jobs/tests/**/*.test.ts', 'src/features/auth/authErrors.test.ts'],
  },
});
