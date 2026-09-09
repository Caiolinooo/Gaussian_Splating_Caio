import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from 'vitest/config';

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: [
      {
        find: /^@gs\/overlays\/types$/,
        replacement: path.resolve(root, '../overlays/src/types.ts'),
      },
      {
        find: /^@gs\/overlays\/validate$/,
        replacement: path.resolve(root, '../overlays/src/validate.ts'),
      },
      {
        find: /^@gs\/overlays\/serialize$/,
        replacement: path.resolve(root, '../overlays/src/serialize.ts'),
      },
      {
        find: /^@gs\/units$/,
        replacement: path.resolve(root, '../units/src/index.ts'),
      },
    ],
  },
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts', 'src/**/*.test.ts'],
  },
});
