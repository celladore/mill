import path from 'node:path';
import { fileURLToPath } from 'node:url';

import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, 'src'),
    },
  },
  build: {
    outDir: 'build',
    rollupOptions: {
      input: {
        main: path.resolve(rootDir, 'index.html'),
        silentRenew: path.resolve(rootDir, 'silent-renew.html'),
      },
    },
  },
  test: {
    environment: 'jsdom',
  },
});
