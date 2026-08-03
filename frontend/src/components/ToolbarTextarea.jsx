import React, { useRef, useState, useEffect, useCallback } from 'react';
import { Bold, Italic, Underline, List, ListOrdered, Link, Image, Paperclip, Palette, Code, Table, Eye } from 'lucide-react';
import api from '../services/api';

// ─── Markdown ↔ HTML Conversion ────────────────────────────────────────
const mdToHtml = (md) => {
  if (!md) return '';
  if (/^<[a-z][^>]*>/i.test(md.trim()) && /<\/[a-z]+>\s*$/i.test(md.trim())) return md;
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
    const w = src.startsWith('data:image/') ? '400px' : '200px';
    return `<img src="${src}" alt="${alt}" style="width:${w};height:auto;">`;
  });
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
  html = html.replace(/^###\s+(.*?)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.*?)$/gm, '<h2>$1</h2>');
  html = html.replace(/^#\s+(.*?)$/gm, '<h1>$1</h1>');
  html = html.replace(/^[-*_]{3,}\s*$/gm, '<hr style="border: none; border-top: 2px solid #475569; margin: 16px 0;">');
  html = html.replace(/\n/g, '<br>');
  return html;
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
  md = md.replace(/&amp;/gi, '&').replace(/&lt;/gi, '<').replace(/&gt;/gi, '>').replace(/&nbsp;/gi, ' ');
  md = md.replace(/\n{3,}/g, '\n\n');
  return md.trim();
};

const isHtml = (str) => /<[a-z][\s\S]*>/i.test(str);

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

// ─── ToolbarTextarea ───────────────────────────────────────────────────

const ToolbarTextarea = ({ value, onChange, rows, placeholder, className, readOnly }) => {
  const textareaRef = useRef(null);
  const editorRef = useRef(null);
  const [showSource, setShowSource] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showTextColors, setShowTextColors] = useState(false);
  const [showBgColors, setShowBgColors] = useState(false);
  const textColorBtnRef = useRef(null);
  const bgColorBtnRef = useRef(null);
  const editorSyncedRef = useRef(''); // Tracks what's currently in the editor DOM

  // ── Conversion helpers ──────────────────────────────────────────────

  const toHtml = useCallback((raw) => {
    if (!raw) return '';
    return isHtml(raw) ? raw : mdToHtml(raw);
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
      const expectedHtml = toHtml(value);
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
    const newHtml = editorRef.current.innerHTML;
    // Mark as user-synced so the useEffect skips DOM update — cursor stays put!
    editorSyncedRef.current = newHtml;
    const raw = newHtml === '<br>' ? '' : newHtml;
    if (onChange) onChange({ target: { value: raw } });
  }, [onChange]);

  // ── WYSIWYG execCommand ────────────────────────────────────────────

  const execWysiwyg = useCallback((cmd, cmdValue = null) => {
    if (!editorRef.current || showSource) return;
    editorRef.current.focus();
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

  const handleSizeChange = (e) => {
    const size = e.target.value;
    if (!size) return;
    e.target.value = '';
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

  const applyTextColor = (color) => {
    setShowTextColors(false);
    if (showSource) {
      insert(`<span style="color:${color};">`, `</span>`);
      return;
    }
    execWysiwyg('foreColor', color);
  };

  const applyBgColor = (color) => {
    setShowBgColors(false);
    if (showSource) {
      insert(`<span style="background-color:${color};">`, `</span>`);
      return;
    }
    execWysiwyg('hiliteColor', color);
  };

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
      const currentHtml = editorRef.current?.innerHTML || '';
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
    <div className="flex flex-col flex-1 min-w-0">
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
        <select
          onChange={handleSizeChange}
          defaultValue=""
          className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
        >
          <option value="" disabled>Size</option>
          {FONT_SIZES.map(s => (
            <option key={s} value={s}>{s}px</option>
          ))}
        </select>
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
          onBlur={syncFromEditor}
          className={`w-full bg-black/40 border border-white/5 rounded-b-xl p-3 text-[13px] text-white outline-none resize-none overflow-y-auto leading-relaxed min-h-[120px] focus:border-blue-500/50 [&:empty:before]:content-[attr(data-placeholder)] [&:empty:before]:text-slate-500 [&:empty:before]:italic ${className || ''}`}
          style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0, ...(rows ? { minHeight: `${rows * 28}px` } : {}) }}
          data-placeholder={placeholder || 'Start writing...'}
        />
      )}
    </div>
  );
};

export default ToolbarTextarea;
