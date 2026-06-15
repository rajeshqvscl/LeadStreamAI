import React, { useRef } from 'react';
import { Bold, Italic, List, ListOrdered, Link, Heading, FileText } from 'lucide-react';

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

  const handleHeading = () => {
    const ta = textareaRef.current;
    if (!ta) return;
    const start = ta.selectionStart;
    const val = value;
    const lineStart = val.lastIndexOf('\n', start - 1) + 1;
    insertLinePrefix('### ');
  };

  const toolbarItems = [
    { icon: Bold, title: 'Bold (Ctrl+B)', onClick: () => insert('**', '**') },
    { icon: Italic, title: 'Italic (Ctrl+I)', onClick: () => insert('*', '*') },
    { type: 'separator' },
    { icon: List, title: 'Bullet List', onClick: () => insertLinePrefix('- ') },
    { icon: ListOrdered, title: 'Numbered List', onClick: () => insertLinePrefix('1. ') },
    { type: 'separator' },
    { icon: Link, title: 'Insert Link', onClick: handleLink },
    { icon: Heading, title: 'Heading', onClick: handleHeading },
  ];

  return (
    <div className="flex flex-col flex-1 min-w-0">
      <div className="flex items-center gap-0.5 px-2 py-1.5 bg-black/30 border border-b-0 border-white/5 rounded-t-xl">
        {toolbarItems.map((item, idx) =>
          item.type === 'separator' ? (
            <div key={idx} className="w-px h-4 bg-white/10 mx-1" />
          ) : (
            <ToolButton key={idx} icon={item.icon} title={item.title} onClick={item.onClick} />
          )
        )}
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
