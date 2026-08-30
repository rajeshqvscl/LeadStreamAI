import React, { useState, useEffect, useCallback } from 'react';
import { Pen, Save, Loader2, CheckCircle2, X, FileUp, Sparkles, Plus, Trash2, Star, Copy, Pencil } from 'lucide-react';
import api from '../services/api';
import ToolbarTextarea from './ToolbarTextarea';
import SignaturePreview from './SignaturePreview';
import { applyForcedLogoStyles } from '../utils/logoSize';

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

  const SignatureEditor = ({ userId, onSave, onClose, children }) => {
    const [isOpen, setIsOpen] = useState(false);
  const [signatures, setSignatures] = useState([]);
  const [loading, setLoading] = useState(false);
  const [currentSigId, setCurrentSigId] = useState(null);
  const [currentName, setCurrentName] = useState('');
  const [currentContent, setCurrentContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);
  const [deletingId, setDeletingId] = useState(null);
  const [editingName, setEditingName] = useState(null);
  const [editNameValue, setEditNameValue] = useState('');

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

  useEffect(() => {
    if (isOpen) {
      setLoading(true);
      fetchSignatures().then(sigs => {
        const user = JSON.parse(localStorage.getItem('user') || '{}');
        if (sigs.length > 0) {
          // Select default signature or first one
          const defaultSig = sigs.find(s => s.is_default) || sigs[0];
          setCurrentSigId(defaultSig.id);
          setCurrentName(defaultSig.name);
          setCurrentContent(defaultSig.content);
        } else if (user.signature) {
          setCurrentSigId(null);
          setCurrentName('My Signature');
          setCurrentContent(user.signature);
        } else {
          // Auto-generate from profile
          const n = user.full_name || user.name || user.username || 'Your Name';
          const t = user.job_title || user.designation || 'Analyst';
          const p = user.phone || '+91-9876543210';
          const l = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
          setCurrentSigId(null);
          setCurrentName('My Signature');
          setCurrentContent(`--\n*Thanks & Regards,*\n***${n}***\n*${t}*\n[Website](https://qvscl.com) | [LinkedIn](${l})\n*${p}*`);
        }
        setLoading(false);
      });
    }
  }, [isOpen, fetchSignatures]);

  const close = () => {
    setIsOpen(false);
    if (onClose) onClose();
  };

  const selectSignature = (sig) => {
    setCurrentSigId(sig.id);
    setCurrentName(sig.name);
    setCurrentContent(sig.content);
  };

  const handleNewSignature = async () => {
    const user = JSON.parse(localStorage.getItem('user') || '{}');
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
      const newSig = res.data;
      const _sigs = await fetchSignatures();
      setCurrentSigId(newSig.id);
      setCurrentName(newSig.name);
      setCurrentContent(newSig.content);
    } catch (_err) {
      alert('Failed to create signature');
    }
  };

  const handleSave = async () => {
    if (!currentContent.trim()) return;
    setSaving(true);
    setSaved(false);
    try {
      if (currentSigId) {
        // Update existing signature
        await api.put(`/api/signatures/${currentSigId}`, 
          { name: currentName, content: currentContent },
          { headers: { 'X-User-Id': userId } }
        );
      } else {
        // Create new
        const res = await api.post('/api/signatures',
          { name: currentName, content: currentContent },
          { headers: { 'X-User-Id': userId } }
        );
        setCurrentSigId(res.data.id);
      }
      // Also keep the legacy users.signature field in sync
      await api.put('/api/auth/signature', { signature: currentContent }, { headers: { 'X-User-Id': userId } });
      await api.put('/api/auth/signature-mode', { signature_mode: 'custom' }, { headers: { 'X-User-Id': userId } });
      
      const u = JSON.parse(localStorage.getItem('user') || '{}');
      u.signature = currentContent;
      u.signature_mode = 'custom';
      localStorage.setItem('user', JSON.stringify(u));
      
      await fetchSignatures();
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      if (onSave) onSave(currentContent, 'custom');
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
        }
      }
    } catch (_err) {
      alert('Failed to delete signature');
    } finally {
      setDeletingId(null);
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
    // Read image width/height fresh from localStorage so a Settings change applies
    // to the preview without remounting the editor.
    const _su = JSON.parse(localStorage.getItem('user') || localStorage.getItem('user_admin') || '{}');
    const sigImgW = _su?.image_width || '400px';
    const sigImgH = _su?.image_height || 'auto';
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
    html = html.replace(/!\[(.*?)\]\((.*?)\)/g, `<img src="$2" alt="$1" style="width:${sigImgW};height:${sigImgH};border-radius:8px;" />`);
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
    // Apply Settings image_width/height to ALL <img> tags so preview matches
    html = html.replace(/<img\b[^>]*>/gi, (m) => {
      // Strip any HTML width/height attributes (they override CSS)
      m = m.replace(/\s+width="[^"]*"/gi, '');
      m = m.replace(/\s+height="[^"]*"/gi, '');
      m = m.replace(/\s+width='[^']*'/gi, '');
      m = m.replace(/\s+height='[^']*'/gi, '');
      // Strip existing width/height/max-width from style attribute, then set our values
      if (/style\s*=\s*["']/i.test(m)) {
        return m.replace(/style\s*=\s*["']([^"']*)["']/i, (sm, existing) => {
          let cleaned = existing.replace(/width\s*:\s*[^;]+;?/gi, '').replace(/height\s*:\s*[^;]+;?/gi, '').replace(/max-width\s*:\s*[^;]+;?/gi, '').replace(/;\s*;/g, ';').trim();
          if (cleaned && !cleaned.endsWith(';')) cleaned += ';';
          return `style="${cleaned}width:${sigImgW};height:${sigImgH};display:block;"`;
        });
      }
      return m.replace('<img', `<img style="width:${sigImgW};height:${sigImgH};display:block;"`);
    });
    // Palak's logo (stored as markdown after editor re-save) must preview at
    // 150x150 — same forced size the backend applies to sent emails.
    return applyForcedLogoStyles(html);
  };

  return (
    <>
      {children ? (
        <span onClick={() => setIsOpen(true)}>{children}</span>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-400 hover:bg-purple-600/30 text-[11px] font-bold transition-all"
        >
          <Pen className="w-3.5 h-3.5" />
          Signature
        </button>
      )}

      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={close}>
          <div className="bg-[#0a0d14] border border-white/10 rounded-[24px] w-full max-w-4xl max-h-[90vh] overflow-hidden shadow-2xl flex" onClick={e => e.stopPropagation()}>
            {/* Sidebar - Signature List */}
            <div className="w-56 shrink-0 border-r border-white/5 flex flex-col bg-black/20">
              <div className="flex items-center justify-between px-4 py-3 border-b border-white/5">
                <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">Signatures</h4>
                <button
                  onClick={handleNewSignature}
                  className="p-1 rounded-lg hover:bg-blue-500/20 text-blue-400 transition-all"
                  title="New Signature"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto custom-scrollbar p-2 space-y-1">
                {loading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-4 h-4 text-slate-500 animate-spin" />
                  </div>
                ) : signatures.length === 0 ? (
                  <p className="text-[10px] text-slate-600 text-center py-6 italic">
                    No saved signatures yet
                  </p>
                ) : (
                  signatures.map(sig => (
                    <div
                      key={sig.id}
                      onClick={() => selectSignature(sig)}
                      className={`group relative flex items-center gap-2 px-3 py-2 rounded-xl cursor-pointer transition-all ${
                        currentSigId === sig.id
                          ? 'bg-purple-600/20 border border-purple-500/30 text-white'
                          : 'text-slate-400 hover:bg-white/5 hover:text-slate-300 border border-transparent'
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          {sig.is_default && <Star className="w-3 h-3 text-amber-400 shrink-0" />}
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
                            <span className="text-[11px] font-semibold truncate">{sig.name}</span>
                          )}
                        </div>
                        <p className="text-[9px] text-slate-600 truncate mt-0.5">
                          {sig.content ? sig.content.replace(/[#*[\]`>]/g, '').substring(0, 40) : 'Empty'}
                        </p>
                      </div>
                      {/* Actions on hover */}
                      <div className="absolute right-1 top-1/2 -translate-y-1/2 hidden group-hover:flex items-center gap-0.5 bg-[#0a0d14]/90 rounded-lg px-1">
                        {!sig.is_default && (
                          <button
                            onClick={e => { e.stopPropagation(); handleSetDefault(sig.id); }}
                            className="p-1 rounded hover:bg-amber-500/20 text-slate-500 hover:text-amber-400 transition-all"
                            title="Set as default"
                          >
                            <Star className="w-3 h-3" />
                          </button>
                        )}
                        <button
                          onClick={e => { e.stopPropagation(); setEditingName(sig.id); setEditNameValue(sig.name); }}
                          className="p-1 rounded hover:bg-blue-500/20 text-slate-500 hover:text-blue-400 transition-all"
                          title="Rename"
                        >
                          <Pencil className="w-3 h-3" />
                        </button>
                        <button
                          onClick={e => { e.stopPropagation(); handleDelete(sig.id); }}
                          disabled={deletingId === sig.id}
                          className="p-1 rounded hover:bg-red-500/20 text-slate-500 hover:text-red-400 transition-all"
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

            {/* Main Editor */}
            <div className="flex-1 flex flex-col min-w-0">
              <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-bold text-white">Edit Signature</h3>
                  {currentSigId && (() => {
                    const sig = signatures.find(s => s.id === currentSigId);
                    return sig?.is_default ? (
                      <span className="text-[9px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-1.5 py-0.5 rounded font-black uppercase tracking-wider">Default</span>
                    ) : null;
                  })()}
                </div>
                <button onClick={close} className="text-slate-500 hover:text-white transition-colors"><X className="w-4 h-4" /></button>
              </div>
              <div className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-80px)]">
                {/* Signature Name */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1.5">Name</label>
                  <input
                    value={currentName}
                    onChange={e => setCurrentName(e.target.value)}
                    placeholder="Signature name"
                    className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-blue-500/50 outline-none"
                  />
                </div>

                {/* Templates */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2 flex items-center gap-1.5">
                    <Sparkles className="w-3 h-3" /> Quick Templates
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {TEMPLATES.map(tpl => {
                      const user = JSON.parse(localStorage.getItem('user') || '{}');
                      const autoName = user.full_name || user.name || user.username || 'Your Name';
                      const autoTitle = user.job_title || user.designation || 'Analyst';
                      const autoPhone = user.phone || '+91-9876543210';
                      const autoLinkedin = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';
                      return (
                        <button
                          key={tpl.name}
                          type="button"
                          onClick={() => setCurrentContent(tpl.gen(autoName, autoTitle, autoPhone, autoLinkedin))}
                          className="px-3 py-1.5 rounded-lg text-[11px] font-bold border border-white/10 text-slate-300 hover:bg-purple-600/20 hover:border-purple-500/30 hover:text-purple-300 transition-all"
                        >
                          {tpl.name}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Content Editor */}
                <ToolbarTextarea
                  value={currentContent}
                  onChange={e => setCurrentContent(e.target.value)}
                  rows={6}
                  placeholder="Write your signature here..."
                />

                {/* Upload */}
                <button
                  type="button"
                  onClick={handleUploadDoc}
                  disabled={uploadingDoc}
                  className="w-full px-3 py-2 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-[11px] font-bold hover:bg-emerald-600/40 hover:text-emerald-300 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {uploadingDoc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileUp className="w-3.5 h-3.5" />}
                  {uploadingDoc ? 'Extracting...' : 'Upload DOCX / PDF to auto-format as signature'}
                </button>

                {/* Preview */}
                <div>
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Preview</label>
                  <SignaturePreview
                    html={mdToPreviewHtml(currentContent)}
                    content={currentContent}
                    onChangeContent={setCurrentContent}
                    emptyText="Write your signature above to see a preview. Tip: click an image in the preview to Replace or Remove it."
                  />
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={close}
                    className="px-4 py-2 rounded-xl text-[11px] font-bold text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 transition-all"
                  >
                    Close
                  </button>
                  <button
                    type="button"
                    onClick={handleSave}
                    disabled={saving || !currentContent.trim()}
                    className="px-5 py-2 rounded-xl text-[11px] font-bold flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Signature'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default SignatureEditor;
