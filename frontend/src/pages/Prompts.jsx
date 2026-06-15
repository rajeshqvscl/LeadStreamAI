import React, { useState, useEffect } from 'react';
import { Plus, Loader2, CheckCircle2, AlertCircle, Trash2, ChevronDown, ChevronUp, Save, Upload, Paperclip, AtSign } from 'lucide-react';
import api from '../services/api';
import ToolbarTextarea from '../components/ToolbarTextarea';

const Prompts = () => {
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [preview, setPreview] = useState({ show: false, content: '', label: '', subject: '' });
  const [attaching, setAttaching] = useState(null);
  const [form, setForm] = useState({ name: '', content: '', description: '', followup_1: '', followup_2: '', followup_3: '', subject: '', cc: '' });
  const [saveField, setSaveField] = useState({ id: null, field: null });
  const [saveFieldSuccess, setSaveFieldSuccess] = useState({ id: null, field: null });

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 'admin';
  const userSenderName = user.name || user.full_name || user.username || 'Your Name';
  const userTitle = user.job_title || user.designation || 'Analyst';
  const userPhone = user.phone || '+91-9876543210';
  const userLinkedin = user.linkedin_url || 'https://www.linkedin.com/company/qvscl/';

  const fetchPrompts = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/api/custom-draft-templates', { headers: { 'X-User-Id': userId } });
      setPrompts(res.data || []);
    } catch (err) {
      console.error('Failed to fetch prompts', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchPrompts(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim() || !form.content.trim()) return alert('Name and Body are required');
    try {
      await api.post('/api/custom-draft-templates', form, { headers: { 'X-User-Id': userId } });
      setForm({ name: '', content: '', description: '', followup_1: '', followup_2: '', followup_3: '', subject: '', cc: '' });
      setShowForm(false);
      fetchPrompts();
    } catch (err) {
      alert('Failed to create template');
    }
  };

  const handleUpdate = async (id, data) => {
    setIsSaving(id);
    try {
      await api.put(`/api/prompts/${id}`, data);
      setSaveSuccess(id);
      setTimeout(() => setSaveSuccess(null), 3000);
      fetchPrompts();
    } catch (err) {
      alert('Failed to save');
    } finally {
      setIsSaving(null);
    }
  };

  const handleFieldSave = async (id, field, value) => {
    setSaveField({ id, field });
    try {
      await api.put(`/api/prompts/${id}`, { [field]: value });
      setSaveFieldSuccess({ id, field });
      setTimeout(() => setSaveFieldSuccess({ id: null, field: null }), 2000);
      fetchPrompts();
    } catch (err) {
      alert('Failed to save');
    } finally {
      setSaveField({ id: null, field: null });
    }
  };

  const handleAttachment = async (id, file) => {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith('.pdf')) return alert('Only PDF files are allowed');
    setAttaching(id);
    const formData = new FormData();
    formData.append('file', file);
    try {
      await api.post(`/api/prompts/${id}/attachment`, formData);
      fetchPrompts();
    } catch (err) {
      alert('Failed to upload attachment');
    } finally {
      setAttaching(null);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this template permanently?')) return;
    setDeleting(id);
    try {
      await api.delete(`/api/prompts/${id}`, { headers: { 'X-User-Id': userId } });
      fetchPrompts();
    } catch (err) {
      alert('Failed to delete');
    } finally {
      setDeleting(null);
    }
  };

  const renderEmailPreview = (text, showSigDisc = true) => {
    if (!text) return '<p class="text-slate-500 italic">(empty)</p>';
    const backendUrl = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
    text = text.replace(/\[\[BACKEND_URL\]\]/g, backendUrl);
    text = text.replace(/\{\{First Name\}\}/g, 'Harsh');
    text = text.replace(/\{\{Company Name\}\}/g, 'ABC Corp');
    text = text.replace(/\{\{Sender First Name\}\}/g, userSenderName.split(' ')[0] || 'Your');
    text = text.replace(/\{\{Sender Name\}\}/g, userSenderName);
    text = text.replace(/\{\{Sender Title\}\}/g, userTitle);
    text = text.replace(/\{\{Sender LinkedIn\}\}/g, userLinkedin);
    text = text.replace(/\{\{Sender Phone\}\}/g, userPhone);

    // Strip SIG_START...SIG_END from display
    const sigStartIdx = text.indexOf('SIG_START');
    const sigEndIdx = text.indexOf('SIG_END');
    let mainText = text;
    let afterSig = '';
    if (sigStartIdx !== -1) {
      mainText = text.substring(0, sigStartIdx);
      if (sigEndIdx !== -1) {
        afterSig = text.substring(sigEndIdx + 8).trim();
      }
    }

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
          if (match) listHtml += `<li style="margin-bottom: 0.4em; position: relative; padding-left: 14px; line-height: 1.6; color: #cbd5e1;"><span style="position: absolute; left: 0; color: #94a3b8; font-size: 9px; top: 0px; display: inline-block; vertical-align: middle;">•</span>${match[1].trim()}</li>`;
          else if (l.trim()) listHtml += ` ${l.trim()}`;
        });
        listHtml += '</ul>';
        htmlParts.push(listHtml);
      } else if (isOrdered) {
        let listHtml = '<ol style="margin: 1em 0; padding-left: 1.5em; list-style-type: decimal;">';
        lines.forEach(l => {
          const match = l.trim().match(/^\d+\.\s+(.*)/);
          if (match) listHtml += `<li style="margin-bottom: 0.5em; color: #cbd5e1;">${match[1].trim()}</li>`;
          else if (l.trim()) listHtml += ` ${l.trim()}`;
        });
        listHtml += '</ol>';
        htmlParts.push(listHtml);
      } else {
        let content = trimmed.replace(/\n/g, '<br />');
        content = content.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/_(.*?)_/g, '<em>$1</em>').replace(/\*(.*?)\*/g, '<em>$1</em>').replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>');
        htmlParts.push(`<p style="margin-bottom: 1em; color: #cbd5e1;">${content}</p>`);
      }
    });

    let afterHtml = '';
    if (afterSig) {
      const afterParagraphs = afterSig.split('\n\n').filter(p => p.trim());
      afterHtml = afterParagraphs.map(p => {
        let content = p.replace(/\n/g, '<br />');
        content = content.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/_(.*?)_/g, '<em>$1</em>').replace(/\*(.*?)\*/g, '<em>$1</em>').replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color:#3b82f6; text-decoration:underline;">$1</a>');
        return `<p style="margin-top:1.2em; color:#94a3b8; font-size:12px;">${content}</p>`;
      }).join('');
    }

    // Auto signature
    let autoSigHtml = '';
    if (showSigDisc) {
      autoSigHtml = `
        <div style="margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 10px; font-family: sans-serif;">
          <div style="color: #475569; margin-bottom: 2px;">--</div>
          <div style="color: #e2e8f0; font-weight: 700;">${userSenderName}</div>
          <div style="color: #94a3b8; font-size: 12px;">${userTitle}</div>
          <a href="${userLinkedin}" target="_blank" style="color: #3b82f6; font-weight: 700; font-size: 12px; text-decoration: underline; display: block; margin-top: 2px;">LinkedIn</a>
          <div style="color: #94a3b8; font-size: 12px;">${userPhone}</div>
          <div style="margin-top: 12px; padding: 10px; background: rgba(239,68,68,0.06); border: 1px solid rgba(239,68,68,0.12); border-radius: 8px; color: #94a3b8; font-size: 10px; line-height: 1.5;">
            Important: This message and its attachments are intended only for the addressee and may contain legally privileged and/or confidential information. If you are not the intended recipient, you are hereby notified that you must not use, disseminate, or copy this material in any form, or take any action based upon it. If you have received this message by error, please immediately delete it and its attachments and notify the sender at QV Strategic Consulting LLP by electronic mail message reply. Thank you.
          </div>
        </div>`;
    }

    let finalHtml = htmlParts.join('') + afterHtml + autoSigHtml;
    finalHtml = finalHtml.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>').replace(/\*\*(.*?)\*\*/g, '<strong style="color: white; font-weight: 800;">$1</strong>').replace(/_(.*?)_/g, '<em style="font-style:italic">$1</em>').replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 700;">$1</a>');
    return finalHtml;
  };

  return (
    <div className="max-w-[1200px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h1 className="text-[28px] font-black text-white tracking-tight">My Templates</h1>
          <p className="text-slate-400 text-sm mt-1 font-medium italic">
            Create and manage your own draft templates with follow-ups
          </p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn bg-blue-600 hover:bg-blue-500 text-white border-none py-2.5 px-6 rounded-xl flex items-center gap-2 shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all hover:scale-105 active:scale-95">
          <Plus className="w-4 h-4" />
          <span className="text-[13px] font-bold">{showForm ? 'Cancel' : 'New Template'}</span>
        </button>
      </div>

      {showForm && (
        <div className="mb-10 bg-[#0f121b] border border-white/5 rounded-[24px] p-8">
          <h2 className="text-lg font-black text-white mb-6">Create Custom Template</h2>
          <div className="space-y-4">
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Template Name</label>
              <input value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="e.g. My Custom Draft" className="w-full bg-black/40 border border-white/5 rounded-xl p-4 text-sm text-white focus:border-blue-500/50 outline-none" />
            </div>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Email Body</label>
              <p className="text-[10px] text-slate-600 mb-2">Use placeholders: {'{{First Name}}'}, {'{{Company Name}}'}, {'{{Sender Name}}'}</p>
              <ToolbarTextarea value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={8} placeholder="Write your email body here..." />
            </div>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Subject (optional)</label>
              <input value={form.subject} onChange={e => setForm({...form, subject: e.target.value})} placeholder="e.g. Strategic Partnership Opportunity – JV & Investment" className="w-full bg-black/40 border border-white/5 rounded-xl p-4 text-sm text-white focus:border-blue-500/50 outline-none" />
            </div>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">CC Email (optional)</label>
              <input value={form.cc} onChange={e => setForm({...form, cc: e.target.value})} placeholder="e.g. team@qvscl.com" className="w-full bg-black/40 border border-white/5 rounded-xl p-4 text-sm text-white focus:border-blue-500/50 outline-none" />
            </div>
            <div>
              <label className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 block">Description (optional)</label>
              <input value={form.description} onChange={e => setForm({...form, description: e.target.value})} placeholder="Brief description" className="w-full bg-black/40 border border-white/5 rounded-xl p-4 text-sm text-white focus:border-blue-500/50 outline-none" />
            </div>
            <div className="border-t border-white/5 pt-6">
              <h3 className="text-sm font-bold text-white mb-4">Follow-up Emails</h3>
              <p className="text-[10px] text-slate-600 mb-4">Write your own follow-ups. Same placeholders work here too.</p>
              {[1, 2, 3].map(i => (
                <div key={i} className="mb-3">
                  <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1.5 block">Follow-up {i}</label>
                  <div className="flex gap-2">
                    <ToolbarTextarea value={form[`followup_${i}`]} onChange={e => setForm({...form, [`followup_${i}`]: e.target.value})} rows={3} placeholder={`Follow-up ${i} content...`} />
                    <button onClick={() => setPreview({ show: true, content: form[`followup_${i}`], label: `Follow-up ${i}`, attachment: null })} className="self-start px-3 py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded-lg text-[10px] font-bold border border-blue-500/20 whitespace-nowrap transition-all">Preview</button>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={handleCreate} className="btn bg-emerald-600 hover:bg-emerald-500 text-white border-none py-3 px-8 rounded-xl text-sm font-bold">Save Template</button>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading...</p>
        </div>
      ) : prompts.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-white/5 rounded-[32px] bg-white/[0.02]">
          <AlertCircle className="w-12 h-12 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-500 font-medium">No custom templates yet.</p>
          <button onClick={() => setShowForm(true)} className="mt-4 text-blue-400 text-sm font-bold hover:text-blue-300">Create your first template</button>
        </div>
      ) : (
        <div className="space-y-4">
          {prompts.map((tpl) => {
            const isExpanded = expandedId === tpl.id;
            return (
              <div key={tpl.id} className="bg-[#0f121b] border border-white/5 rounded-[20px] overflow-hidden group">
                <div className="p-6 flex items-center justify-between cursor-pointer" onClick={() => setExpandedId(isExpanded ? null : tpl.id)}>
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="text-base font-bold text-white">{tpl.name}</h3>
                      <span className="px-2 py-0.5 rounded text-[9px] font-black tracking-[1px] border uppercase bg-purple-500/10 text-purple-500 border-purple-500/20">Custom Draft</span>
                    </div>
                    {tpl.description && <p className="text-xs text-slate-500 mt-1">{tpl.description}</p>}
                  </div>
                  <div className="flex items-center gap-3">
                    <button onClick={(e) => { e.stopPropagation(); handleDelete(tpl.id); }} disabled={deleting === tpl.id} className="p-2 rounded-lg hover:bg-red-500/10 text-slate-600 hover:text-red-400 transition-all">
                      {deleting === tpl.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                    </button>
                    {isExpanded ? <ChevronUp className="w-5 h-5 text-slate-500" /> : <ChevronDown className="w-5 h-5 text-slate-500" />}
                  </div>
                </div>

                {isExpanded && (
                  <div className="px-6 pb-6 border-t border-white/5 pt-4 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Subject</label>
                        <div className="flex gap-2">
                          <input value={tpl.subject || ''} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], subject: e.target.value}; setPrompts(updated); }} placeholder="Email subject line..." className="flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-blue-500/50 outline-none" />
                          <button onClick={() => handleFieldSave(tpl.id, 'subject', tpl.subject || '')} disabled={saveField.id === tpl.id && saveField.field === 'subject'} className={`px-3 py-2 rounded-xl text-[10px] font-bold border border-white/10 whitespace-nowrap transition-all ${saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'subject' ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10'}`}>
                            {saveField.id === tpl.id && saveField.field === 'subject' ? <Loader2 className="w-3 h-3 animate-spin" /> : saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'subject' ? <CheckCircle2 className="w-3 h-3" /> : 'Save'}
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">CC Email</label>
                        <div className="flex gap-2">
                          <input value={tpl.cc || ''} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], cc: e.target.value}; setPrompts(updated); }} placeholder="cc@email.com" className="flex-1 bg-black/40 border border-white/5 rounded-xl px-4 py-2.5 text-sm text-white focus:border-blue-500/50 outline-none" />
                          <button onClick={() => handleFieldSave(tpl.id, 'cc', tpl.cc || '')} disabled={saveField.id === tpl.id && saveField.field === 'cc'} className={`px-3 py-2 rounded-xl text-[10px] font-bold border border-white/10 whitespace-nowrap transition-all ${saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'cc' ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10'}`}>
                            {saveField.id === tpl.id && saveField.field === 'cc' ? <Loader2 className="w-3 h-3 animate-spin" /> : saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'cc' ? <CheckCircle2 className="w-3 h-3" /> : 'Save'}
                          </button>
                        </div>
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Body</label>
                      <div className="flex gap-2">
                        <ToolbarTextarea value={tpl.content} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], content: e.target.value}; setPrompts(updated); }} rows={6} placeholder="Email body..." />
                        <div className="flex flex-col gap-2">
                          <button onClick={() => setPreview({ show: true, content: tpl.content, label: 'Body', subject: tpl.subject, attachment: tpl.attachment_file })} className="px-3 py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded-lg text-[10px] font-bold border border-blue-500/20 whitespace-nowrap transition-all">Preview</button>
                          <button onClick={() => handleFieldSave(tpl.id, 'content', tpl.content)} disabled={saveField.id === tpl.id && saveField.field === 'content'} className={`px-3 py-2 rounded-lg text-[10px] font-bold border whitespace-nowrap transition-all ${saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'content' ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 border-white/10'}`}>
                            {saveField.id === tpl.id && saveField.field === 'content' ? <Loader2 className="w-3 h-3 animate-spin" /> : saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === 'content' ? <CheckCircle2 className="w-3 h-3" /> : 'Save'}
                          </button>
                        </div>
                      </div>
                    </div>
                    {[1, 2, 3].map(i => (
                      <div key={i}>
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Follow-up {i}</label>
                        <div className="flex gap-2">
                          <ToolbarTextarea value={tpl[`followup_${i}`] || ''} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], [`followup_${i}`]: e.target.value}; setPrompts(updated); }} rows={2} placeholder="(empty)" />
                          <div className="flex flex-col gap-2">
                            <button onClick={() => setPreview({ show: true, content: tpl[`followup_${i}`] || '', label: `Follow-up ${i}`, subject: tpl.subject, attachment: null })} className="px-3 py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded-lg text-[10px] font-bold border border-blue-500/20 whitespace-nowrap transition-all">Preview</button>
                            <button onClick={() => handleFieldSave(tpl.id, `followup_${i}`, tpl[`followup_${i}`] || '')} disabled={saveField.id === tpl.id && saveField.field === `followup_${i}`} className={`px-3 py-2 rounded-lg text-[10px] font-bold border whitespace-nowrap transition-all ${saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === `followup_${i}` ? 'bg-emerald-600/20 text-emerald-400 border-emerald-500/30' : 'bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 border-white/10'}`}>
                              {saveField.id === tpl.id && saveField.field === `followup_${i}` ? <Loader2 className="w-3 h-3 animate-spin" /> : saveFieldSuccess.id === tpl.id && saveFieldSuccess.field === `followup_${i}` ? <CheckCircle2 className="w-3 h-3" /> : 'Save'}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                    <div className="border-t border-white/5 pt-4">
                      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-2">Attachment</label>
                      <div className="flex items-center gap-3">
                        {tpl.attachment_file ? (
                          <div className="flex items-center gap-2 text-xs text-slate-400 bg-black/30 px-3 py-1.5 rounded-lg border border-white/5">
                            <Paperclip className="w-3.5 h-3.5 text-blue-400" />
                            <span>{tpl.attachment_file}</span>
                            <button onClick={() => {
                              const updated = [...prompts];
                              const idx = updated.findIndex(p => p.id === tpl.id);
                              updated[idx] = {...updated[idx], attachment_file: null};
                              setPrompts(updated);
                            }} className="text-red-400 hover:text-red-300 ml-1">&times;</button>
                          </div>
                        ) : (
                          <label className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border border-dashed border-white/10 text-xs text-slate-400 hover:text-white hover:border-blue-500/50 cursor-pointer transition-all ${attaching === tpl.id ? 'opacity-50' : ''}`}>
                            {attaching === tpl.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                            {attaching === tpl.id ? 'Uploading...' : 'Attach PDF'}
                            <input type="file" accept=".pdf" className="hidden" disabled={attaching === tpl.id} onChange={e => { const f = e.target.files[0]; if (f) handleAttachment(tpl.id, f); e.target.value = ''; }} />
                          </label>
                        )}
                      </div>
                    </div>
                    <div className="flex justify-end pt-2">
                      <button onClick={() => handleUpdate(tpl.id, { subject: tpl.subject || null, cc: tpl.cc || null, content: tpl.content, followup_1: tpl.followup_1, followup_2: tpl.followup_2, followup_3: tpl.followup_3 })} disabled={isSaving === tpl.id} className={`btn h-auto py-2.5 px-8 rounded-xl text-[12px] font-black transition-all flex items-center gap-2 border-none shadow-lg ${saveSuccess === tpl.id ? 'bg-emerald-600 text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}>
                        {isSaving === tpl.id ? <Loader2 className="w-4 h-4 animate-spin" /> : saveSuccess === tpl.id ? <><CheckCircle2 className="w-4 h-4" /> SAVED</> : <><Save className="w-4 h-4" /> SAVE ALL</>}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {preview.show && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm" onClick={() => setPreview({ show: false, content: '', label: '' })}>
          <div className="bg-[#0a0d14] border border-white/10 rounded-[24px] w-full max-w-3xl max-h-[85vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
              <h3 className="text-sm font-bold text-white">Preview — {preview.label}</h3>
              <button onClick={() => setPreview({ show: false, content: '', label: '' })} className="text-slate-500 hover:text-white text-lg leading-none">&times;</button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[75vh]">
              {preview.subject && (
                <div className="mb-4 px-3 py-2 bg-slate-800/50 border border-slate-700/50 rounded-lg text-xs">
                  <span className="text-slate-500 font-bold uppercase tracking-wider">Subject: </span>
                  <span className="text-blue-300 font-medium">{preview.subject}</span>
                </div>
              )}
              {preview.attachment && (
                <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-blue-500/10 border border-blue-500/20 rounded-lg text-xs text-blue-300">
                  <Paperclip className="w-3.5 h-3.5" />
                  <span className="font-medium">{preview.attachment}</span>
                  <span className="text-blue-400/50 ml-auto">attached</span>
                </div>
              )}
              <div className="email-preview text-slate-300 text-[14px] leading-relaxed" dangerouslySetInnerHTML={{ __html: renderEmailPreview(preview.content) }} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
export default Prompts;
