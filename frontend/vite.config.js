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
    exclude: ['pdfjs-dist', 'xlsx', 'mammoth', 'dompurify', 'papaparse'],
  },
  build: {
    chunkSizeWarningLimit: 1000,
    rollupOptions: {
      external: ['pdfjs-dist/build/pdf.worker.min.mjs'],
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('react') || id.includes('react-dom') || id.includes('react-router')) {
              return 'vendor-react';
            }
            if (id.includes('lucide-react') || id.includes('date-fns') || id.includes('clsx')) {
              return 'vendor-ui';
            }
            if (id.includes('recharts')) {
              return 'vendor-charts';
            }
            if (id.includes('html2canvas') || id.includes('jspdf')) {
              return 'vendor-pdf';
            }
            if (id.includes('react-hook-form') || id.includes('react-quill') || id.includes('react-datepicker')) {
              return 'vendor-forms';
            }
            if (id.includes('xlsx') || id.includes('papaparse')) {
              return 'vendor-excel';
            }
            if (id.includes('mammoth')) {
              return 'vendor-mammoth';
            }
            if (id.includes('pdfjs-dist')) {
              return 'vendor-pdfjs';
            }
            if (id.includes('dompurify')) {
              return 'vendor-dompurify';
            }
            if (id.includes('react-markdown') || id.includes('react-dropzone')) {
              return 'vendor-other';
            }
            return 'vendor-other';
          }
          // Split large app pages into separate chunks
          if (id.includes('/pages/')) {
            const pageName = id.split('/pages/')[1].split('/')[0].replace('.jsx', '');
            return `page-${pageName}`;
          }
          // Put api.js in its own chunk
          if (id.includes('/services/api.js')) {
            return 'vendor-api';
          }
        }
      }
    }
  }
})