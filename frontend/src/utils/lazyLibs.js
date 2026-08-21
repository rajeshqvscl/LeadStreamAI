// Lazy-loaded heavy library wrappers - prevents bundling in page chunks
import { lazy } from 'react';

// Charts - lazy loaded
export const LazyCharts = {
  BarChart: lazy(() => import('recharts').then(m => ({ default: m.BarChart }))),
  Bar: lazy(() => import('recharts').then(m => ({ default: m.Bar }))),
  PieChart: lazy(() => import('recharts').then(m => ({ default: m.PieChart }))),
  Pie: lazy(() => import('recharts').then(m => ({ default: m.Pie }))),
  Cell: lazy(() => import('recharts').then(m => ({ default: m.Cell }))),
  XAxis: lazy(() => import('recharts').then(m => ({ default: m.XAxis }))),
  YAxis: lazy(() => import('recharts').then(m => ({ default: m.YAxis }))),
  CartesianGrid: lazy(() => import('recharts').then(m => ({ default: m.CartesianGrid }))),
  Tooltip: lazy(() => import('recharts').then(m => ({ default: m.Tooltip }))),
  Legend: lazy(() => import('recharts').then(m => ({ default: m.Legend }))),
  ResponsiveContainer: lazy(() => import('recharts').then(m => ({ default: m.ResponsiveContainer }))),
  AreaChart: lazy(() => import('recharts').then(m => ({ default: m.AreaChart }))),
  Area: lazy(() => import('recharts').then(m => ({ default: m.Area }))),
};

// PDF libraries - lazy loaded
export const LazyPDF = {
  html2canvas: lazy(() => import('html2canvas').then(m => ({ default: m.default }))),
  jsPDF: lazy(() => import('jspdf').then(m => ({ default: m.default }))),
};

// Excel - lazy loaded
export const LazyXLSX = {
  XLSX: lazy(() => import('xlsx').then(m => ({ default: m.default }))),
};

// Papa Parse - lazy loaded
export const LazyPapa = {
  Papa: lazy(() => import('papaparse').then(m => ({ default: m.default }))),
};

// React Markdown - lazy loaded
export const LazyMarkdown = {
  ReactMarkdown: lazy(() => import('react-markdown').then(m => ({ default: m.default }))),
};

// DatePicker - lazy loaded
export const LazyDatePicker = {
  DatePicker: lazy(() => import('react-datepicker').then(m => ({ default: m.default }))),
};

// Mammoth - lazy loaded
export const LazyMammoth = {
  mammoth: lazy(() => import('mammoth').then(m => ({ default: m.default }))),
};

// DOM Purify - lazy loaded
export const LazyDOMPurify = {
  DOMPurify: lazy(() => import('dompurify').then(m => ({ default: m.default }))),
};

// React Quill - lazy loaded
export const LazyQuill = {
  ReactQuill: lazy(() => import('react-quill').then(m => ({ default: m.default }))),
};

// React Dropzone - lazy loaded
export const LazyDropzone = {
  useDropzone: lazy(() => import('react-dropzone').then(m => ({ default: m.useDropzone }))),
};

// Sanitize HTML - lazy loaded
export const LazySanitize = {
  sanitizeHtml: lazy(() => import('../utils/sanitizeHtml').then(m => ({ default: m.sanitizeHtml }))),
};

// PDF.js - already handled via pdfWorker.js
export { getPdfJs } from './pdfWorker';