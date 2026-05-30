import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 18432,
    host: '0.0.0.0',
    allowedHosts: ['www.intelhub.club', 'intelhub.club'],
    proxy: {
      '/api': {
        target: 'http://localhost:18923',
        changeOrigin: true,
      }
    }
  }
})
