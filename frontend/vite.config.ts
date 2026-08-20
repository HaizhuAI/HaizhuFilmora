import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8001', '/v1': 'http://127.0.0.1:8001', '/exports': 'http://127.0.0.1:8001', '/jobs': 'http://127.0.0.1:8001' } },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1200 }
})
