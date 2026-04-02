import React, { useState, useEffect } from 'react';
import { 
  Search, Plus, Filter, MoreHorizontal, Play, Pause, 
  Trash2, Loader2, BarChart3, Users, Mail, MousePointer2,
  X, Sparkles, Target, MessageSquare, Layout, Activity,
  ChevronDown
} from 'lucide-react';
import api from '../services/api';

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    tone: 'professional',
    target_industry: '',
    target_persona: '',
    subject: '',
    html_body: '',
    context_prompt: '',
    strategy_prompt: '',
    is_active: true
  });
  
  const [showPersonaDropdown, setShowPersonaDropdown] = useState(false);
  const [showIndustryDropdown, setShowIndustryDropdown] = useState(false);
  const [industrySearch, setIndustrySearch] = useState('');

  const personaOptions = ["CEO", "Founder", "Managing Director", "CFO", "Partner", "Investor"];
  const sectorOptions = [
    { id: 'DEEP_TECH', label: 'Deep Tech' },
    { id: 'HIGH_TECH', label: 'High Tech' },
    { id: 'SAAS', label: 'SAAS' },
    { id: 'DEFENCE_TECH', label: 'Defence Tech' },
    { id: 'TRAVEL', label: 'Travel' },
    { id: 'AUTOMOTIVE', label: 'Automotive' },
    { id: 'AI_INFRA', label: 'AI Infra' },
    { id: 'AI_INTEL', label: 'AI Intelligence' },
    { id: 'GEN_AI', label: 'Generative AI' },
    { id: 'ESPORTS', label: 'Esports' },
    { id: 'ENT_APP', label: 'Enterprise Applications' },
    { id: 'ENT_SW', label: 'Enterprise Software' },
    { id: 'EDTECH', label: 'EdTech' },
    { id: 'PHARMA', label: 'Pharmaceutical (M&A)' },
    { id: 'NUTRA', label: 'Nutraceutical (M&A)' },
    { id: 'CHEMICAL', label: 'Chemical (M&A)' },
    { id: 'FOOD_EXT', label: 'Food Extracts (M&A)' },
    { id: 'TEXTILE', label: 'Textile (Clothing/Brands)' }
  ];

  const filteredIndustries = sectorOptions.filter(s => 
    s.label.toLowerCase().includes(industrySearch.toLowerCase())
  );

  const fetchCampaigns = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/campaigns');
      setCampaigns(response.data || []);
    } catch (err) {
      console.error('Failed to fetch campaigns', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post('/api/campaigns', formData);
      setShowCreateModal(false);
      setFormData({
        name: '', description: '', tone: 'professional',
        target_industry: '', target_persona: '',
        subject: '', html_body: '',
        context_prompt: '', strategy_prompt: '',
        is_active: true
      });
      fetchCampaigns();
    } catch (err) {
      alert('Failed to create campaign: ' + (err.response?.data?.detail || err.message));
    }
  };

  const toggleStatus = async (id, currentStatus) => {
    try {
      await api.put(`/api/campaigns/${id}`, { is_active: !currentStatus });
      fetchCampaigns();
    } catch (err) {
      alert('Failed to update campaign status');
    }
  };

  const deleteCampaign = async (id) => {
    if (!window.confirm('Are you sure you want to delete this campaign?')) return;
    try {
      await api.delete(`/api/campaigns/${id}`);
      fetchCampaigns();
    } catch (err) {
      alert('Failed to delete campaign');
    }
  };

  const stats = [
    { label: 'Active Campaigns', value: campaigns.filter(c => c.is_active).length, icon: Play, color: 'text-green-400', bg: 'bg-green-400/10' },
    { label: 'Total Leads', value: campaigns.reduce((acc, c) => acc + (c.total_recipients || 0), 0), icon: Users, color: 'text-blue-400', bg: 'bg-blue-400/10' },
    { label: 'Total Opens', value: campaigns.reduce((acc, c) => acc + (c.opens || 0), 0), icon: Mail, color: 'text-purple-400', bg: 'bg-purple-400/10' },
    { label: 'Avg Open Rate', value: campaigns.length > 0 ? (campaigns.reduce((acc, c) => acc + (c.open_rate || 0), 0) / campaigns.length).toFixed(1) + '%' : '0%', icon: BarChart3, color: 'text-amber-400', bg: 'bg-amber-400/10' },
  ];

  const filteredCampaigns = campaigns.filter(c => 
    c.name.toLowerCase().includes(search.toLowerCase()) || 
    (c.description || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex justify-between items-end mb-10">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Target className="w-5 h-5 text-blue-500" />
            </div>
            <h1 className="text-3xl font-black text-white tracking-tight">Campaigns</h1>
          </div>
          <p className="text-slate-400 text-sm max-w-lg">
            Deploy high-converting outbound sequences with AI-powered personalization and real-time performance tracking.
          </p>
        </div>
        <button 
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary px-8 py-3 rounded-2xl shadow-lg shadow-blue-500/20 hover:scale-105 transition-all flex items-center gap-2 group"
        >
          <Plus className="w-5 h-5 group-hover:rotate-90 transition-transform" />
          <span className="font-bold">New Campaign</span>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
        {stats.map((stat, i) => (
          <div key={i} className="bg-slate-900/40 border border-white/5 rounded-3xl p-6 backdrop-blur-xl relative overflow-hidden group hover:border-white/10 transition-all">
            <div className={`absolute -right-4 -bottom-4 w-24 h-24 ${stat.bg.replace('10', '5')} blur-3xl rounded-full group-hover:scale-150 transition-transform duration-700`}></div>
            <div className="flex justify-between items-start mb-4 relative z-10">
              <div className={`p-2.5 ${stat.bg} rounded-xl`}>
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
              </div>
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-[2px] mt-1">{stat.label}</span>
            </div>
            <div className="relative z-10">
              <div className="text-3xl font-black text-white mb-1 tracking-tight">{stat.value}</div>
              <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-500 italic uppercase">
                <Activity className="w-3 h-3" /> Real-time metrics
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-slate-900/40 border border-white/5 rounded-[32px] backdrop-blur-xl overflow-hidden shadow-2xl">
        <div className="px-8 py-6 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
          <div className="flex items-center gap-6 w-full max-w-2xl">
            <div className="relative flex-1">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="Search by campaign name or purpose..." 
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 pl-12 pr-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all placeholder:text-slate-600 font-medium"
              />
            </div>
            <div className="flex gap-2">
              <button className="p-3 bg-white/5 border border-white/5 rounded-xl text-slate-400 hover:text-white transition-all">
                <Filter className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-separate border-spacing-0">
            <thead>
              <tr className="bg-black/20">
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Core Details</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Status</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px] text-center">Volume</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Performance (Open/Click)</th>
                <th className="px-8 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px] text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="px-8 py-24 text-center">
                    <Loader2 className="w-10 h-10 text-blue-500 animate-spin mx-auto mb-4" />
                    <p className="text-slate-500 font-bold uppercase tracking-widest text-xs">Synchronizing Campaigns</p>
                  </td>
                </tr>
              ) : filteredCampaigns.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-8 py-24 text-center">
                    <div className="w-16 h-16 bg-slate-800/40 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-white/5">
                      <Plus className="w-8 h-8 text-slate-600" />
                    </div>
                    <p className="text-slate-500 font-bold text-lg mb-1">Scale your outreach today.</p>
                    <p className="text-slate-600 text-sm mb-6">No campaigns match your current view.</p>
                    <button 
                      onClick={() => setShowCreateModal(true)}
                      className="btn btn-ghost hover:bg-blue-500/10 hover:text-blue-400"
                    >
                      Start your first campaign
                    </button>
                  </td>
                </tr>
              ) : filteredCampaigns.map((campaign) => (
                <tr key={campaign.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center border border-white/5 group-hover:scale-110 transition-transform">
                        <Layout className="w-5 h-5 text-blue-400" />
                      </div>
                      <div>
                        <div className="font-black text-white group-hover:text-blue-400 transition-colors tracking-tight text-base">{campaign.name}</div>
                        <div className="text-[11px] text-slate-500 font-bold uppercase tracking-wider mt-0.5">{campaign.target_industry || 'Universal'} • {campaign.tone}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-6">
                    <span className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest ${campaign.is_active ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-slate-500/10 text-slate-400 border border-white/5'}`}>
                      <div className={`w-1.5 h-1.5 rounded-full ${campaign.is_active ? 'bg-green-400 shadow-[0_0_8px_#4ade80]' : 'bg-slate-400'}`}></div>
                      {campaign.is_active ? 'Active' : 'Paused'}
                    </span>
                  </td>
                  <td className="px-8 py-6 text-center">
                    <div className="font-black text-white text-lg">{campaign.total_recipients || 0}</div>
                    <div className="text-[10px] text-slate-500 font-bold uppercase">Targets</div>
                  </td>
                  <td className="px-8 py-6">
                    <div className="flex items-center gap-10">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                          Open Rate
                        </div>
                        <div className="text-base font-black text-blue-400 tracking-tight">
                          {(campaign.open_rate || 0).toFixed(1)}%
                        </div>
                        <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-blue-500" style={{ width: `${Math.min(campaign.open_rate || 0, 100)}%` }}></div>
                        </div>
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">
                          CTR
                        </div>
                        <div className="text-base font-black text-purple-400 tracking-tight">
                          {(campaign.click_rate || 0).toFixed(1)}%
                        </div>
                        <div className="w-16 h-1 bg-white/5 rounded-full overflow-hidden">
                          <div className="h-full bg-purple-500" style={{ width: `${Math.min(campaign.click_rate || 0, 100)}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-8 py-6 text-right">
                    <div className="flex justify-end gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button 
                        onClick={() => toggleStatus(campaign.id, campaign.is_active)}
                        className={`p-2.5 rounded-xl border border-white/5 transition-all ${campaign.is_active ? 'hover:bg-amber-500/20 hover:text-amber-400' : 'hover:bg-green-500/20 hover:text-green-400'} bg-black/20`}
                        title={campaign.is_active ? 'Pause Campaign' : 'Resume Campaign'}
                      >
                        {campaign.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                      </button>
                      <button 
                        onClick={() => deleteCampaign(campaign.id)}
                        className="p-2.5 rounded-xl border border-white/5 hover:bg-red-500/20 hover:text-red-400 transition-all bg-black/20 text-slate-500"
                        title="Delete Archive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Campaign Creation Drawer */}
      <div className={`fixed inset-0 bg-black/60 backdrop-blur-sm z-50 transition-opacity duration-300 ${showCreateModal ? 'opacity-100' : 'opacity-0 pointer-events-none'}`} onClick={() => setShowCreateModal(false)}></div>
      <div className={`fixed top-0 right-0 h-full w-[600px] bg-slate-900 border-l border-white/10 z-50 transform transition-transform duration-500 ease-out shadow-[-20px_0_40px_rgba(0,0,0,0.4)] flex flex-col ${showCreateModal ? 'translate-x-0' : 'translate-x-full'}`}>
        <div className="p-8 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
          <div>
            <h2 className="text-2xl font-black text-white flex items-center gap-3">
              <Sparkles className="w-6 h-6 text-blue-500" /> Build Campaign
            </h2>
            <p className="text-slate-500 text-xs font-bold uppercase mt-1 tracking-widest">New Outreach Strategy</p>
          </div>
          <button onClick={() => setShowCreateModal(false)} className="p-2.5 bg-white/5 rounded-xl hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
          <form onSubmit={handleCreate} id="campaign-form" className="space-y-8">
            <div className="space-y-6">
              <div className="flex items-center gap-2 text-[11px] font-black text-blue-500 uppercase tracking-widest border-b border-blue-500/10 pb-2">
                <Target className="w-3 h-3" /> Basic Information
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Campaign Name</label>
                  <input 
                    required 
                    type="text" 
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    placeholder="e.g. Q2 Enterprise Founders" 
                    className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all font-medium"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Tone of Voice</label>
                  <select 
                    value={formData.tone}
                    onChange={(e) => setFormData({...formData, tone: e.target.value})}
                    className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer font-medium"
                  >
                    <option value="professional">Professional</option>
                    <option value="casual">Casual</option>
                    <option value="friendly">Friendly</option>
                    <option value="expert">Technical Expert</option>
                  </select>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Description</label>
                <textarea 
                  value={formData.description}
                  onChange={(e) => setFormData({...formData, description: e.target.value})}
                  placeholder="What is the goal of this campaign?" 
                  className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all min-h-[80px] font-medium"
                ></textarea>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center gap-2 text-[11px] font-black text-purple-500 uppercase tracking-widest border-b border-purple-500/10 pb-2">
                <Users className="w-3 h-3" /> Target Audience
              </div>
              <div className="grid grid-cols-2 gap-6 relative">
                <div className="space-y-3 relative">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Focus Industry</label>
                  <div className="relative">
                    <input 
                      type="text" 
                      value={formData.target_industry || industrySearch}
                      onFocus={() => setShowIndustryDropdown(true)}
                      onChange={(e) => {
                        setIndustrySearch(e.target.value);
                        if (formData.target_industry) setFormData({...formData, target_industry: ''});
                      }}
                      placeholder="Search industry..." 
                      className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all font-medium pr-10"
                    />
                    <ChevronDown className={`absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 transition-transform ${showIndustryDropdown ? 'rotate-180' : ''}`} />
                  </div>

                  {showIndustryDropdown && (
                    <>
                      <div className="fixed inset-0 z-[60]" onClick={() => setShowIndustryDropdown(false)}></div>
                      <div className="absolute top-full left-0 right-0 mt-3 bg-[#0f172a] border border-white/10 rounded-2xl shadow-2xl z-[70] overflow-hidden animate-in fade-in slide-in-from-top-2">
                        <div className="max-h-[200px] overflow-y-auto p-2 space-y-1">
                          {filteredIndustries.length === 0 ? (
                            <div className="px-3 py-4 text-center text-slate-500 text-[10px] font-black uppercase tracking-widest">No matching sectors</div>
                          ) : (
                            filteredIndustries.map(s => (
                              <div 
                                key={s.id}
                                onClick={() => {
                                  setFormData({...formData, target_industry: s.label});
                                  setIndustrySearch(s.label);
                                  setShowIndustryDropdown(false);
                                }}
                                className={`px-4 py-3 rounded-xl cursor-pointer transition-all ${formData.target_industry === s.label ? 'bg-blue-600/10 text-blue-400' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                              >
                                <span className="text-sm font-bold">{s.label}</span>
                              </div>
                            ))
                          )}
                        </div>
                      </div>
                    </>
                  )}
                </div>

                <div className="space-y-3 relative">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Target Persona</label>
                  <div 
                    className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white cursor-pointer flex justify-between items-center hover:border-blue-500/30 transition-all font-medium h-[46px]"
                    onClick={() => setShowPersonaDropdown(!showPersonaDropdown)}
                  >
                    <span className={!formData.target_persona ? "text-slate-600" : "text-white"}>
                      {formData.target_persona || "Select persona..."}
                    </span>
                    <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform ${showPersonaDropdown ? 'rotate-180' : ''}`} />
                  </div>

                  {showPersonaDropdown && (
                    <>
                      <div className="fixed inset-0 z-[60]" onClick={() => setShowPersonaDropdown(false)}></div>
                      <div className="absolute top-full left-0 right-0 mt-3 bg-[#0f172a] border border-white/10 rounded-2xl shadow-2xl z-[70] overflow-hidden animate-in fade-in slide-in-from-top-2">
                        <div className="max-h-[200px] overflow-y-auto p-2 space-y-1">
                          {personaOptions.map(p => (
                            <div 
                              key={p}
                              onClick={() => {
                                setFormData({...formData, target_persona: p});
                                setShowPersonaDropdown(false);
                              }}
                              className={`px-4 py-3 rounded-xl cursor-pointer transition-all ${formData.target_persona === p ? 'bg-indigo-600/10 text-indigo-400' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                            >
                              <span className="text-sm font-bold">{p}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center gap-2 text-[11px] font-black text-amber-500 uppercase tracking-widest border-b border-amber-500/10 pb-2">
                <Mail className="w-3 h-3" /> Email Content
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Subject Line</label>
                <input 
                  type="text" 
                  value={formData.subject}
                  onChange={(e) => setFormData({...formData, subject: e.target.value})}
                  placeholder="Default subject line..." 
                  className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all font-medium"
                />
              </div>
              <div className="space-y-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Email Body (HTML)</label>
                <textarea 
                  value={formData.html_body}
                  onChange={(e) => setFormData({...formData, html_body: e.target.value})}
                  placeholder="Master template for emails..." 
                  className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 transition-all min-h-[160px] font-medium font-mono"
                ></textarea>
              </div>
            </div>

            <div className="space-y-6">
              <div className="flex items-center gap-2 text-[11px] font-black text-green-500 uppercase tracking-widest border-b border-green-500/10 pb-2">
                <Sparkles className="w-3 h-3" /> AI Strategy (Overrides)
              </div>
              <div className="space-y-4">
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Context Prompt</label>
                  <textarea 
                    value={formData.context_prompt}
                    onChange={(e) => setFormData({...formData, context_prompt: e.target.value})}
                    placeholder="Custom context for the AI model..." 
                    className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-[13px] text-slate-300 focus:outline-none focus:border-blue-500/50 transition-all min-h-[80px] font-medium italic"
                  ></textarea>
                </div>
                <div className="space-y-2">
                  <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Strategy Prompt</label>
                  <textarea 
                    value={formData.strategy_prompt}
                    onChange={(e) => setFormData({...formData, strategy_prompt: e.target.value})}
                    placeholder="Custom pitch/angle instructions..." 
                    className="w-full bg-black/40 border border-white/10 rounded-2xl py-3 px-4 text-[13px] text-slate-300 focus:outline-none focus:border-blue-500/50 transition-all min-h-[80px] font-medium italic"
                  ></textarea>
                </div>
              </div>
            </div>
          </form>
        </div>
        
        <div className="p-8 border-t border-white/5 bg-black/40 flex gap-4">
          <button 
            type="button"
            onClick={() => setShowCreateModal(false)}
            className="flex-1 px-6 py-4 bg-white/5 border border-white/5 rounded-2xl font-black text-[11px] uppercase tracking-[3px] hover:bg-white/10 transition-all text-slate-400 hover:text-white"
          >
            Discard
          </button>
          <button 
            form="campaign-form"
            type="submit"
            className="flex-1 px-6 py-4 bg-blue-600 rounded-2xl font-black text-[11px] uppercase tracking-[3px] hover:bg-blue-500 transition-all text-white shadow-xl shadow-blue-600/20"
          >
            Deploy Campaign
          </button>
        </div>
      </div>
    </div>
  );
};

export default Campaigns;
