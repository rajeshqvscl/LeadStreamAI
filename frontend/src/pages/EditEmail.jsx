import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, Sparkles, Loader2, Save, Wand2, Type, Briefcase, BarChart3, Smile, CheckCircle2, AlertCircle, Send, Link as LinkIcon, FileText, List, RotateCcw, Bold, Italic, Heading, Image, Paperclip, Palette, Pen } from 'lucide-react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import api from '../services/api';
import SignatureEditor from '../components/SignatureEditor';

const mdToHtml = (md) => {
  if (!md) return '';
  // If already contains only HTML block-level tags, return as-is
  if (/^<[a-z][^>]*>/i.test(md.trim()) && /<\/[a-z]+>\s*$/i.test(md.trim())) return md;
  let html = md.replace(/•/g, '*');
  html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/_(.*?)_/g, '<em>$1</em>');
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  html = html.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:200px;height:auto;">');
  html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank">$1</a>');
  html = html.replace(/^###\s+(.*?)$/gm, '<h3>$1</h3>');
  html = html.replace(/^##\s+(.*?)$/gm, '<h2>$1</h2>');
  html = html.replace(/^#\s+(.*?)$/gm, '<h1>$1</h1>');
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
  // Preserve <span> with style attributes (color, font-family, font-size, background-color)
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

const EditEmail = () => {
  const { draftId } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [cc, setCc] = useState('');
  const [remarks, setRemarks] = useState('');
  const [aiInstruction, setAiInstruction] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [notification, setNotification] = useState(null);
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(null);
  const [history, setHistory] = useState([]);
  const [showTextColors, setShowTextColors] = useState(false);
  const [showBgColors, setShowBgColors] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [showSource, setShowSource] = useState(false);
  const bodyRef = React.useRef(null);
  const editorRef = React.useRef(null);
  const textColorBtnRef = React.useRef(null);
  const bgColorBtnRef = React.useRef(null);
  const [userSignature, setUserSignature] = useState('');
  const [showSigEditor, setShowSigEditor] = useState(false);
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 'admin';

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

  const execWysiwyg = (cmd, value = null) => {
    if (editorRef.current && !showSource) {
      editorRef.current.focus();
      document.execCommand(cmd, false, value);
      setBody(editorRef.current.innerHTML);
    }
  };

  const applyFormat = (tag, attr = '') => {
    if (editorRef.current && !showSource) {
      // WYSIWYG mode - use document.execCommand
      if (tag === 'b') execWysiwyg('bold');
      else if (tag === 'i') execWysiwyg('italic');
      else if (tag === 'list') execWysiwyg('insertUnorderedList');
      else if (tag === 'ordered') execWysiwyg('insertOrderedList');
      else if (tag === 'color') execWysiwyg('foreColor', attr);
      return;
    }

    // Source mode - textarea manipulation
    const el = bodyRef.current;
    if (!el) return;

    setHistory(prev => [...prev.slice(-29), body]);

    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = body.substring(start, end);
    
    let wrapped;
    if (tag === 'color') {
      wrapped = `<span style="color:${attr}">${selected || 'text'}</span>`;
    } else if (tag === 'b') {
      wrapped = `**${selected || 'bold'}**`;
    } else if (tag === 'i') {
      wrapped = `_${selected || 'italic'}_`;
    } else if (tag === 'list') {
      if (!selected) {
        wrapped = '* ';
      } else {
        const lines = selected.split('\n');
        wrapped = lines.map(l => {
          const trimmed = l.trim();
          if (trimmed.startsWith('*')) return l;
          return `* ${l}`;
        }).join('\n');
      }
    } else if (tag === 'ordered') {
      if (!selected) {
        wrapped = '1. ';
      } else {
        const lines = selected.split('\n');
        wrapped = lines.map((l, idx) => {
          const num = idx + 1;
          if (/^\d+\./.test(l.trim())) return l;
          return `${num}. ${l}`;
        }).join('\n');
      }
    }

    const newBody = body.substring(0, start) + wrapped + body.substring(end);
    setBody(newBody);
    setTimeout(() => {
      el.focus();
      const newPos = start + wrapped.length;
      el.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const handleUndo = () => {
    if (editorRef.current && !showSource) {
      document.execCommand('undo');
      setBody(editorRef.current.innerHTML);
      return;
    }
    if (history.length === 0) return;
    const prev = history[history.length - 1];
    setBody(prev);
    setHistory(prevHist => prevHist.slice(0, -1));
  };

  const wrapSelection = (before, after = '') => {
    const el = bodyRef.current;
    if (!el) return;
    setHistory(prev => [...prev.slice(-29), body]);
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = body.substring(start, end);
    const wrapped = before + (selected || 'text') + after;
    const newBody = body.substring(0, start) + wrapped + body.substring(end);
    setBody(newBody);
    setTimeout(() => {
      el.focus();
      const newPos = start + wrapped.length;
      el.setSelectionRange(newPos, newPos);
    }, 0);
  };

  const handleFontChange = (e) => {
    const font = e.target.value;
    if (!font) return;
    if (editorRef.current && !showSource) {
      editorRef.current.focus();
      document.execCommand('fontName', false, font);
      setBody(editorRef.current.innerHTML);
      return;
    }
    wrapSelection(`<span style="font-family:${font};">`, `</span>`);
  };

  const handleSizeChange = (e) => {
    const size = e.target.value;
    if (!size) return;
    if (editorRef.current && !showSource) {
      editorRef.current.focus();
      document.execCommand('fontSize', false, '7');
      // execCommand fontSize uses 1-7, so use span for precise size
      const selection = window.getSelection();
      if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const span = document.createElement('span');
        span.style.fontSize = `${size}px`;
        range.surroundContents(span);
      }
      setBody(editorRef.current.innerHTML);
      return;
    }
    wrapSelection(`<span style="font-size:${size}px;">`, `</span>`);
  };

  const applyTextColor = (color) => {
    setShowTextColors(false);
    applyFormat('color', color);
  };

  const applyBgColor = (color) => {
    setShowBgColors(false);
    if (editorRef.current && !showSource) {
      editorRef.current.focus();
      document.execCommand('hiliteColor', false, color);
      setBody(editorRef.current.innerHTML);
      return;
    }
    const el = bodyRef.current;
    if (!el) return;
    setHistory(prev => [...prev.slice(-29), body]);
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const selected = body.substring(start, end);
    const wrapped = `<span style="background-color:${color}">${selected || 'text'}</span>`;
    const newBody = body.substring(0, start) + wrapped + body.substring(end);
    setBody(newBody);
    setTimeout(() => {
      el.focus();
      const newPos = start + wrapped.length;
      el.setSelectionRange(newPos, newPos);
    }, 0);
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
        if (editorRef.current && !showSource) {
          editorRef.current.focus();
          document.execCommand('insertImage', false, imgUrl);
          setBody(editorRef.current.innerHTML);
        } else {
          wrapSelection(`![](${imgUrl})\n`, '');
        }
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
        if (editorRef.current && !showSource) {
          editorRef.current.focus();
          const linkHtml = `<a href="${fileUrl}" target="_blank">${file.name}</a>`;
          document.execCommand('insertHTML', false, linkHtml);
          setBody(editorRef.current.innerHTML);
        } else {
          wrapSelection(`[${file.name}](${fileUrl})`, '');
        }
      } catch (err) {
        alert('Failed to upload file');
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  const handleLink = () => {
    if (editorRef.current && !showSource) {
      const url = window.prompt('Enter URL:', 'https://');
      if (!url) return;
      editorRef.current.focus();
      const selected = window.getSelection().toString();
      if (selected) {
        document.execCommand('createLink', false, url);
      } else {
        const display = window.prompt('Enter link text:', 'link');
        if (!display) return;
        document.execCommand('insertHTML', false, `<a href="${url}">${display}</a>`);
      }
      setBody(editorRef.current.innerHTML);
      return;
    }
    const el = bodyRef.current;
    if (!el) return;
    const selected = body.substring(el.selectionStart, el.selectionEnd);
    const url = window.prompt('Enter URL:', 'https://');
    if (!url) return;
    const display = selected || window.prompt('Enter link text:', 'link');
    if (!display) return;
    wrapSelection(`[${display}](${url})`, '');
  };

  const handleHeading = (e) => {
    const prefix = e.target.value;
    if (!prefix) return;
    e.target.value = '';
    if (editorRef.current && !showSource) {
      editorRef.current.focus();
      const tag = prefix.trim() === '#' ? 'h1' : prefix.trim() === '##' ? 'h2' : 'h3';
      document.execCommand('formatBlock', false, tag);
      setBody(editorRef.current.innerHTML);
      return;
    }
    const el = bodyRef.current;
    if (!el) return;
    setHistory(prev => [...prev.slice(-29), body]);
    const start = el.selectionStart;
    const val = body;
    const lineStart = val.lastIndexOf('\n', start - 1) + 1;
    const lineEnd = val.indexOf('\n', start);
    const line = val.substring(lineStart, lineEnd === -1 ? val.length : lineEnd);
    const newLine = prefix + line;
    const newBody = val.substring(0, lineStart) + newLine + val.substring(lineEnd === -1 ? val.length : lineEnd);
    setBody(newBody);
    setTimeout(() => {
      el.focus();
      el.setSelectionRange(lineStart + prefix.length, lineStart + prefix.length);
    }, 0);
  };

  const handleInsertSignature = () => {
    if (!userSignature) {
      alert('No custom signature set. Go to Templates to create one.');
      return;
    }
    setHistory(prev => [...prev.slice(-29), body]);
    // Render signature as HTML for WYSIWYG mode
    const sigHtml = mdToHtml(userSignature);
    const sigBlock = `<br><br>--<br>${sigHtml}`;
    if (isHtml(body)) {
      // Strip any existing signature block (everything from last -- separator onwards)
      const lastDash = body.lastIndexOf('--');
      if (lastDash !== -1) {
        const beforeSig = body.substring(0, body.lastIndexOf('<br>', lastDash));
        setBody((beforeSig || '') + sigBlock);
      } else {
        setBody(body + sigBlock);
      }
    } else {
      const sigMdBlock = `\n\n--\n${userSignature}`;
      const idx = body.lastIndexOf('\n--');
      if (idx !== -1) {
        setBody(body.substring(0, idx) + '\n--\n' + userSignature + body.substring(idx + 3));
      } else {
        setBody(body + sigMdBlock);
      }
    }
  };

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const renderEmailPreview = (text) => {
    if (!text) return 'Generate AI draft to begin...';

    // Resolve [[BACKEND_URL]] so images show in preview
    const backendUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    text = text.replace(/\[\[BACKEND_URL\]\]/g, backendUrl);

    // If text is already HTML, wrap it in styled container and return
    if (/<[a-z][\s\S]*>/i.test(text) && !text.includes('**') && !text.includes('\n--')) {
      return `<div style="color: #cbd5e1; font-size: 13px; line-height: 1.6;">${text}</div>`;
    }

    // Handle markdown images before other markdown processing

    // 1. Handle Signature Block — split at SIG_START and SIG_END
    const sigStartIdx = text.indexOf('SIG_START');
    const sigEndIdx = text.indexOf('SIG_END');
    let sigHtml = '';
    let mainText = text;
    let afterSig = '';
    if (sigStartIdx !== -1) {
      mainText = text.substring(0, sigStartIdx);
      if (sigEndIdx !== -1) {
        // Content between SIG_START and SIG_END = signature
        const sigContent = text.substring(sigStartIdx + 9, sigEndIdx).trim();
        // Content after SIG_END = footer (unsubscribe, confidential)
        afterSig = text.substring(sigEndIdx + 8).trim();
        
        const sigLines = sigContent.split('\n').filter(l => l.trim());
        sigHtml = '<div style="margin-top:10px; border-top:1px solid #ffffff15; padding-top:8px; font-family: sans-serif;">';
        sigLines.forEach(line => {
          const trimmed = line.trim();
          if (trimmed === '--') {
            sigHtml += '<div style="color:#475569; margin-bottom:4px;">--</div>';
          } else if (trimmed.startsWith('SIG_LINK_LABEL:')) {
            const rest = trimmed.replace('SIG_LINK_LABEL:', '');
            const colonIdx = rest.indexOf(':');
            const label = colonIdx !== -1 ? rest.substring(0, colonIdx).trim() : 'LinkedIn';
            const url = colonIdx !== -1 ? rest.substring(colonIdx + 1).trim() : rest;
            sigHtml += `<a href="${url}" target="_blank" style="color:#3b82f6; font-weight:700; text-decoration:underline; display:block; margin-top:2px;">${label}</a>`;
          } else if (trimmed.startsWith('SIG_LINK:')) {
            const url = trimmed.replace('SIG_LINK:', '').trim();
            sigHtml += `<a href="${url}" target="_blank" style="color:#3b82f6; font-weight:700; text-decoration:underline; display:block; margin-top:2px;">LinkedIn</a>`;
          } else if (trimmed.startsWith('<img') || trimmed.startsWith('<div')) {
            sigHtml += trimmed;
          } else if (trimmed) {
            // Apply inline markdown to signature lines too
            let lineHtml = trimmed
              .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
              .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              .replace(/_(.*?)_/g, '<em>$1</em>')
              .replace(/\*(.*?)\*/g, '<em>$1</em>')
              .replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:120px;height:auto;display:block;margin-top:8px;" />')
              .replace(/\[(.*?)\]\((.*?)\)/g, `<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>`);

            sigHtml += `<div style="color:#94a3b8; font-size:12px; line-height:1.4; margin-bottom:0px;">${lineHtml}</div>`;
          }
        });
        sigHtml += '</div>';
      } else {
        // No SIG_END — treat everything after SIG_START as sig (backward compat)
        const sigContent = text.substring(sigStartIdx + 9).trim();
        const sigLines = sigContent.split('\n').filter(l => l.trim());
        sigHtml = '<div style="margin-top:10px; border-top:1px solid #ffffff15; padding-top:8px; font-family: sans-serif;">';
        sigLines.forEach(line => {
          const trimmed = line.trim();
          if (trimmed === '--') {
            sigHtml += '<div style="color:#475569; margin-bottom:4px;">--</div>';
          } else if (trimmed.startsWith('SIG_LINK_LABEL:')) {
            const rest = trimmed.replace('SIG_LINK_LABEL:', '');
            const colonIdx = rest.indexOf(':');
            const label = colonIdx !== -1 ? rest.substring(0, colonIdx).trim() : 'LinkedIn';
            const url = colonIdx !== -1 ? rest.substring(colonIdx + 1).trim() : rest;
            sigHtml += `<a href="${url}" target="_blank" style="color:#3b82f6; font-weight:700; text-decoration:underline; display:block; margin-top:2px;">${label}</a>`;
          } else if (trimmed.startsWith('SIG_LINK:')) {
            const url = trimmed.replace('SIG_LINK:', '').trim();
            sigHtml += `<a href="${url}" target="_blank" style="color:#3b82f6; font-weight:700; text-decoration:underline; display:block; margin-top:2px;">LinkedIn</a>`;
          } else if (trimmed.startsWith('<img') || trimmed.startsWith('<div')) {
            sigHtml += trimmed;
          } else if (trimmed) {
            let lineHtml = trimmed
              .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
              .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
              .replace(/_(.*?)_/g, '<em>$1</em>')
              .replace(/\*(.*?)\*/g, '<em>$1</em>')
              .replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:120px;height:auto;display:block;margin-top:8px;" />')
              .replace(/\[(.*?)\]\((.*?)\)/g, `<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>`);

            sigHtml += `<div style="color:#94a3b8; font-size:12px; line-height:1.4; margin-bottom:0px;">${lineHtml}</div>`;
          }
        });
        sigHtml += '</div>';
      }
    }

    // Normalize bullet characters
    mainText = mainText.replace(/•/g, '*');
    // 2. Split main text into paragraphs
    const paragraphs = mainText.split('\n\n');
    let htmlParts = [];
    paragraphs.forEach(p => {
      const trimmed = p.trim();
      if (!trimmed) return;

      const lines = trimmed.split('\n');
      
      const isUnordered = lines.some(l => /^\s*[\*\-•]\s+/.test(l));
      const isOrdered = lines.some(l => /^\s*\d+\.\s+/.test(l));

      if (isUnordered) {
        let listHtml = '<ul style="margin: 0.8em 0; padding-left: 0; list-style: none;">';
        lines.forEach(l => {
          const match = l.trim().match(/^[\*\-•]\s+(.*)/);
          if (match) {
            listHtml += `<li style="margin-bottom: 0.4em; position: relative; padding-left: 14px; line-height: 1.6; color: #cbd5e1;"><span style="position: absolute; left: 0; color: #94a3b8; font-size: 9px; top: 0px; display: inline-block; vertical-align: middle;">•</span>${match[1].trim()}</li>`;
          } else if (l.trim()) {
            listHtml += ` ${l.trim()}`;
          }
        });
        listHtml += '</ul>';
        htmlParts.push(listHtml);
      } else if (isOrdered) {
        let listHtml = '<ol style="margin: 1em 0; padding-left: 1.5em; list-style-type: decimal;">';
        lines.forEach(l => {
          const match = l.trim().match(/^\d+\.\s+(.*)/);
          if (match) {
            listHtml += `<li style="margin-bottom: 0.5em; color: #cbd5e1;">${match[1].trim()}</li>`;
          } else if (l.trim()) {
            listHtml += ` ${l.trim()}`;
          }
        });
        listHtml += '</ol>';
        htmlParts.push(listHtml);
      } else if (lines.length >= 2 && lines.every(l => !l.trim() || (l.trim().startsWith('|') && l.trim().endsWith('|')))) {
        let tableHtml = '<table style="width:100%;border-collapse:collapse;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;">';
        const dataLines = lines.filter(l => l.trim() && !l.trim().match(/^\|[-:\s]+\|$/));
        dataLines.forEach((line, i) => {
          const cells = line.trim().split('|').slice(1, -1).map(c => c.trim());
          const tag = i === 0 ? 'th' : 'td';
          const cellStyle = tag === 'th'
            ? 'border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;'
            : 'border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;';
          const cellHtml = cells.map(c => `<${tag} style="${cellStyle}">${c}</${tag}>`).join('');
          tableHtml += `<tr>${cellHtml}</tr>`;
        });
        tableHtml += '</table>';
        htmlParts.push(tableHtml);
      } else {
        // Paragraph: preserve single newlines as line breaks
        let content = trimmed.replace(/\n/g, '<br />');
        content = content
          .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/_(.*?)_/g, '<em>$1</em>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>');
        htmlParts.push(`<p style="margin-bottom: 1em; color: #cbd5e1;">${content}</p>`);
      }
    });

    // Render afterSig (content after SIG_END — unsubscribe, confidential) as regular paragraphs
    let afterHtml = '';
    if (afterSig) {
      const afterParagraphs = afterSig.split('\n\n').filter(p => p.trim());
      afterHtml = afterParagraphs.map(p => {
        let content = p.replace(/\n/g, '<br />');
        content = content
          .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/_(.*?)_/g, '<em>$1</em>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>');
        return `<p style="margin-top:1.2em; color:#94a3b8; font-size:12px;">${content}</p>`;
      }).join('');
    }

    let finalHtml = htmlParts.join('') + sigHtml + afterHtml;

    // 3. Inline Styles (Bold, Italic, Links, Fonts)
    finalHtml = finalHtml
      .replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
      .replace(/\*\*(.*?)\*\*/g, '<strong style="color: white; font-weight: 800;">$1</strong>')
      .replace(/_(.*?)_/g, '<em style="font-style:italic">$1</em>')
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 700;">$1</a>')
      .replace(/<span style="color:\s*(.*?)">(.*?)<\/span>/g, '<span style="color: $1;">$2</span>');
    // Ensure all HTML tables have visible borders
    finalHtml = finalHtml
      .replace(/<table(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border-collapse:collapse;width:100%;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;"');
        }
        return m.replace('<table', '<table style="border-collapse:collapse;width:100%;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;"');
      })
      .replace(/<th(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;"');
        }
        return m.replace('<th', '<th style="border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;"');
      })
      .replace(/<td(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;"');
        }
        return m.replace('<td', '<td style="border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;"');
      });
    return finalHtml;
  };

  const fetchDraft = async () => {
    setIsLoading(true);
    try {
      // In our current API, draftId is the leadId
      const response = await api.get(`/api/leads/${draftId}`);
      const lead = response.data;

      // Robust extraction of subject and body
      let draftContent = lead.email_draft || "";
      // Normalize literal escapes
      draftContent = draftContent.replace(/\\n/g, "\n").replace(/\\r\\n/g, "\n");

      let sub = "";
      let bd = draftContent;

      if (draftContent.includes("Subject:")) {
        const lines = draftContent.split('\n');
        sub = lines[0].replace(/Subject:\s*/, "").trim();
        bd = lines.slice(1).join('\n').trim();
        // If there was a double newline after subject, lines[1] might be empty, which is fine.
      }

      setDraft(lead);
      setSubject(sub);
      const sigUser = JSON.parse(localStorage.getItem('user') || '{}');
      setUserSignature(sigUser.signature || '');
      // Convert markdown body to HTML for WYSIWYG editor
      setBody(isHtml(bd) ? bd : mdToHtml(bd));
      const userStr = localStorage.getItem('user') || localStorage.getItem('user_admin');
      let isVismaya = false;
      if (userStr) {
        try {
          const user = JSON.parse(userStr);
          isVismaya = ((user.username || user.full_name || '').toLowerCase()).includes('vismaya');
        } catch (e) {}
      }
      setCc(lead.cc_email || (isVismaya ? 'rajesh.s@qvscl.com' : 'lalit.h@qvscl.com'));
      setRemarks(lead.remarks || '');
    } catch (err) {
      console.error('Failed to fetch draft', err);
      showNotification('error', 'Failed to load draft');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDraft();
  }, [draftId]);

  // Sync editor content when body changes from non-editor sources (AI refine, insert signature)
  useEffect(() => {
    if (editorRef.current && !showSource) {
      const cursor = window.getSelection();
      const wasFocused = editorRef.current.contains(cursor?.anchorNode);
      editorRef.current.innerHTML = body;
      if (wasFocused && cursor) {
        const range = document.createRange();
        range.selectNodeContents(editorRef.current);
        range.collapse(false);
        cursor.removeAllRanges();
        cursor.addRange(range);
      }
    }
  }, [body, showSource]);

  const [isSavingTask, setIsSavingTask] = useState(false);


  const handleSave = async (silent = false) => {
    const taskId = `save-${draftId}`;
    if (!silent) {
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Saving Draft', subtitle: 'Syncing with matrix...', progress: 40, status: 'RUNNING' } 
      }));
    }
    setIsSaving(true);
    try {
      const rawBody = isHtml(body) ? htmlToMd(body) : body;
      const email_draft = `Subject: ${subject}\n\n${rawBody}`;
      await api.patch(`/api/leads/${draftId}`, { email_draft, remarks, cc_email: cc });
      if (!silent) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Draft Saved', subtitle: 'Sync successful', progress: 100, status: 'COMPLETED' } 
        }));
      }
    } catch {
      if (!silent) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Save Failed', subtitle: 'Network error', progress: 0, status: 'FAILED' } 
        }));
      }
      showNotification('error', 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefine = async (instruction = null) => {
    const finalInstruction = instruction || aiInstruction;
    if (!finalInstruction) return;

    const taskId = `refine-${draftId}`;
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'AI Refinement', subtitle: 'Analyzing context...', progress: 30, status: 'RUNNING' } 
    }));
    
    // Convert HTML body to markdown for AI processing
    const bodyForAI = isHtml(body) ? htmlToMd(body) : body;
    setIsRefining(true);
    try {
      const response = await api.post(`/api/refine-email/${draftId}`, {
        instruction: finalInstruction,
        subject,
        body: bodyForAI
      });
      if (response.data.error) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Refinement Failed', subtitle: response.data.error, progress: 0, status: 'FAILED' } 
        }));
        showNotification('error', `AI refinement failed`);
        return;
      }

      if (response.data.subject || response.data.body) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Refinement Complete', subtitle: 'AI content applied', progress: 100, status: 'COMPLETED' } 
        }));
        setSubject(response.data.subject || '');
        const refinedBody = response.data.body || '';
        setBody(isHtml(refinedBody) ? refinedBody : mdToHtml(refinedBody));
        setAiInstruction('');
      }
    } catch {
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Refinement Failed', subtitle: 'AI Matrix Error', progress: 0, status: 'FAILED' } 
      }));
      showNotification('error', 'AI refinement failed');
    } finally {
      setIsRefining(false);
    }
  };

  const handleApproveAndSend = async () => {
    const taskId = `send-${draftId}`;
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'Dispatching Email', subtitle: 'Gmail API sync...', progress: 20, status: 'RUNNING' } 
    }));

    await handleSave(true);
    try {
      await api.post(`/api/approve-email/${draftId}`, { cc: cc });
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Email Sent', subtitle: 'Draft removed from queue', progress: 100, status: 'COMPLETED' } 
      }));
      navigate('/dashboard/emails');
    } catch {
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Dispatch Failed', subtitle: 'Gmail sync error', progress: 0, status: 'FAILED' } 
      }));
      showNotification('error', 'Approval failed');
    }
  };

  const handleSchedule = async () => {
    if (!scheduledAt) {
      showNotification('error', 'Please select a date and time');
      return;
    }
    const taskId = `schedule-${draftId}`;
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'Scheduling Outreach', subtitle: 'Queuing in matrix...', progress: 30, status: 'RUNNING' } 
    }));

    await handleSave(true);
    setIsSaving(true);
    try {
      const isoString = new Date(scheduledAt).toISOString();
      await api.post(`/api/schedule-email/${draftId}`, { scheduled_at: isoString });
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Email Scheduled', subtitle: `At: ${isoString.split('T')[0]}`, progress: 100, status: 'COMPLETED' } 
      }));
      navigate('/dashboard/emails');
    } catch {
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Schedule Failed', subtitle: 'Queue error', progress: 0, status: 'FAILED' } 
      }));
      showNotification('error', 'Scheduling failed');
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading || !draft) {
    return (
      <div className="py-20 flex flex-col items-center justify-center">
        <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading Editor...</p>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-500 min-h-screen bg-[#0a0f1a] pb-20 p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/dashboard/emails')} className="px-3 py-1.5 flex items-center gap-1.5 rounded-md bg-[#131722] border border-[#ffffff10] text-slate-300 hover:text-white transition-colors text-[11px] font-bold cursor-pointer">
          <ChevronLeft className="w-3.5 h-3.5" /> Back
        </button>
        <div>
          <h1 className="text-[20px] font-bold text-white tracking-tight">Edit Email Draft #{draftId}</h1>
          <p className="text-[#64748b] text-[12px] font-medium mt-0.5">
            To: {draft.first_name} {draft.last_name} ({draft.email})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        {/* Left: Editor Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
          <div className="px-6 py-4 border-b border-[#ffffff08] flex items-center gap-2 bg-[#0f121b]/50">
            <span className="text-amber-500 text-sm">✏️</span>
            <h3 className="text-white font-bold text-[13px] tracking-wide">Edit Draft</h3>
          </div>

          <div className="p-6 flex-1 flex flex-col gap-6">
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-slate-400">Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enter email subject..."
                className="w-full bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white font-medium outline-none focus:border-blue-500/50"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-medium text-slate-400">CC Recipient</label>
              <input
                type="text"
                value={cc}
                onChange={(e) => setCc(e.target.value)}
                placeholder="Copy person (e.g., manager@qvscl.com)"
                className="w-full bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white font-medium outline-none focus:border-blue-500/50"
              />
            </div>

            <div className="space-y-2 flex-1 flex flex-col">
              <div className="flex items-center justify-between">
                <label className="text-[11px] font-medium text-slate-400">Body</label>
                {/* Formatting Toolbar */}
                <div className="flex items-center gap-1.5 flex-wrap">
                  <button
                    type="button"
                    title="Undo Change"
                    onClick={handleUndo}
                    disabled={history.length === 0}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer disabled:opacity-30"
                  >
                    <RotateCcw className="w-3.5 h-3.5" />
                  </button>
                  <div className="w-px h-4 bg-white/10 mx-0.5" />

                  <button
                    type="button"
                    title="Bold"
                    onClick={() => applyFormat('b')}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-white font-black text-[13px] hover:bg-blue-500/20 hover:border-blue-500/40 transition-all cursor-pointer"
                  ><Bold className="w-3.5 h-3.5" /></button>
                  <button
                    type="button"
                    title="Italic"
                    onClick={() => applyFormat('i')}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-white italic font-bold text-[13px] hover:bg-purple-500/20 hover:border-purple-500/40 transition-all cursor-pointer"
                  ><Italic className="w-3.5 h-3.5" /></button>
                  <button
                    type="button"
                    title="Numbered List"
                    onClick={() => applyFormat('ordered')}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-white text-[11px] font-bold hover:bg-amber-500/20 hover:border-amber-500/40 transition-all cursor-pointer"
                  ><List className="w-3.5 h-3.5" /></button>
                  <button
                    type="button"
                    title="Bullet List"
                    onClick={() => applyFormat('list')}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-white hover:bg-emerald-500/20 hover:border-emerald-500/40 transition-all cursor-pointer"
                  >
                    <List className="w-3.5 h-3.5" />
                  </button>
                  <div className="w-px h-4 bg-white/10 mx-0.5" />
                  <button
                    type="button"
                    title="Insert Link"
                    onClick={handleLink}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
                  ><LinkIcon className="w-3.5 h-3.5" /></button>
                  <button
                    type="button"
                    title="Insert Image"
                    onClick={handleImageUpload}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
                  ><Image className="w-3.5 h-3.5" /></button>
                  <select
                    onChange={handleHeading}
                    defaultValue=""
                    className="bg-black/50 border border-white/10 rounded-md px-1 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
                  >
                    <option value="" disabled>Heading</option>
                    {HEADINGS.map(h => (
                      <option key={h.label} value={h.prefix}>{h.label}</option>
                    ))}
                  </select>
                  <div className="w-px h-4 bg-white/10 mx-0.5" />
                  <div className="relative">
                    <button
                      type="button"
                      title="Text Color"
                      ref={textColorBtnRef}
                      onClick={() => { setShowTextColors(!showTextColors); setShowBgColors(false); }}
                      className={`w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer ${showTextColors ? 'bg-blue-500/20 border-blue-500/40 text-blue-400' : ''}`}
                    ><Palette className="w-3.5 h-3.5" /></button>
                    {showTextColors && (
                      <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl p-2 shadow-2xl w-[248px]" onMouseDown={e => e.preventDefault()}>
                        <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 px-0.5">Text Color</div>
                        <div className="grid grid-cols-8 gap-1">
                          {COLORS.map(c => (
                            <button
                              key={c}
                              type="button"
                              title={c}
                              onClick={() => applyTextColor(c)}
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
                      onClick={() => { setShowBgColors(!showBgColors); setShowTextColors(false); }}
                      className={`w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer ${showBgColors ? 'bg-blue-500/20 border-blue-500/40 text-blue-400' : ''}`}
                      style={{ background: 'linear-gradient(135deg, transparent 50%, #ffd70020 50%)' }}
                    ><span className="text-[11px] font-bold leading-none" style={{ textShadow: '0 0 2px rgba(255,215,0,0.5)' }}>H</span></button>
                    {showBgColors && (
                      <div className="absolute top-full left-0 mt-1 z-50 bg-[#1a1d26] border border-white/10 rounded-xl p-2 shadow-2xl w-[248px]" onMouseDown={e => e.preventDefault()}>
                        <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest mb-1.5 px-0.5">Highlight Color</div>
                        <div className="grid grid-cols-8 gap-1">
                          {COLORS.map(c => (
                            <button
                              key={c}
                              type="button"
                              title={c}
                              onClick={() => applyBgColor(c)}
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
                    title="Attach File (PDF, DOCX, XLSX)"
                    onClick={handleFileUpload}
                    className={`w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 transition-all cursor-pointer ${uploading ? 'text-blue-400 animate-pulse' : 'text-slate-400 hover:text-white hover:bg-white/10'}`}
                  ><Paperclip className="w-3.5 h-3.5" /></button>
                  <div className="w-px h-4 bg-white/10 mx-0.5" />
                  <select
                    onChange={handleFontChange}
                    defaultValue=""
                    className="bg-black/50 border border-white/10 rounded-md px-1 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
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
                    className="bg-black/50 border border-white/10 rounded-md px-1 py-1 text-[10px] text-slate-300 cursor-pointer outline-none focus:border-blue-500/50 appearance-none"
                  >
                    <option value="" disabled>Size</option>
                    {FONT_SIZES.map(s => (
                      <option key={s} value={s}>{s}px</option>
                    ))}
                  </select>
                  <div className="w-px h-4 bg-white/10 mx-0.5" />
                  <button
                    type="button"
                    title="Edit Signature"
                    onClick={() => setShowSigEditor(true)}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
                  ><Pen className="w-3.5 h-3.5" /></button>
                  <button
                    type="button"
                    title="Insert Signature"
                    onClick={handleInsertSignature}
                    className="w-7 h-7 flex items-center justify-center rounded bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all cursor-pointer"
                  ><FileText className="w-3.5 h-3.5" /></button>
                  {showSigEditor && (
                    <SignatureEditor
                      userId={userId}
                      onClose={() => setShowSigEditor(false)}
                      onSave={() => {
                        const u = JSON.parse(localStorage.getItem('user') || '{}');
                        setUserSignature(u.signature || '');
                      }}
                    />
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 mb-2">
                <button
                  type="button"
                  onClick={() => setShowSource(!showSource)}
                  className={`text-[10px] font-bold uppercase tracking-widest px-2 py-1 rounded ${showSource ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 'text-slate-500 hover:text-slate-300'}`}
                >
                  {showSource ? 'Rich Text' : 'Source'}
                </button>
              </div>
              {showSource ? (
                <textarea
                  ref={bodyRef}
                  value={isHtml(body) ? htmlToMd(body) : body}
                  onChange={(e) => setBody(mdToHtml(e.target.value))}
                  placeholder="Generate AI draft to begin or write your own message..."
                  className="w-full h-full min-h-[300px] flex-1 bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white font-medium outline-none focus:border-blue-500/50 resize-none leading-relaxed"
                />
              ) : (
                <div
                  ref={editorRef}
                  contentEditable
                  suppressContentEditableWarning
                  onInput={(e) => {
                    const html = e.currentTarget.innerHTML;
                    if (html !== body) setBody(html);
                  }}
                  onKeyDown={(e) => {
                    if (e.ctrlKey || e.metaKey) {
                      if (e.key === 'b') { document.execCommand('bold'); e.preventDefault(); }
                      if (e.key === 'i') { document.execCommand('italic'); e.preventDefault(); }
                      if (e.key === 'u') { document.execCommand('underline'); e.preventDefault(); }
                    }
                  }}
                  dangerouslySetInnerHTML={{ __html: body }}
                  className="w-full h-full min-h-[300px] flex-1 bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white outline-none focus:border-blue-500/50 resize-none leading-relaxed overflow-y-auto [&:empty:before]:content-[attr(data-placeholder)] [&:empty:before]:text-slate-600 [&:empty:before]:italic"
                  data-placeholder="Generate AI draft to begin or write your own message..."
                />
              )}
            </div>

            <div className="space-y-2">
              <label className="text-[11px] font-medium text-slate-400">Lead Remarks / Context</label>
              <textarea
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Private notes about this lead's background or specific needs..."
                className="w-full bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[12px] text-slate-300 font-medium outline-none focus:border-blue-500/50 resize-none min-h-[80px]"
              />
            </div>

            {/* AI Refinement Tools */}
            <div className="space-y-4 pt-4">
              <div className="relative flex items-center bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-3 py-1 focus-within:border-blue-500/50 transition-colors">
                <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                <input
                  type="text"
                  value={aiInstruction}
                  onChange={(e) => setAiInstruction(e.target.value)}
                  placeholder="Edit with AI (e.g., 'Make it more formal', 'Add focus on ROI'...)"
                  className="flex-1 bg-transparent border-none text-[12px] text-slate-300 px-3 py-2 outline-none italic placeholder-slate-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
                />
                <button
                  onClick={() => handleRefine()}
                  disabled={isRefining || !aiInstruction}
                  className="bg-[#10b981] hover:bg-emerald-500 text-white text-[11px] font-bold px-4 py-1.5 rounded-md transition-colors disabled:opacity-50 flex items-center shadow-lg shadow-emerald-500/20 cursor-pointer"
                >
                  {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : ''}
                  {isRefining ? 'Refining...' : 'Refine Draft'}
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button onClick={() => handleRefine('Shorten this email')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  SHORTEN
                </button>
                <button onClick={() => handleRefine('Make it more professional')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  MORE PROFESSIONAL
                </button>
                <button onClick={() => handleRefine('Add specific ROI data or metrics')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  ADD ROI DATA
                </button>
                <button onClick={() => handleRefine('Make it more friendly and conversational')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  FRIENDLY TONE
                </button>
              </div>

              <div className="pt-6 flex flex-col gap-4">
                <div className="flex items-center gap-4 w-full">
                  <button
                    onClick={() => handleSave()}
                    disabled={isSaving}
                    className="bg-[#1e293b] hover:bg-[#334155] text-white text-[12px] font-bold px-5 py-2.5 rounded-md transition-colors disabled:opacity-50 flex items-center border border-[#ffffff10] cursor-pointer shrink-0"
                  >
                    {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                    Save Changes
                  </button>
                  <button
                    onClick={() => setShowDatePicker(!showDatePicker)}
                    className="bg-[#1e293b] hover:bg-[#334155] text-slate-300 hover:text-white text-[12px] font-bold px-5 py-2.5 rounded-md transition-colors disabled:opacity-50 flex items-center border border-[#ffffff10] cursor-pointer shrink-0"
                  >
                    Schedule...
                  </button>
                  <button
                    onClick={handleApproveAndSend}
                    className="flex-1 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white text-[12px] font-black uppercase tracking-widest px-4 py-2.5 rounded-md transition-all shadow-lg shadow-red-500/20 flex items-center justify-center gap-2 cursor-pointer"
                  >
                    Approve & Send Now <Send className="w-4 h-4" />
                  </button>
                </div>

                {showDatePicker && (
                  <div className="flex items-center gap-3 p-4 bg-[#0a0f1a] border border-blue-500/30 rounded-lg animate-in slide-in-from-top-2 shadow-[0_0_15px_rgba(59,130,246,0.1)]">
                    <span className="text-slate-400 font-bold text-[11px] uppercase tracking-wider">Send At:</span>
                    <DatePicker
                      selected={scheduledAt}
                      onChange={(date) => setScheduledAt(date)}
                      showTimeSelect
                      timeFormat="HH:mm"
                      timeIntervals={15}
                      timeCaption="Time"
                      dateFormat="MMMM d, yyyy h:mm aa"
                      placeholderText="Select date and time"
                      className="bg-[#131722] border border-[#ffffff10] rounded px-3 py-2 text-white text-[13px] outline-none focus:border-blue-500/50 w-[220px]"
                      wrapperClassName="w-auto"
                      minDate={new Date()}
                    />
                    <button
                      onClick={handleSchedule}
                      disabled={!scheduledAt || isSaving}
                      className="bg-blue-600 hover:bg-blue-500 text-white px-5 py-2 rounded text-[12px] font-bold cursor-pointer disabled:opacity-50 transition-colors shadow-lg shadow-blue-500/20"
                    >
                      Confirm Schedule
                    </button>
                    <button
                      onClick={() => setShowDatePicker(false)}
                      className="text-slate-400 hover:text-white text-[12px] ml-auto font-medium cursor-pointer transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Email Preview Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
          {/* Preview Header */}
          <div className="p-6 border-b border-[#ffffff08] bg-[#0a0f1a]">
            <div className="flex justify-between items-start">
              <div className="flex gap-4 items-center">
                <div className="w-12 h-12 rounded-full bg-[#8b5cf6] flex items-center justify-center text-white font-bold text-lg shadow-lg">
                  {draft.first_name?.charAt(0)}{draft.last_name?.charAt(0)}
                </div>
                <div>
                  <h3 className="text-white font-bold text-[15px] flex items-center gap-2">
                    {draft.first_name} {draft.last_name}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5">
                    <p className="text-[12px] text-[#94a3b8] font-medium">{draft.designation} at {draft.company_name || draft.family_office_name}, {draft.city}</p>
                    {draft.linkedin_url && (
                      <a href={draft.linkedin_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-blue-400 hover:underline">
                        <LinkIcon className="w-3 h-3" /> LinkedIn
                      </a>
                    )}
                  </div>
                </div>
              </div>

              <div className="text-right flex flex-col items-end gap-1">
                <span className="text-[#64748b] text-[9px] font-black uppercase tracking-[2px]">PERSONA</span>
                <span className="text-[#10b981] text-[12px] font-black uppercase tracking-[1px]">{draft.persona || 'PARTNER'}</span>
              </div>
            </div>
          </div>

          {/* Preview Body */}
          <div className="p-8 flex-1 bg-[#131722] overflow-y-auto w-full custom-scrollbar">
            <div className="w-full space-y-8">
              <div className="text-[13px]">
                <span className="text-[#94a3b8] font-medium mr-2">Subject:</span>
                <span className={`font-bold ${subject ? 'text-blue-400' : 'text-slate-600 italic text-[11px]'}`}>
                  {subject || '(No subject specified)'}
                </span>
              </div>

              {cc && (
                <div className="text-[13px] -mt-4">
                  <span className="text-[#94a3b8] font-medium mr-2">CC:</span>
                  <span className="text-slate-400 font-bold">{cc}</span>
                </div>
              )}

              <div
                className={`text-[13px] leading-relaxed font-medium ${body ? 'text-slate-300' : 'text-slate-600 italic text-[11px]'}`}
                dangerouslySetInnerHTML={{ __html: renderEmailPreview(body) }}
              />

              {/* Attachments Section */}
              <div className="pt-10 mt-10 border-t border-[#ffffff05]">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-[#64748b] text-[10px] font-black uppercase tracking-[2px]">Attachments ({draft.attachments?.length || 0})</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {draft.attachments?.map((att, idx) => (
                    <div key={idx} className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0f1a] border border-[#ffffff08] hover:border-blue-500/30 transition-colors group cursor-default">
                      <div className="w-10 h-10 rounded-md bg-red-500/10 flex items-center justify-center text-red-500">
                        <FileText className="w-5 h-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-[12px] font-bold text-slate-200 truncate group-hover:text-blue-400 transition-colors text-ellipsis">{att.name}</p>
                        <p className="text-[10px] text-slate-500 font-medium uppercase tracking-tight">{att.size || ''}{att.size ? ' • ' : ''}PDF Document</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Preview Stats Footer */}
          <div className="p-8 border-t border-[#ffffff08] bg-[#0a0f1a]">
            <div className="space-y-4 max-w-[400px]">
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px]">
                <span className="text-[#64748b] font-medium">Status</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-[1px] bg-transparent w-max ${draft.email_status === 'SENT' || draft.email_status === 'APPROVED' ? 'text-[#10b981]' :
                  draft.email_status === 'REJECTED' || draft.email_status === 'FAILED' ? 'text-red-500' :
                    draft.email_status === 'SCHEDULED' ? 'text-blue-400' :
                      'text-amber-500'
                  }`}>
                  {draft.email_status || 'PENDING APPROVAL'}
                  {draft.email_status === 'SCHEDULED' && draft.scheduled_at && ` (For ${new Date(draft.scheduled_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })})`}
                </span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Approved By</span>
                <span className="text-white">{(draft.email_status === 'SENT' || draft.email_status === 'APPROVED') ? (draft.verifier || 'Admin') : '—'}</span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Sent At</span>
                <span className="text-white">
                  {draft.email_status === 'SENT' && draft.updated_at
                    ? new Date(draft.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
                    : '—'}
                </span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Opens</span>
                <span className="text-slate-300">0</span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Clicks</span>
                <span className="text-slate-300">0</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {notification && (
        <div className="fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4">
          <div className={`px-6 py-4 rounded-xl shadow-2xl border backdrop-blur-md flex items-center gap-3 ${notification.type === 'success' ? 'bg-[#10b981]/10 border-[#10b981]/20 text-[#10b981]' : 'bg-red-500/10 border-red-500/20 text-red-500'
            }`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="font-bold text-[13px]">{notification.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default EditEmail;
