// Dynamic PDF.js worker loader - uses CDN to avoid bundling 1.2MB worker
let pdfjsLib = null;
let workerLoaded = false;

export async function getPdfJs() {
  if (pdfjsLib && workerLoaded) return pdfjsLib;

  // Dynamic import - creates separate chunk
  pdfjsLib = await import('pdfjs-dist');
  
  if (!workerLoaded) {
    // Use CDN for worker to avoid bundling 1.2MB in build
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://unpkg.com/pdfjs-dist@4.x/build/pdf.worker.min.mjs';
    workerLoaded = true;
  }
  
  return pdfjsLib;
}

export function resetPdfJs() {
  pdfjsLib = null;
  workerLoaded = false;
}