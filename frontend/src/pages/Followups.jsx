import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  History, Mail, CheckCircle, Clock, AlertCircle, 
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
    } catch (err) {
      console.error('Failed to mark as responded:', err);
      showNotification('error', 'Failed to update lead status');
    }
  };

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
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

  const getStageLabel = (stage) => {
    switch (stage) {
      case 0: return 'Initial Sent';
      case 1: return 'Day 2 Follow-up';
      case 2: return 'Day 4 Follow-up';
      default: return 'Unknown';
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
              <p className="text-[11px] text-slate-500 font-bold uppercase tracking-[2px] mt-0.5">Automated Follow-up Management</p>
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          {[
            { label: 'Active Sequences', value: followups.length, icon: Zap, color: 'text-indigo-400', bg: 'bg-indigo-400/10' },
            { label: 'Day 2 Nudges', value: followups.filter(f => f.followup_stage === 0).length, icon: Clock, color: 'text-blue-400', bg: 'bg-blue-400/10' },
            { label: 'Day 4 Nudges', value: followups.filter(f => f.followup_stage === 1).length, icon: Calendar, color: 'text-emerald-400', bg: 'bg-emerald-400/10' }
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
                className="bg-[#0f172a] border border-white/[0.05] rounded-2xl p-6 transition-all duration-300 hover:bg-[#131722] hover:border-indigo-500/20 group"
              >
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
                        <span className={`text-[10px] font-black uppercase px-2.5 py-1 rounded-md border ${getStageColor(lead.followup_stage)}`}>
                          {getStageLabel(lead.followup_stage)}
                        </span>
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

                  <div className="flex items-center gap-3 px-6 h-14 border-x border-white/[0.05]">
                    <div className="space-y-1">
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none">Next Step</p>
                      <p className="text-[12px] font-black text-white italic">
                        {lead.followup_stage === 0 ? "Automatic Day 2 Nudge" : "Automatic Day 4 Nudge"}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <button 
                      onClick={() => navigate(`/leads/edit/${lead.id}`)}
                      className="p-3 bg-[#1a2235] text-slate-400 rounded-xl border border-white/[0.05] hover:text-white hover:border-white/20 transition-all shadow-sm"
                      title="View Thread"
                    >
                      <Mail className="w-4 h-4" />
                    </button>
                    {lead.linkedin_url && (
                      <a 
                        href={lead.linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        className="p-3 bg-[#1a2235] text-blue-400/60 rounded-xl border border-white/[0.05] hover:text-blue-400 hover:border-blue-500/30 transition-all shadow-sm"
                      >
                        <Linkedin className="w-4 h-4" />
                      </a>
                    )}
                    <button
                      onClick={() => handleMarkResponded(lead.id)}
                      className="flex items-center gap-2 px-6 py-3 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded-xl text-[12px] font-black uppercase tracking-wider hover:bg-emerald-500/10 hover:text-emerald-400 hover:border-emerald-500/20 transition-all"
                    >
                      <CheckCircle className="w-4 h-4" />
                      Mark Responded
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Notification Toast */}
      {notification && (
        <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-8 py-4 rounded-2xl border backdrop-blur-xl shadow-2xl flex items-center gap-4 z-[100] animate-in fade-in slide-in-from-bottom-5 duration-500 ${
          notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
        }`}>
          {notification.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <p className="text-sm font-black uppercase tracking-wide italic">{notification.message}</p>
        </div>
      )}
    </div>
  );
};

export default Followups;
