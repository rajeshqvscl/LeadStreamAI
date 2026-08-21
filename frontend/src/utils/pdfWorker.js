// Dynamic PDF.js worker loader - prevents bundling 1.2MB worker in initial chunk
let pdfjsLib = null;
let workerLoaded = false;

export async function getPdfJs() {
  if (pdfjsLib && workerLoaded) return pdfjsLib;

  // Dynamic import - creates separate chunk
  pdfjsLib = await import('pdfjs-dist');
  
  if (!workerLoaded) {
    const workerModule = await import('pdfjs-dist/build/pdf.worker.min.mjs?url');
    pdfjsLib.GlobalWorkerOptions.workerSrc = workerModule.default;
    workerLoaded = true;
  }
  
  return pdfjsLib;
}

export function resetPdfJs() {
  pdfjsLib = null;
  workerLoaded = false;
}