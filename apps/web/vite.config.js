import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const page = (name) => fileURLToPath(new URL(`${name}.html`, import.meta.url));

// Cinco páginas independientes. En desarrollo, /api/local va al panel local (tools/web.sh).
export default defineConfig({
  base: './',
  plugins: [react()],
  build: {
    rollupOptions: {
      input: { index: page('index'), operator: page('operator'), patient: page('patient'), coldchain: page('coldchain'), company: page('company') },
    },
  },
  server: {
    proxy: { '/api/local': `http://127.0.0.1:${process.env.WEB_PORT || 8080}` },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
    setupFiles: ['src/test/setup.js'],
  },
});
