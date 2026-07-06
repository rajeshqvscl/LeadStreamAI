import React, { useState, useEffect } from 'react';
import { Pen, Save, Loader2, CheckCircle2, X, FileUp, Sparkles } from 'lucide-react';
import api from '../services/api';
import ToolbarTextarea from './ToolbarTextarea';

const TEMPLATES = [
  {
    name: 'Classic',
    gen: (n, t, p, l) => `--
*Thanks & Regards,*
***${n}***
*${t}*
[Website](https://qvscl.com) | [LinkedIn](${l})
*${p}*`,
  },
  {
    name: 'Modern',
    gen: (n, t, p, l) => `---
Best regards,

**${n}**
${t}
${p}
[linkedin.com/in/yourprofile](${l})`,
  },
  {
    name: 'Minimal',
    gen: (n, t, p) => `Thanks,
${n}
${t}
${p}`,
  },
  {
    name: 'Executive',
    gen: (n, t, p, l) => `Sincerely,

${n}, ${t}
QV Strategic Consulting LLP
${p}
${l}`,
  },
  {
    name: 'Simple',
    gen: (n, t) => `Regards,
${n}
${t}
QV Strategic Consulting LLP`,
  },
];

const SignatureEditor = ({ userId, onSave, onClose, children }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [signature, setSignature] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [uploadingDoc, setUploadingDoc] = useState(false);

  useEffect(() => {
    if (isOpen) {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      setSignature(user.signature || '');
    }
  }, [isOpen]);

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const autoName = user.full_name || user.name || user.username || 'Your Name';
  const autoTitle = user.job_title || user.designation || 'Analyst';
  const autoPhone = user.phone || '+91-9876543210';
  const autoLinkedin = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';

  const close = () => {
    setIsOpen(false);
    if (onClose) onClose();
  };

  const doSave = async (content) => {
    setSaving(true);
    setSaved(false);
    try {
      await api.put('/api/auth/signature', { signature: content }, { headers: { 'X-User-Id': userId } });
      await api.put('/api/auth/signature-mode', { signature_mode: 'custom' }, { headers: { 'X-User-Id': userId } });
      const u = JSON.parse(localStorage.getItem('user') || '{}');
      u.signature = content;
      u.signature_mode = 'custom';
      localStorage.setItem('user', JSON.stringify(u));
      setSignature(content);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      if (onSave) onSave(content, 'custom');
    } catch (err) {
      alert('Failed to save signature');
    } finally {
      setSaving(false);
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
        if (extracted) {
          setSignature(extracted);
        }
      } catch (err) {
        alert('Failed to extract signature from document');
      } finally {
        setUploadingDoc(false);
      }
    };
    input.click();
  };

  const mdToPreviewHtml = (text) => {
    let html = text;
    html = html.replace(/^###\s+(.*?)$/gm, '<h3 style="margin:0 0 4px 0;font-size:15px;font-weight:700;">$1</h3>');
    html = html.replace(/^##\s+(.*?)$/gm, '<h2 style="margin:0 0 4px 0;font-size:17px;font-weight:700;">$1</h2>');
    html = html.replace(/^#\s+(.*?)$/gm, '<h1 style="margin:0 0 4px 0;font-size:19px;font-weight:700;">$1</h1>');
    html = html.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/_(.*?)_/g, '<em>$1</em>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/!\[(.*?)\]\((.*?)\)/g, '<img src="$2" alt="$1" style="max-width:100%;height:auto;border-radius:8px;" />');
    html = html.replace(/(?<!href=")(?<!src=")\[([^\]]*)\]\(([^)]*)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6;text-decoration:underline;">$1</a>');
    html = html.replace(/\n{2,}/g, '<br /><br />');
    html = html.replace(/\n/g, '<br />');
    return html;
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
          <div className="bg-[#0a0d14] border border-white/10 rounded-[24px] w-full max-w-3xl max-h-[90vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
              <h3 className="text-sm font-bold text-white">Your Signature</h3>
              <button onClick={close} className="text-slate-500 hover:text-white text-lg leading-none"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-6 space-y-4 overflow-y-auto max-h-[calc(90vh-80px)]">
              <p className="text-[11px] text-slate-500">
                Write your email signature using the formatting tools below.
              </p>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2 flex items-center gap-1.5">
                  <Sparkles className="w-3 h-3" /> Templates
                </label>
                <div className="flex flex-wrap gap-2 mb-3">
                  {TEMPLATES.map(tpl => (
                    <button
                      key={tpl.name}
                      type="button"
                      onClick={() => setSignature(tpl.gen(autoName, autoTitle, autoPhone, autoLinkedin))}
                      className="px-3 py-1.5 rounded-lg text-[11px] font-bold border border-white/10 text-slate-300 hover:bg-purple-600/20 hover:border-purple-500/30 hover:text-purple-300 transition-all"
                    >
                      {tpl.name}
                    </button>
                  ))}
                </div>
              </div>
              <ToolbarTextarea
                value={signature}
                onChange={e => setSignature(e.target.value)}
                rows={6}
                placeholder="Write your signature here..."
              />
              <button
                type="button"
                onClick={handleUploadDoc}
                disabled={uploadingDoc}
                className="w-full px-3 py-2 rounded-xl bg-emerald-600/20 border border-emerald-500/30 text-emerald-400 text-[11px] font-bold hover:bg-emerald-600/40 hover:text-emerald-300 transition-all flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploadingDoc ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileUp className="w-3.5 h-3.5" />}
                {uploadingDoc ? 'Extracting...' : 'Upload DOCX / PDF to auto-format as signature'}
              </button>
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Preview</label>
                <div className="bg-black/40 border border-white/5 rounded-xl p-5 text-slate-300 text-[13px] leading-relaxed email-preview">
                  {signature ? (
                    <div style={{ color: '#666', fontFamily: 'Arial, sans-serif', fontSize: '13px', lineHeight: '1.4' }}
                      dangerouslySetInnerHTML={{ __html: mdToPreviewHtml(signature) + `<div style="font-size: 10px; color: #999999; line-height: 1.2; margin-top: 6px;">Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you.</div>` }}
                    />
                  ) : (
                    <span className="text-slate-600 italic">Write your signature above to see a preview.</span>
                  )}
                </div>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={close}
                  className="px-4 py-2 rounded-xl text-[11px] font-bold text-slate-400 hover:text-white border border-white/10 hover:bg-white/5 transition-all"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => doSave(signature)}
                  disabled={saving || !signature.trim()}
                  className="px-5 py-2 rounded-xl text-[11px] font-bold flex items-center gap-2 bg-purple-600 hover:bg-purple-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  {saved ? 'Saved!' : saving ? 'Saving...' : 'Save Signature'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default SignatureEditor;
