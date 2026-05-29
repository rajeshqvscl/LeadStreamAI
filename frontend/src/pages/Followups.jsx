import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  History, Mail, CheckCircle, Clock, AlertCircle, X,
  ChevronRight, Loader2, Search, Filter, ChevronLeft, ChevronRight as ChevronRightIcon,
  Zap, Calendar, User, Rocket, Building2, CheckSquare, Square,
  ChevronsRight, Cpu, Save
} from 'lucide-react';
import api from '../services/api';

const TYPE_FILTERS = ['All', 'Investor', 'Client'];

const STAGE_CONFIGS = {
  All: [
    { label: '2nd Day', stage: 0, type: 'Client' },
    { label: '4th Day', stage: 1, type: 'Client' },
    { label: '7th Day', stage: 0, type: 'Investor' },
    { label: '10th Day', stage: 2, type: 'Client' },
    { label: '14th Day', stage: 1, type: 'Investor' },
    { label: '30th Day', stage: 2, type: 'Investor' },
  ],
  Investor: [
    { label: '7th Day', stage: 0 },
    { label: '14th Day', stage: 1 },
    { label: '30th Day', stage: 2 },
  ],
  Client: [
    { label: '2nd Day', stage: 0 },
    { label: '4th Day', stage: 1 },
    { label: '10th Day', stage: 2 },
  ]
};

const getLeadType = (lead) => {
  // FORCE INVESTOR FOR YASHIKA & GUPTA: They don't deal with clients
  try {
    const userStr = localStorage.getItem('user');
    if (userStr) {
      const user = JSON.parse(userStr);
      const name = String(user.username || user.full_name || '').toLowerCase();
      if (name.includes('yashika') || name.includes('gupta')) return 'Investor';
    }
  } catch (e) {}

  const text = String(`${lead.company_name || lead.company || ''} ${lead.sector || ''} ${lead.persona || ''}`).toUpperCase();
  
  const investorKeywords = [
    "VENTURE", "CAPITAL", "EQUITY", "INVEST", "PARTNER", "ASSET", 
    "FAMILY OFFICE", "ANGEL", "CIRCLE", "NETWORK", "FUND", "VC", "PE", "ADVISORY",
    "HOLDING", "SFO", "OFFICE", "MANAGEMENT", "PRIVATE", "TRUST", "WEALTH",
    "ASSOCIATES", "GROUP", "PARTNERS", "ADVISORS", "FOUNDATION"
  ];
  
  // High Priority: Keyword matching in company name/sector
  if (investorKeywords.some(kw => text.includes(kw))) return 'Investor';
  
  // Secondary: Explicit lead_type field
  if (lead.lead_type) {
    const lt = String(lead.lead_type).toUpperCase();
    if (lt.includes('CLIENT')) return 'Client';
    if (lt.includes('INVESTOR')) return 'Investor';
  }
  
  const clientKeywords = ["SAAS", "FINTECH", "SOFTWARE", "CLIENT", "CUSTOMER", "PRODUCT", "SERVICES"];
  if (clientKeywords.some(kw => text.includes(kw))) return 'Client';

  return 'Investor';
};

const getStageLabel = (stage, lead, status = 'DUE') => {
  const isInvestor = getLeadType(lead) === 'Investor';
  
  // If we are in the SENT tab, we want to show the badge for what was JUST sent.
  // If we are in the DUE tab, we show the badge for what is ABOUT to be sent.
  let displayStage = stage;
  if (status === 'SENT' && stage > 0) displayStage = stage - 1;

  if (displayStage === 0) return isInvestor ? 'Day 7' : 'Day 2';
  if (displayStage === 1) return isInvestor ? 'Day 14' : 'Day 4';
  if (displayStage === 2) return isInvestor ? 'Day 30' : 'Day 10';
  return `${displayStage + 1}th Follow-up`;
};

const getStageColor = (stage) => {
  if (stage === 0) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
  if (stage === 1) return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
  if (stage === 2) return 'bg-violet-500/10 text-violet-400 border-violet-500/20';
  if (stage === 3) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (stage === 4) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  if (stage >= 5) return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
};

const Followups = () => {
  const navigate = useNavigate();
  const [followups, setFollowups] = useState([]);
  
  const parseUtcDate = (dateStr) => {
    if (!dateStr) return null;
    let cleanStr = dateStr;
    if (typeof cleanStr === 'string' && !cleanStr.endsWith('Z') && !cleanStr.includes('+') && !/-[0-9]{2}:[0-9]{2}$/.test(cleanStr)) {
      cleanStr = cleanStr.replace(' ', 'T') + 'Z';
    }
    const d = new Date(cleanStr);
    return isNaN(d.getTime()) ? null : d;
  };

  const [isLoading, setIsLoading] = useState(true);
  const [isBulkSending, setIsBulkSending] = useState(false);
  const [progress, setProgress] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [notification, setNotification] = useState(null);
  const [selectedLead, setSelectedLead] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [typeFilter, setTypeFilter] = useState(() => {
    try {
      const userStr = localStorage.getItem('user');
      if (userStr) {
        const user = JSON.parse(userStr);
        if (user.username?.toLowerCase() === 'yashika') return 'Investor';
      }
    } catch (e) {}
    return 'All';
  });
  const [stageFilter, setStageFilter] = useState('All');
  const [statusFilter, setStatusFilter] = useState('DUE'); // DUE, SENT, REPLIED
  const [selectedIds, setSelectedIds] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [isEditing, setIsEditing] = useState(false);
  const [editedDraft, setEditedDraft] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [systemSettings, setSystemSettings] = useState({ auto_followup: false, outreach_daily_limit: 200 });
  const [localLimit, setLocalLimit] = useState('200');
  const perPage = 100;

  useEffect(() => { 
    if (page === 1) {
      fetchFollowups(1); 
    } else {
      setPage(1); 
    }
    fetchSystemSettings();
  }, [searchQuery, typeFilter, stageFilter, statusFilter]);

  const fetchSystemSettings = async () => {
    try {
      const res = await api.get('/api/admin/stats/settings');
      const limit = res.data.outreach_daily_limit || 200;
      setSystemSettings({
        auto_followup: res.data.auto_followup,
        outreach_daily_limit: limit
      });
      setLocalLimit(String(limit));
    } catch {}
  };

  const handleUpdateSettings = async (auto, limit) => {
    // Update local state immediately for snappy UI
    setSystemSettings({ auto_followup: auto, outreach_daily_limit: limit });
    setLocalLimit(String(limit));
    try {
      await api.post('/api/admin/stats/settings', { 
        auto_followup: auto, 
        outreach_daily_limit: limit 
      });
      showNotification('success', `Settings updated: Auto-Pilot ${auto ? 'ON' : 'OFF'}, Limit ${limit}`);
    } catch {
      showNotification('error', 'Failed to update settings');
    }
  };

  useEffect(() => { fetchFollowups(page); }, [page]);

  const fetchFollowups = async (pageNum = 1) => {
    try {
      setIsLoading(true);
      const params = {
        page: pageNum,
        per_page: perPage,
        search: searchQuery || undefined,
        type: typeFilter === 'All' ? undefined : typeFilter,
        status: statusFilter === 'DUE' ? undefined : statusFilter,
      };

      // Map stage filter to numeric stage
      if (stageFilter !== 'All') {
        if (statusFilter === 'IN_PROGRESS') {
          const match = stageFilter.match(/Stage (\d+)/);
          if (match) params.stage = parseInt(match[1]);
        } else {
          const currentConfigs = STAGE_CONFIGS[typeFilter];
          const config = currentConfigs.find(c => c.label === stageFilter);
          if (config) {
            params.stage = config.stage;
            if (config.type) params.type = config.type;
          }
        }
      }

      const res = await api.get('/api/leads/followups', { params });
      setFollowups(res.data.leads || []);
      setTotal(res.data.total || 0);
      setSelectedIds([]); 
    } catch (err) {
      showNotification('error', 'Failed to load active follow-ups');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!selectedLead) return;
    try {
      setIsSaving(true);
      await api.post(`/api/leads/${selectedLead.id}/save-followup-draft`, { 
        custom_body: editedDraft 
      });
      
      // Re-fetch preview to show the updated HTML with signature
      const res = await api.get(`/api/leads/${selectedLead.id}/followup-preview`);
      if (res.data?.full_html) {
        setSelectedLead(prev => ({ 
          ...prev, 
          followup_draft: res.data.full_html,
          followup_subject: res.data.subject || prev.followup_subject || 'Following up'
        }));
      }
      
      showNotification('success', 'Draft saved successfully');
      setIsEditing(false);
    } catch { showNotification('error', 'Failed to save draft'); }
    finally { setIsSaving(false); }
  };

  const handleApproveFollowup = async (leadId) => {
    try {
      await api.post(`/api/leads/${leadId}/approve-followup`, { 
        custom_body: isEditing ? editedDraft : undefined 
      });
      showNotification('success', 'Follow-up sent successfully!');
      fetchFollowups(page);
      setIsModalOpen(false);
      setIsEditing(false);
    } catch { showNotification('error', 'Failed to send follow-up.'); }
  };

  const handleBulkSend = async () => {
    if (selectedIds.length === 0) return;
    const idsToSend = [...selectedIds]; // Keep local copy for the API call
    try {
      setIsBulkSending(true);
      setSelectedIds([]); // Clear selection immediately
      setProgress(10);
      
      // Simulate progress while calling API
      const interval = setInterval(() => {
        setProgress(prev => prev < 90 ? prev + 5 : prev);
      }, 300);

      const res = await api.post('/api/leads/bulk-approve-followups', { lead_ids: idsToSend });
      
      clearInterval(interval);
      setProgress(100);
      
      const successCount = res.data.success?.length || 0;
      const failCount = res.data.failed?.length || 0;
      
      setTimeout(() => {
        setIsBulkSending(false);
        setProgress(0);
        showNotification('success', `Matrix Dispatch Complete: ${successCount} sent.`);
        fetchFollowups();
      }, 1000);
      
    } catch (err) {
      setIsBulkSending(false);
      setProgress(0);
      showNotification('error', err?.response?.data?.detail || 'Matrix Dispatch Error');
    }
  };

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const openLeadDetails = async (lead) => {
    setSelectedLead({
      ...lead,
      followup_subject: lead.last_outreach_subject || 'Following up'
    });
    setIsModalOpen(true);
    setIsEditing(false);
    try {
      const res = await api.get(`/api/leads/${lead.id}/followup-preview`);
      if (res.data?.full_html) {
        setSelectedLead(prev => ({ 
          ...prev, 
          followup_draft: res.data.full_html,
          followup_subject: res.data.subject || prev.followup_subject || 'Following up'
        }));
        setEditedDraft(res.data.body || '');
      }
    } catch {}
  };

  const toggleSelect = (id) => {
    setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  };

  const toggleSelectAll = (filteredLeads) => {
    if (selectedIds.length === filteredLeads.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredLeads.map(f => f.id));
    }
  };

  const leadsToDisplay = followups; // Now handled by server-side filtering

  return (
    <div className="min-h-screen bg-[#0a0f1a] text-slate-200 pb-24">
      {/* Matrix Dispatch Drawer */}
      {isBulkSending && (
        <div className="fixed top-0 right-0 w-[400px] h-full bg-[#0f172a] border-l border-white/10 z-[100] shadow-2xl animate-in slide-in-from-right duration-500 flex flex-col">
          <div className="p-8 border-b border-white/5 bg-[#131b2e]">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-black text-white tracking-tighter italic uppercase">System Matrix Dispatch</h2>
              <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center">
                <ChevronsRight className="w-4 h-4 text-slate-400" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse" />
              <span className="text-[11px] font-black text-indigo-400 uppercase tracking-widest">{selectedIds.length} Active Operations</span>
            </div>
            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-[2px] mt-2">Background Operations Queue</p>
          </div>

          <div className="flex-1 p-8 space-y-8">
            <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 relative overflow-hidden">
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-4">
                  <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                    <Zap className="w-6 h-6 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-black text-white uppercase tracking-wider">Batch Outreach</h3>
                    <p className="text-[10px] text-slate-500 font-bold uppercase">Processing {selectedIds.length} Dispatch Units...</p>
                  </div>
                </div>
                <span className="text-sm font-black text-indigo-400 italic">{progress}%</span>
              </div>
              
              <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                <div 
                  className="h-full bg-gradient-to-r from-indigo-600 to-purple-600 transition-all duration-500 ease-out shadow-[0_0_20px_rgba(79,70,229,0.5)]"
                  style={{ width: `${progress}%` }}
                />
              </div>
              
              <div className="mt-4 flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-indigo-500" />
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">In Progress</span>
              </div>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between px-2">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Dispatch Logs</span>
                <Cpu className="w-3.5 h-3.5 text-slate-600" />
              </div>
              <div className="space-y-2">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="flex items-center gap-3 text-[10px] font-bold text-slate-600 uppercase italic">
                    <span className="text-indigo-500/50">[{new Date().toLocaleTimeString()}]</span>
                    <span>Synchronizing Unit-{Math.floor(Math.random() * 1000)}...</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="p-8 border-t border-white/5 bg-slate-950/50 text-center">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-relaxed">
              Multi-threaded processing active.<br/>You can safely navigate while tasks complete.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="border-b border-white/[0.05] bg-[#0f172a]/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-[1600px] mx-auto px-8 h-24 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
              <History className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-xl font-black text-white uppercase tracking-tight">Outreach Sequences</h1>
              <p className="text-[11px] text-slate-500 font-bold uppercase tracking-[2px] mt-0.5">Manual Approval Required</p>
            </div>
          </div>
          
          <div className="flex items-center gap-6">
            {/* Auto-Pilot Settings Panel */}
            <div className="bg-[#131722] border border-white/[0.05] rounded-xl px-4 py-2 flex items-center gap-4 shadow-xl">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${systemSettings.auto_followup ? 'bg-emerald-500 animate-pulse' : 'bg-slate-600'}`} />
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Auto-Pilot</span>
                <button
                  onClick={() => handleUpdateSettings(!systemSettings.auto_followup, systemSettings.outreach_daily_limit)}
                  className={`w-10 h-5 rounded-full relative transition-all ${systemSettings.auto_followup ? 'bg-indigo-600' : 'bg-slate-700'}`}
                >
                  <div className={`absolute top-1 w-3 h-3 rounded-full bg-white transition-all ${systemSettings.auto_followup ? 'left-6' : 'left-1'}`} />
                </button>
              </div>
              <div className="w-px h-6 bg-white/10" />
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Daily Limit</span>
                <input
                  type="number"
                  value={localLimit}
                  onChange={(e) => setLocalLimit(e.target.value)}
                  onBlur={() => {
                    const val = parseInt(localLimit, 10);
                    if (isNaN(val) || val <= 0) {
                      setLocalLimit(String(systemSettings.outreach_daily_limit));
                      return;
                    }
                    if (val !== systemSettings.outreach_daily_limit) {
                      handleUpdateSettings(systemSettings.auto_followup, val);
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.target.blur();
                    }
                  }}
                  className="w-16 bg-white/5 border border-white/10 rounded-lg py-1 px-2 text-[11px] font-black text-white text-center outline-none focus:border-indigo-500/50"
                />
              </div>
            </div>

            <div className="relative group">
              <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
                <Search className="w-4 h-4 text-slate-500 group-focus-within:text-indigo-400 transition-colors" />
              </div>
              <input
                type="text"
                placeholder="Search sequences..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-[#131722] border border-white/[0.05] rounded-xl pl-12 pr-6 py-3 w-[280px] text-[13px] font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/30 transition-all placeholder:text-slate-600"
              />
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-[1600px] mx-auto px-8 py-8">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-6 mb-6 p-5 bg-[#0f172a] border border-white/[0.05] rounded-2xl">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest">Lead Type</span>
          </div>
          <div className="flex gap-2">
            {TYPE_FILTERS.map(t => (
              <button
                key={t}
                onClick={() => { setTypeFilter(t); setStageFilter('All'); }}
                className={`px-4 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all cursor-pointer border ${
                  typeFilter === t
                    ? t === 'Investor'
                      ? 'bg-purple-500/20 text-purple-300 border-purple-500/40'
                      : t === 'Client'
                        ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                        : 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                    : 'bg-white/[0.03] text-slate-500 border-white/[0.05] hover:border-white/20'
                }`}
              >
                {t}
              </button>
            ))}
          </div>

          <div className="w-px h-6 bg-white/10" />

          <div className="flex items-center gap-2">
            <CheckCircle className="w-4 h-4 text-slate-500" />
            <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest">Status</span>
          </div>
          <div className="flex gap-2">
            {['DUE', 'SENT', 'REPLIED', 'IN PROGRESS', 'STOPPED'].map(s => (
              <button
                key={s}
                onClick={() => { setStatusFilter(s === 'IN PROGRESS' ? 'IN_PROGRESS' : s); setStageFilter('All'); }}
                className={`px-4 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all cursor-pointer border ${
                  statusFilter === (s === 'IN PROGRESS' ? 'IN_PROGRESS' : s)
                    ? s === 'IN PROGRESS' ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                    : s === 'STOPPED' ? 'bg-red-500/20 text-red-300 border-red-500/40'
                    : 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                    : 'bg-white/[0.03] text-slate-500 border-white/[0.05] hover:border-white/20'
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="w-px h-6 bg-white/10" />

          <div className="flex items-center gap-2">
            <Clock className="w-4 h-4 text-slate-500" />
            <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest">Stage</span>
          </div>
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setStageFilter('All')}
              className={`px-4 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all cursor-pointer border ${
                stageFilter === 'All'
                  ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40'
                  : 'bg-white/[0.03] text-slate-500 border-white/[0.05] hover:border-white/20'
              }`}
            >
              All
            </button>
            {(statusFilter === 'IN_PROGRESS' ? [1,2,3].map(s => ({ label: `Stage ${s}`, stage: s })) : STAGE_CONFIGS[typeFilter]).map(s => (
              <button
                key={s.label}
                onClick={() => setStageFilter(s.label)}
                className={`px-4 py-1.5 rounded-lg text-[11px] font-black uppercase tracking-wider transition-all cursor-pointer border ${
                  stageFilter === s.label
                    ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40'
                    : 'bg-white/[0.03] text-slate-500 border-white/[0.05] hover:border-white/20'
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
          {isLoading && (
            <div className="flex items-center gap-2 ml-auto">
              <Loader2 className="w-3.5 h-3.5 text-indigo-400 animate-spin" />
              <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest animate-pulse">Filtering...</span>
            </div>
          )}
        </div>

        {/* Search Bar */}
        <div className="relative mb-4">
          <div className="absolute inset-y-0 left-4 flex items-center pointer-events-none">
            <Search className="w-4 h-4 text-slate-500" />
          </div>
          <input
            type="text"
            placeholder="Search by name, email, company..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-[#0f172a] border border-white/[0.05] rounded-xl pl-12 pr-4 py-3 text-[13px] font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500/30 transition-all placeholder:text-slate-600"
          />
        </div>

        {/* List Actions */}
        <div className="flex items-center justify-between mb-4 px-2">
          <div className="flex items-center gap-3">
            <button
              onClick={() => toggleSelectAll(leadsToDisplay)}
              className="flex items-center gap-2 text-[11px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors cursor-pointer"
            >
              {selectedIds.length === leadsToDisplay.length && leadsToDisplay.length > 0 ? <CheckSquare className="w-4 h-4 text-indigo-400" /> : <Square className="w-4 h-4" />}
              {selectedIds.length === leadsToDisplay.length && leadsToDisplay.length > 0 ? 'Deselect All' : 'Select All'}
            </button>
            <span className="text-slate-700">|</span>
            <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest">
              {total} total results
              {selectedIds.length > 0 && <span className="text-indigo-400 ml-2">({selectedIds.length} selected)</span>}
            </p>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="h-[400px] flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-indigo-400 animate-spin" />
            <p className="text-xs font-bold text-slate-500 uppercase tracking-[2px]">Syncing pipeline...</p>
          </div>
        ) : leadsToDisplay.length === 0 ? (
          <div className="bg-[#0f172a] border border-white/[0.05] rounded-3xl p-20 flex flex-col items-center justify-center text-center space-y-6">
            <History className="w-10 h-10 text-slate-600" />
            <h3 className="text-lg font-black text-white uppercase italic">No Sequences Found</h3>
          </div>
        ) : (
          <>
          <div className="grid grid-cols-1 gap-3">
            {leadsToDisplay.map((lead) => {
              const lt = getLeadType(lead);
              const isInvestor = lt === 'Investor';
              const isSelected = selectedIds.includes(lead.id);
              return (
                <div
                  key={lead.id}
                  onClick={() => toggleSelect(lead.id)}
                  className={`bg-[#0f172a] border rounded-2xl p-5 transition-all hover:bg-[#131722] group cursor-pointer ${isSelected ? 'border-indigo-500/50 bg-indigo-500/[0.03]' : 'border-white/[0.05]'}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`w-6 h-6 rounded flex items-center justify-center border transition-all ${isSelected ? 'bg-indigo-600 border-indigo-600 text-white' : 'border-white/10 text-transparent'}`}>
                        <CheckCircle className="w-4 h-4" />
                      </div>
                      <div className="w-14 h-14 rounded-2xl bg-[#1a2235] flex items-center justify-center border border-white/[0.05] flex-shrink-0">
                        <User className="w-7 h-7 text-slate-400" />
                      </div>
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="text-[15px] font-black text-white group-hover:text-indigo-400 transition-colors">
                            {lead.first_name} {lead.last_name}
                          </h3>
                          <span className="text-slate-600 text-xs font-medium">({lead.email})</span>
                          <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full border ${isInvestor ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                            {lt}
                          </span>
                          <span className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-md border ${getStageColor(statusFilter === 'SENT' ? Math.max(0, lead.followup_stage - 1) : lead.followup_stage)}`}>
                            {statusFilter === 'IN_PROGRESS' ? `Stage ${lead.followup_stage}/3` : getStageLabel(lead.followup_stage, lead, statusFilter)}
                          </span>
                          {statusFilter === 'IN_PROGRESS' && (
                            <>
                              <span className={`text-[10px] font-black px-2 py-0.5 rounded-md border ${lead.followup_stage >= 3 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20'}`}>
                                {lead.followup_stage}x sent
                              </span>
                              {(lead.first_outreach_at || lead.last_outreach_at) && (
                                <span className="text-[10px] font-black px-2 py-0.5 rounded-md border bg-amber-500/10 text-amber-400 border-amber-500/20">
                                  {(() => {
                                    const d = new Date(lead.first_outreach_at || lead.last_outreach_at);
                                    if (isNaN(d.getTime())) return '';
                                    const now = new Date();
                                    const diff = now.getTime() - d.getTime();
                                    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
                                    return `${days}d`;
                                  })()}
                                </span>
                              )}
                            </>
                          )}
                        </div>
                        {lead.last_outreach_subject && (
                          <div className="text-[11px] font-black text-indigo-400/90 uppercase tracking-widest flex items-center gap-1.5 mt-1 bg-indigo-500/[0.04] border border-indigo-500/10 rounded-lg px-2.5 py-1 w-fit">
                            <span className="text-slate-500">Thread Subject:</span>
                            <span className="italic font-bold">"{lead.last_outreach_subject}"</span>
                          </div>
                        )}
                        <div className="flex items-center gap-3 text-[12px] font-bold text-slate-500">
                          <span className="flex items-center gap-1.5 text-slate-300">
                            <Building2 className="w-3.5 h-3.5 text-indigo-400" /> 
                            {lead.company_name || 'Independent'}
                          </span>
                          <span className="w-1 h-1 rounded-full bg-slate-700" />
                          <div className="flex flex-col gap-1 py-1 px-2 rounded-lg bg-white/[0.03]">
                            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-500">
                              <Calendar className="w-3 h-3 text-slate-600" />
                              <span>Initial Outreach: {lead.first_outreach_at ? parseUtcDate(lead.first_outreach_at)?.toLocaleString('en-IN', { day: '2-digit', month: 'short' }) : 'Never'}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] font-bold text-slate-400">
                              <Clock className="w-3 h-3 text-slate-600" />
                              <span>Last Outreach: {lead.last_outreach_at ? parseUtcDate(lead.last_outreach_at)?.toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Never'}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {statusFilter === 'IN_PROGRESS' && (
                        <div className="flex flex-col items-end gap-1">
                          <div className="flex items-center gap-1">
                            {[1,2,3].map(s => (
                              <div key={s} className={`w-6 h-6 rounded-full flex items-center justify-center text-[9px] font-black border transition-all ${lead.followup_stage >= s ? 'bg-indigo-500/30 border-indigo-500/60 text-indigo-300' : 'bg-white/5 border-white/10 text-slate-600'}`}>
                                {s}
                              </div>
                            ))}
                          </div>
                          <span className={`text-[8px] font-black uppercase tracking-widest px-2 py-0.5 rounded-md ${lead.followup_stage >= 3 ? 'bg-emerald-500/10 text-emerald-400' : lead.followup_stage >= 2 ? 'bg-amber-500/10 text-amber-400' : 'bg-indigo-500/10 text-indigo-400'}`}>
                            Stage {lead.followup_stage}/3
                          </span>
                        </div>
                      )}
                      <button
                        onClick={(e) => { e.stopPropagation(); openLeadDetails(lead); }}
                        className="p-2.5 bg-[#1a2235] text-slate-400 rounded-xl border border-white/[0.05] hover:text-white hover:border-white/20 transition-all cursor-pointer"
                      >
                        <Mail className="w-4 h-4" />
                      </button>
                      {statusFilter !== 'IN_PROGRESS' && (
                      <button
                        onClick={(e) => { e.stopPropagation(); handleApproveFollowup(lead.id); }}
                        className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-600/20 cursor-pointer"
                      >
                        <Zap className="w-3.5 h-3.5" /> Send
                      </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          {total > perPage && (
            <div className="mt-8 flex items-center justify-center gap-4">
              <button
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all text-[11px] font-black uppercase tracking-widest cursor-pointer"
              >
                Previous
              </button>
              <div className="flex items-center gap-2">
                {[...Array(Math.ceil(total / perPage))].map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setPage(i + 1)}
                    className={`w-10 h-10 rounded-xl border flex items-center justify-center text-[11px] font-black transition-all cursor-pointer ${
                      page === i + 1
                        ? 'bg-indigo-600 border-indigo-600 text-white'
                        : 'bg-white/5 border-white/10 text-slate-400 hover:border-white/20'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
              <button
                disabled={page === Math.ceil(total / perPage)}
                onClick={() => setPage(p => p + 1)}
                className="px-4 py-2 rounded-xl bg-white/5 border border-white/10 text-slate-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all text-[11px] font-black uppercase tracking-widest cursor-pointer"
              >
                Next
              </button>
            </div>
          )}
          </>
        )}
      </div>

      {/* Modal */}
      {isModalOpen && selectedLead && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center px-4">
          <div className="absolute inset-0 bg-black/90 backdrop-blur-md" onClick={() => setIsModalOpen(false)} />
          <div className="relative bg-[#0f172a] border border-white/10 rounded-[2rem] w-full max-w-3xl overflow-hidden shadow-2xl">
            <div className="p-8 border-b border-white/5 bg-gradient-to-b from-indigo-500/[0.03] to-transparent relative">
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
                  <User className="w-8 h-8 text-indigo-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-black text-white">{selectedLead.first_name} {selectedLead.last_name}</h2>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full border ${getLeadType(selectedLead) === 'Investor' ? 'bg-purple-500/10 text-purple-400 border-purple-500/20' : 'bg-blue-500/10 text-blue-400 border-blue-500/20'}`}>
                      {getLeadType(selectedLead)}
                    </span>
                    <span className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-md border ${getStageColor(selectedLead.followup_stage)}`}>
                      {getStageLabel(selectedLead.followup_stage, selectedLead)}
                    </span>
                  </div>
                </div>
              </div>
              <button onClick={() => setIsModalOpen(false)} className="absolute top-8 right-8 p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] text-slate-500 hover:text-white transition-all cursor-pointer border border-white/[0.05]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-8 space-y-6 max-h-[60vh] overflow-y-auto">
              {/* Display Subject Line */}
              <div className="bg-white/[0.02] border border-white/[0.05] rounded-2xl px-6 py-4 flex flex-col gap-1.5 relative overflow-hidden">
                <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500/60" />
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Email Subject</span>
                <span className="text-[14px] font-black text-indigo-400">
                  {selectedLead.followup_subject || selectedLead.last_outreach_subject || 'Following up'}
                </span>
              </div>

              <div className="flex items-center justify-between px-2">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Message Draft</span>
                <button 
                  onClick={() => setIsEditing(!isEditing)}
                  className={`px-3 py-1 rounded-lg text-[10px] font-black uppercase transition-all ${isEditing ? 'bg-indigo-500 text-white' : 'bg-white/5 text-slate-400 hover:text-white'}`}
                >
                  {isEditing ? 'Preview Mode' : '✏️ Edit Draft'}
                </button>
              </div>
              
              {isEditing ? (
                <textarea
                  value={editedDraft}
                  onChange={(e) => setEditedDraft(e.target.value)}
                  className="w-full h-[300px] bg-slate-950/60 border border-indigo-500/30 rounded-2xl p-6 text-slate-200 text-sm font-medium outline-none focus:border-indigo-500 transition-all resize-none leading-relaxed"
                  placeholder="Enter your custom message here..."
                />
              ) : (
                <div className="bg-slate-950/40 rounded-2xl p-8 border border-white/[0.03] relative overflow-hidden">
                  <div className="absolute top-0 left-0 w-1 h-full bg-indigo-500/40" />
                  <div
                    className="prose prose-invert prose-sm max-w-none text-slate-300 leading-relaxed text-[14px]"
                    dangerouslySetInnerHTML={{ __html: selectedLead.followup_draft || '<p class="animate-pulse italic text-slate-500">Generating draft...</p>' }}
                  />
                </div>
              )}
            </div>

            <div className="p-6 bg-[#131722]/50 border-t border-white/5 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                {isEditing && (
                  <button
                    onClick={handleSaveDraft}
                    disabled={isSaving}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white/5 text-slate-300 rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-white/10 transition-all cursor-pointer border border-white/10 disabled:opacity-50"
                  >
                    {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                    Save Changes
                  </button>
                )}
              </div>
              <div className="flex items-center gap-3">
                <button onClick={() => setIsModalOpen(false)} className="px-5 py-2.5 text-[11px] font-black text-slate-400 uppercase tracking-wider hover:text-white transition-colors cursor-pointer">Close</button>
                <button
                  onClick={() => handleApproveFollowup(selectedLead.id)}
                  disabled={isSaving}
                  className="flex items-center gap-2 px-7 py-2.5 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-indigo-500 transition-all cursor-pointer shadow-lg shadow-indigo-600/20"
                >
                  <Zap className="w-4 h-4" /> Approve & Send
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Bottom Action Bar */}
      {selectedIds.length > 0 && !isBulkSending && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[50] animate-in slide-in-from-bottom-10 duration-300">
          <div className="bg-[#131b2e]/80 backdrop-blur-2xl border border-indigo-500/30 rounded-2xl px-6 py-4 shadow-[0_0_50px_rgba(79,70,229,0.3)] flex items-center gap-6">
            <div className="flex flex-col">
              <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Selection Active</span>
              <span className="text-sm font-black text-white">{selectedIds.length} leads ready</span>
            </div>
            <div className="w-px h-8 bg-white/10" />
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSelectedIds([])}
                className="px-4 py-2 text-[11px] font-black text-slate-400 uppercase tracking-wider hover:text-white transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleBulkSend}
                className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 text-white rounded-xl text-[11px] font-black uppercase tracking-wider hover:bg-indigo-500 transition-all shadow-lg shadow-indigo-600/20 cursor-pointer"
              >
                <Zap className="w-4 h-4" /> Matrix Dispatch
              </button>
            </div>
          </div>
        </div>
      )}

      {notification && (
        <div className={`fixed bottom-8 left-1/2 -translate-x-1/2 px-8 py-4 rounded-2xl border backdrop-blur-xl shadow-2xl flex items-center gap-4 z-[100] animate-in fade-in slide-in-from-bottom-5 duration-500 ${notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
          {notification.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
          <p className="text-sm font-black uppercase tracking-wide">{notification.message}</p>
        </div>
      )}
    </div>
  );
};

export default Followups;
