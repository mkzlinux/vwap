import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Bound to 0.0.0.0 and with allowedHosts so the sandbox preview proxy can
// reach the dev server. localhost-only binding would show a blank preview.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
  },
  preview: {
    host: '0.0.0.0',
    port: 4173,
    strictPort: true,
    allowedHosts: true,
  },
});
