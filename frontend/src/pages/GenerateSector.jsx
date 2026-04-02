import React, { useState, useEffect } from 'react';
import { Sparkles, Plus, Settings2, Filter, ChevronDown, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import api from '../services/api';

const GenerateSector = () => {
  const [sectors, setSectors] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newSectorName, setNewSectorName] = useState('');
  const [generatingSector, setGeneratingSector] = useState(null);
  const [notification, setNotification] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchSectors = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/generate/sectors');
      setSectors(response.data.sectors || []);
      setCampaigns(response.data.campaigns || []);
    } catch (err) {
      console.error('Failed to fetch sectors', err);
      // Mock data for UI development if API is missing
      setSectors([
        // DO'S
        { sector: 'DEEP_TECH', display_name: 'Deep Tech', count: 15, total: 42, context: '', strategy: '' },
        { sector: 'HIGH_TECH', display_name: 'High Tech', count: 15, total: 38, context: '', strategy: '' },
        { sector: 'SAAS', display_name: 'SAAS', count: 15, total: 65, context: '', strategy: '' },
        { sector: 'DEFENCE_TECH', display_name: 'Defence Tech', count: 15, total: 28, context: '', strategy: '' },
        { sector: 'TRAVEL', display_name: 'Travel', count: 15, total: 35, context: '', strategy: '' },
        { sector: 'AUTOMOTIVE', display_name: 'Automotive', count: 15, total: 30, context: '', strategy: '' },
        { sector: 'AI_INFRA', display_name: 'AI Infra', count: 15, total: 55, context: '', strategy: '' },
        { sector: 'AI_INTEL', display_name: 'AI Intelligence', count: 15, total: 48, context: '', strategy: '' },
        { sector: 'GEN_AI', display_name: 'Generative AI', count: 15, total: 70, context: '', strategy: '' },
        { sector: 'ESPORTS', display_name: 'Esports', count: 15, total: 32, context: '', strategy: '' },
        { sector: 'ENT_APP', display_name: 'Enterprise Applications', count: 15, total: 42, context: '', strategy: '' },
        { sector: 'ENT_SW', display_name: 'Enterprise Software', count: 15, total: 50, context: '', strategy: '' },
        { sector: 'EDTECH', display_name: 'EdTech', count: 15, total: 34, context: '', strategy: '' },
        // ONLY FOR M&A
        { sector: 'PHARMA', display_name: 'Pharmaceutical (M&A)', count: 15, total: 28, context: '', strategy: '' },
        { sector: 'NUTRA', display_name: 'Nutraceutical (M&A)', count: 15, total: 25, context: '', strategy: '' },
        { sector: 'CHEMICAL', display_name: 'Chemical (M&A)', count: 15, total: 27, context: '', strategy: '' },
        { sector: 'FOOD_EXT', display_name: 'Food Extracts (M&A)', count: 15, total: 24, context: '', strategy: '' },
        { sector: 'TEXTILE', display_name: 'Textile (Clothing/Brands)', count: 15, total: 29, context: '', strategy: '' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSectors();
  }, []);

  const handleBulkGenerate = async (sector, formData) => {
    setGeneratingSector(sector);
    try {
      await api.post('/api/generate/bulk', { sector, ...formData });
      showNotification('success', `Bulk generation started for ${sector}`);
      fetchSectors();
    } catch (err) {
      showNotification('error', 'Failed to start bulk generation');
    } finally {
      setGeneratingSector(null);
    }
  };

  const handleSaveSettings = async (sector, settings) => {
    try {
      await api.post('/api/generate/save-settings', { sector, ...settings });
      showNotification('success', 'Strategy settings saved');
      fetchSectors();
    } catch (err) {
      showNotification('error', 'Failed to save settings');
    }
  };

  return (
    <div className="animate-in fade-in duration-500 pb-20">
      <div className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-2xl font-black text-white uppercase tracking-tight flex items-center gap-3">
            Sector-wise <span className="text-blue-500">Draft Generation</span>
          </h1>
          <p className="text-slate-400 text-sm mt-1">Trigger AI email drafting for specific business sectors with specialized strategies.</p>
        </div>
        <button
          className="btn btn-primary px-8 rounded-xl shadow-lg shadow-blue-500/20"
          onClick={() => setShowAddModal(true)}
        >
          <Plus className="w-5 h-5 mr-2" /> Add New Sector
        </button>
      </div>

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Analyzing Sector Pipeline...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {sectors.map((s) => (
            <div key={s.sector} className={`card border-white/5 transition-all relative overflow-hidden flex flex-col ${s.count > 0 ? 'bg-slate-800/40 ring-1 ring-blue-500/20 shadow-2xl shadow-blue-500/5' : 'bg-slate-900/40 opacity-80'}`}>
              {s.count > 0 && (
                <div className="absolute top-0 left-0 w-1 h-full bg-blue-500"></div>
              )}

              <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
                <h3 className="text-white font-black text-lg tracking-tight capitalize">{s.display_name}</h3>
                <span className={`px-2 py-0.5 rounded-md text-[9px] font-black uppercase tracking-widest border ${s.count > 0 ? 'border-blue-500/30 text-blue-400 bg-blue-500/10' : 'border-slate-500/30 text-slate-500 bg-slate-500/10'}`}>
                  {s.total} Total
                </span>
              </div>

              <div className="p-6 flex-1 flex flex-col">
                <div className="flex justify-between items-center pb-6 border-b border-white/5 mb-6">
                  <span className="text-slate-400 text-xs font-bold uppercase tracking-wide">Needing Emails</span>
                  <span className={`text-2xl font-black ${s.count > 0 ? 'text-blue-500' : 'text-slate-600'}`}>{s.count}</span>
                </div>

                <details className="group mb-8">
                  <summary className="flex items-center gap-2 text-[10px] font-black uppercase tracking-widest text-slate-500 cursor-pointer hover:text-blue-400 transition-colors list-none select-none">
                    <Settings2 className="w-3.5 h-3.5" />
                    Configure Strategy
                    <ChevronDown className="w-3.5 h-3.5 ml-auto group-open:rotate-180 transition-transform" />
                  </summary>

                  <div className="mt-4 space-y-4 animate-in slide-in-from-top-2 duration-300">
                    <div className="space-y-1.5">
                      <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest ml-1">Context Override</label>
                      <textarea
                        className="form-control text-xs bg-black/40 border-white/5 rounded-xl min-h-[60px]"
                        placeholder="e.g. We help biotech firms scale their AI infra..."
                        defaultValue={s.context}
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest ml-1">Drafting Strategy</label>
                      <textarea
                        className="form-control text-xs bg-black/40 border-white/5 rounded-xl min-h-[60px]"
                        placeholder="e.g. Mention specific recent industry regulations..."
                        defaultValue={s.strategy}
                      />
                    </div>
                    <button
                      className="btn btn-ghost w-full py-2 border-dashed border-blue-500/30 text-blue-400 hover:bg-blue-500/5 text-[10px] uppercase font-black"
                      onClick={() => handleSaveSettings(s.sector, {})}
                    >
                      💾 Save Strategy
                    </button>
                  </div>
                </details>

                {s.count > 0 ? (
                  <div className="space-y-4 pt-6 border-t border-white/5 mt-auto">
                    <div className="space-y-1.5">
                      <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest ml-1">Apply Campaign</label>
                      <select className="form-control text-xs bg-black/20 border-white/10 rounded-xl appearance-none">
                        <option value="">No Global Campaign</option>
                        {campaigns.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <label className="text-[9px] font-black text-slate-600 uppercase tracking-widest ml-1">Batch Limit</label>
                        <select className="form-control text-xs bg-black/20 border-white/10 rounded-xl appearance-none">
                          <option value="10">10 Leads</option>
                          <option value="25">25 Leads</option>
                          <option value="50">50 Leads</option>
                        </select>
                      </div>
                      <div className="space-y-1.5 pt-6">
                        <button
                          className="btn btn-primary w-full h-[38px] rounded-xl text-xs font-black shadow-xl shadow-blue-500/30 flex items-center justify-center gap-2"
                          onClick={() => handleBulkGenerate(s.sector, {})}
                          disabled={generatingSector === s.sector}
                        >
                          {generatingSector === s.sector ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5" />
                          )}
                          {generatingSector === s.sector ? 'Generating...' : 'Generate'}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-auto py-8 text-center bg-black/20 rounded-2xl border border-white/5">
                    <CheckCircle2 className="w-8 h-8 text-slate-700 mx-auto mb-2" />
                    <p className="text-slate-500 text-[10px] font-black uppercase tracking-tight">Full Coverage Reached</p>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Sector Modal Mock */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="card w-full max-w-md bg-slate-900 border-white/10 shadow-2xl">
            <div className="p-6 border-b border-white/5 flex justify-between items-center">
              <h3 className="text-white font-black uppercase tracking-tight">Add New Sector</h3>
              <button className="text-slate-500 hover:text-white" onClick={() => setShowAddModal(false)}>✕</button>
            </div>
            <div className="p-6 space-y-6">
              <div className="space-y-1.5">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Sector Name</label>
                <input
                  type="text"
                  className="form-control bg-black/40 border-white/10 rounded-xl"
                  placeholder="e.g. BioTech"
                  value={newSectorName}
                  onChange={(e) => setNewSectorName(e.target.value)}
                />
              </div>
              <div className="flex gap-3 pt-4">
                <button className="btn btn-ghost flex-1 border-white/10 text-slate-400" onClick={() => setShowAddModal(false)}>Cancel</button>
                <button className="btn btn-primary flex-1 shadow-lg shadow-blue-500/20">Create Sector</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4 duration-300`}>
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${notification.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <p className="text-sm font-bold tracking-tight">{notification.message}</p>
            <button
              onClick={() => setNotification(null)}
              className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GenerateSector;
