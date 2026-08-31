import React, { useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import api from '../services/api';
import { sanitizeHtml } from '../utils/sanitizeHtml';

const escapeRegExp = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Match by full src OR by filename tail (preview URLs may be absolutized
// while the stored markdown holds relative [[BACKEND_URL]] paths).
const tailOf = (u) => (u || '').split(/[?#]/)[0].split('/').filter(Boolean).pop() || '';

function removeImageFromContent(content, clickedSrc) {  let out = content;
  const escExact = escapeRegExp(clickedSrc);
  out = out.replace(new RegExp(`!\\[[^\\]]*\\]\\(${escExact}\\)`, 'g'), '');
  out = out.replace(new RegExp(`<img[^>]*src=["']${escExact}["'][^>]*>`, 'gi'), '');

  const tail = tailOf(clickedSrc);
  if (tail && tail.length > 3) {
    const escTail = escapeRegExp(tail);
    out = out.replace(new RegExp(`!\\[[^\\]]*\\]\\([^)]*${escTail}\\)`, 'g'), '');
    out = out.replace(new RegExp(`<img[^>]*src=["'][^"']*${escTail}["'][^>]*>`, 'gi'), '');
  }
  return out.replace(/\n{3,}/g, '\n\n');
}

function replaceImageInContent(content, clickedSrc, newUrl) {
  let out = content;
  const escExact = escapeRegExp(clickedSrc);
  out = out.replace(new RegExp(`(!\\[[^\\]]*\\]\\()${escExact}(\\))`, 'g'), `$1${newUrl}$2`);
  out = out.replace(new RegExp(`(<img[^>]*src=["'])${escExact}(["'])`, 'gi'), `$1${newUrl}$2`);

  const tail = tailOf(clickedSrc);
  if (tail && tail.length > 3) {
    const escTail = escapeRegExp(tail);
    out = out.replace(new RegExp(`(!\\[[^\\]]*\\]\\([^)]*)${escTail}(\\))`, 'g'), `$1${newUrl}$2`);
    out = out.replace(new RegExp(`(<img[^>]*src=["'][^"']*)${escTail}(["'])`, 'gi'), `$1${newUrl}$2`);
  }
  return out;
}

/**
 * Read-only signature preview with click-to-manage images.
 * Click an image in the preview -> floating Replace/Remove toolbar appears.
 * Content is markdown-or-HTML string; mutations reported via onChangeContent.
 */
const SignaturePreview = ({ html, content, onChangeContent, emptyText }) => {
  const containerRef = useRef(null);
  const fileRef = useRef(null);
  const [selectedSrc, setSelectedSrc] = useState(null);
  const [toolbarPos, setToolbarPos] = useState(null);
  const [replacing, setReplacing] = useState(false);

  const clearSelection = () => {
    setSelectedSrc(null);
    setToolbarPos(null);
  };

  const handleClick = (e) => {
    const img = e.target.closest('img');
    if (!img || !containerRef.current) {
      clearSelection();
      return;
    }
    e.stopPropagation();
    const cRect = containerRef.current.getBoundingClientRect();
    const r = img.getBoundingClientRect();
    setSelectedSrc(img.getAttribute('src'));
    setToolbarPos({
      top: Math.max(2, r.top - cRect.top - 12),
      left: Math.max(4, r.left - cRect.left),
    });
  };

  const handleRemove = () => {
    if (!selectedSrc) return;
    onChangeContent(removeImageFromContent(content || '', selectedSrc));
    clearSelection();
  };

  const handleFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file || !selectedSrc) return;
    setReplacing(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('/api/upload-image', fd);
      onChangeContent(replaceImageInContent(content || '', selectedSrc, res.data.url));
      clearSelection();
    } catch {
      alert('Failed to upload replacement image');
    } finally {
      setReplacing(false);
    }
  };

  return (
    <div
      ref={containerRef}
      onClick={handleClick}
      className="relative bg-black/40 border border-white/5 rounded-xl p-6 text-slate-300 text-[13px] leading-relaxed email-preview min-h-[120px]"
    >
      {content ? (
        <div
          style={{ color: '#666', fontFamily: 'Arial, sans-serif', fontSize: '13px', lineHeight: '1.4' }}
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(html) }}
        />
      ) : (
        <span className="text-slate-600 italic">{emptyText || 'Nothing to preview yet.'}</span>
      )}

      {selectedSrc && toolbarPos && (
        <div
          className="absolute z-40 flex items-center gap-1 bg-[#1a1d26] border border-white/15 rounded-lg px-1.5 py-1 shadow-2xl"
          style={{ top: toolbarPos.top, left: toolbarPos.left }}
          onClick={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            title="Replace this image"
            onClick={() => fileRef.current?.click()}
            disabled={replacing}
            className="px-2 py-1 rounded-md bg-blue-500/20 hover:bg-blue-500/40 text-blue-300 text-[9px] font-black uppercase tracking-widest flex items-center gap-1 transition-all disabled:opacity-50 cursor-pointer"
          >
            {replacing ? <Loader2 className="w-3 h-3 animate-spin" /> : null}
            Replace
          </button>
          <button
            type="button"
            title="Remove this image"
            onClick={handleRemove}
            className="px-2 py-1 rounded-md bg-red-500/20 hover:bg-red-500/40 text-red-300 text-[9px] font-black uppercase tracking-widest flex items-center gap-1 transition-all cursor-pointer"
          >
            Remove
          </button>
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml"
        className="hidden"
        onChange={handleFile}
      />
    </div>
  );
};

export default SignaturePreview;
