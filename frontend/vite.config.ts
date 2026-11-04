/// <reference types="vitest/config" />
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Read VITE_* variables from the repo-root .env shared with the backend.
  envDir: '..',
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      // `make dev` runs its own backend on 8101; 8100 is the always-on app (launchd).
      '/api': `http://127.0.0.1:${process.env.DONGSEON_API_PORT ?? '8101'}`,
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
