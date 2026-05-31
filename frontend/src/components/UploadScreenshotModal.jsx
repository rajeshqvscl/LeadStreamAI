import React, { useState, useRef } from 'react';
import { Upload, FileText, Sparkles, X, Loader2, CheckCircle2, AlertCircle, Image } from 'lucide-react';
import api from '../services/api';

const UploadScreenshotModal = ({ isOpen, onClose, onSaved }) => {
  const [step, setStep] = useState('upload');
  const [mainFiles, setMainFiles] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [description, setDescription] = useState('');
  const [followup1, setFollowup1] = useState('');
  const [followup2, setFollowup2] = useState('');
  const [followup3, setFollowup3] = useState('');
  const [analyzingFup, setAnalyzingFup] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const mainInputRef = useRef(null);
  const fupInputRefs = {};

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 'admin';
  const acceptedTypes = "image/*,.pdf,.doc,.docx";

  if (!isOpen) return null;

  const analyzeFile = async (file) => {
    const formData = new FormData();
    formData.append('files', file);
    const res = await api.post('/api/analyze-template-screenshot', formData);
    return res.data;
  };

  const handleMainUpload = async (e) => {
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    setMainFiles(files);
    setAnalyzing(true);
    setError(null);
    try {
      const data = await analyzeFile(files[0]);
      if (!data.body && !data.subject) {
        setError('AI could not extract content. Try a clearer file.');
        return;
      }
      setSubject(data.subject || '');
      setBody(data.body || '');
      setStep('edit');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleFupUpload = async (idx) => {
    const input = fupInputRefs[idx];
    if (!input || !input.files?.length) return;
    const file = input.files[0];
    setAnalyzingFup(idx);
    setError(null);
    try {
      const data = await analyzeFile(file);
      const text = data.body || '';
      const setter = idx === 1 ? setFollowup1 : idx === 2 ? setFollowup2 : setFollowup3;
      setter(text);
    } catch (err) {
      setError(`Follow-up ${idx} analysis failed`);
    } finally {
      setAnalyzingFup(null);
      input.value = '';
    }
  };

  const handleSave = async () => {
    if (!templateName.trim()) { setError('Enter a template name.'); return; }
    if (!body.trim()) { setError('Body cannot be empty.'); return; }
    setSaving(true);
    setError(null);
    try {
      const content = subject ? `Subject: ${subject}\n\n${body}` : body;
      await api.post('/api/custom-draft-templates', {
        name: templateName.trim(),
        content,
        description: description.trim() || `Created from upload: ${templateName.trim()}`,
        followup_1: followup1.trim() || null,
        followup_2: followup2.trim() || null,
        followup_3: followup3.trim() || null
      }, { headers: { 'X-User-Id': userId } });
      setSuccess('Template saved!');
      setTimeout(() => { onSaved?.(); handleClose(); }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    setStep('upload'); setMainFiles([]); setAnalyzing(false);
    setSubject(''); setBody(''); setTemplateName(''); setDescription('');
    setFollowup1(''); setFollowup2(''); setFollowup3('');
    setSaving(false); setError(null); setSuccess(null);
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[6000] animate-in fade-in duration-300" onClick={handleClose} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl bg-[#0d1117] border border-white/10 rounded-3xl shadow-[0_0_60px_rgba(0,0,0,0.6)] z-[6001] animate-in zoom-in-95 duration-300 overflow-hidden max-h-[90vh] flex flex-col">
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-rose-500" />
        <div className="p-8 overflow-y-auto flex-1 space-y-4">

          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-black text-white tracking-tight flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-400" /> Create Template
              </h2>
              <p className="text-slate-500 text-[11px] font-medium">Upload screenshot/PDF/DOCX — AI extracts template + follow-ups</p>
            </div>
            <button onClick={handleClose} className="text-slate-500 hover:text-white transition-colors cursor-pointer"><X className="w-5 h-5" /></button>
          </div>

          {error && <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm"><AlertCircle className="w-4 h-4 shrink-0" />{error}</div>}
          {success && <div className="p-3 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-2 text-green-400 text-sm"><CheckCircle2 className="w-4 h-4 shrink-0" />{success}</div>}

          {/* Step 1: Upload Main Template */}
          {step === 'upload' && (
            <div>
              <div className="mb-2">
                <h3 className="text-sm font-bold text-white flex items-center gap-2"><FileText className="w-4 h-4 text-blue-400" /> Upload Template</h3>
                <p className="text-[10px] text-slate-600">Screenshot, PDF, or DOCX of your email template</p>
              </div>
              <div onClick={() => mainInputRef.current?.click()} className="border-2 border-dashed border-white/10 hover:border-blue-500/40 rounded-2xl p-10 text-center cursor-pointer transition-colors bg-white/[0.02]">
                {analyzing ? (
                  <div className="flex flex-col items-center gap-3"><Loader2 className="w-8 h-8 text-blue-400 animate-spin" /><p className="text-slate-400 text-sm font-medium">AI is extracting template...</p></div>
                ) : (
                  <>
                    <Upload className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                    <p className="text-white font-bold mb-1">Click to upload template file</p>
                    <p className="text-slate-500 text-xs">PNG, JPG, PDF, DOCX</p>
                  </>
                )}
                <input ref={mainInputRef} type="file" accept={acceptedTypes} className="hidden" onChange={handleMainUpload} />
              </div>
            </div>
          )}

          {/* Step 2: Edit + Follow-ups */}
          {step === 'edit' && (
            <>
              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Template Name</label>
                <input value={templateName} onChange={e => setTemplateName(e.target.value)} placeholder="e.g. My Template" className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-blue-500/50 transition-colors" />
              </div>
              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Description (optional)</label>
                <input value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description" className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-blue-500/50 transition-colors" />
              </div>
              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Subject Line</label>
                <input value={subject} onChange={e => setSubject(e.target.value)} className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm focus:outline-none focus:border-blue-500/50 transition-colors" />
              </div>
              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Email Body</label>
                <textarea value={body} onChange={e => setBody(e.target.value)} rows={8} className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white text-sm font-mono leading-relaxed focus:outline-none focus:border-blue-500/50 transition-colors resize-y" />
              </div>

              {/* Follow-ups */}
              <div className="border-t border-white/10 pt-5">
                <h3 className="text-sm font-bold text-white mb-1">Follow-up Emails</h3>
                <p className="text-[10px] text-slate-600 mb-4">Upload screenshots/docs for each follow-up, or type manually</p>
                {[1, 2, 3].map(i => {
                  const val = i === 1 ? followup1 : i === 2 ? followup2 : followup3;
                  const set = i === 1 ? setFollowup1 : i === 2 ? setFollowup2 : setFollowup3;
                  return (
                    <div key={i} className="mb-4 p-4 rounded-xl bg-white/[0.02] border border-white/5">
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">Follow-up {i}</label>
                        <label className="flex items-center gap-1.5 text-[10px] text-blue-400 hover:text-blue-300 cursor-pointer font-bold">
                          {analyzingFup === i ? <Loader2 className="w-3 h-3 animate-spin" /> : <Image className="w-3 h-3" />}
                          {analyzingFup === i ? 'Analyzing...' : 'Upload from file'}
                          <input ref={el => fupInputRefs[i] = el} type="file" accept={acceptedTypes} className="hidden" onChange={() => handleFupUpload(i)} />
                        </label>
                      </div>
                      <textarea value={val} onChange={e => set(e.target.value)} rows={3} placeholder={`Follow-up ${i} content (or upload a file)...`} className="w-full px-3 py-2 rounded-lg bg-black/40 border border-white/5 text-white text-xs font-mono focus:outline-none focus:border-blue-500/50 transition-colors resize-y" />
                    </div>
                  );
                })}
              </div>

              <div className="flex gap-3 pt-2">
                <button onClick={() => setStep('upload')} className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-bold text-xs uppercase tracking-widest border border-white/5 cursor-pointer transition-colors">Upload Different File</button>
                <button onClick={handleSave} disabled={saving || !templateName.trim()} className="flex-[2] py-3 px-6 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-black text-xs uppercase tracking-widest shadow-lg shadow-green-500/20 flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  {saving ? 'Saving...' : 'Save Template'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
};
export default UploadScreenshotModal;
