import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  History, Mail, CheckCircle, Clock, AlertCircle, X,
  ChevronRight, ArrowRight, Loader2, Search,
  Zap, Calendar, User, Linkedin, ExternalLink, Rocket
} from 'lucide-react';
import api from '../services/api';

const Followups = () => {
  const navigate = useNavigate();
  const [followups, setFollowups] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [notification, setNotification] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    fetchFollowups();
  }, []);

  const fetchFollowups = async () => {
    try {
      setIsLoading(true);
      const res = await api.get('/api/followups');
      setFollowups(res.data);
    } catch (err) {
      console.error('Failed to fetch follow-ups:', err);
      showNotification('error', 'Failed to load active follow-ups');
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkResponded = async (leadId) => {
    try {
      await api.post(`/api/leads/${leadId}/respond`);
      showNotification('success', 'Lead marked as responded. Sequence stopped.');
      setFollowups(prev => prev.filter(f => f.id !== leadId));
      if (selectedLead?.id === leadId) setIsModalOpen(false);
    } catch (err) {
      console.error('Failed to mark as responded:', err);
      showNotification('error', 'Failed to update lead status');
    }
  };

  const handleApproveFollowup = async (leadId) => {
    try {
      await api.post(`/api/leads/${leadId}/approve-followup`);
      showNotification('success', 'Follow-up approved and sent successfully!');
      fetchFollowups();
      setIsModalOpen(false);
    } catch (err) {
      console.error('Failed to approve follow-up:', err);
      showNotification('error', 'Failed to send follow-up. Check Gmail connection.');
    }
  };

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const getStageLabel = (stage, leadType) => {
    const typeStr = String(leadType || '').toUpperCase();
    const isInvestor = !typeStr || (!typeStr.includes('CLIENT') && !typeStr.includes('CUSTOMER'));
    switch (stage) {
      case 0: return isInvestor ? 'Day 7 Follow-up' : 'Day 2 Follow-up';
      case 1: return isInvestor ? 'Day 17 Follow-up' : 'Day 4 Follow-up';
      default: return 'Sequence Completed';
    }
  };

  const filteredFollowups = followups.filter(f =>
    f.first_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    f.last_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    f.company_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    f.email?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getStageColor = (stage) => {
    switch (stage) {
      case 0: return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 1: return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
      case 2: return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      default: return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  const openLeadDetails = async (lead) => {
    setSelectedLead(lead);
    setIsModalOpen(true);
    
    // If no draft exists, or just to get the freshest version
    try {
      const res = await api.get(`/api/leads/${lead.id}/followup-preview`);
      if (res.data && res.data.full_html) {
        // Update the selected lead with the fetched draft
        setSelectedLead(prev => ({
          ...prev,
          followup_draft: res.data.full_html
        }));
      }
    } catch (err) {
      console.error('Failed to fetch follow-up preview:', err);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-slate-200">
      {/* Header Section */}
      <div className="border-b border-white/[0.05] bg-[#0f172a]/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-[1600px] mx-auto px-8 h-24 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shadow-lg shadow-indigo-500/5">
              <History className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl font-black text-white leading-tight tracking-tight uppercase">Outreach Sequences</h1>
              <p className="text-[11px] text-slate-500 font-bold uppercase tracking-[2px] mt-0.5">Manual Approval Required</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="relative group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                <Search className="w-4 h-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
              </div>
              <input
                type="text"
                placeholder="Search active sequences..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#131722] border border-white/[0.05] rounded-xl pl-12 pr-6 py-3 w-[350px] text-[13px] font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/30 transition-all placeholder:text-slate-600"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1600px] mx-auto px-8 py-10">
        {/* Sequence Overview Bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
          {[
            { label: 'Pending Approval', value: followups.filter(f => f.followup_status === 'PENDING_APPROVAL').length, icon: Zap, color: 'text-amber-400', bg: 'bg-amber-400/10' },
            { label: 'Active Sequences', value: followups.filter(f => f.followup_status === 'ACTIVE').length, icon: Clock, color: 'text-blue-400', bg: 'bg-blue-400/10' },
            { label: 'Total Leads', value: followups.length, icon: User, color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
            { label: 'Avg Frequency', value: 'Manual', icon: Calendar, color: 'text-emerald-400', bg: 'bg-emerald-400/10' }
          ].map((stat, i) => (
            <div key={i} className="bg-[#0f172a] border border-white/[0.05] rounded-2xl p-6 flex items-center justify-between group hover:border-indigo-500/20 transition-all duration-500">
              <div className="space-y-1">
                <p className="text-[11px] font-black text-slate-500 uppercase tracking-widest">{stat.label}</p>
                <p className="text-3xl font-black text-white">{stat.value}</p>
              </div>
              <div className={`w-14 h-14 rounded-2xl ${stat.bg} flex items-center justify-center group-hover:scale-110 transition-transform duration-500`}>
                <stat.icon className={`w-7 h-7 ${stat.color}`} />
              </div>
            </div>
          ))}
        </div>

        {/* Content Area */}
        {isLoading ? (
          <div className="h-[400px] flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
            <p className="text-xs font-bold text-slate-500 uppercase tracking-[2px]">Syncing pipeline...</p>
          </div>
        ) : filteredFollowups.length === 0 ? (
          <div className="bg-[#0f172a] border border-white/[0.05] rounded-3xl p-20 flex flex-col items-center justify-center text-center space-y-6">
            <div className="w-24 h-24 rounded-full bg-slate-500/5 flex items-center justify-center border border-dashed border-slate-500/20">
              <History className="w-10 h-10 text-slate-600" />
            </div>
            <div className="space-y-2">
              <h3 className="text-lg font-black text-white uppercase italic">Silence is Golden</h3>
              <p className="text-sm text-slate-500 max-w-md font-medium leading-relaxed"> No active follow-up sequences found. Start by sending outreach emails from the Lead Pipeline!</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredFollowups.map((lead) => (
              <div
                key={lead.id}
                onClick={() => openLeadDetails(lead)}
                className="bg-[#0f172a] border border-white/[0.05] rounded-2xl p-6 transition-all duration-300 hover:bg-[#131722] hover:border-indigo-500/20 group cursor-pointer"
              >
                <div className="flex flex-col gap-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-6">
                      {/* User Avatar */}
                      <div className="w-16 h-16 rounded-2xl bg-[#1a2235] flex items-center justify-center border border-white/[0.05] flex-shrink-0 group-hover:border-indigo-500/30 transition-colors">
                        <User className="w-8 h-8 text-slate-400" />
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center gap-3">
                          <h3 className="text-base font-black text-white group-hover:text-indigo-400 transition-colors">
                            {lead.first_name} {lead.last_name}
                          </h3>
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-black uppercase px-2.5 py-1 rounded-md border ${getStageColor(lead.followup_stage)}`}>
                              {getStageLabel(lead.followup_stage, lead.lead_type || lead.sector)}
                            </span>
                            <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full border ${(!String(lead.lead_type || lead.sector || '').toUpperCase().includes('CLIENT') && !String(lead.lead_type || lead.sector || '').toUpperCase().includes('CUSTOMER')) ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                              {(!String(lead.lead_type || lead.sector || '').toUpperCase().includes('CLIENT') && !String(lead.lead_type || lead.sector || '').toUpperCase().includes('CUSTOMER')) ? 'Investor' : 'Client'}
                            </span>
                          </div>
                          {lead.followup_status === 'PENDING_APPROVAL' && (
                            <span className="text-[9px] font-black uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse">
                              Pending Approval
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 text-[12px] font-bold text-slate-400">
                          <span className="flex items-center gap-1.5 opacity-60">
                            <Rocket className="w-3.5 h-3.5" />
                            {lead.company_name}
                          </span>
                          <span className="w-1 h-1 rounded-full bg-slate-700" />
                          <span className="flex items-center gap-1.5 opacity-60">
                            <Calendar className="w-3.5 h-3.5" />
                            Last Outreach: {new Date(lead.last_outreach_at).toLocaleDateString()}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      <button
                        onClick={(e) => { e.stopPropagation(); openLeadDetails(lead); }}
                        className="p-3 bg-[#1a2235] text-slate-400 rounded-xl border border-white/[0.05] hover:text-white hover:border-white/20 transition-all shadow-sm cursor-pointer"
                        title="View Follow-up Details"
                      >
                        <Mail className="w-4 h-4" />
                      </button>
                      
                      <button
                        onClick={(e) => { e.stopPropagation(); handleApproveFollowup(lead.id); }}
                        className="flex items-center gap-2 px-6 py-3 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-[0.15em] hover:bg-indigo-500 hover:scale-[1.02] active:scale-[0.98] transition-all shadow-xl shadow-indigo-600/20 cursor-pointer"
                      >
                        <Zap className="w-3.5 h-3.5" />
                        Approve & Send
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lead Detail & Draft Modal */}
      {isModalOpen && selectedLead && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center px-4 sm:px-6">
          <div className="absolute inset-0 bg-black/90 backdrop-blur-md" onClick={() => setIsModalOpen(false)} />
          <div className="relative bg-[#0f172a] border border-white/10 rounded-[2.5rem] w-full max-w-3xl overflow-hidden shadow-[0_0_50px_rgba(0,0,0,0.5)] animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="p-10 border-b border-white/5 bg-gradient-to-b from-indigo-500/[0.03] to-transparent relative">
              <div className="flex items-center gap-6">
                <div className="w-20 h-20 rounded-3xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 shadow-2xl shadow-indigo-500/10">
                  <User className="w-10 h-10 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-3xl font-black text-white tracking-tight">{selectedLead.first_name} {selectedLead.last_name}</h2>
                  <div className="flex items-center gap-2 mt-1.5">
                    <div className="w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.5)]" />
                    <p className="text-[11px] font-black text-slate-500 uppercase tracking-[0.2em]">{selectedLead.company_name || 'Active Prospect'}</p>
                  </div>
                </div>
              </div>
              <button 
                onClick={() => setIsModalOpen(false)} 
                className="absolute top-10 right-10 p-3 rounded-2xl bg-white/[0.03] hover:bg-white/[0.08] text-slate-500 hover:text-white transition-all cursor-pointer border border-white/[0.05]"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-8 space-y-8 max-h-[70vh] overflow-y-auto custom-scrollbar">
              {/* Draft Section */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-indigo-400" />
                    <span className="text-[11px] font-black text-white uppercase tracking-widest">Follow-up Draft</span>
                  </div>
                  <span className={`text-[10px] font-black uppercase px-2 py-1 rounded border ${getStageColor(selectedLead.followup_stage)}`}>
                    {getStageLabel(selectedLead.followup_stage, selectedLead.lead_type)}
                  </span>
                </div>
                
                <div className="bg-slate-950/40 rounded-[2.5rem] p-12 border border-white/[0.03] shadow-inner relative overflow-hidden group">
                  <div className="absolute top-0 left-0 w-1.5 h-full bg-indigo-500/40" />
                  <div 
                    className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed font-medium text-[15px]"
                    dangerouslySetInnerHTML={{ 
                      __html: selectedLead.followup_draft || '<p class="animate-pulse italic text-slate-500">Drafting personalized follow-up...</p>' 
                    }}
                  />
                </div>
              </div>

              {/* Lead Details Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white/5 rounded-2xl p-4 border border-white/5">
                  <p className="text-[10px] font-black text-slate-500 uppercase mb-1">Email</p>
                  <p className="text-[13px] font-bold text-slate-300 truncate">{selectedLead.email}</p>
                </div>
                <div className="bg-white/5 rounded-2xl p-4 border border-white/5">
                  <p className="text-[10px] font-black text-slate-500 uppercase mb-1">Last Contacted</p>
                  <p className="text-[13px] font-bold text-slate-300">{new Date(selectedLead.last_outreach_at).toLocaleDateString()}</p>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-8 bg-[#131722]/50 border-t border-white/5 flex items-center justify-end gap-4">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-6 py-3 text-[11px] font-black text-slate-400 uppercase tracking-wider hover:text-white transition-colors cursor-pointer"
              >
                Close
              </button>
              
              <button
                onClick={() => handleApproveFollowup(selectedLead.id)}
                className="flex items-center gap-2 px-8 py-3 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-[0.2em] hover:bg-indigo-500 hover:scale-[1.02] active:scale-[0.98] transition-all cursor-pointer shadow-lg shadow-indigo-600/20"
              >
                <Zap className="w-4 h-4" />
                Approve & Send
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Notification Toast */}
      {notification && (
        <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-8 py-4 rounded-2xl border backdrop-blur-xl shadow-2xl flex items-center gap-4 z-[100] animate-in fade-in slide-in-from-bottom-5 duration-500 ${notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
          {notification.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <p className="text-sm font-black uppercase tracking-wide italic">{notification.message}</p>
        </div>
      )}
    </div>
  );
};

export default Followups;
