import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Bold, Italic, Underline, List, ListOrdered, Link, Image, Paperclip, Palette, Code, Table, Eye, ChevronDown, Trash2, ArrowUp, ArrowDown, ArrowLeft, ArrowRight } from 'lucide-react';
import api from '../services/api';
import { applyForcedLogoStyles } from '../utils/logoSize';

// ─── Markdown ↔ HTML Conversion ────────────────────────────────────────
const _getEditorImgSizes = () => {
  try {
    const _su = JSON.parse(localStorage.getItem('user') || localStorage.getItem('user_admin') || '{}');
    return [_su?.image_width || '400px', _su?.image_height || 'auto'];
  } catch { return ['400px', 'auto']; }
};

const mdToHtml = (md) => {
  const [imgW, imgH] = _getEditorImgSizes();
  if (!md) return '';
  if (/^<[a-z][^>]*>/i.test(md.trim()) && /<\/[a-z]+>\s*$/i.test(md.trim())) return md;
  const _editorBackendUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  md = md.replace(/\[\[BACKEND_URL\]\]/g, _editorBackendUrl);
  let html = md.replace(/•/g, '*');
  let lines = html.split('\n');
  let result = [];
  let inList = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (/^\*\s+/.test(line)) {
      if (!inList) { result.push('<ul>'); inList = true; }
      result.push('<li>' + line.replace(/^\*\s+/, '') + '</li>');
    } else {
      if (inList) { result.push('</ul>'); inList = false; }
      result.push(line);
    }
  }
  if (inList) result.push('</ul>');
  html = result.join('\n');
  html = html.replace(/<ul>\n/g, '<ul>').replace(/\n<\/ul>/g, '</ul>');
  html = html.replace(/<li>\n/g, '<li>').replace(/\n<\/li>/g, '</li>');
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*([^*]+)\*/g, (m, inner) => {
    if (inner.startsWith(' ') || inner.endsWith(' ')) return m;
    return `<em>${inner}</em>`;
  });
  html = html.replace(/!\[(.*?)\]\((.*?)\)/g, (m, alt, src) => {
    return `<img src="${src}" alt="${alt}" style="width:${imgW};height:${imgH};">`;
  });
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
  html = html.replace(/^###\s+(.*?)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.*?)$/gm, '<h2>$1</h2>');
  html = html.replace(/^#\s+(.*?)$/gm, '<h1>$1</h1>');
  html = html.replace(/^[-*_]{3,}\s*$/gm, '<hr style="border: none; border-top: 2px solid #475569; margin: 16px 0;">');
  html = html.replace(/\n/g, '<br>');
  // Palak's logo must preview at 150x150 (backend forces the same size in sent emails).
  return applyForcedLogoStyles(html);
};

const htmlToMd = (html) => {
  if (!html) return '';
  let md = html;
  md = md.replace(/<strong><em>(.*?)<\/em><\/strong>/g, '***$1***');
  md = md.replace(/<strong>(.*?)<\/strong>/g, '**$1**');
  md = md.replace(/<em>(.*?)<\/em>/g, '*$1*');
  md = md.replace(/<b>(.*?)<\/b>/g, '**$1**');
  md = md.replace(/<i>(.*?)<\/i>/g, '*$1*');
  md = md.replace(/<u>(.*?)<\/u>/gi, '<u>$1</u>');
  md = md.replace(/<h1>(.*?)<\/h1>/gi, '# $1\n');
  md = md.replace(/<h2>(.*?)<\/h2>/gi, '## $1\n');
  md = md.replace(/<h3>(.*?)<\/h3>/gi, '### $1\n');
  md = md.replace(/<a\s+[^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/gi, '[$2]($1)');
  md = md.replace(/<img[^>]*src="([^"]*)"[^>]*>/gi, '![]($1)');
  md = md.replace(/<br\s*\/?>/gi, '\n');
  md = md.replace(/<\/div>/gi, '\n').replace(/<div[^>]*>/gi, '');
  md = md.replace(/<\/p>/gi, '\n\n').replace(/<p[^>]*>/gi, '');
  md = md.replace(/<\/li>/gi, '\n').replace(/<li[^>]*>/gi, '');
  md = md.replace(/<\/ul>/gi, '\n').replace(/<ul[^>]*>/gi, '');
  md = md.replace(/<\/ol>/gi, '\n').replace(/<ol[^>]*>/gi, '');
  md = md.replace(/<span\s+style="([^"]*)"[^>]*>/gi, (m, style) => {
    if (style) return `<span style="${style}">`;
    return '';
  });
  md = md.replace(/<\/span>/gi, '</span>');
  // Legacy <font color/face/size> tags (older execCommand foreColor output) -> styled span
  md = md.replace(/<font\s+([^>]*)>/gi, (m, attrs) => {
    const styles = [];
    const mColor = attrs.match(/color\s*=\s*["']?([^"'\s>]+)["']?/i);
    const mFace = attrs.match(/face\s*=\s*["']?([^"'\s>]+)["']?/i);
    const mSize = attrs.match(/size\s*=\s*["']?([^"'\s>]+)["']?/i);
    if (mColor) styles.push(`color: ${mColor[1]}`);
    if (mFace) styles.push(`font-family: ${mFace[1]}`);
    if (mSize) {
      let sz = mSize[1];
      const sizeMap = { '1': '10px', '2': '12px', '3': '14px', '4': '16px', '5': '18px', '6': '22px', '7': '28px' };
      if (/^[+-]\d+$/.test(sz)) sz = String(3 + parseInt(sz, 10)); // HTML relative size (base 3)
      const px = sizeMap[sz] || '';
      if (px) styles.push(`font-size: ${px}`);
    }
    return styles.length ? `<span style="${styles.join('; ')};">` : '';
  });
  md = md.replace(/<\/font\s*>/gi, '</span>');
  md = md.replace(/&amp;/gi, '&').replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&nbsp;/gi, ' ');
  md = md.replace(/\n{3,}/g, '\n\n');
  return md.trim();
};

const isHtml = (str) => /<[a-z][\s\S]*>/i.test(str);

// Stored content (signatures, draft bodies) can be a MIX of HTML and raw
// markdown — e.g. `<span style="color:...">**Thanks & Regards,**</span>\n**Ayush Heda**\n[LinkedIn](https://…)`.
// When the raw value already contains HTML tags we can't run mdToHtml on it
// wholesale (it would double-wrap tags), but we still need the markdown
// remnants and the \n line breaks converted so the WYSIWYG editor shows the
// real signature formatting instead of literal `**Name**` on one collapsed
// line. Newlines are converted to <br> EXCEPT next to block-level tags
// (div/table/tr/td/p/h1-6/ul/ol/li/…) so existing HTML bodies are untouched.
const convertHtmlMarkdownRemnants = (html) => {
  if (!html) return html;
  const [imgW, imgH] = _getEditorImgSizes();
  const _editorBackendUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
  html = html.replace(/\[\[BACKEND_URL\]\]/g, _editorBackendUrl);
  const converted = html
    .replace(/!\[(.*?)\]\((.*?)\)/g, (m, alt, src) => `<img src="${src}" alt="${alt}" style="width:${imgW};height:${imgH};">`)
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*\n]+)\*/g, (m, inner) => {
      if (inner.startsWith(' ') || inner.endsWith(' ')) return m;
      return `<em>${inner}</em>`;
    })
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/^\s*(--|—)\s*$/gm, '<div style="color:#475569; font-style:italic;">--</div>')
    .replace(/\n(?=[ \t]*(?:<\/?)(?:div|table|tbody|thead|tfoot|tr|td|th|p|h[1-6]|ul|ol|li|blockquote|section|article|header|footer|main|aside|nav|form|fieldset|figure|figcaption|hr|pre|address|br)[\s/>])/gi, '@@LSBLOCKNL@@')
    .replace(/(<\/?(?:div|table|tbody|thead|tfoot|tr|td|th|p|h[1-6]|ul|ol|li|blockquote|section|article|header|footer|main|aside|nav|form|fieldset|figure|figcaption|hr|pre|address|br)[^>]*>)\n/gi, '$1@@LSBLOCKNL@@')
    .replace(/\n/g, '<br>')
    .replace(/@@LSBLOCKNL@@/g, '\n');
  // Palak's logo must preview at 150x150 (backend forces the same size in sent emails).
  return applyForcedLogoStyles(converted);
};

// ─── Constants ─────────────────────────────────────────────────────────

const FONTS = [
  { label: 'Sans Serif', value: 'sans-serif' },
  { label: 'Arial', value: 'Arial, Helvetica, sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", Times, serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Courier New', value: '"Courier New", monospace' },
  { label: 'Tahoma', value: 'Tahoma, Geneva, sans-serif' },
  { label: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
  { label: 'Verdana', value: 'Verdana, Geneva, sans-serif' },
  { label: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
  { label: 'Impact', value: 'Impact, Charcoal, sans-serif' },
  { label: 'Lucida Console', value: '"Lucida Console", Monaco, monospace' },
];

const FONT_SIZES = Array.from({ length: 11 }, (_, i) => i + 6);

// Scrollable font-size picker (used in the toolbar)
const SizeDropdown = ({ options, onSelect }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onMouseDown={(e) => { e.preventDefault(); setOpen(o => !o); }}
        className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none hover:text-white flex items-center gap-1"
      >
        Size <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl shadow-2xl max-h-[200px] overflow-y-auto custom-scrollbar w-[84px]">
          {options.map(s => (
            <button
              key={s}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onSelect(String(s)); setOpen(false); }}
              className="w-full text-left px-3 py-1.5 text-[11px] text-slate-200 hover:bg-white/10 hover:text-white"
            >
              {s}px
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const LINE_HEIGHT_OPTIONS = ['1.0', '1.2', '1.4', '1.5', '1.6', '1.8', '2.0'];
const TABLE_LINE_HEIGHT_OPTIONS = ['1.0', '1.2', '1.4', '1.5', '1.6', '1.8', '2.0'];

const LineHeightDropdown = ({ value, onSelect, label = 'Line' }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onMouseDown={(e) => { e.preventDefault(); setOpen(o => !o); }}
        className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none hover:text-white flex items-center gap-1"
      >
        {label} <ChevronDown className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl shadow-2xl max-h-[200px] overflow-y-auto custom-scrollbar w-[72px]">
          {LINE_HEIGHT_OPTIONS.map(lh => (
            <button
              key={lh}
              type="button"
              onMouseDown={(e) => { e.preventDefault(); onSelect(lh); setOpen(false); }}
              className={`w-full text-left px-3 py-1.5 text-[11px] hover:bg-white/10 ${lh === value ? 'text-blue-400 font-bold' : 'text-slate-200 hover:text-white'}`}
            >
              {lh}x
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const HEADINGS = [
  { label: 'H1', prefix: '# ', tag: 'h1' },
  { label: 'H2', prefix: '## ', tag: 'h2' },
  { label: 'H3', prefix: '### ', tag: 'h3' },
];

const COLORS = [
  '#000000', '#434343', '#666666', '#999999', '#b7b7b7', '#cccccc', '#d9d9d9', '#ffffff',
  '#980000', '#ff0000', '#ff9900', '#ffff00', '#00ff00', '#00ffff', '#4a86e8', '#0000ff',
  '#9900ff', '#ff00ff', '#e6b8af', '#f4cccc', '#fce5cd', '#fff2cc', '#d9ead3', '#d0e0e3',
  '#c9daf8', '#cfe2f3', '#d9d2e9', '#ead1dc', '#dd7e6b', '#ea9999', '#f9cb9c', '#ffe599',
  '#b6d7a8', '#a2c4c9', '#a4c2f4', '#9fc5e8', '#b4a7d6', '#d5a6bd', '#cc4125', '#e06666',
  '#f6b26b', '#ffd966', '#93c47d', '#76a5af', '#6d9eeb', '#6fa8dc', '#8e7cc3', '#c27ba0',
  '#a61c00', '#cc0000', '#e69138', '#f1c232', '#6aa84f', '#45818e', '#3c78d8', '#3d85c6',
  '#674ea7', '#a64d79', '#85200c', '#990000', '#b45f06', '#bf9000', '#38761d', '#134f5c',
  '#1155cc', '#0b5394', '#351c75', '#741b47', '#5b0f00', '#660000', '#783f04', '#7f6000',
  '#274e13', '#0c343d', '#1c4587', '#073763', '#20124d', '#4c1130',
];

// ─── ToolButton ────────────────────────────────────────────────────────

const ToolButton = ({ icon: Icon, title, onClick, active, className = '' }) => (
  <button
    type="button"
    title={title}
    onMouseDown={e => { e.preventDefault(); onClick?.(); }}
    className={`p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all ${active ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : ''} ${className}`}
  >
    <Icon className="w-3.5 h-3.5" />
  </button>
);

// ─── Context Menu Item ────────────────────────────────────────────────
const CtxItem = ({ icon: Icon, label, onMouseDown, danger }) => (
  <button
    type="button"
    onMouseDown={e => { e.preventDefault(); e.stopPropagation(); onMouseDown?.(); }}
    className={`w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-left transition-colors ${danger ? 'text-red-400 hover:bg-red-500/10 hover:text-red-300' : 'text-slate-300 hover:bg-white/10 hover:text-white'}`}
  >
    <Icon className="w-3 h-3 shrink-0" />
    {label}
  </button>
);

// Inject global styles for contentEditable lists
if (typeof document !== 'undefined' && !document.getElementById('wysiwyg-list-styles')) {
  const style = document.createElement('style');
  style.id = 'wysiwyg-list-styles';
  style.textContent = `
    .wysiwyg-editor ul, .wysiwyg-editor ol {
      margin: 0.8em 0;
      padding-left: 1.5em;
      list-style-type: disc;
    }
    .wysiwyg-editor ol {
      list-style-type: decimal;
    }
    .wysiwyg-editor li {
      margin-bottom: 0.4em;
      line-height: 1.5;
    }
    .wysiwyg-editor ul ul {
      list-style-type: circle;
      margin-top: 0.4em;
      margin-bottom: 0.4em;
    }
    .wysiwyg-editor ol ol {
      list-style-type: lower-alpha;
    }
    /* ── Table resize handles ── */
    .wysiwyg-editor table { position: relative; }
    .wysiwyg-editor td, .wysiwyg-editor th {
      position: relative;
      user-select: text;
    }
    .wysiwyg-editor .col-resize-handle {
      position: absolute;
      top: 0; right: -3px;
      width: 6px; height: 100%;
      cursor: col-resize;
      z-index: 10;
      background: transparent;
      transition: background 0.15s;
    }
    .wysiwyg-editor .col-resize-handle:hover,
    .wysiwyg-editor .col-resize-handle.active {
      background: rgba(59, 130, 246, 0.4);
    }
    .wysiwyg-editor .row-resize-handle {
      position: absolute;
      bottom: -3px; left: 0;
      height: 6px; width: 100%;
      cursor: row-resize;
      z-index: 10;
      background: transparent;
      transition: background 0.15s;
    }
    .wysiwyg-editor .row-resize-handle:hover,
    .wysiwyg-editor .row-resize-handle.active {
      background: rgba(59, 130, 246, 0.4);
    }
  `;
  document.head.appendChild(style);
}

// ─── ToolbarTextarea ───────────────────────────────────────────────────

const ToolbarTextarea = ({ value, onChange, rows, placeholder, className, readOnly, fontSizeOptions = FONT_SIZES }) => {
  const textareaRef = useRef(null);
  const editorRef = useRef(null);
  const [showSource, setShowSource] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showTextColors, setShowTextColors] = useState(false);
  const [showBgColors, setShowBgColors] = useState(false);
  const [lineHeight, setLineHeight] = useState('1.4');
  const lineHeightRef = useRef('1.4');
  const [tableLineHeight, setTableLineHeight] = useState('1.2');
  const tableLineHeightRef = useRef('1.2');
  const textColorBtnRef = useRef(null);
  const bgColorBtnRef = useRef(null);
  const editorSyncedRef = useRef(''); // Tracks what's currently in the editor DOM

  // ── Table editing state ─────────────────────────────────────────────
  const [tableMenu, setTableMenu] = useState(null); // { x, y, tableEl, rowIndex, colIndex }
  const tableMenuDataRef = useRef(null); // Never-stale copy for event handlers
  const resizeRef = useRef(null); // { type:'col'|'row', tableEl, index, startX, startWidths }

  // Close context menu on outside click
  useEffect(() => {
    if (!tableMenu) { tableMenuDataRef.current = null; return; }
    const close = (e) => {
      if (tableMenuRef.current && !tableMenuRef.current.contains(e.target)) {
        setTableMenu(null);
        tableMenuDataRef.current = null;
      }
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [tableMenu]);
  const tableMenuRef = useRef(null);

  // ── Conversion helpers ──────────────────────────────────────────────

  const toHtml = useCallback((raw) => {
    if (!raw) return '';
    // HTML content gets markdown-remnant conversion so mixed signatures render
    // properly; pure markdown goes through the full mdToHtml pipeline.
    return isHtml(raw) ? convertHtmlMarkdownRemnants(raw) : mdToHtml(raw);
  }, []);

  const toRaw = useCallback((html) => {
    if (!html) return '';
    if (!isHtml(html)) return html;
    return htmlToMd(html);
  }, []);

  // ── Sync editor DOM only when value changes from EXTERNAL sources ──
  // When user types, syncFromEditor updates editorSyncedRef so this skips — cursor stays put!

  useEffect(() => {
    if (!showSource && editorRef.current) {
      // Extract lineHeight and tableLineHeight from data-lh/data-lh-table wrappers
      let rawValue = value;
      let detectedLh = '1.4';
      let detectedTlh = '1.2';
      if (rawValue && /^<div\s+(?:[^>]*>)?/i.test(rawValue)) {
        const lhMatch = rawValue.match(/data-lh="([^"]+)"/i);
        const tlhMatch = rawValue.match(/data-lh-table="([^"]+)"/i);
        if (lhMatch) detectedLh = lhMatch[1];
        if (tlhMatch) detectedTlh = tlhMatch[1];
        rawValue = rawValue.replace(/^<div\s+data-lh(?:-table)?="[^"]*"\s*(?:data-lh(?:-table)?="[^"]*")?>/i, '').replace(/<\/div>\s*$/i, '');
      }
      if (detectedLh !== lineHeight) setLineHeight(detectedLh);
      if (detectedTlh !== tableLineHeight) setTableLineHeight(detectedTlh);

      const expectedHtml = toHtml(rawValue);
      // Skip if DOM already matches — preserves cursor position during user typing
      if (editorSyncedRef.current === expectedHtml) return;

      // External update (toolbar button, parent value change, mode switch)
      const sel = window.getSelection();
      const wasFocused = editorRef.current.contains(sel?.anchorNode);

      // Save cursor position as character offset
      let savedOffset = null;
      if (wasFocused && sel?.rangeCount > 0) {
        try {
          const range = sel.getRangeAt(0);
          const preRange = range.cloneRange();
          preRange.selectNodeContents(editorRef.current);
          preRange.setEnd(range.endContainer, range.endOffset);
          savedOffset = preRange.toString().length;
        } catch(_e) { /* ignore */ }
      }

      editorRef.current.innerHTML = expectedHtml;
      editorSyncedRef.current = expectedHtml;

      // Restore cursor to character offset
      if (wasFocused && savedOffset !== null) {
        try {
          const newSel = window.getSelection();
          if (newSel && editorRef.current.firstChild) {
            const textLen = editorRef.current.textContent?.length || 0;
            const offset = Math.min(savedOffset, textLen);
            const range = document.createRange();
            range.setStart(editorRef.current.firstChild, offset);
            range.collapse(true);
            newSel.removeAllRanges();
            newSel.addRange(range);
          }
        } catch(_e) { /* fallback */ }
      }
    }
  }, [value, showSource, toHtml]);

  // ── Update parent from WYSIWYG editor ──────────────────────────────

  const syncFromEditor = useCallback(() => {
    if (!editorRef.current) return;
    let newHtml = editorRef.current.innerHTML;
    // Embed lineHeight and tableLineHeight in content so they persist across save/load
    const lh = lineHeightRef.current;
    const tlh = tableLineHeightRef.current;
    const hasLh = lh && lh !== '1.4';
    const hasTlh = tlh && tlh !== '1.2';
    if (hasLh || hasTlh) {
      const attrs = [];
      if (hasLh) attrs.push(`data-lh="${lh}"`);
      if (hasTlh) attrs.push(`data-lh-table="${tlh}"`);
      newHtml = `<div ${attrs.join(' ')}>${newHtml}</div>`;
    }
    // Mark as user-synced so the useEffect skips DOM update — cursor stays put!
    editorSyncedRef.current = newHtml;
    const raw = newHtml === '<br>' ? '' : newHtml;
    if (onChange) onChange({ target: { value: raw } });
  }, [onChange]);

  // Blur handler: skip sync while context menu is open so DOM refs stay live
  const handleEditorBlur = useCallback(() => {
    if (tableMenuDataRef.current) return;
    syncFromEditor();
  }, [syncFromEditor]);

  // ── WYSIWYG execCommand ────────────────────────────────────────────

  const execWysiwyg = useCallback((cmd, cmdValue = null, useCss = false) => {
    if (!editorRef.current || showSource) return;
    editorRef.current.focus();
    // styleWithCSS is a STICKY document-level setting — always set it explicitly.
    // true  -> foreColor/hiliteColor emit <span style="color:..."> (survive save)
    // false -> bold/italic/underline keep producing <b>/<i>/<u> (convert to **/*)
    document.execCommand('styleWithCSS', false, useCss);
    document.execCommand(cmd, false, cmdValue);
    syncFromEditor();
  }, [showSource, syncFromEditor]);

  // ── Source mode handlers ────────────────────────────────────────────

  const insert = (before, after = '') => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    const selected = value.substring(start, end);
    const newVal = value.substring(0, start) + before + selected + after + value.substring(end);
    onChange({ target: { value: newVal } });
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(start + before.length, start + before.length + selected.length);
    }, 0);
  };

  const insertLinePrefix = (prefix) => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const val = value;
    const lineStart = val.lastIndexOf('\n', start - 1) + 1;
    const lineEnd = val.indexOf('\n', start);
    const line = val.substring(lineStart, lineEnd === -1 ? val.length : lineEnd);
    const newLine = prefix + line;
    const newVal = val.substring(0, lineStart) + newLine + val.substring(lineEnd === -1 ? val.length : lineEnd);
    onChange({ target: { value: newVal } });
    setTimeout(() => {
      ta.focus();
      ta.setSelectionRange(lineStart + prefix.length, lineStart + prefix.length);
    }, 0);
  };

  // ── Unified handlers (WYSIWYG + Source) ─────────────────────────────

  const handleBold = () => {
    if (showSource) { insert('**', '**'); return; }
    execWysiwyg('bold');
  };

  const handleItalic = () => {
    if (showSource) { insert('*', '*'); return; }
    execWysiwyg('italic');
  };

  const handleUnderline = () => {
    if (showSource) { insert('<u>', '</u>'); return; }
    execWysiwyg('underline');
  };

  const handleBulletList = () => {
    if (showSource) { insertLinePrefix('- '); return; }
    execWysiwyg('insertUnorderedList');
  };

  const handleOrderedList = () => {
    if (showSource) { insertLinePrefix('1. '); return; }
    execWysiwyg('insertOrderedList');
  };

  const handleLink = () => {
    if (showSource) {
      const ta = textareaRef.current;
      if (!ta) return;
      const selected = value.substring(ta.selectionStart, ta.selectionEnd);
      const url = window.prompt('Enter URL:', 'https://');
      if (!url) return;
      const display = selected || window.prompt('Enter link text:', 'link');
      if (!display) return;
      insert(`[${display}](${url})`);
      return;
    }
    const url = window.prompt('Enter URL:', 'https://');
    if (!url) return;
    editorRef.current?.focus();
    const sel = window.getSelection()?.toString();
    if (sel) {
      execWysiwyg('createLink', url);
    } else {
      const display = window.prompt('Enter link text:', 'link');
      if (!display) return;
      document.execCommand('insertHTML', false, `<a href="${url}">${display}</a>`);
      syncFromEditor();
    }
  };

  const handleImageUpload = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml';
    const MAX_SIZE = 10 * 1024 * 1024;
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > MAX_SIZE) {
        alert(`Image too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum allowed is 10MB.`);
        return;
      }
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await api.post('/api/upload-image', formData);
        const imgUrl = res.data.url;
        if (!showSource && editorRef.current) {
          editorRef.current.focus();
          document.execCommand('insertImage', false, imgUrl);
          syncFromEditor();
        } else {
          insert(`![](${imgUrl})\n`);
        }
      } catch (_err) {
        alert('Failed to upload image');
      }
    };
    input.click();
  };

  const handleFileUpload = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    const MAX_SIZE = 15 * 1024 * 1024;
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      if (file.size > MAX_SIZE) {
        alert(`File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Maximum allowed is 15MB.`);
        return;
      }
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const isImage = file.type.startsWith('image/');
        const endpoint = isImage ? '/api/upload-image' : '/api/upload-file';
        const res = await api.post(endpoint, formData);
        const fileUrl = res.data.url;
        const ext = file.name.split('.').pop()?.toLowerCase() || '';
        const imageExts = ['png','jpg','jpeg','gif','webp','svg','bmp','ico'];
        if (isImage || imageExts.includes(ext)) {
          if (!showSource && editorRef.current) {
            editorRef.current.focus();
            document.execCommand('insertImage', false, fileUrl);
            syncFromEditor();
          } else {
            insert(`![](${fileUrl})\n`);
          }
        } else {
          if (!showSource && editorRef.current) {
            editorRef.current.focus();
            document.execCommand('insertHTML', false, `<a href="${fileUrl}" target="_blank">📎 ${file.name}</a>`);
            syncFromEditor();
          } else {
            insert(`[📎 ${file.name}](${fileUrl})`);
          }
        }
      } catch (_err) {
        alert('Failed to upload file');
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  const handleHeading = (e) => {
    const selected = e.target.value;
    if (!selected) return;
    e.target.value = '';
    if (showSource) {
      insertLinePrefix(selected);
      return;
    }
    const tagMap = { '# ': 'h1', '## ': 'h2', '### ': 'h3' };
    const tag = tagMap[selected] || 'h3';
    execWysiwyg('formatBlock', tag);
  };

  const handleFontChange = (e) => {
    const font = e.target.value;
    if (!font) return;
    e.target.value = '';
    if (showSource) {
      insert(`<span style="font-family:${font};">`, `</span>`);
      return;
    }
    if (editorRef.current) {
      editorRef.current.focus();
      // styleWithCSS ensures execCommand('fontName') produces <span style="font-family:...">
      document.execCommand('styleWithCSS', false, true);
      document.execCommand('fontName', false, font);
      syncFromEditor();
    }
  };

  const handleSizeChange = (size) => {
    if (!size) return;
    if (showSource) {
      insert(`<span style="font-size:${size}px;">`, `</span>`);
      return;
    }
    if (editorRef.current) {
      editorRef.current.focus();
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        const range = sel.getRangeAt(0);
        const span = document.createElement('span');
        span.style.fontSize = `${size}px`;
        try {
          // Works for single-text-node selections
          range.surroundContents(span);
        } catch(_e) {
          // Fallback for multi-element selections — extract, wrap, reinsert
          const fragment = range.extractContents();
          span.appendChild(fragment);
          range.insertNode(span);
          range.setStartAfter(span);
          range.collapse(true);
          sel.removeAllRanges();
          sel.addRange(range);
        }
      }
      syncFromEditor();
    }
  };

  const handleLineHeightChange = (lh) => {
    setLineHeight(lh);
    lineHeightRef.current = lh;
    // Sync to parent immediately so line-height is saved with the content
    setTimeout(syncFromEditor, 0);
  };

  const handleTableLineHeightChange = (tlh) => {
    setTableLineHeight(tlh);
    tableLineHeightRef.current = tlh;
    setTimeout(syncFromEditor, 0);
  };

  // Apply lineHeight to editor div whenever it changes
  useEffect(() => {
    lineHeightRef.current = lineHeight;
    if (editorRef.current) {
      editorRef.current.style.lineHeight = lineHeight;
    }
  }, [lineHeight]);

  // Apply tableLineHeight to tables inside editor
  useEffect(() => {
    tableLineHeightRef.current = tableLineHeight;
    if (editorRef.current) {
      editorRef.current.querySelectorAll('table').forEach(tbl => {
        tbl.style.lineHeight = tableLineHeight;
      });
      editorRef.current.querySelectorAll('td, th').forEach(cell => {
        cell.style.lineHeight = tableLineHeight;
      });
    }
  }, [tableLineHeight]);

  const applyTextColor = (color) => {
    setShowTextColors(false);
    if (showSource) {
      insert(`<span style="color:${color};">`, `</span>`);
      return;
    }
    execWysiwyg('foreColor', color, true);
  };

  const applyBgColor = (color) => {
    setShowBgColors(false);
    if (showSource) {
      insert(`<span style="background-color:${color};">`, `</span>`);
      return;
    }
    execWysiwyg('hiliteColor', color, true);
  };

  // ── Table editing helpers ──────────────────────────────────────────

  const getCellFromEvent = useCallback((e) => {
    const td = e.target.closest('td, th');
    if (!td) return null;
    const tr = td.closest('tr');
    const table = td.closest('table');
    if (!tr || !table) return null;
    return { td, tr, table, colIndex: Array.from(tr.cells).indexOf(td), rowIndex: Array.from(table.rows).indexOf(tr) };
  }, []);

  const handleEditorContextMenu = useCallback((e) => {
    if (showSource) return;
    const cell = getCellFromEvent(e);
    if (!cell) { setTableMenu(null); tableMenuDataRef.current = null; return; }
    e.preventDefault();
    const data = { x: e.clientX, y: e.clientY, ...cell };
    setTableMenu(data);
    tableMenuDataRef.current = data;
  }, [showSource, getCellFromEvent]);

  const insertTableRow = useCallback((table, rowIndex, above) => {
    if (!table || rowIndex < 0) return;
    const cols = table.rows[0]?.cells.length || 3;
    const newRow = table.insertRow(above ? rowIndex : rowIndex + 1);
    for (let c = 0; c < cols; c++) {
      const cell = newRow.insertCell();
      cell.innerHTML = '&nbsp;';
      cell.style.cssText = 'border:1px solid #475569;padding:1px 6px;text-align:left;color:#cbd5e1;font-size:10px;';
    }
    syncFromEditor();
  }, [syncFromEditor]);

  const deleteTableRow = useCallback((table, rowIndex) => {
    if (!table || table.rows.length <= 1) return;
    table.deleteRow(rowIndex);
    syncFromEditor();
  }, [syncFromEditor]);

  const insertTableCol = useCallback((table, colIndex, before) => {
    if (!table) return;
    for (let r = 0; r < table.rows.length; r++) {
      const row = table.rows[r];
      const cellIdx = before ? colIndex : colIndex + 1;
      const cell = row.insertCell(cellIdx);
      cell.innerHTML = '&nbsp;';
      const isHeader = row.cells[cellIdx - 1]?.tagName === 'TH' || row.cells[0]?.tagName === 'TH' && cellIdx === 0;
      cell.style.cssText = isHeader
        ? 'border:1px solid #475569;padding:2px 6px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:10px;'
        : 'border:1px solid #475569;padding:1px 6px;text-align:left;color:#cbd5e1;font-size:10px;';
    }
    syncFromEditor();
  }, [syncFromEditor]);

  const deleteTableCol = useCallback((table, colIndex) => {
    if (!table || (table.rows[0] && table.rows[0].cells.length <= 1)) return;
    for (let r = table.rows.length - 1; r >= 0; r--) {
      if (table.rows[r].cells[colIndex]) table.rows[r].deleteCell(colIndex);
    }
    syncFromEditor();
  }, [syncFromEditor]);

  const deleteTable = useCallback((table) => {
    if (!table) return;
    const br = table.nextElementSibling;
    table.remove();
    if (br && br.tagName === 'BR') br.remove();
    syncFromEditor();
  }, [syncFromEditor]);

  const moveTableRow = useCallback((table, rowIndex, direction) => {
    if (!table) return;
    const targetIdx = rowIndex + direction;
    if (targetIdx < 0 || targetIdx >= table.rows.length) return;
    const row = table.rows[rowIndex];
    const targetRow = table.rows[targetIdx];
    // Use parentNode — browsers auto-wrap <tr> in <tbody>, so table.insertBefore fails
    const parent = row.parentNode;
    if (direction === -1) {
      parent.insertBefore(row, targetRow);
    } else {
      parent.insertBefore(row, targetRow.nextSibling);
    }
    syncFromEditor();
  }, [syncFromEditor]);

  const moveTableCol = useCallback((table, colIndex, direction) => {
    if (!table) return;
    const targetIdx = colIndex + direction;
    if (targetIdx < 0 || targetIdx >= (table.rows[0]?.cells.length || 0)) return;
    for (let r = 0; r < table.rows.length; r++) {
      const cells = Array.from(table.rows[r].cells);
      const cell = cells[colIndex];
      const targetCell = cells[targetIdx];
      if (!cell || !targetCell) continue;
      if (direction === -1) {
        table.rows[r].insertBefore(cell, targetCell);
      } else {
        table.rows[r].insertBefore(cell, targetCell.nextSibling);
      }
    }
    syncFromEditor();
  }, [syncFromEditor]);

  // ── Column resize via drag ─────────────────────────────────────────

  const handleColResizeStart = useCallback((e, table, colIndex) => {
    e.preventDefault();
    e.stopPropagation();
    const cells = Array.from(table.rows[0]?.cells || []);
    const widths = cells.map(c => c.getBoundingClientRect().width);
    resizeRef.current = { type: 'col', table, index: colIndex, startX: e.clientX, startWidths: widths };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const handleMove = (ev) => {
      const r = resizeRef.current;
      if (!r || r.type !== 'col') return;
      const delta = ev.clientX - r.startX;
      const newW = Math.max(30, r.startWidths[r.index] + delta);
      const ratio = newW / r.startWidths[r.index];
      // Update all cells in this column across all rows
      for (let ri = 0; ri < r.table.rows.length; ri++) {
        const cell = r.table.rows[ri].cells[r.index];
        if (cell) cell.style.width = newW + 'px';
      }
    };

    const handleUp = () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      resizeRef.current = null;
      syncFromEditor();
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }, [syncFromEditor]);

  const handleRowResizeStart = useCallback((e, table, rowIndex) => {
    e.preventDefault();
    e.stopPropagation();
    const startH = table.rows[rowIndex]?.getBoundingClientRect().height || 30;
    resizeRef.current = { type: 'row', table, index: rowIndex, startY: e.clientY, startHeight: startH };
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';

    const handleMove = (ev) => {
      const r = resizeRef.current;
      if (!r || r.type !== 'row') return;
      const delta = ev.clientY - r.startY;
      const newH = Math.max(20, r.startHeight + delta);
      const row = r.table.rows[r.index];
      if (row) {
        for (let ci = 0; ci < row.cells.length; ci++) {
          row.cells[ci].style.height = newH + 'px';
        }
      }
    };

    const handleUp = () => {
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      resizeRef.current = null;
      syncFromEditor();
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleUp);
  }, [syncFromEditor]);

  const handleInsertTable = () => {
    const cols = parseInt(window.prompt('Columns:', '3'));
    const rows = parseInt(window.prompt('Rows:', '3'));
    if (!cols || !rows || cols < 1 || rows < 1) return;
    if (isNaN(cols) || isNaN(rows)) return;
    if (showSource) {
      // Generate markdown table
      let table = '';
      for (let r = 0; r < rows; r++) {
        table += '| ';
        for (let c = 0; c < cols; c++) {
          table += ` ${r === 0 ? `Header ${c + 1}` : r === 1 ? '---' : ''} |`;
        }
        table += '\n';
        if (r === 0) {
          table += '|';
          for (let c = 0; c < cols; c++) table += ' --- |';
          table += '\n';
        }
      }
      insert(table);
      return;
    }
    if (editorRef.current) {
      editorRef.current.focus();
      let tableHtml = `<table style="width:100%;border-collapse:collapse;margin-bottom:1em;font-family:sans-serif;font-size:13px;">`;
      for (let r = 0; r < rows; r++) {
        tableHtml += '<tr>';
        for (let c = 0; c < cols; c++) {
          const tag = r === 0 ? 'th' : 'td';
          const style = r === 0
            ? 'border:1px solid #475569;padding:2px 6px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:10px;'
            : 'border:1px solid #475569;padding:1px 6px;text-align:left;color:#cbd5e1;font-size:10px;';
          tableHtml += `<${tag} style="${style}">${r === 0 ? `Header ${c + 1}` : ''}</${tag}>`;
        }
        tableHtml += '</tr>';
      }
      tableHtml += '</table><br>';
      document.execCommand('insertHTML', false, tableHtml);
      syncFromEditor();
    }
  };

  // ── Toggle source/WYSIWYG ──────────────────────────────────────────

  const toggleSource = () => {
    if (!showSource) {
      // Switching to Source: convert HTML → raw
      let currentHtml = editorRef.current?.innerHTML || '';
      const lh = lineHeightRef.current;
      const tlh = tableLineHeightRef.current;
      const hasLh = lh && lh !== '1.4';
      const hasTlh = tlh && tlh !== '1.2';
      if (hasLh || hasTlh) {
        const attrs = [];
        if (hasLh) attrs.push(`data-lh="${lh}"`);
        if (hasTlh) attrs.push(`data-lh-table="${tlh}"`);
        currentHtml = `<div ${attrs.join(' ')}>${currentHtml}</div>`;
      }
      const raw = toRaw(currentHtml);
      onChange({ target: { value: raw } });
    } else {
      // Switching to WYSIWYG: convert raw → HTML and force DOM update
      const raw = textareaRef.current?.value || value;
      const html = toHtml(raw);
      editorSyncedRef.current = ''; // Force DOM update
      if (editorRef.current) editorRef.current.innerHTML = html;
      editorSyncedRef.current = html; // Mark as synced
    }
    setShowSource(!showSource);
    setShowTextColors(false);
    setShowBgColors(false);
  };

  // ── Keyboard shortcuts for WYSIWYG ─────────────────────────────────

  const handleEditorKeyDown = (e) => {
    if (e.ctrlKey || e.metaKey) {
      if (e.key === 'b') { document.execCommand('bold'); e.preventDefault(); }
      if (e.key === 'i') { document.execCommand('italic'); e.preventDefault(); }
      if (e.key === 'u') { document.execCommand('underline'); e.preventDefault(); }
    }
    // Delayed sync after any keyboard action
    setTimeout(syncFromEditor, 0);
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="flex flex-col flex-1 min-w-0 relative">
      {/* Toolbar */}
      <div className="flex items-center gap-0.5 px-2 py-1.5 bg-black/30 border border-b-0 border-white/5 rounded-t-xl flex-wrap relative">
        <ToolButton icon={Bold} title="Bold (Ctrl+B)" onClick={handleBold} />
        <ToolButton icon={Italic} title="Italic (Ctrl+I)" onClick={handleItalic} />
        <ToolButton icon={Underline} title="Underline (Ctrl+U)" onClick={handleUnderline} />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <ToolButton icon={List} title="Bullet List" onClick={handleBulletList} />
        <ToolButton icon={ListOrdered} title="Numbered List" onClick={handleOrderedList} />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <ToolButton icon={Link} title="Insert Link" onClick={handleLink} />
        <ToolButton icon={Image} title="Insert Image" onClick={handleImageUpload} />
        <ToolButton icon={Table} title="Insert Table" onClick={handleInsertTable} />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <select
          onChange={handleHeading}
          defaultValue=""
          className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
        >
          <option value="" disabled>Heading</option>
          {HEADINGS.map(h => (
            <option key={h.prefix} value={h.prefix}>{h.label}</option>
          ))}
        </select>
        <div className="w-px h-4 bg-white/10 mx-1" />
        <div className="relative">
          <button
            type="button"
            title="Text Color"
            ref={textColorBtnRef}
            onMouseDown={e => { e.preventDefault(); setShowTextColors(!showTextColors); setShowBgColors(false); }}
            className={`p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all relative ${showTextColors ? 'bg-blue-500/20 text-blue-400' : ''}`}
          >
            <Palette className="w-3.5 h-3.5" />
          </button>
          {showTextColors && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl p-2 shadow-2xl w-[248px]" onMouseDown={e => e.preventDefault()}>
              <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 px-0.5">Text Color</div>
              <div className="grid grid-cols-8 gap-1">
                {COLORS.map(c => (
                  <button
                    key={c}
                    type="button"
                    title={c}
                    onMouseDown={() => applyTextColor(c)}
                    className="w-6 h-6 rounded-md border border-white/10 hover:scale-110 transition-transform cursor-pointer"
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="relative">
          <button
            type="button"
            title="Background / Highlight Color"
            ref={bgColorBtnRef}
            onMouseDown={e => { e.preventDefault(); setShowBgColors(!showBgColors); setShowTextColors(false); }}
            className={`p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all relative ${showBgColors ? 'bg-blue-500/20 text-blue-400' : ''}`}
            style={{ background: 'linear-gradient(135deg, transparent 50%, #ffd70020 50%)' }}
          >
            <span className="text-[11px] font-bold leading-none" style={{ textShadow: '0 0 2px rgba(255,215,0,0.5)' }}>H</span>
          </button>
          {showBgColors && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl p-2 shadow-2xl w-[248px]" onMouseDown={e => e.preventDefault()}>
              <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 px-0.5">Highlight Color</div>
              <div className="grid grid-cols-8 gap-1">
                {COLORS.map(c => (
                  <button
                    key={c}
                    type="button"
                    title={c}
                    onMouseDown={() => applyBgColor(c)}
                    className="w-6 h-6 rounded-md border border-white/10 hover:scale-110 transition-transform cursor-pointer"
                    style={{ backgroundColor: c }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
        <button
          type="button"
          title="Attach File"
          onMouseDown={e => { e.preventDefault(); handleFileUpload(); }}
          className={`p-1.5 rounded-md transition-all ${uploading ? 'text-blue-400 animate-pulse' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
        >
          <Paperclip className="w-3.5 h-3.5" />
        </button>
        <div className="w-px h-4 bg-white/10 mx-1" />
        <select
          onChange={handleFontChange}
          defaultValue=""
          className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
          style={{ fontFamily: 'inherit' }}
        >
          <option value="" disabled>Font</option>
          {FONTS.map(f => (
            <option key={f.value} value={f.value} style={{ fontFamily: f.value }}>{f.label}</option>
          ))}
        </select>
        <SizeDropdown options={fontSizeOptions} onSelect={handleSizeChange} />
        <LineHeightDropdown value={lineHeight} onSelect={handleLineHeightChange} />
        <LineHeightDropdown value={tableLineHeight} onSelect={handleTableLineHeightChange} label="Table" />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <button
          type="button"
          title={showSource ? 'Rich Text View' : 'Source View'}
          onMouseDown={e => { e.preventDefault(); toggleSource(); }}
          className={`p-1.5 rounded-md transition-all ${showSource ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
        >
          {showSource ? <Eye className="w-3.5 h-3.5" /> : <Code className="w-3.5 h-3.5" />}
        </button>
      </div>

      {/* Editor Area */}
      {showSource ? (
        <textarea
          ref={textareaRef}
          value={value}
          onChange={onChange}
          rows={rows}
          placeholder={placeholder}
          readOnly={readOnly}
          className={`w-full bg-black/40 border border-white/5 rounded-b-xl p-3 text-xs text-white focus:border-blue-500/50 outline-none resize-none font-mono ${className || ''}`}
          style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
        />
      ) : (
        <div
          ref={editorRef}
          contentEditable={!readOnly}
          suppressContentEditableWarning
          onInput={syncFromEditor}
          onKeyDown={handleEditorKeyDown}
          onBlur={handleEditorBlur}
          onContextMenu={handleEditorContextMenu}
          onMouseDown={(e) => {
            // Column resize: detect click near right border of td/th (within 5px)
            if (showSource || e.button !== 0) return;
            const td = e.target.closest('td, th');
            if (!td) return;
            const table = td.closest('table');
            const tr = td.closest('tr');
            if (!table || !tr) return;
            const rect = td.getBoundingClientRect();
            const distFromRight = rect.right - e.clientX;
            if (distFromRight <= 5 && distFromRight >= -2) {
              const colIndex = Array.from(tr.cells).indexOf(td);
              handleColResizeStart(e, table, colIndex);
            }
          }}
          className={`wysiwyg-editor w-full bg-black/40 border border-white/5 rounded-b-xl p-3 text-[13px] text-white outline-none resize-none overflow-y-auto min-h-[120px] focus:border-blue-500/50 [&:empty:before]:content-[attr(data-placeholder)] [&:empty:before]:text-slate-500 [&:empty:before]:italic ${className || ''}`}
          style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, lineHeight: lineHeight, ...(rows ? { minHeight: `${rows * 28}px` } : {}) }}
          data-placeholder={placeholder || 'Start writing...'}
        />
      )}

      {/* Table Context Menu */}
      {tableMenu && (
        <div
          ref={tableMenuRef}
          onMouseDown={e => e.preventDefault()}
          className="fixed z-[9999] bg-[#1a1d26] border border-white/10 rounded-xl shadow-2xl py-1 min-w-[180px]"
          style={{ left: tableMenu.x, top: tableMenu.y }}
        >
          {(() => {
            const d = tableMenuDataRef.current || tableMenu;
            const doAction = (fn) => () => { fn(); setTableMenu(null); tableMenuDataRef.current = null; };
            return (<>
              <CtxItem icon={ArrowUp} label="Move Row Up" onMouseDown={doAction(() => moveTableRow(d.table, d.rowIndex, -1))} />
              <CtxItem icon={ArrowDown} label="Move Row Down" onMouseDown={doAction(() => moveTableRow(d.table, d.rowIndex, 1))} />
              <div className="h-px bg-white/5 my-1" />
              <CtxItem icon={ArrowLeft} label="Move Col Left" onMouseDown={doAction(() => moveTableCol(d.table, d.colIndex, -1))} />
              <CtxItem icon={ArrowRight} label="Move Col Right" onMouseDown={doAction(() => moveTableCol(d.table, d.colIndex, 1))} />
              <div className="h-px bg-white/5 my-1" />
              <CtxItem icon={ArrowUp} label="Insert Row Above" onMouseDown={doAction(() => insertTableRow(d.table, d.rowIndex, true))} />
              <CtxItem icon={ArrowDown} label="Insert Row Below" onMouseDown={doAction(() => insertTableRow(d.table, d.rowIndex, false))} />
              <CtxItem icon={Trash2} label="Delete Row" danger onMouseDown={doAction(() => deleteTableRow(d.table, d.rowIndex))} />
              <div className="h-px bg-white/5 my-1" />
              <CtxItem icon={ArrowLeft} label="Insert Col Left" onMouseDown={doAction(() => insertTableCol(d.table, d.colIndex, true))} />
              <CtxItem icon={ArrowRight} label="Insert Col Right" onMouseDown={doAction(() => insertTableCol(d.table, d.colIndex, false))} />
              <CtxItem icon={Trash2} label="Delete Column" danger onMouseDown={doAction(() => deleteTableCol(d.table, d.colIndex))} />
              <div className="h-px bg-white/5 my-1" />
              <CtxItem icon={Trash2} label="Delete Table" danger onMouseDown={doAction(() => deleteTable(d.table))} />
            </>);
          })()}
        </div>
      )}
    </div>
  );
};

export default ToolbarTextarea;
