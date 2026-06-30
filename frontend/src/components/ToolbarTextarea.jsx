import React, { useRef, useState } from 'react';
import { Bold, Italic, Underline, List, ListOrdered, Link, Image, Paperclip, Palette } from 'lucide-react';
import api from '../services/api';

const FONTS = [
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
  { label: 'Small', prefix: '### ' },
  { label: 'Medium', prefix: '## ' },
  { label: 'Big', prefix: '# ' },
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

const ToolButton = ({ icon: Icon, title, onClick }) => (
  <button
    type="button"
    title={title}
    onMouseDown={e => { e.preventDefault(); onClick(); }}
    className="p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all"
  >
    <Icon className="w-3.5 h-3.5" />
  </button>
);

const ToolbarTextarea = ({ value, onChange, rows, placeholder, className }) => {
  const textareaRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [showTextColors, setShowTextColors] = useState(false);
  const [showBgColors, setShowBgColors] = useState(false);
  const textColorBtnRef = useRef(null);
  const bgColorBtnRef = useRef(null);

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

  const handleFontChange = (e) => {
    const font = e.target.value;
    if (!font) return;
    insert(`<span style="font-family:${font};">`, `</span>`);
  };

  const handleSizeChange = (e) => {
    const size = e.target.value;
    if (!size) return;
    insert(`<span style="font-size:${size}px;">`, `</span>`);
  };

  const applyTextColor = (color) => {
    setShowTextColors(false);
    insert(`<span style="color:${color};">`, `</span>`);
  };

  const applyBgColor = (color) => {
    setShowBgColors(false);
    insert(`<span style="background-color:${color};">`, `</span>`);
  };

  const handleImageUpload = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/jpg,image/gif,image/webp,image/svg+xml';
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await api.post('/api/upload-image', formData);
        const imgUrl = res.data.url;
        insert(`![](${imgUrl})\n`);
      } catch (err) {
        alert('Failed to upload image');
      }
    };
    input.click();
  };

  const handleFileUpload = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.pdf,.doc,.docx,.xls,.xlsx';
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploading(true);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await api.post('/api/upload-file', formData);
        const fileUrl = res.data.url;
        insert(`[${file.name}](${fileUrl})`);
      } catch (err) {
        alert('Failed to upload file');
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  const handleLink = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    const selected = value.substring(ta.selectionStart, ta.selectionEnd);
    const url = window.prompt('Enter URL:', 'https://');
    if (!url) return;
    const display = selected || window.prompt('Enter link text:', 'link');
    if (!display) return;
    insert(`[${display}](${url})`);
  };

  const handleHeading = (e) => {
    const prefix = e.target.value;
    if (!prefix) return;
    e.target.value = '';
    insertLinePrefix(prefix);
  };

  return (
    <div className="flex flex-col flex-1 min-w-0">
      <div className="flex items-center gap-0.5 px-2 py-1.5 bg-black/30 border border-b-0 border-white/5 rounded-t-xl flex-wrap relative">
        <ToolButton icon={Bold} title="Bold (Ctrl+B)" onClick={() => insert('**', '**')} />
        <ToolButton icon={Italic} title="Italic (Ctrl+I)" onClick={() => insert('*', '*')} />
        <ToolButton icon={Underline} title="Underline (Ctrl+U)" onClick={() => insert('<u>', '</u>')} />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <ToolButton icon={List} title="Bullet List" onClick={() => insertLinePrefix('- ')} />
        <ToolButton icon={ListOrdered} title="Numbered List" onClick={() => insertLinePrefix('1. ')} />
        <div className="w-px h-4 bg-white/10 mx-1" />
        <ToolButton icon={Link} title="Insert Link" onClick={handleLink} />
        <ToolButton icon={Image} title="Insert Image" onClick={handleImageUpload} />
        <select
          onChange={handleHeading}
          defaultValue=""
          className="bg-black/50 border border-white/10 rounded-md px-1.5 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
        >
          <option value="" disabled>Heading</option>
          {HEADINGS.map(h => (
            <option key={h.label} value={h.prefix}>{h.label}</option>
          ))}
        </select>
        <div className="w-px h-4 bg-white/10 mx-1" />
        <button
          type="button"
          title="Text Color"
          ref={textColorBtnRef}
          onMouseDown={e => { e.preventDefault(); setShowTextColors(!showTextColors); setShowBgColors(false); }}
          className="p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all relative"
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
        <button
          type="button"
          title="Background / Highlight Color"
          ref={bgColorBtnRef}
          onMouseDown={e => { e.preventDefault(); setShowBgColors(!showBgColors); setShowTextColors(false); }}
          className="p-1.5 rounded-md hover:bg-white/10 text-slate-400 hover:text-white transition-all relative"
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
        <button
          type="button"
          title="Attach File (PDF, DOCX, XLSX)"
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
      </div>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={onChange}
        rows={rows}
        placeholder={placeholder}
        className={`w-full bg-black/40 border border-white/5 rounded-b-xl p-3 text-xs text-white font-mono focus:border-blue-500/50 outline-none resize-none ${className || ''}`}
        style={{ borderTopLeftRadius: 0, borderTopRightRadius: 0 }}
      />
    </div>
  );
};

export default ToolbarTextarea;
