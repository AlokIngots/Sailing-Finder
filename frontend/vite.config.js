import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The bundle is built to frontend/dist and copied into the image, where FastAPI
// serves it. One origin for app and API, so the session cookie works without
// CORS and without a second public port.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 5173,
    // Local development only: forward /api to uvicorn so the cookie is
    // same-origin here too. Not used in production.
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/healthz': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
});
