import React, { useState, useEffect } from 'react';
import { Sparkles, Save, Plus, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const Prompts = () => {
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(null); // stores ID of saving prompt
  const [saveSuccess, setSaveSuccess] = useState(null);

  const fetchPrompts = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/prompts');
      setPrompts(response.data || []);
    } catch (err) {
      console.error('Failed to fetch prompts', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchPrompts();
  }, []);

  const handleUpdate = (id, field, value) => {
    setPrompts(prev => prev.map(p => p.id === id ? { ...p, [field]: value } : p));
  };

  const onSave = async (prompt) => {
    setIsSaving(prompt.id);
    try {
      await api.put(`/api/prompts/${prompt.id}`, {
        name: prompt.name,
        prompt_type: prompt.prompt_type,
        content: prompt.content,
        description: prompt.description,
        is_active: prompt.is_active
      });
      setSaveSuccess(prompt.id);
      setTimeout(() => setSaveSuccess(null), 3000);
    } catch (err) {
      alert('Failed to save prompt');
    } finally {
      setIsSaving(null);
    }
  };

  const getBadgeColor = (type) => {
    switch (type) {
      case 'CLASSIFICATION': return 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20';
      case 'EMAIL_GENERATION': return 'bg-blue-500/10 text-blue-500 border-blue-500/20';
      case 'STRATEGY': return 'bg-purple-500/10 text-purple-500 border-purple-500/20';
      case 'CONTEXT': return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  return (
    <div className="max-w-[1200px] mx-auto animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex justify-between items-start mb-10">
        <div>
          <h1 className="text-[28px] font-black text-white tracking-tight flex items-center gap-3">
            AI Prompts
          </h1>
          <p className="text-slate-400 text-sm mt-1 font-medium italic">
            Manage prompt templates for classification and email generation
          </p>
        </div>
        <button className="btn bg-blue-600 hover:bg-blue-500 text-white border-none py-2.5 px-6 rounded-xl flex items-center gap-2 shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all hover:scale-105 active:scale-95">
          <Plus className="w-4 h-4" />
          <span className="text-[13px] font-bold">New Prompt</span>
        </button>
      </div>

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Syncing with backend...</p>
        </div>
      ) : prompts.length === 0 ? (
        <div className="py-20 text-center border-2 border-dashed border-white/5 rounded-[32px] bg-white/[0.02]">
          <AlertCircle className="w-12 h-12 text-slate-700 mx-auto mb-4" />
          <p className="text-slate-500 font-medium">No prompt templates initialized yet.</p>
        </div>
      ) : (
        <div className="space-y-8">
          {prompts.map((prompt) => (
            <div key={prompt.id} className="group relative">
              <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500/20 to-purple-500/20 rounded-[24px] blur opacity-0 group-hover:opacity-100 transition duration-1000"></div>
              
              <div className="relative bg-[#0f121b] border border-white/5 rounded-[24px] overflow-hidden shadow-2xl transition-all">
                <div className="p-8">
                  <div className="flex justify-between items-start mb-6">
                    <div className="space-y-1">
                      <h3 className="text-lg font-black text-white tracking-tight">{prompt.name}</h3>
                      <div className="flex items-center gap-2">
                        <span className={`px-2 py-0.5 rounded text-[9px] font-black tracking-[1px] border uppercase ${getBadgeColor(prompt.prompt_type)}`}>
                          {prompt.prompt_type.replace('_', ' ')}
                        </span>
                        {prompt.is_active && (
                          <span className="bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-2 py-0.5 rounded text-[9px] font-black tracking-[1px] uppercase flex items-center gap-1">
                            <CheckCircle2 className="w-2.5 h-2.5" /> ACTIVE
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <p className="text-[12px] text-slate-500 mb-6 font-medium leading-relaxed">
                    {prompt.description || "System instruction for AI model processing."}
                  </p>

                  <div className="space-y-3">
                    <div className="flex justify-between items-center px-1">
                      <label className="text-[11px] font-extrabold text-slate-400 uppercase tracking-widest">Prompt Content</label>
                    </div>
                    <div className="relative">
                      <textarea
                        value={prompt.content}
                        onChange={(e) => handleUpdate(prompt.id, 'content', e.target.value)}
                        className="w-full bg-black/40 border border-white/5 rounded-2xl p-6 text-[13px] text-slate-300 font-mono leading-relaxed focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/5 transition-all outline-none resize-none min-h-[160px]"
                        spellCheck="false"
                      />
                      <div className="absolute top-4 right-4 opacity-20 group-hover:opacity-100 transition-opacity">
                        <Sparkles className="w-4 h-4 text-blue-400" />
                      </div>
                    </div>
                  </div>

                  <div className="mt-8 flex items-center justify-between pt-6 border-t border-white/5">
                    <label className="flex items-center gap-3 cursor-pointer group/toggle">
                      <div className="relative">
                        <input
                          type="checkbox"
                          checked={prompt.is_active}
                          onChange={(e) => handleUpdate(prompt.id, 'is_active', e.target.checked)}
                          className="sr-only"
                        />
                        <div className={`w-10 h-5 rounded-full transition-colors ${prompt.is_active ? 'bg-blue-600' : 'bg-slate-800'} border border-white/5`}></div>
                        <div className={`absolute top-1 left-1 w-3 h-3 rounded-full bg-white transition-transform ${prompt.is_active ? 'translate-x-5' : 'translate-x-0'}`}></div>
                      </div>
                      <span className="text-[11px] font-bold text-slate-400 group-hover/toggle:text-white transition-colors">Active</span>
                    </label>

                    <button
                      onClick={() => onSave(prompt)}
                      disabled={isSaving === prompt.id}
                      className={`btn h-auto py-2.5 px-8 rounded-xl text-[12px] font-black transition-all flex items-center gap-2 ${
                        saveSuccess === prompt.id 
                          ? 'bg-emerald-600 hover:bg-emerald-500 text-white' 
                          : 'bg-blue-600 hover:bg-blue-500 text-white'
                      } border-none shadow-lg`}
                    >
                      {isSaving === prompt.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : saveSuccess === prompt.id ? (
                        <><CheckCircle2 className="w-4 h-4" /> SAVED</>
                      ) : (
                        <><Save className="w-4 h-4" /> SAVE</>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      
      <div className="mt-20 p-10 rounded-[32px] bg-gradient-to-br from-blue-600/5 to-purple-600/5 border border-white/5">
        <div className="flex gap-6 items-start">
          <div className="w-12 h-12 rounded-2xl bg-blue-600/10 flex items-center justify-center shrink-0">
            <AlertCircle className="w-6 h-6 text-blue-500" />
          </div>
          <div className="space-y-2">
            <h4 className="text-white font-bold text-sm">System Variables</h4>
            <p className="text-slate-500 text-[12px] leading-relaxed max-w-[800px]">
              Use double curly brackets <code className="bg-white/5 px-1.5 py-0.5 rounded text-blue-400 font-mono">{"{{variable}}"}</code> to inject dynamic data into your prompts. 
              Commonly used: name, email, designation, company_name, industry, context, tone.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Prompts;
