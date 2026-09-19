import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const nonBlockingCSS = () => ({
  name: 'non-blocking-css',
  transformIndexHtml(html) {
    let result = html.replace(
      /<link rel="stylesheet"([^>]*href="\/assets\/[^"]*"[^>]*)>/g,
      '<link rel="preload"$1 as="style" onload="this.onload=null;this.rel=\'stylesheet\'"><noscript><link rel="stylesheet"$1></noscript>'
    )
    // Remove modulepreload for non-critical page chunks (keep only rolldown-runtime, vendor-react, and current page)
    result = result.replace(
      /<link rel="modulepreload"[^>]*href="\/assets\/(?:page-(?!Dashboard)|vendor-(?!react)|vendor-other)[^"]*"[^>]*>\n?/g,
      ''
    )
    return result
  }
})

export default defineConfig({
  plugins: [react(), nonBlockingCSS()],
  base: '/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    },
    historyApiFallback: true,
  },
  optimizeDeps: {
    exclude: ['pdfjs-dist', 'xlsx', 'mammoth', 'dompurify', 'html2canvas', 'jspdf'],
  },
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 1000,
    cssMinify: 'esbuild',
    modulePreload: { polyfill: false },
    rollupOptions: {
      external: ['pdfjs-dist/build/pdf.worker.min.mjs'],
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('react-router')) {
              return 'vendor-router';
            }
            if (id.includes('react') || id.includes('react-dom')) {
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
            if (id.includes('react-datepicker')) {
              return 'vendor-forms';
            }
            if (id.includes('xlsx')) {
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
          if (id.includes('/pages/')) {
            const pageName = id.split('/pages/')[1].split('/')[0].replace('.jsx', '');
            return `page-${pageName}`;
          }
          if (id.includes('/services/api.js')) {
            return 'vendor-api';
          }
        }
      }
    }
  }
})