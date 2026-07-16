import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    },
    historyApiFallback: true,
  },
  optimizeDeps: {
    include: ['html2canvas', 'jspdf'],
  },
})