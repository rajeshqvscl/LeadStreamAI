import React, { useState, useRef } from 'react';
import { Upload, FileText, Sparkles, X, Loader2, CheckCircle2, AlertCircle, Plus } from 'lucide-react';
import api from '../services/api';

const UploadScreenshotModal = ({ isOpen, onClose, onSaved }) => {
  const [files, setFiles] = useState([]);
  const [previews, setPreviews] = useState([]);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [templateName, setTemplateName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [step, setStep] = useState('upload');
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleFileSelect = (e) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length === 0) return;
    const remaining = 5 - files.length;
    const toAdd = selected.slice(0, remaining);
    setFiles(prev => [...prev, ...toAdd]);
    setPreviews(prev => [...prev, ...toAdd.map(f => URL.createObjectURL(f))]);
    setError(null);
    if (files.length + toAdd.length > 0) setStep('preview');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const selected = Array.from(e.dataTransfer?.files || []);
    if (selected.length === 0) return;
    const remaining = 5 - files.length;
    const toAdd = selected.slice(0, remaining);
    if (toAdd.length === 0) return;
    setFiles(prev => [...prev, ...toAdd]);
    setPreviews(prev => [...prev, ...toAdd.map(f => URL.createObjectURL(f))]);
    setError(null);
    setStep('preview');
  };

  const removeFile = (idx) => {
    URL.revokeObjectURL(previews[idx]);
    setFiles(prev => prev.filter((_, i) => i !== idx));
    setPreviews(prev => prev.filter((_, i) => i !== idx));
    if (files.length <= 1) setStep('upload');
  };

  const handleAnalyze = async () => {
    if (files.length === 0) return;
    setAnalyzing(true);
    setError(null);
    try {
      const formData = new FormData();
      files.forEach(f => formData.append('files', f));
      const res = await api.post('/api/analyze-template-screenshot', formData);
      const data = res.data;
      if (data.body === '' && !data.subject) {
        setError('AI could not extract template content. Try clearer screenshots.');
        return;
      }
      setResult(data);
      setSubject(data.subject || '');
      setBody(data.body || '');
      setTemplateName('');
      setDescription('');
      setStep('edit');
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Analysis failed. Try again.');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleSave = async () => {
    if (!templateName.trim()) {
      setError('Please enter a template name.');
      return;
    }
    if (!body.trim()) {
      setError('Body content cannot be empty.');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const content = subject ? `Subject: ${subject}\n\n${body}` : body;
      await api.post('/api/prompts', {
        name: templateName.trim(),
        prompt_type: 'CUSTOM_DRAFT',
        content,
        description: description.trim() || `Template created from screenshot: ${templateName.trim()}`,
        is_active: true
      });
      setSuccess(`Template "${templateName.trim()}" saved successfully!`);
      setTimeout(() => {
        onSaved?.();
        handleClose();
      }, 1500);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to save template.');
    } finally {
      setSaving(false);
    }
  };

  const handleClose = () => {
    previews.forEach(p => URL.revokeObjectURL(p));
    setFiles([]);
    setPreviews([]);
    setAnalyzing(false);
    setResult(null);
    setSubject('');
    setBody('');
    setTemplateName('');
    setDescription('');
    setSaving(false);
    setError(null);
    setSuccess(null);
    setStep('upload');
    onClose();
  };

  return (
    <>
      <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[6000] animate-in fade-in duration-300" onClick={handleClose} />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-2xl bg-[#0d1117] border border-white/10 rounded-3xl shadow-[0_0_60px_rgba(0,0,0,0.6)] z-[6001] animate-in zoom-in-95 duration-300 overflow-hidden max-h-[90vh] flex flex-col">
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-rose-500" />

        <div className="p-8 overflow-y-auto flex-1">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-black text-white tracking-tight flex items-center gap-2">
                <Upload className="w-5 h-5 text-blue-400" /> Create Template from Screenshot
              </h2>
              <p className="text-slate-500 text-[11px] mt-0.5 font-medium">
                Upload an email template screenshot — AI extracts & recreates it
              </p>
            </div>
            <button onClick={handleClose} className="text-slate-500 hover:text-white transition-colors cursor-pointer">
              <X className="w-5 h-5" />
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 shrink-0" />
              {error}
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center gap-2 text-green-400 text-sm">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              {success}
            </div>
          )}

          {/* Step 1: Upload */}
          {step === 'upload' && (
            <div>
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-white/10 hover:border-blue-500/40 rounded-2xl p-12 text-center cursor-pointer transition-colors bg-white/[0.02]"
              >
                <Upload className="w-12 h-12 text-slate-600 mx-auto mb-4" />
                <p className="text-white font-bold mb-1">Drop screenshots or click to upload</p>
                <p className="text-slate-500 text-xs">PNG, JPG, JPEG accepted (up to 5 images)</p>
                <input ref={fileInputRef} type="file" accept="image/*" multiple className="hidden" onChange={handleFileSelect} />
              </div>
            </div>
          )}

          {/* Step 2: Preview + Analyze */}
          {step === 'preview' && previews.length > 0 && (
            <div>
              <p className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-3">{files.length} image{files.length > 1 ? 's' : ''} selected</p>
              <div className="grid grid-cols-2 gap-2 mb-4 max-h-80 overflow-y-auto">
                {previews.map((p, i) => (
                  <div key={i} className="relative rounded-xl overflow-hidden border border-white/10 group">
                    <img src={p} alt={`Screenshot ${i + 1}`} className="w-full h-36 object-cover bg-black/40" />
                    <button
                      onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                      className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/70 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                    <span className="absolute bottom-1 left-1 text-[10px] bg-black/70 text-white px-1.5 py-0.5 rounded font-medium">{i + 1}</span>
                  </div>
                ))}
                {files.length < 5 && (
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="h-36 rounded-xl border-2 border-dashed border-white/10 hover:border-blue-500/40 flex items-center justify-center text-slate-600 hover:text-blue-400 transition-colors cursor-pointer bg-white/[0.02]"
                  >
                    <Plus className="w-6 h-6" />
                  </button>
                )}
              </div>
              <div className="flex gap-3">
                <button
                  onClick={() => { previews.forEach(p => URL.revokeObjectURL(p)); setFiles([]); setPreviews([]); setStep('upload'); }}
                  className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-bold text-xs uppercase tracking-widest border border-white/5 cursor-pointer transition-colors"
                >
                  Clear All
                </button>
                <button
                  onClick={handleAnalyze}
                  disabled={analyzing}
                  className="flex-[2] py-3 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-black text-xs uppercase tracking-widest shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50"
                >
                  {analyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  {analyzing ? 'Analyzing...' : `Analyze ${files.length} Image${files.length > 1 ? 's' : ''} with AI`}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Edit */}
          {step === 'edit' && (
            <div className="space-y-4">
              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Template Name</label>
                <input
                  type="text"
                  value={templateName}
                  onChange={(e) => setTemplateName(e.target.value)}
                  placeholder="e.g. my_custom_template"
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium text-sm placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 transition-colors"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Description (optional)</label>
                <input
                  type="text"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief description of this template"
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium text-sm placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 transition-colors"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Subject Line</label>
                <input
                  type="text"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Email subject line"
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium text-sm placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 transition-colors"
                />
              </div>

              <div>
                <label className="text-slate-400 text-xs font-bold uppercase tracking-wider mb-1.5 block">Email Body</label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={14}
                  className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white font-medium text-sm placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 transition-colors font-mono leading-relaxed resize-y"
                />
              </div>

              {result?.formatting_notes && (
                <div className="p-3 rounded-xl bg-yellow-500/5 border border-yellow-500/10">
                  <p className="text-yellow-400 text-xs font-bold uppercase tracking-wider mb-1">Formatting Notes</p>
                  <p className="text-yellow-500/80 text-xs">{result.formatting_notes}</p>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => { setStep('preview'); setResult(null); }}
                  className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-bold text-xs uppercase tracking-widest border border-white/5 cursor-pointer transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !templateName.trim()}
                  className="flex-[2] py-3 px-6 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white font-black text-xs uppercase tracking-widest shadow-lg shadow-green-500/20 flex items-center justify-center gap-2 cursor-pointer transition-all disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                  {saving ? 'Saving...' : 'Save as Template'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
};

export default UploadScreenshotModal;
