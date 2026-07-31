import React, { useState, useEffect, useCallback } from 'react';
import { Pen, Save, Loader2, CheckCircle2, FileUp, Upload, Sparkles, Plus, Trash2, Star, Pencil, ArrowLeft, Eye, Paperclip, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '../services/api';
import ToolbarTextarea from '../components/ToolbarTextarea';

const TEMPLATES = [
  {
    name: 'Classic',
    gen: (n, t, p, l) => `--\n*Thanks & Regards,*\n***${n}***\n*${t}*\n[Website](https://qvscl.com) | [LinkedIn](${l})\n*${p}*`,
  },
  {
    name: 'Modern',
    gen: (n, t, p, l) => `---\nBest regards,\n\n**${n}**\n${t}\n${p}\n[linkedin.com/in/yourprofile](${l})`,
  },
  {
    name: 'Minimal',
    gen: (n, t, p) => `Thanks,\n${n}\n${t}\n${p}`,
  },
  {
    name: 'Executive',
    gen: (n, t, p, l) => `Sincerely,\n\n${n}, ${t}\nQV Strategic Consulting LLP\n${p}\n${l}`,
  },
  {
    name: 'Simple',
    gen: (n, t) => `Regards,\n${n}\n${t}\nQV Strategic Consulting LLP`,
  },
];

const Signatures = () => {
  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 'admin';

  const [signatures, setSignatures] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentSigId, setCurrentSigId] = useState(null);
  const [currentName, setCurrentName] = useState('');
  const [currentContent, setCurrentContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [uploadingAttach, setUploadingAttach] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [deletingFile, setDeletingFile] = useState(null);
  const [editingName, setEditingName] = useState(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [availablePdfs, setAvailablePdfs] = useState([]);
  const [currentAttachments, setCurrentAttachments] = useState([]);
  const [showAttachments, setShowAttachments] = useState(false);

  const fetchSignatures = useCallback(async () => {
    try {
      const res = await api.get('/api/signatures', { headers: { 'X-User-Id': userId } });
      const sigs = res.data || [];
      setSignatures(sigs);
      return sigs;
    } catch (err) {
      console.error('Failed to fetch signatures', err);
      return [];
    }
  }, [userId]);

  const fetchPdfs = useCallback(async () => {
    try {
      const res = await api.get('/api/assets/pdfs', { headers: { 'X-User-Id': userId } });
      setAvailablePdfs(res.data || []);
    } catch (err) {
      console.error('Failed to fetch PDFs', err);
      setAvailablePdfs([]);
    }
  }, [userId]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchPdfs();
    fetchSignatures().then(async sigs => {
      if (cancelled) return;
      if (sigs.length > 0) {
        const defaultSig = sigs.find(s => s.is_default) || sigs[0];
        setCurrentSigId(defaultSig.id);
        setCurrentName(defaultSig.name);
        setCurrentContent(defaultSig.content);
        const atts = defaultSig.attachment_file ? defaultSig.attachment_file.split(',').map(s => s.trim()).filter(Boolean) : [];
        setCurrentAttachments(atts);
        setShowAttachments(atts.length > 0);
      } else if (user.signature) {
        setCurrentSigId(null);
        setCurrentName('My Signature');
        setCurrentContent(user.signature);
        setCurrentAttachments([]);
        setShowAttachments(false);
      } else {
        // Try to get the backend hardcoded signature (same as inject_signature() uses)
        try {
          const res = await api.get('/api/signatures/default-hardcoded', { headers: { 'X-User-Id': userId } });
          const def = res.data || {};
          if (def.signature) {
            setCurrentSigId(null);
            setCurrentName(def.name || 'My Default Signature');
            setCurrentContent(def.signature);
          } else {
            throw new Error('No default returned');
          }
        } catch (_e) {
          // Fallback: auto-generate from profile
          const n = user.full_name || user.name || user.username || 'Your Name';
          const t = user.job_title || user.designation || 'Analyst';
          const p = user.phone || '+91-9876543210';
          const l = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
          setCurrentSigId(null);
          setCurrentName('My Signature');
          setCurrentContent(`--\n*Thanks & Regards,*\n***${n}***\n*${t}*\n[Website](https://qvscl.com) | [LinkedIn](${l})\n*${p}*`);
        }
        setCurrentAttachments([]);
        setShowAttachments(false);
      }
      if (!cancelled) setLoading(false);
    }).catch(err => {
      console.error('Error loading signatures:', err);
      if (!cancelled) {
        const n = user.full_name || user.name || user.username || 'Your Name';
        const t = user.job_title || user.designation || 'Analyst';
        const p = user.phone || '+91-9876543210';
        const l = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
        setCurrentSigId(null);
        setCurrentName('My Signature');
        setCurrentContent(`--\n*Thanks & Regards,*\n***${n}***\n*${t}*\n[Website](https://qvscl.com) | [LinkedIn](${l})\n*${p}*`);
        setCurrentAttachments([]);
        setShowAttachments(false);
        setLoading(false);
      }
    });
    return () => { cancelled = true; };
  }, [fetchSignatures, fetchPdfs]);

  const selectSignature = (sig) => {
    setCurrentSigId(sig.id);
    setCurrentName(sig.name);
    setCurrentContent(sig.content);
    const atts = sig.attachment_file ? sig.attachment_file.split(',').map(s => s.trim()).filter(Boolean) : [];
    setCurrentAttachments(atts);
    setShowAttachments(atts.length > 0);
  };

  const handleNewSignature = async () => {
    const n = user.full_name || user.name || user.username || 'Your Name';
    const t = user.job_title || user.designation || 'Analyst';
    const p = user.phone || '+91-9876543210';
    const l = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
    const defaultContent = `--\n*Thanks & Regards,*\n***${n}***\n*${t}*\n[Website](https://qvscl.com) | [LinkedIn](${l})\n*${p}*`;

    try {
      const res = await api.post('/api/signatures',
        { name: 'New Signature', content: defaultContent },
        { headers: { 'X-User-Id': userId } }
      );
      const _sigs = await fetchSignatures();
      setCurrentSigId(res.data.id);
      setCurrentName(res.data.name);
      setCurrentContent(res.data.content);
      setCurrentAttachments([]);
      setShowAttachments(false);
    } catch (_err) {
      alert('Failed to create signature');
    }
  };

  const handleSave = async () => {
    if (!currentContent.trim()) return;
    setSaving(true);
    setSaved(false);
    try {
      const attachmentVal = currentAttachments.length > 0 ? currentAttachments.join(', ') : '';
      if (currentSigId) {
        await api.put(`/api/signatures/${currentSigId}`,
          { name: currentName, content: currentContent, attachment_file: attachmentVal },
          { headers: { 'X-User-Id': userId } }
        );
      } else {
        const res = await api.post('/api/signatures',
          { name: currentName, content: currentContent, attachment_file: attachmentVal },
          { headers: { 'X-User-Id': userId } }
        );
        setCurrentSigId(res.data.id);
      }
      // Keep legacy users.signature field in sync
      await api.put('/api/auth/signature', { signature: currentContent }, { headers: { 'X-User-Id': userId } });
      await api.put('/api/auth/signature-mode', { signature_mode: 'custom' }, { headers: { 'X-User-Id': userId } });

      const u = JSON.parse(localStorage.getItem('user') || '{}');
      u.signature = currentContent;
      u.signature_mode = 'custom';
      localStorage.setItem('user', JSON.stringify(u));

      await fetchSignatures();
      // If attachments were cleared, update UI to reflect that
      if (!attachmentVal) {
        setCurrentAttachments([]);
        setShowAttachments(false);
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (_err) {
      alert('Failed to save signature');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (sigId) => {
    if (!window.confirm('Delete this signature permanently?')) return;
    setDeletingId(sigId);
    try {
      await api.delete(`/api/signatures/${sigId}`, { headers: { 'X-User-Id': userId } });
      const sigs = await fetchSignatures();
      if (currentSigId === sigId) {
        if (sigs.length > 0) {
          const defaultSig = sigs.find(s => s.is_default) || sigs[0];
          setCurrentSigId(defaultSig.id);
          setCurrentName(defaultSig.name);
          setCurrentContent(defaultSig.content);
        } else {
          setCurrentSigId(null);
          setCurrentName('My Signature');
          setCurrentContent('');
          setCurrentAttachments([]);
          setShowAttachments(false);
        }
      }
    } catch (_err) {
      alert('Failed to delete signature');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDeleteFile = async (filename) => {
    if (!window.confirm(`Delete "${filename}" permanently? This cannot be undone.`)) return;
    setDeletingFile(filename);
    try {
      await api.delete(`/api/signatures/attachment/${encodeURIComponent(filename)}`, { headers: { 'X-User-Id': userId } });
      // Remove from selected attachments if it was checked
      setCurrentAttachments(prev => prev.filter(f => f !== filename));
      // Refresh the available files list
      await fetchPdfs();
    } catch (err) {
      const detail = err.response?.data?.detail || err.message;
      alert(`Failed to delete file: ${detail}`);
    } finally {
      setDeletingFile(null);
    }
  };

  const handleSetDefault = async (sigId) => {
    try {
      await api.put(`/api/signatures/${sigId}`, { is_default: true }, { headers: { 'X-User-Id': userId } });
      await fetchSignatures();
    } catch (_err) {
      alert('Failed to set default signature');
    }
  };

  const handleUploadDoc = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.docx,.pdf,.doc';
    input.onchange = async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setUploadingDoc(true);
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await api.post('/api/upload-signature-doc', formData);
        const extracted = res.data.text || '';
        if (extracted) setCurrentContent(extracted);
      } catch (_err) {
        alert('Failed to extract signature from document');
      } finally {
        setUploadingDoc(false);
      }
    };
    input.click();
  };

  const mdToPreviewHtml = (text) => {
    let html = text;
    // Protect ALL URLs first so the _ and * italic rules can't corrupt them
    // (e.g. upload_123_456.jpg -> upload<em>123</em>456.jpg) — applies to both
    // HTML src/href attributes and markdown (url) destinations
    const urls = [];
    html = html.replace(/https?:\/\/[^\s"'<>)\]]+/gi, (m) => {
      urls.push(m);
      // NOTE: token must contain NO underscores/asterisks so the markdown
      // italic rules can't cross-match between adjacent placeholders
      return `@@LSURL${urls.length - 1}@@`;
    });
    // Convert markdown images FIRST (their URLs are now safe placeholders)
    html = html.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto;border-radius:8px;" />');
    // Protect ALL <img> tags (pre-existing HTML + markdown-converted) so the
    // _ and * italic rules can't corrupt src URLs (e.g. upload_123_456.jpg)
    const imgTags = [];
    html = html.replace(/<img[^>]*>/gi, (m) => {
      imgTags.push(m);
      // NOTE: token must contain NO underscores/asterisks so the markdown
      // italic rules can't cross-match between adjacent placeholders
      return `@@LSIMG${imgTags.length - 1}@@`;
    });
    html = html.replace(/^###\s+(.*?)$/gm, '<h3 style="margin:0 0 4px 0;font-size:15px;font-weight:700;">$1</h3>');
    html = html.replace(/^##\s+(.*?)$/gm, '<h2 style="margin:0 0 4px 0;font-size:17px;font-weight:700;">$1</h2>');
    html = html.replace(/^#\s+(.*?)$/gm, '<h1 style="margin:0 0 4px 0;font-size:19px;font-weight:700;">$1</h1>');
    html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/_(.*?)_/g, '<em>$1</em>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/(?<!href=")(?<!src=")\[([^\]]*)\]\(([^)]*)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6;text-decoration:underline;">$1</a>');
    html = html.replace(/\n{2,}/g, '<br /><br />');
    html = html.replace(/\n/g, '<br />');
    // Restore original <img> tags
    html = html.replace(/@@LSIMG(\d+)@@/g, (m, i) => imgTags[parseInt(i, 10)] || m);
    // Restore URLs (data:image URIs are untouched and handled below)
    html = html.replace(/@@LSURL(\d+)@@/g, (m, i) => urls[parseInt(i, 10)] || m);
    // Legacy data-URI images already in content get a fixed width
    html = html.replace(/<img\s+[^>]*src="data:image\/[^"]*"[^>]*>/gi, (m) => {
      if (/style\s*=\s*"/i.test(m)) return m.replace(/style\s*=\s*"([^"]*)"/i, 'style="width:400px;height:auto;display:block;"');
      return m.replace('<img', '<img style="width:400px;height:auto;display:block;"');
    });
    return html;
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700 h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-4">
          <Link
            to="/dashboard/prompts"
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-[28px] font-black text-white tracking-tight">Signatures</h1>
            <p className="text-slate-400 text-sm mt-1 font-medium italic">
              Create and manage multiple email signatures
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleNewSignature}
            className="flex items-center gap-2 px-4 py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-[13px] font-bold transition-all hover:scale-105 active:scale-95 shadow-[0_0_20px_rgba(147,51,234,0.3)]"
          >
            <Plus className="w-4 h-4" />
            New Signature
          </button>
        </div>
      </div>

      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading signatures...</p>
        </div>
      ) : (
        <div className="bg-[#0f121b] border border-white/5 rounded-[24px] overflow-hidden flex" style={{ minHeight: 'calc(100vh - 220px)' }}>
          {/* Left Sidebar - Signature List */}
          <div className="w-64 shrink-0 border-r border-white/5 flex flex-col bg-black/20">
            <div className="px-4 py-4 border-b border-white/5">
              <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">My Signatures</h4>
              <p className="text-[9px] text-slate-600 mt-1">{signatures.length} signature{signatures.length !== 1 ? 's' : ''} saved</p>
            </div>
            <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
              {signatures.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center px-4">
                  <div className="w-12 h-12 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mb-3">
                    <Pen className="w-5 h-5 text-purple-400" />
                  </div>
                  <p className="text-[11px] text-slate-500 font-medium mb-1">No signatures yet</p>
                  <p className="text-[9px] text-slate-600 italic">Click "New Signature" to create one</p>
                </div>
              ) : (
                signatures.map(sig => (
                  <div
                    key={sig.id}
                    onClick={() => selectSignature(sig)}
                    className={`group relative flex items-center gap-3 px-3 py-3 rounded-xl cursor-pointer transition-all ${
                      currentSigId === sig.id
                        ? 'bg-purple-600/20 border border-purple-500/30 text-white shadow-[0_0_15px_rgba(147,51,234,0.1)]'
                        : 'text-slate-400 hover:bg-white/5 hover:text-slate-300 border border-transparent'
                    }`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-[11px] font-bold shrink-0 transition-all ${
                      currentSigId === sig.id
                        ? 'bg-purple-600/40 text-purple-300'
                        : 'bg-white/5 text-slate-500'
                    }`}>
                      {sig.is_default ? <Star className="w-4 h-4 text-amber-400" /> : sig.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      {editingName === sig.id ? (
                        <input
                          value={editNameValue}
                          onChange={e => setEditNameValue(e.target.value)}
                          onBlur={async () => {
                            if (editNameValue.trim()) {
                              try {
                                await api.put(`/api/signatures/${sig.id}`, { name: editNameValue.trim() }, { headers: { 'X-User-Id': userId } });
                                await fetchSignatures();
                              } catch(_e) { /* noop */ }
                            }
                            setEditingName(null);
                          }}
                          onKeyDown={e => e.key === 'Escape' && setEditingName(null)}
                          autoFocus
                          className="bg-black/60 border border-blue-500/50 rounded px-2 py-0.5 text-[11px] text-white w-full outline-none"
                          onClick={e => e.stopPropagation()}
                        />
                      ) : (
                        <div className="flex items-center gap-1.5">
                          <span className="text-[12px] font-semibold truncate">{sig.name}</span>
                          {sig.is_default && (
                            <span className="text-[8px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1 py-0.5 rounded font-black uppercase tracking-wider">Default</span>
                          )}
                        </div>
                      )}
                      <p className="text-[9px] text-slate-600 truncate mt-0.5">
                        {sig.content ? sig.content.replace(/[#*[\]`>]/g, '').substring(0, 50) : 'Empty'}
                      </p>
                    </div>
                    {/* Actions */}
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5 bg-[#0f121b]/95 rounded-lg border border-white/5 px-1 py-0.5 shadow-lg">
                      {!sig.is_default && (
                        <button
                          onClick={e => { e.stopPropagation(); handleSetDefault(sig.id); }}
                          className="p-1.5 rounded hover:bg-amber-500/20 text-slate-500 hover:text-amber-400 transition-all"
                          title="Set as default"
                        >
                          <Star className="w-3 h-3" />
                        </button>
                      )}
                      <button
                        onClick={e => { e.stopPropagation(); setEditingName(sig.id); setEditNameValue(sig.name); }}
                        className="p-1.5 rounded hover:bg-blue-500/20 text-slate-500 hover:text-blue-400 transition-all"
                        title="Rename"
                      >
                        <Pencil className="w-3 h-3" />
                      </button>
                      <button
                        onClick={e => { e.stopPropagation(); handleDelete(sig.id); }}
                        disabled={deletingId === sig.id}
                        className="p-1.5 rounded hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-all"
                        title="Delete"
                      >
                        {deletingId === sig.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Main Editor Area */}
          <div className="flex-1 flex flex-col min-w-0">
            {currentSigId || currentContent ? (
              <div className="p-6 space-y-5 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 220px)' }}>
                {/* Signature Name */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Signature Name</label>
                  <input
                    value={currentName}
                    onChange={e => setCurrentName(e.target.value)}
                    placeholder="e.g. My Professional Signature"
                    className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-purple-500/50 outline-none transition-all"
                  />
                </div>

                {/* Quick Templates */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    Quick Templates
                  </label>
                  <p className="text-[10px] text-slate-600 mb-3">Choose a style to auto-fill your signature with your profile info</p>
                  <div className="flex flex-wrap gap-2">
                    {TEMPLATES.map(tpl => {
                      const autoName = user.full_name || user.name || user.username || 'Your Name';
                      const autoTitle = user.job_title || user.designation || 'Analyst';
                      const autoPhone = user.phone || '+91-9876543210';
                      const autoLinkedin = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
                      return (
                        <button
                          key={tpl.name}
                          type="button"
                          onClick={() => setCurrentContent(tpl.gen(autoName, autoTitle, autoPhone, autoLinkedin))}
                          className="px-4 py-2 rounded-xl text-[12px] font-bold border border-white/10 text-slate-300 hover:bg-purple-600/20 hover:border-purple-500/30 hover:text-purple-300 transition-all"
                        >
                          {tpl.name}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Content Editor */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Signature Content</label>
                  <p className="text-[10px] text-slate-600 mb-2">Use markdown for formatting. Text after `--` appears as signature block.</p>
                  <ToolbarTextarea
                    value={currentContent}
                    onChange={e => setCurrentContent(e.target.value)}
                    rows={8}
                    placeholder="Write your signature here... e.g.&#10;&#10;--&#10;*Thanks & Regards,*&#10;***Your Name***&#10;*Your Title*&#10;[LinkedIn](https://linkedin.com/in/yourprofile)"
                  />
                </div>

                {/* Upload Document */}
                <button
                  type="button"
                  onClick={handleUploadDoc}
                  disabled={uploadingDoc}
                  className="w-full px-4 py-3 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-[12px] font-bold hover:bg-emerald-600/40 hover:text-emerald-300 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploadingDoc ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileUp className="w-4 h-4" />}
                  {uploadingDoc ? 'Extracting signature...' : 'Upload DOCX / PDF to auto-format as signature'}
                </button>

                {/* Live Preview */}
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <Eye className="w-4 h-4 text-slate-400" />
                    <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Live Preview</label>
                  </div>
                  <div className="bg-black/40 border border-white/5 rounded-xl p-6 text-slate-300 text-[13px] leading-relaxed email-preview min-h-[120px]">
                    {currentContent ? (
                      <div
                        style={{ color: '#666', fontFamily: 'Arial, sans-serif', fontSize: '13px', lineHeight: '1.4' }}
                        dangerouslySetInnerHTML={{
                          __html: mdToPreviewHtml(currentContent) + `<div style="font-size: 10px; color: #999999; line-height: 1.2; margin-top: 6px;">Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you.</div>`
                        }}
                      />
                    ) : (
                      <span className="text-slate-600 italic">Write your signature above to see a live preview.</span>
                    )}
                  </div>
                </div>

                {/* Optional Attachments */}
                <div className="border border-white/5 rounded-xl p-4 bg-white/[0.01]">
                  <div className="flex items-center justify-between">
                    <label className="flex items-center gap-3 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={showAttachments}
                        onChange={e => {
                          setShowAttachments(e.target.checked);
                          if (!e.target.checked) setCurrentAttachments([]);
                        }}
                        className="w-4 h-4 rounded border-white/20 bg-black/40 text-purple-600 focus:ring-purple-500/50 cursor-pointer shrink-0"
                      />
                      <div className="flex items-center gap-1.5">
                        <Paperclip className={`w-3.5 h-3.5 ${showAttachments ? 'text-purple-400' : 'text-slate-500'}`} />
                        <span className={`text-[11px] font-bold uppercase tracking-widest ${showAttachments ? 'text-purple-300' : 'text-slate-500'}`}>
                          Optional Attachments
                        </span>
                        {currentAttachments.length > 0 && showAttachments && (
                          <span className="text-[9px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded font-bold">
                            {currentAttachments.length}
                          </span>
                        )}
                        {currentAttachments.length === 0 && showAttachments && (
                          <span className="text-[9px] bg-slate-500/10 text-slate-500 border border-slate-500/20 px-1.5 py-0.5 rounded font-bold">
                            None
                          </span>
                        )}
                      </div>
                    </label>
                    {currentAttachments.length > 0 && showAttachments && (
                      <button
                        onClick={() => {
                          setCurrentAttachments([]);
                          setShowAttachments(false);
                        }}
                        title="Clear all selected attachments"
                        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-bold text-red-400 hover:text-red-300 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 hover:border-red-500/40 transition-all"
                      >
                        <X className="w-3 h-3" />
                        Clear All
                      </button>
                    )}
                  </div>

                  {showAttachments && (
                    <div className="mt-3 space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                      <p className="text-[10px] text-slate-600">Check files to attach when sending emails with this signature, or upload new ones.</p>
                      
                      {/* No files selected banner */}
                      {currentAttachments.length === 0 && availablePdfs.length > 0 && (
                        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-500/5 border border-amber-500/15 rounded-xl">
                          <Paperclip className="w-3.5 h-3.5 shrink-0 text-amber-400/60" />
                          <span className="text-[11px] text-amber-400/70 font-medium">No files selected for this signature — check files below to attach them.</span>
                        </div>
                      )}

                      <div className="space-y-1.5 max-h-40 overflow-y-auto custom-scrollbar bg-black/20 border border-white/5 rounded-xl p-2">
                        {availablePdfs.length === 0 ? (
                          <p className="text-[11px] text-slate-600 italic text-center py-3">No files available. Upload one below.</p>
                        ) : (
                          availablePdfs.map(pdf => {
                            const isChecked = currentAttachments.includes(pdf.filename);
                            return (
                              <label
                                key={pdf.filename}
                                className={`group flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-all ${
                                  isChecked
                                    ? 'bg-purple-600/15 border border-purple-500/30'
                                    : 'hover:bg-white/5 border border-transparent'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={isChecked}
                                  onChange={() => {
                                    setCurrentAttachments(prev =>
                                      isChecked
                                        ? prev.filter(f => f !== pdf.filename)
                                        : [...prev, pdf.filename]
                                    );
                                  }}
                                  className="w-4 h-4 rounded border-white/20 bg-black/40 text-purple-600 focus:ring-purple-500/50 cursor-pointer"
                                />
                                <Paperclip className={`w-3.5 h-3.5 shrink-0 ${isChecked ? 'text-purple-400' : 'text-slate-500'}`} />
                                <span className={`flex-1 text-[12px] truncate ${isChecked ? 'text-purple-200 font-medium' : 'text-slate-400'}`}>
                                  {pdf.filename}
                                </span>
                                {/* Delete button (hidden by default, shows on row hover) */}
                                <button
                                  onClick={e => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    handleDeleteFile(pdf.filename);
                                  }}
                                  disabled={deletingFile === pdf.filename}
                                  className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-500/15 transition-all"
                                  title={`Delete ${pdf.filename}`}
                                >
                                  {deletingFile === pdf.filename ? (
                                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                  ) : (
                                    <Trash2 className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </label>
                            );
                          })
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <label className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border border-dashed border-white/10 text-slate-400 hover:text-white hover:border-purple-500/50 cursor-pointer transition-all text-[11px] font-bold ${uploadingAttach ? 'opacity-50 pointer-events-none' : ''}`}>
                          {uploadingAttach ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                          {uploadingAttach ? 'Uploading...' : 'Upload New File'}
                          <input
                            type="file"
                            className="hidden"
                            disabled={uploadingAttach}
                            onChange={async (e) => {
                              const file = e.target.files?.[0];
                              if (!file) return;
                              setUploadingAttach(true);
                              try {
                                const formData = new FormData();
                                formData.append('file', file);
                                const res = await api.post('/api/signatures/upload-attachment', formData, { headers: { 'X-User-Id': userId } });
                                const filename = res.data?.filename;
                                if (filename) {
                                  await fetchPdfs();
                                  setCurrentAttachments(prev => [...prev, filename]);
                                }
                              } catch (_err) {
                                alert('Failed to upload attachment');
                              } finally {
                                setUploadingAttach(false);
                                if (e.target) e.target.value = '';
                              }
                            }}
                          />
                        </label>
                        {currentAttachments.length > 0 && (
                          <div className="flex items-center gap-1.5 px-3 py-2 bg-purple-500/10 border border-purple-500/20 rounded-lg text-[11px] text-purple-300">
                            <Paperclip className="w-3.5 h-3.5" />
                            <span className="font-medium">{currentAttachments.length} selected</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4 border-t border-white/5">
                  <button
                    type="button"
                    onClick={() => {
                      setCurrentSigId(null);
                      setCurrentName('');
                      setCurrentContent('');
                      setCurrentAttachments([]);
                      setShowAttachments(false);
                    }}
                    className="px-5 py-2.5 rounded-xl text-[12px] font-bold text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || !currentContent.trim()}
                    className="px-6 py-2.5 rounded-xl text-[12px] font-bold flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-[0_0_20px_rgba(147,51,234,0.2)]"
                  >
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                    {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Signature'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <div className="w-16 h-16 rounded-full bg-purple-500/10 border border-purple-500/20 flex items-center justify-center mx-auto mb-4">
                    <Pencil className="w-7 h-7 text-purple-400" />
                  </div>
                  <h3 className="text-white font-bold text-base mb-1">No Signature Selected</h3>
                  <p className="text-slate-500 text-sm">Choose a signature from the left panel or create a new one.</p>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Signatures;
