import React, { useState, useEffect } from 'react';
import { Search, Plus, Filter, MoreHorizontal, Play, Pause, Trash2, Loader2, BarChart3, Users, Mail, MousePointer2 } from 'lucide-react';
import api from '../services/api';

const Campaigns = () => {
  const [campaigns, setCampaigns] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total: 0 });
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchCampaigns = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/campaigns', {
        params: { page: pagination.page, per_page: 10 }
      });
      setCampaigns(response.data.items || []);
      setPagination(prev => ({ ...prev, total: response.data.total }));
    } catch (err) {
      console.error('Failed to fetch campaigns', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaigns();
  }, [pagination.page]);

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

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Campaigns</h1>
          <p className="text-slate-400 text-sm mt-1">Manage outbound sequences and track real-time engagement metrics.</p>
        </div>
        <button 
          onClick={() => setShowCreateModal(true)}
          className="btn btn-primary px-6 py-2.5 shadow-blue-500/20"
        >
          <Plus className="w-5 h-5 mr-2" /> Create Campaign
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Active', value: campaigns.filter(c => c.is_active).length, icon: Play, color: 'text-green-400' },
          { label: 'Total Leads', value: campaigns.reduce((acc, c) => acc + (c.total_leads || 0), 0), icon: Users, color: 'text-blue-400' },
          { label: 'Emails Sent', value: '1.2k', icon: Mail, color: 'text-purple-400' },
          { label: 'Avg Open Rate', value: '24.8%', icon: BarChart3, color: 'text-amber-400' },
        ].map((stat, i) => (
          <div key={i} className="bg-slate-800/40 border border-white/5 rounded-2xl p-5 backdrop-blur-sm">
            <div className="flex justify-between items-start mb-2">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{stat.label}</span>
              <stat.icon className={`w-4 h-4 ${stat.color}`} />
            </div>
            <div className="text-2xl font-bold text-white">{stat.value}</div>
          </div>
        ))}
      </div>

      <div className="card border-white/5 bg-slate-800/20 backdrop-blur-md overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-slate-800/40">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input 
                type="text" 
                placeholder="Search campaigns..." 
                className="bg-slate-900/50 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-blue-500/50 w-64 transition-all"
              />
            </div>
            <button className="btn btn-ghost py-2 px-3 h-auto">
              <Filter className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Campaign Name</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider text-center">Leads</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Performance</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Created</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isLoading ? (
                <tr>
                  <td colSpan="6" className="px-6 py-20 text-center">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-2" />
                    <p className="text-slate-500 text-sm font-medium">Loading campaigns...</p>
                  </td>
                </tr>
              ) : campaigns.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-20 text-center">
                    <p className="text-slate-500 font-medium">No campaigns found. Create your first one above.</p>
                  </td>
                </tr>
              ) : campaigns.map((campaign) => (
                <tr key={campaign.id} className="hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-5">
                    <div className="font-bold text-white group-hover:text-blue-400 transition-colors">{campaign.name}</div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{campaign.description || 'No description provided'}</div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`badge ${campaign.is_active ? 'badge-green' : 'badge-amber'}`}>
                      {campaign.is_active ? 'Active' : 'Paused'}
                    </span>
                  </td>
                  <td className="px-6 py-5 text-center font-bold text-slate-300">
                    {campaign.total_leads || 0}
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-6">
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-[11px] font-bold text-slate-400 uppercase tracking-tight">
                          <Mail className="w-3 h-3" /> Opens
                        </div>
                        <div className="text-xs font-black text-blue-400">22.4%</div>
                      </div>
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-2 text-[11px] font-bold text-slate-400 uppercase tracking-tight">
                          <MousePointer2 className="w-3 h-3" /> Clicks
                        </div>
                        <div className="text-xs font-black text-purple-400">8.1%</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-[11px] text-slate-500 font-medium whitespace-nowrap">
                    {new Date(campaign.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-5 text-right">
                    <div className="flex justify-end gap-2">
                      <button 
                        onClick={() => toggleStatus(campaign.id, campaign.is_active)}
                        className={`p-2 rounded-lg border border-white/5 transition-all ${campaign.is_active ? 'hover:bg-amber-500/20 hover:text-amber-400' : 'hover:bg-green-500/20 hover:text-green-400'}`}
                        title={campaign.is_active ? 'Pause' : 'Resume'}
                      >
                        {campaign.is_active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </button>
                      <button 
                        onClick={() => deleteCampaign(campaign.id)}
                        className="p-2 rounded-lg border border-white/5 hover:bg-red-500/20 hover:text-red-400 transition-all text-slate-500"
                        title="Delete"
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

      {/* Create Campaign Mock Drawer */}
      <div className={`drawer-backdrop ${showCreateModal ? 'show' : ''}`} onClick={() => setShowCreateModal(false)}></div>
      <div className={`drawer ${showCreateModal ? 'show' : ''}`}>
        <div className="drawer-header">
          <h2 className="text-white font-bold text-lg flex items-center gap-2">
            <span className="text-xl">🚀</span> Launch New Campaign
          </h2>
          <button onClick={() => setShowCreateModal(false)} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="drawer-body">
          <form className="space-y-6">
            <div className="form-group">
              <label>Campaign Title</label>
              <input type="text" className="form-control" placeholder="e.g. Q1 Founder Outreach" />
            </div>
            <div className="form-group">
              <label>Description (Optional)</label>
              <textarea className="form-control h-24" placeholder="Briefly describe the objective..."></textarea>
            </div>
            <div className="form-group">
              <label className="flex justify-between">
                Initial Status
                <span className="text-blue-500 font-bold lowercase tracking-normal">Active by default</span>
              </label>
              <div className="flex gap-4 mt-2">
                <label className="flex-1 flex items-center gap-3 p-4 bg-slate-900 border border-blue-500/30 rounded-2xl cursor-pointer">
                  <input type="radio" name="status" defaultChecked className="accent-blue-500" />
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-white">Active</span>
                    <span className="text-[10px] text-slate-500">Starts immediately</span>
                  </div>
                </label>
                <label className="flex-1 flex items-center gap-3 p-4 bg-slate-900 border border-white/5 rounded-2xl cursor-pointer hover:border-white/20 transition-all">
                  <input type="radio" name="status" className="accent-slate-500" />
                  <div className="flex flex-col">
                    <span className="text-sm font-bold text-white text-slate-400">Draft</span>
                    <span className="text-[10px] text-slate-500">Launch later</span>
                  </div>
                </label>
              </div>
            </div>
          </form>
        </div>
        <div className="drawer-footer">
          <button className="btn btn-ghost" onClick={() => setShowCreateModal(false)}>Cancel</button>
          <button className="btn btn-primary px-8">Save & Launch</button>
        </div>
      </div>
    </div>
  );
};

// Internal sub-component for icons if needed (or just use Lucide)
const X = ({ className, onClick }) => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    width="24" 
    height="24" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className={className}
    onClick={onClick}
  >
    <path d="M18 6 6 18" /><path d="m6 6 12 12" />
  </svg>
);

export default Campaigns;
