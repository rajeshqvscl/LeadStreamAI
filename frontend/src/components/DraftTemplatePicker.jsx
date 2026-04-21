import React, { useState, useEffect } from 'react';
import { Sparkles, Loader2, X } from 'lucide-react';
import api from '../services/api';

/**
 * Reusable template picker modal.
 * Props:
 *   isOpen          — boolean
 *   onClose         — () => void
 *   selectedCount   — number of selected leads/companies
 *   onGenerate      — async (templateName: string) => void
 *                     called with 'ai' or a custom template name
 */
const DraftTemplatePicker = ({ isOpen, onClose, selectedCount, onGenerate }) => {
  const [customTemplates, setCustomTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('ai');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    api.get('/api/custom-draft-templates')
      .then(r => setCustomTemplates(r.data || []))
      .catch(() => {});
  }, []);

  // Reset selection whenever modal opens
  useEffect(() => {
    if (isOpen) setSelectedTemplate('ai');
  }, [isOpen]);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      await onGenerate(selectedTemplate);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/80 backdrop-blur-md z-[5000] animate-in fade-in duration-300"
        onClick={onClose}
      />
      <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-[#0d1117] border border-white/10 rounded-3xl shadow-[0_0_60px_rgba(0,0,0,0.6)] z-[5001] animate-in zoom-in-95 duration-300 overflow-hidden">
        {/* Top gradient bar */}
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-gradient-to-r from-blue-500 via-purple-500 to-rose-500" />

        <div className="p-8">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-black text-white tracking-tight flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-blue-400" /> Choose Draft Template
              </h2>
              <p className="text-slate-500 text-[11px] mt-0.5 font-medium">
                Generating for <span className="text-white font-bold">{selectedCount}</span> selected item{selectedCount !== 1 ? 's' : ''}
              </p>
            </div>
            <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors cursor-pointer">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Options */}
          <div className="space-y-3 mb-8">
            {/* Regular AI */}
            <label className={`flex items-start gap-4 p-4 rounded-2xl border cursor-pointer transition-all ${selectedTemplate === 'ai' ? 'border-blue-500/60 bg-blue-500/10' : 'border-white/8 bg-white/[0.02] hover:border-white/15'}`}>
              <input type="radio" name="tpl" value="ai" className="sr-only" checked={selectedTemplate === 'ai'} onChange={() => setSelectedTemplate('ai')} />
              <div className={`mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${selectedTemplate === 'ai' ? 'border-blue-500' : 'border-slate-600'}`}>
                {selectedTemplate === 'ai' && <div className="w-2 h-2 rounded-full bg-blue-500" />}
              </div>
              <div>
                <p className="text-white font-bold text-sm flex items-center gap-2">
                  🤖 Regular AI Draft
                  <span className="text-[9px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-black uppercase tracking-wider">Default</span>
                </p>
                <p className="text-slate-500 text-[11px] mt-0.5">AI generates a personalized email based on the lead's profile, industry, and persona.</p>
              </div>
            </label>

            {/* Custom templates */}
            {customTemplates.map(tpl => (
              <label key={tpl.name} className={`flex items-start gap-4 p-4 rounded-2xl border cursor-pointer transition-all ${selectedTemplate === tpl.name ? 'border-purple-500/60 bg-purple-500/10' : 'border-white/8 bg-white/[0.02] hover:border-white/15'}`}>
                <input type="radio" name="tpl" value={tpl.name} className="sr-only" checked={selectedTemplate === tpl.name} onChange={() => setSelectedTemplate(tpl.name)} />
                <div className={`mt-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${selectedTemplate === tpl.name ? 'border-purple-500' : 'border-slate-600'}`}>
                  {selectedTemplate === tpl.name && <div className="w-2 h-2 rounded-full bg-purple-500" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-bold text-sm flex items-center gap-2">
                    📝 {tpl.name}
                    <span className="text-[9px] bg-purple-500/10 text-purple-400 border border-purple-500/20 px-1.5 py-0.5 rounded font-black uppercase tracking-wider">Custom</span>
                  </p>
                  <p className="text-slate-500 text-[11px] mt-0.5">{tpl.description || 'Custom template with lead name & company auto-filled.'}</p>
                  <p className="text-slate-600 text-[10px] mt-1.5 font-mono truncate">{tpl.content?.substring(0, 90)}...</p>
                </div>
              </label>
            ))}
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-bold text-xs uppercase tracking-widest border border-white/5 cursor-pointer transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex-[2] py-3 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-black text-xs uppercase tracking-widest shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer transition-all"
            >
              {isGenerating
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                : <><Sparkles className="w-4 h-4" /> Generate {selectedCount} Draft{selectedCount !== 1 ? 's' : ''}</>
              }
            </button>
          </div>
        </div>
      </div>
    </>
  );
};

export default DraftTemplatePicker;
