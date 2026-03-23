import React, { useState, useEffect } from 'react';
import { Sparkles, Save, RotateCcw, Info, Hash, Play, Loader2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const Prompts = () => {
  const [prompts, setPrompts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingId, setEditingId] = useState(null);
  const [editData, setEditData] = useState({ content: '', description: '' });
  const [isSaving, setIsSaving] = useState(false);

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

  const handleEdit = (prompt) => {
    setEditingId(prompt.id);
    setEditData({ content: prompt.content, description: prompt.description || '' });
  };

  const handleSave = async (id) => {
    setIsSaving(true);
    try {
      await api.put(`/api/prompts/${id}`, editData);
      setEditingId(null);
      fetchPrompts();
    } catch (err) {
      alert('Failed to save prompt');
    } finally {
      setIsSaving(false);
    }
  };

  const getTags = (content) => {
    const regex = /\{\{(.*?)\}\}/g;
    const matches = content.match(regex);
    return matches ? [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))] : [];
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">AI Engine Prompts</h1>
          <p className="text-slate-400 text-sm mt-1">Fine-tune the intelligence behind lead classification and email personalization.</p>
        </div>
        <div className="bg-blue-500/10 border border-blue-500/20 px-4 py-2 rounded-xl flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_#3b82f6]"></div>
          <span className="text-[11px] font-black text-blue-400 uppercase tracking-widest">GPT-4o Integration Active</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {isLoading ? (
          <div className="md:col-span-2 py-32 flex flex-col items-center justify-center opacity-50">
            <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
            <p className="text-slate-400 font-medium">Loading LLM instructions...</p>
          </div>
        ) : prompts.length === 0 ? (
          <div className="md:col-span-2 py-20 text-center text-slate-500 border border-dashed border-white/10 rounded-3xl">
            No prompts found. Re-run backend migrations to seed defaults.
          </div>
        ) : prompts.map((prompt) => (
          <div key={prompt.id} className="card bg-slate-800/40 border-white/5 hover:border-blue-500/30 transition-all backdrop-blur-sm group p-6 shadow-xl relative overflow-hidden">
            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500/50 opacity-0 group-hover:opacity-100 transition-opacity"></div>
            
            <div className="flex justify-between items-start mb-6">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-white/5 flex items-center justify-center shadow-inner group-hover:scale-110 transition-transform">
                  <Sparkles className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-white font-bold leading-tight uppercase tracking-tight">{prompt.name}</h3>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Type:</span>
                    <span className="text-[10px] font-black text-blue-500 uppercase tracking-widest bg-blue-500/10 px-1.5 py-0.5 rounded">{prompt.prompt_type}</span>
                  </div>
                </div>
              </div>
              
              {editingId === prompt.id ? (
                <div className="flex gap-2">
                  <button 
                    onClick={() => setEditingId(null)}
                    className="btn btn-ghost py-2 px-3 h-auto"
                  >
                    <RotateCcw className="w-4 h-4" />
                  </button>
                  <button 
                    onClick={() => handleSave(prompt.id)}
                    disabled={isSaving}
                    className="btn btn-primary py-2 px-4 h-auto shadow-blue-500/20"
                  >
                    {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Save className="w-4 h-4 mr-2" /> Save</>}
                  </button>
                </div>
              ) : (
                <button 
                  onClick={() => handleEdit(prompt)}
                  className="btn btn-ghost py-2 px-4 h-auto border-white/10 hover:border-blue-500/30"
                >
                  Edit Instruction
                </button>
              )}
            </div>

            <div className="space-y-4">
              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest flex items-center gap-1.5 ml-1">
                  <Play className="w-2.5 h-2.5 fill-slate-500" /> System Instruction
                </label>
                {editingId === prompt.id ? (
                  <textarea 
                    className="form-control min-h-[160px] bg-slate-950 font-mono text-xs leading-relaxed border-blue-500/30"
                    value={editData.content}
                    onChange={(e) => setEditData({ ...editData, content: e.target.value })}
                  />
                ) : (
                  <div className="bg-slate-900/50 border border-white/5 rounded-2xl p-4 text-[13px] text-slate-400 leading-relaxed min-h-[120px] font-medium italic">
                    {prompt.content}
                  </div>
                )}
              </div>

              <div className="flex flex-col gap-2">
                <label className="text-[10px] font-extrabold text-slate-500 uppercase tracking-widest flex items-center gap-1.5 ml-1">
                  <Hash className="w-3 h-3" /> Predicted Variables
                </label>
                <div className="flex flex-wrap gap-2">
                  {getTags(prompt.content).length > 0 ? getTags(prompt.content).map(tag => (
                    <span key={tag} className="px-2 py-1 rounded-lg bg-slate-900/80 border border-white/10 text-[10px] font-bold text-slate-300 font-mono">
                      {tag}
                    </span>
                  )) : (
                    <span className="text-[10px] text-slate-600 font-bold uppercase py-1">No dynamic tags detected</span>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-8 pt-5 border-t border-white/5 flex items-center gap-2 opacity-60">
              <Info className="w-4 h-4 text-blue-400" />
              <p className="text-[11px] text-slate-400 font-medium">
                {editingId === prompt.id ? 'Changes will take effect instantly for all new AI operations.' : (prompt.description || 'This prompt controls how the AI analyzes and generates outbound content.')}
              </p>
            </div>
            
            <div className="absolute bottom-4 right-4 flex items-center gap-2 text-[9px] font-black text-slate-600 uppercase tracking-widest pointer-events-none group-hover:opacity-100 opacity-0 transition-opacity">
              <AlertCircle className="w-3 h-3" /> Advanced Override
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Prompts;
