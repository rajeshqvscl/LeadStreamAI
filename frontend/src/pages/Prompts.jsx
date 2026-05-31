import React, { useState, useEffect } from 'react';
import { Plus, Loader2, CheckCircle2, AlertCircle, Trash2, ChevronDown, ChevronUp, Save } from 'lucide-react';
import api from '../services/api';

const Prompts = () => {
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [deleting, setDeleting] = useState(null);
  const [form, setForm] = useState({ name: '', content: '', description: '', followup_1: '', followup_2: '', followup_3: '' });

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const userId = user.id || 'admin';

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
      setForm({ name: '', content: '', description: '', followup_1: '', followup_2: '', followup_3: '' });
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
              <textarea value={form.content} onChange={e => setForm({...form, content: e.target.value})} rows={8} className="w-full bg-black/40 border border-white/5 rounded-xl p-4 text-sm text-white font-mono focus:border-blue-500/50 outline-none resize-none" />
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
                  <textarea value={form[`followup_${i}`]} onChange={e => setForm({...form, [`followup_${i}`]: e.target.value})} rows={3} placeholder={`Follow-up ${i} content...`} className="w-full bg-black/40 border border-white/5 rounded-xl p-3 text-xs text-white font-mono focus:border-blue-500/50 outline-none resize-none" />
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
                    <div>
                      <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Body</label>
                      <textarea value={tpl.content} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], content: e.target.value}; setPrompts(updated); }} rows={6} className="w-full bg-black/40 border border-white/5 rounded-xl p-3 text-xs text-white font-mono focus:border-blue-500/50 outline-none resize-none" />
                    </div>
                    {[1, 2, 3].map(i => (
                      <div key={i}>
                        <label className="text-[10px] font-bold text-slate-500 uppercase tracking-widest block mb-1">Follow-up {i}</label>
                        <textarea value={tpl[`followup_${i}`] || ''} onChange={e => { const updated = [...prompts]; const idx = updated.findIndex(p => p.id === tpl.id); updated[idx] = {...updated[idx], [`followup_${i}`]: e.target.value}; setPrompts(updated); }} rows={2} placeholder="(empty)" className="w-full bg-black/40 border border-white/5 rounded-xl p-3 text-xs text-white font-mono focus:border-blue-500/50 outline-none resize-none" />
                      </div>
                    ))}
                    <div className="flex justify-end pt-2">
                      <button onClick={() => handleUpdate(tpl.id, { content: tpl.content, followup_1: tpl.followup_1, followup_2: tpl.followup_2, followup_3: tpl.followup_3 })} disabled={isSaving === tpl.id} className={`btn h-auto py-2.5 px-8 rounded-xl text-[12px] font-black transition-all flex items-center gap-2 border-none shadow-lg ${saveSuccess === tpl.id ? 'bg-emerald-600 text-white' : 'bg-blue-600 hover:bg-blue-500 text-white'}`}>
                        {isSaving === tpl.id ? <Loader2 className="w-4 h-4 animate-spin" /> : saveSuccess === tpl.id ? <><CheckCircle2 className="w-4 h-4" /> SAVED</> : <><Save className="w-4 h-4" /> SAVE</>}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
export default Prompts;
