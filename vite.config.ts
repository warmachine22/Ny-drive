import { defineConfig } from 'vite';

export default defineConfig({
  publicDir: 'tools/map_compiler/fixtures/flatiron/compiled',
  build: {
    target: 'es2022',
    sourcemap: true,
  },
  server: {
    host: '127.0.0.1',
  },
});
