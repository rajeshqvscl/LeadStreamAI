
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import api from '../services/api';
import {
  Users, Target, MessageSquare, Calendar,
  TrendingUp, BarChart3, Search, Filter,
  Download, MoreHorizontal, ChevronRight,
  Sparkles, ShieldCheck, Mail, ArrowUpRight,
  Clock, CheckCircle2, AlertCircle, X, AlertTriangle,
  FileText, Briefcase, Zap, Info, DollarSign,
  RefreshCcw, Terminal
} from 'lucide-react';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis
} from 'recharts';

const AdminDashboard = () => {
  const parseUtcDate = (dateStr) => {
    if (!dateStr) return null;
    let cleanStr = dateStr;
    if (!cleanStr.endsWith('Z') && !cleanStr.includes('+') && !/-[0-9]{2}:[0-9]{2}$/.test(cleanStr)) {
      cleanStr = cleanStr.replace(' ', 'T') + 'Z';
    }
    return new Date(cleanStr);
  };

  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({
    total_leads: 0,
    interested_leads: 0,
    meetings_scheduled: 0,
    conversion_rate: 0,
    avg_score: 0,
    active_followups: 0
  });
  const [statsLoading, setStatsLoading] = useState(true);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLead, setSelectedLead] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [ragStats, setRagStats] = useState(null);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, pages: 1, limit: 50 });
  const [availableSectors, setAvailableSectors] = useState([]);
  const [availableOwners, setAvailableOwners] = useState([]);
  const [systemSettings, setSystemSettings] = useState({ auto_followup: false, outreach_daily_limit: 50 });
  const [isUpdatingSettings, setIsUpdatingSettings] = useState(false);

  useEffect(() => {
    if (selectedLead?.id) {
      const fetchTimeline = async () => {
        setIsTimelineLoading(true);
        try {
          const res = await api.get(`/api/intelligence/leads/${selectedLead.id}/ai-timeline`);
          setTimelineData(res.data);
        } catch (err) {
          console.error('Timeline fetch failed', err);
        } finally {
          setIsTimelineLoading(false);
        }
      };
      fetchTimeline();
    } else {
      setTimelineData(null);
    }
  }, [selectedLead?.id]);
  const [filters, setFilters] = useState({
    type: 'ALL',
    status: 'ALL',
    intent: 'ALL',
    owner: 'ALL',
    sector: 'ALL'
  });
  const [chartBreakdowns, setChartBreakdowns] = useState(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState(new Set());
  const [isBulkActionLoading, setIsBulkActionLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [exportRange, setExportRange] = useState('ALL');
  const [lastUpdatedAt, setLastUpdatedAt] = useState(null);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [showAIMenu, setShowAIMenu] = useState(false);
  const [showColumnMenu, setShowColumnMenu] = useState(false);
  const allColumns = [
    { key: 'name', label: 'Name' }, { key: 'company', label: 'Company' },
    { key: 'email', label: 'Email Address' }, { key: 'type', label: 'Type' },
    { key: 'sector', label: 'Sector' }, { key: 'intent', label: 'Intent' },
    { key: 'rag', label: 'RAG Analysis' }, { key: 'check_size', label: 'Check Size' },
    { key: 'score', label: 'Score' }, { key: 'stage', label: 'Stage' },
    { key: 'followups', label: 'Followups' }, { key: 'rejection', label: 'Rejection' },
    { key: 'status', label: 'Status' }, { key: 'sent_draft', label: 'Sent/Draft' },
    { key: 'owner', label: 'Owner' }, { key: 'actions', label: 'Actions' },
  ];
  const [visibleColumns, setVisibleColumns] = useState(new Set(['name', 'company', 'type', 'status', 'stage', 'followups', 'owner', 'sent_draft', 'actions']));
  const activeFilterCount = [filters.type, filters.status, filters.intent, filters.owner, filters.sector].filter(v => v !== 'ALL').length;
  const [chartRange, setChartRange] = useState('ALL');

  const isWithinRange = useCallback((dateStr) => {
    if (chartRange === 'ALL' || !dateStr) return true;
    const d = parseUtcDate(dateStr);
    if (!d) return true;
    const now = Date.now();
    const diff = now - d.getTime();
    if (chartRange === 'DAILY') return diff < 86400000;
    if (chartRange === 'WEEKLY') return diff < 604800000;
    if (chartRange === 'MONTHLY') return diff < 2592000000;
    return true;
  }, [chartRange]);

  const chartFilteredLeads = useMemo(() => leads.filter(l => isWithinRange(l.updated_at)), [leads, isWithinRange]);

  const quickFilterCounts = useMemo(() => ({
    bounced: leads.filter(l => l.email_status === 'BOUNCED').length,
    active: leads.filter(l => l.followup_status === 'ACTIVE').length,
    pending: leads.filter(l => l.email_status === 'PENDING_APPROVAL').length,
    replied: leads.filter(l => l.email_status === 'REPLIED').length,
  }), [leads]);

  // Debounce Search Term
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchTerm), 500);
    return () => clearTimeout(timer);
  }, [searchTerm]);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const stripHtml = (html) => {
    if (!html) return "";
    return html.replace(/<[^>]*>?/gm, '');
  };

  const fetchGlobalStats = async (periodOverride, ownerOverride) => {
    setStatsLoading(true);
    try {
      const params = new URLSearchParams({ _t: Date.now() });
      const p = periodOverride || chartRange;
      const o = ownerOverride || filters.owner;
      if (o !== 'ALL') params.set('owner', o);
      if (p !== 'ALL') params.set('period', p);
      const res = await api.get(`/api/admin/stats/global?${params.toString()}`);
      setStats(res.data || {});
    } catch (err) {
      console.error('Failed to fetch stats', err);
    } finally {
      setStatsLoading(false);
    }
  };

  const fetchSystemSettings = async () => {
    try {
      const res = await api.get('/api/admin/stats/settings');
      setSystemSettings(res.data);
    } catch (err) {
      console.error('Failed to fetch system settings', err);
    }
  };

  const updateSystemSettings = async (updates) => {
    setIsUpdatingSettings(true);
    try {
      const newSettings = { ...systemSettings, ...updates };
      await api.post('/api/admin/stats/settings', newSettings);
      setSystemSettings(newSettings);
      showNotification('success', 'System Intelligence parameters updated successfully.');
    } catch (err) {
      showNotification('error', 'Communication Error: Failed to synchronize settings.');
    } finally {
      setIsUpdatingSettings(false);
    }
  };

  const fetchData = async (page = 1, silent = false, periodOverride) => {
    try {
      if (!silent) setLoading(true);
      const params = new URLSearchParams({
        page: page,
        limit: 50,
        ...filters,
        search: debouncedSearch || '',
        period: periodOverride || chartRange,
        _t: Date.now()
      });
      
      const leadsRes = await api.get(`/api/admin/leads/all?${params.toString()}`);
      
      if (leadsRes.data.leads) {
        setLeads(leadsRes.data.leads);
        setPagination(leadsRes.data.pagination);
        setAvailableSectors(leadsRes.data.sectors || []);
        setAvailableOwners(leadsRes.data.owners || []);
      }
      setLastUpdatedAt(new Date());
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    } finally {
      setLoading(false);
      setIsRagLoading(false);
    }
  };

  useEffect(() => {
    fetchGlobalStats();
    fetchSystemSettings();
  }, []);

  useEffect(() => {
    fetchGlobalStats();
    const fetchChartBreakdowns = async () => {
      try {
        const params = new URLSearchParams({ _t: Date.now() });
        if (filters.type !== 'ALL') params.set('type', filters.type);
        if (filters.status !== 'ALL') params.set('status', filters.status);
        if (filters.owner !== 'ALL') params.set('owner', filters.owner);
        if (filters.sector !== 'ALL') params.set('sector', filters.sector);
        if (chartRange !== 'ALL') params.set('period', chartRange);
        const res = await api.get(`/api/admin/stats/breakdown?${params.toString()}`);
        setChartBreakdowns(res.data);
      } catch (err) {
        console.error('Failed to fetch chart breakdowns', err);
      }
    };
    fetchChartBreakdowns();
  }, [filters, chartRange]);

  useEffect(() => {
    setCurrentPage(1);
  }, [filters, debouncedSearch]);

  useEffect(() => {
    fetchData(currentPage);

    // Auto-refresh interval (silent)
    const pollId = setInterval(() => {
      fetchData(currentPage, true);
      fetchGlobalStats();
      // Also refresh chart breakdowns silently
      const params = new URLSearchParams({ _t: Date.now() });
      if (filters.type !== 'ALL') params.set('type', filters.type);
      if (filters.status !== 'ALL') params.set('status', filters.status);
      if (filters.owner !== 'ALL') params.set('owner', filters.owner);
      if (filters.sector !== 'ALL') params.set('sector', filters.sector);
      if (chartRange !== 'ALL') params.set('period', chartRange);
      api.get(`/api/admin/stats/breakdown?${params.toString()}`).then(res => setChartBreakdowns(res.data)).catch(() => {});
    }, 20000);

    return () => clearInterval(pollId);
  }, [currentPage, filters, debouncedSearch, chartRange]);

  // Live counter for "last updated Xs ago"
  const [timeAgo, setTimeAgo] = useState('');
  useEffect(() => {
    const tick = () => {
      if (!lastUpdatedAt) { setTimeAgo(''); return; }
      const sec = Math.floor((Date.now() - lastUpdatedAt.getTime()) / 1000);
      setTimeAgo(sec < 5 ? 'just now' : sec < 60 ? `${sec}s ago` : `${Math.floor(sec / 60)}m ago`);
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => clearInterval(id);
  }, [lastUpdatedAt]);

  const filteredLeads = useMemo(() => {
    // Backend now handles filtering, so we just return the leads state
    return leads;
  }, [leads]);

  const owners = useMemo(() => {
    return ['ALL', ...availableOwners];
  }, [availableOwners]);

  const sectors = useMemo(() => {
    return ['ALL', ...availableSectors];
  }, [availableSectors]);

  const deriveType = (lead) => {
    const name = (lead.owner_name || '').toLowerCase();
    if (name.includes('yashika')) {
      const sectorLower = (lead.sector || '').toLowerCase();
      const draftLower = (lead.email_draft || '').toLowerCase();
      const personaLower = (lead.persona || '').toLowerCase();
      const subjLower = (lead.first_outreach_subject || lead.last_outreach_subject || '').toLowerCase();
      const isAiHiring = sectorLower.includes('hiring') ||
        draftLower.includes('hiring') ||
        personaLower.includes('hiring') ||
        subjLower.includes('hiring') ||
        sectorLower.includes('recruitment') ||
        draftLower.includes('recruitment') ||
        draftLower.includes('gigin');
      return isAiHiring ? 'Gigin AI' : 'Agrivijay';
    }
    const isInvestorTeam = name.includes('yashika') || name.includes('kajal') || name.includes('ayush');
    const isClientTeam = name.includes('palak');
    return isInvestorTeam ? 'INVESTOR' : isClientTeam ? 'CLIENT' : (lead.lead_type || 'CLIENT');
  };



  const chartSentByType = useMemo(() => {
    const counts = {};
    chartFilteredLeads.filter(l => l.email_status === 'SENT' || l.email_status === 'REPLIED' || l.email_status === 'BOUNCED' || l.email_status === 'OPENED' || l.email_status === 'CLICKED' || l.last_outreach_at).forEach(l => {
      const t = deriveType(l);
      counts[t] = (counts[t] || 0) + 1;
    });
    return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [chartFilteredLeads]);

  const chartFollowupsByType = useMemo(() => {
    const counts = {};
    chartFilteredLeads.filter(l => parseInt(l.followup_stage, 10) > 0).forEach(l => {
      const t = deriveType(l);
      counts[t] = (counts[t] || 0) + (parseInt(l.followup_stage, 10) || 1);
    });
    return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [chartFilteredLeads]);

  const chartSectorFiltered = useMemo(() => {
    const counts = {};
    chartFilteredLeads.forEach(l => {
      const s = l.sector || 'Other';
      counts[s] = (counts[s] || 0) + 1;
    });
    return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value);
  }, [chartFilteredLeads]);

  const chartBouncedDomains = useMemo(() => {
    const counts = {};
    leads.filter(l => l.email_status === 'BOUNCED').forEach(l => {
      const domain = (l.email || '').split('@')[1] || 'unknown';
      counts[domain] = (counts[domain] || 0) + 1;
    });
    return Object.entries(counts).map(([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value).slice(0, 5);
  }, [leads]);

  const exportMasterCSV = async () => {
    try {
      const rangeLabel = exportRange === 'ALL' ? 'full' : exportRange.toLowerCase();
      showNotification('success', `Preparing ${rangeLabel} master export...`);
      const res = await api.get(`/api/admin/leads/export?period=${exportRange}`);
      const allLeads = res.data.leads || [];
      const headers = ['Name','Email','Designation','Company','Type','Status','Intent','Score','Check Size','Rejection Reason','Sector/Industry','Owner','Last Interaction','AI Strategy','Analyst Report','Key Signals','Confidence %'].join(',');
      const rows = allLeads.map(l => {
        const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
        const rejectionReason = l.reply_intent === 'NOT_INTERESTED' ? (l.rag_advice?.split('.')[0] || 'No specific reason') : 'N/A';
        let derivedType = l.lead_type || 'CLIENT';
        const owner = (l.owner_name || '').toLowerCase();
        if (owner.includes('yashika')) {
          const sectorLower = (l.sector || '').toLowerCase();
          const draftLower = (l.email_draft || '').toLowerCase();
          const personaLower = (l.persona || '').toLowerCase();
          const subjLower = (l.first_outreach_subject || l.last_outreach_subject || '').toLowerCase();
          const isAiHiring = sectorLower.includes('hiring') || draftLower.includes('hiring') || personaLower.includes('hiring') || subjLower.includes('hiring') || sectorLower.includes('recruitment') || draftLower.includes('recruitment') || draftLower.includes('gigin');
          derivedType = isAiHiring ? 'Gigin AI' : 'Agrivijay';
        }
        return [clean(`${l.first_name} ${l.last_name}`),clean(l.email),clean(l.designation),clean(l.company_name || l.family_office_name),clean(derivedType),clean(l.email_status),clean(l.reply_intent),clean(l.sentiment_score),clean(l.deal_size),clean(rejectionReason),clean(l.sector || 'Other'),clean(l.owner_name),clean(parseUtcDate(l.updated_at).toLocaleDateString()),clean(l.rag_intelligence?.strategy || 'General Outreach'),clean(l.rag_advice || 'Analyst Review Pending'),clean(Array.isArray(l.rag_intelligence?.signals) ? l.rag_intelligence.signals.join(' | ') : (l.rag_intelligence?.signals || 'N/A')),clean(l.rag_intelligence?.confidence || 'N/A')].join(',');
      });
      const csv = [headers, ...rows].join('\n');
      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.setAttribute('hidden', ''); a.setAttribute('href', url); a.setAttribute('download', `FULL_MASTER_DATA_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      showNotification('success', `${rangeLabel === 'full' ? 'Full' : rangeLabel.charAt(0).toUpperCase() + rangeLabel.slice(1)} master export completed successfully!`);
    } catch (err) {
      console.error('Full export failed', err);
      showNotification('error', 'Export Failure: Unable to aggregate total workspace data.');
    }
  };
  const exportRejections = () => {
    const rejections = leads.filter(l => l.reply_intent === 'NOT_INTERESTED');
    const headers = ['Name','Company','Email','Check Size','Rejection Reason','Full Analyst Feedback'].join(',');
    const rows = rejections.map(l => {
      const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
      return [clean(`${l.first_name} ${l.last_name}`),clean(l.company_name || l.family_office_name),clean(l.email),clean(l.deal_size),clean(l.rag_advice?.split('.')[0] || 'Unknown'),clean(l.rag_advice)].join(',');
    });
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', ''); a.setAttribute('href', url); a.setAttribute('download', `REJECTION_ANALYSIS_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };
  const exportReplies = () => {
    const replies = leads.filter(l => l.email_status === 'REPLIED' || l.is_responded === true || (l.reply_intent && l.reply_intent !== 'NOT_INTERESTED'));
    const headers = ['Name','Company','Email','Intent','Score','Check Size','Response Summary'].join(',');
    const rows = replies.map(l => {
      const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
      return [clean(`${l.first_name} ${l.last_name}`),clean(l.company_name || l.family_office_name),clean(l.email),clean(l.reply_intent || 'N/A'),clean(l.sentiment_score),clean(l.deal_size),clean(l.rag_advice?.split('.')[0] || 'N/A')].join(',');
    });
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', ''); a.setAttribute('href', url); a.setAttribute('download', `REPLIES_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };
  const runAIClassify = async () => {
    try {
      const btn = document.getElementById('ai-classify-btn');
      const original = btn.innerHTML;
      btn.disabled = true; btn.innerHTML = '<span class="animate-pulse">🧠</span> Analyzing...';
      const res = await api.post('/api/intelligence/leads/ai-deep-classify');
      showNotification('success', `AI successfully categorized ${res.data.updated || 0} leads!`);
      fetchData();
      btn.disabled = false; btn.innerHTML = original;
    } catch (err) {
      console.error('AI Refresh failed', err);
      const btn = document.getElementById('ai-classify-btn');
      btn.disabled = false; btn.innerHTML = '❌ AI Classification Failed';
      setTimeout(() => { btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sparkles w-3.5 h-3.5"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path><path d="M5 3v4"></path><path d="M19 17v4"></path><path d="M3 5h4"></path><path d="M17 19h4"></path></svg> AI Deep Classify'; }, 3000);
    }
  };
  const refreshSectors = async () => {
    try {
      const btn = document.getElementById('refresh-sectors-btn');
      const original = btn.innerHTML;
      btn.disabled = true; btn.innerHTML = '<span class="animate-spin">🔄</span> Processing...';
      await api.post('/api/intelligence/leads/auto-enrich-sectors');
      showNotification('success', 'Workspace sectors re-classified successfully!');
      fetchData();
      btn.disabled = false; btn.innerHTML = original;
    } catch (err) {
      console.error('Refresh failed', err);
      const btn = document.getElementById('refresh-sectors-btn');
      btn.disabled = false; btn.innerHTML = 'Sector Refresh Failed';
    }
  };

  if (loading && leads.length === 0) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
          <p className="text-slate-400 font-medium animate-pulse">Aggregating Workspace Intelligence...</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {notification && (
        <div className="fixed top-20 right-4 z-[9999] flex items-center gap-2 px-4 py-2.5 rounded-xl shadow-2xl animate-in slide-in-from-right-8 pointer-events-auto text-[10px]" style={{ background: notification.type === 'success' ? 'rgba(16,185,129,0.12)' : 'rgba(244,63,94,0.12)', border: notification.type === 'success' ? '1px solid rgba(16,185,129,0.2)' : '1px solid rgba(244,63,94,0.2)', color: notification.type === 'success' ? '#34d399' : '#fb7185' }}>
          {notification.type === 'success' ? <CheckCircle2 className="w-3 h-3 shrink-0" /> : <AlertCircle className="w-3 h-3 shrink-0" />}
          <span className="font-black uppercase tracking-widest">{notification.message}</span>
        </div>
      )}
    <div className="flex flex-col min-h-screen bg-[#0a0c10] p-2 lg:p-4 overflow-x-hidden">
      {/* Header Section */}
      <div className="flex justify-between items-end mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-lg bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
            </div>
            <span className="text-[9px] font-black text-indigo-400 uppercase tracking-[0.2em]">Control Center</span>
          </div>
          <h1 className="text-2xl font-black text-white uppercase tracking-tight">Admin <span className="text-indigo-500">Intelligence</span></h1>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest shrink-0">{timeAgo}</div>
          <div className="relative">
            <button
              onClick={() => { setShowExportMenu(!showExportMenu); setShowAIMenu(false); }}
              className="flex items-center gap-2 px-4 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all shrink-0"
            >
              <Download className="w-3.5 h-3.5" /> Export <ChevronRight className={`w-3 h-3 transition-transform ${showExportMenu ? 'rotate-90' : ''}`} />
            </button>
            {showExportMenu && (
              <div className="absolute top-full right-0 mt-1 min-w-[200px] bg-[#111521] border border-white/10 rounded-xl shadow-2xl z-50 py-1 flex flex-col">
                <button onClick={() => { setShowExportMenu(false); exportMasterCSV(); }} className="flex items-center gap-2 px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-slate-300 hover:bg-white/5 hover:text-white transition-all text-left">
                  <Download className="w-3 h-3" /> Full Master Export
                </button>
                <button onClick={() => { setShowExportMenu(false); exportRejections(); }} className="flex items-center gap-2 px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-rose-400 hover:bg-white/5 transition-all text-left">
                  <AlertCircle className="w-3 h-3" /> Export Rejections
                </button>
                <button onClick={() => { setShowExportMenu(false); exportReplies(); }} className="flex items-center gap-2 px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-emerald-400 hover:bg-white/5 transition-all text-left">
                  <Mail className="w-3 h-3" /> Export Replies
                </button>
              </div>
            )}
          </div>

          <select
            value={exportRange}
            onChange={(e) => setExportRange(e.target.value)}
            className="bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-xl px-3 py-3 focus:outline-none focus:border-indigo-500/50 transition-all appearance-none cursor-pointer"
          >
            <option value="ALL">All Time</option>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="QUARTERLY">Quarterly</option>
            <option value="YEARLY">Yearly</option>
          </select>

          <div className="relative">
            <button
              onClick={() => { setShowAIMenu(!showAIMenu); setShowExportMenu(false); }}
              className="flex items-center gap-2 px-4 py-3 bg-violet-600/10 hover:bg-violet-600/20 text-violet-400 border border-violet-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all"
            >
              <Sparkles className="w-3.5 h-3.5" /> AI Actions <ChevronRight className={`w-3 h-3 transition-transform ${showAIMenu ? 'rotate-90' : ''}`} />
            </button>
            {showAIMenu && (
              <div className="absolute top-full right-0 mt-1 min-w-[200px] bg-[#111521] border border-white/10 rounded-xl shadow-2xl z-50 py-1 flex flex-col">
                <button onClick={async () => { setShowAIMenu(false); await runAIClassify(); }} id="ai-classify-btn" className="flex items-center gap-2 px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-violet-400 hover:bg-white/5 transition-all text-left">
                  <Sparkles className="w-3 h-3" /> AI Deep Classify
                </button>
                <button onClick={async () => { setShowAIMenu(false); await refreshSectors(); }} id="refresh-sectors-btn" className="flex items-center gap-2 px-4 py-2.5 text-[10px] font-black uppercase tracking-widest text-indigo-400 hover:bg-white/5 transition-all text-left">
                  <RefreshCcw className="w-3 h-3" /> Refresh All Sectors
                </button>
              </div>
            )}
          </div>
        </div>
      </div>


      {/* Analytics Grid */}
      <div className="relative">
        {loading && (
          <div className="absolute inset-0 z-10 bg-[#0a0c10]/60 flex items-center justify-center rounded-xl">
            <div className="w-6 h-6 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
          </div>
        )}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 mb-4">
        {[
          { label: 'Total Sent', value: stats.total_leads, icon: Users, color: 'indigo', desc: 'Emails successfully sent', contrib: 'From Database' },
          { label: 'Followups Sent', value: stats.total_followups, icon: Mail, color: 'emerald', desc: 'Total stages sent', contrib: 'Activity Log' },
          { label: 'Engaged', value: stats.engaged, icon: Target, color: 'blue', desc: 'Replied or interested', contrib: 'Email Status & Intent' },
          { label: 'Bounced', value: stats.bounced, icon: AlertCircle, color: 'rose', desc: `${stats.bounce_rate || 0}% of sent — invalid emails`, contrib: 'Email Status' },
          { label: 'Meetings', value: stats.meetings, icon: Calendar, color: 'rose', desc: 'Scheduled calls', contrib: 'Meeting Status' },
          { label: 'Interested', value: stats.interested, icon: MessageSquare, color: 'violet', desc: 'Intent identified', contrib: 'AI Classification' },
          { label: 'Avg Score', value: stats.avg_score, icon: TrendingUp, color: 'sky', desc: 'Overall sentiment', contrib: 'Lead Sentiment' },
        ].map((stat, i) => (
          <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-3 hover:border-white/10 transition-all group relative overflow-hidden">
            <div className={`absolute top-0 right-0 w-16 h-16 bg-${stat.color}-500/5 blur-2xl rounded-full -mr-8 -mt-8`} />
            <div className="flex items-start justify-between relative z-10 mb-2">
              <div className={`w-8 h-8 rounded-lg bg-${stat.color}-500/10 flex items-center justify-center border border-${stat.color}-500/20`}>
                <stat.icon className={`w-4 h-4 text-${stat.color}-400`} />
              </div>
              <div className="text-[7px] font-black text-slate-700 uppercase tracking-widest">{stat.contrib}</div>
            </div>
            <div className="relative z-10">
              {statsLoading ? (
                <div className="h-7 w-20 bg-white/5 rounded-lg animate-pulse mb-1.5" />
              ) : (
                <div className="text-[18px] font-black text-white leading-tight mb-0.5">{stat.value}</div>
              )}
              <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest leading-none mb-1">{stat.label}</div>
              <div className="text-[7px] text-slate-600 font-bold uppercase tracking-widest leading-none">{stat.desc}</div>
            </div>
          </div>
        ))}
      </div>
      </div>

      {/* Search & Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="relative flex-1 min-w-[300px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search across all leads, companies, and emails..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-white/[0.03] border border-white/5 rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 transition-all"
          />
        </div>

        <button
          onClick={() => setFilters({ ...filters, status: filters.status === 'REPLIED' ? 'ALL' : 'REPLIED' })}
          className={`flex items-center gap-1.5 px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border shrink-0 ${filters.status === 'REPLIED' ? 'bg-blue-500/20 border-blue-500/40 text-blue-400 shadow-lg shadow-blue-500/10' : 'bg-white/[0.03] border-white/5 text-slate-500 hover:text-white hover:bg-white/[0.06]'}`}
        >
          <Mail className={`w-3.5 h-3.5 ${filters.status === 'REPLIED' ? 'text-blue-400' : ''}`} />
          Replies
        </button>

        <div className="relative shrink-0">
          <button onClick={() => { setShowColumnMenu(!showColumnMenu); setShowExportMenu(false); setShowAIMenu(false); }} className="flex items-center gap-1.5 px-3 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border bg-white/[0.03] border-white/5 text-slate-500 hover:text-white hover:bg-white/[0.06]">
            <BarChart3 className="w-3.5 h-3.5" /> Columns
          </button>
          {showColumnMenu && (
            <div className="absolute top-full left-0 mt-1 min-w-[180px] bg-[#111521] border border-white/10 rounded-xl shadow-2xl z-50 py-2 px-1">
              {allColumns.map(col => (
                <label key={col.key} className="flex items-center gap-2 px-3 py-1.5 text-[9px] font-black uppercase tracking-widest text-slate-400 hover:bg-white/5 hover:text-white rounded-lg cursor-pointer transition-all">
                  <input type="checkbox" checked={visibleColumns.has(col.key)} onChange={() => { const next = new Set(visibleColumns); next.has(col.key) ? next.delete(col.key) : next.add(col.key); setVisibleColumns(next); }} className="accent-indigo-500 w-3 h-3" />
                  {col.label}
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            <option value="ALL">All Types</option>
            <option value="AGRIVIJAY">Agrivijay</option>
            <option value="GIGIN AI">Gigin AI</option>
            <option value="INVESTOR">Investors</option>
            <option value="CLIENT">Clients</option>
          </select>

          <select
            value={chartRange}
            onChange={(e) => {
              const val = e.target.value;
              setChartRange(val);
              fetchData(1, false, val);
              fetchGlobalStats(val, filters.owner);
            }}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            <option value="ALL">All Time</option>
            <option value="DAILY">Daily</option>
            <option value="WEEKLY">Weekly</option>
            <option value="MONTHLY">Monthly</option>
            <option value="QUARTERLY">Quarterly</option>
          </select>

          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            <option value="ALL">All Statuses</option>
            <option value="NEW">New</option>
            <option value="Contacted">Contacted</option>
            <option value="Interested">Interested</option>
            <option value="REPLIED">Replied</option>
            <option value="Meeting Scheduled">Meeting Scheduled</option>
          </select>

          <select
            value={filters.owner}
            onChange={(e) => {
              const val = e.target.value;
              setFilters({ ...filters, owner: val });
              fetchGlobalStats(chartRange, val);
            }}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            {owners.map(o => (
              <option key={o} value={o}>{o === 'ALL' ? 'All Owners' : o}</option>
            ))}
          </select>

          <select
            value={filters.sector}
            onChange={(e) => setFilters({ ...filters, sector: e.target.value })}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            {sectors.map(s => (
              <option key={s} value={s}>{s === 'ALL' ? 'All Sectors' : s}</option>
            ))}
          </select>

          {activeFilterCount > 0 && (
            <div className="flex items-center gap-2 shrink-0">
              <span className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-lg text-[9px] font-black text-indigo-400 uppercase tracking-widest">{activeFilterCount} active</span>
              <button onClick={() => { setFilters({ type: 'ALL', status: 'ALL', intent: 'ALL', owner: 'ALL', sector: 'ALL' }); fetchGlobalStats(chartRange, 'ALL'); }} className="px-2 py-1 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg text-[9px] font-black text-slate-500 hover:text-white uppercase tracking-widest transition-all">Clear</button>
            </div>
          )}
        </div>
      </div>

      {/* Quick Filters Row */}
      <div className="flex flex-wrap items-center gap-2 mb-6">
        {[
          { label: 'Bounced', count: quickFilterCounts.bounced, filterVal: 'BOUNCED', color: 'rose' },
          { label: 'Active', count: quickFilterCounts.active, filterVal: 'ACTIVE', color: 'indigo' },
          { label: 'Pending Approval', count: quickFilterCounts.pending, filterVal: 'PENDING_APPROVAL', color: 'amber' },
          { label: 'Replied', count: quickFilterCounts.replied, filterVal: 'REPLIED', color: 'blue' },
        ].map((chip, i) => (
          <button
            key={i}
            onClick={() => setFilters({ ...filters, status: filters.status === chip.filterVal ? 'ALL' : chip.filterVal })}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all border ${
              filters.status === chip.filterVal
                ? `bg-${chip.color}-500/20 border-${chip.color}-500/40 text-${chip.color}-400 shadow-lg shadow-${chip.color}-500/10`
                : 'bg-white/[0.03] border-white/5 text-slate-500 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            {chip.label} <span className="text-white/70">{chip.count}</span>
          </button>
        ))}
      </div>

      {/* Simplified Visual Analytics */}
      <div className="flex items-center gap-3 mb-4">
        <h3 className="text-[11px] font-black text-white uppercase tracking-[0.2em]">Analytics</h3>
        <div className="h-4 w-px bg-white/10" />
      </div>

      {/* Charts Grid: Sent, Followups, Sector, Bounced Domains */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-3 mb-6">
        {[
          { title: 'Sent by Type', desc: 'Leads with outreach sent', icon: Mail, data: chartSentByType },
          { title: 'Followups by Type', desc: 'Total followup stages sent', icon: Zap, data: chartFollowupsByType },
          { title: 'Sectors', desc: 'Lead volume by sector', icon: Briefcase, data: chartSectorFiltered },
          { title: 'Top Bounced Domains', desc: 'Most common invalid domains', icon: AlertCircle, data: chartBouncedDomains },
        ].map((item, i) => (
          <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-3 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <div>
                <h3 className="text-[10px] font-black text-white uppercase tracking-wider">{item.title}</h3>
                <p className="text-[7px] text-slate-600 font-bold uppercase tracking-widest leading-none">{item.desc}</p>
              </div>
              <item.icon className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="flex-1 min-h-[100px]">
              {item.data.length === 0 ? (
                <div className="flex items-center justify-center h-full text-[8px] text-slate-700 font-black uppercase tracking-widest">No data</div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={(() => { const s = [...item.data].sort((a, b) => b.value - a.value); const t = s.slice(0, 6); const r = s.slice(6); if (r.length > 0) t.push({ label: 'Others', value: r.reduce((x, y) => x + y.value, 0) }); return t; })()} layout="vertical" margin={{ right: 20, left: 0 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="label" type="category" width={55} tick={{ fill: '#94a3b8', fontSize: 8, fontWeight: 700 }} />
                    <Tooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '9px' }} />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[0, 3, 3, 0]} barSize={10} label={{ position: 'right', fill: '#94a3b8', fontSize: 9 }} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* RAG DEBUG PANEL (NEW FEATURE) */}
      {ragStats && (
        <div className="bg-[#111521]/80 backdrop-blur-xl border border-indigo-500/20 rounded-2xl p-6 mb-6 flex flex-wrap items-center justify-between gap-6 shadow-[0_0_50px_rgba(79,70,229,0.05)]">
            <div className="flex items-center gap-4">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${ragStats.status === 'ONLINE' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border-rose-500/20 text-rose-400'}`}>
                    <Terminal className="w-6 h-6" />
                </div>
                <div>
                    <h3 className="text-white text-[13px] font-black uppercase tracking-widest flex items-center gap-2">
                        RAG Engine Status
                        <div className={`w-2 h-2 rounded-full animate-pulse ${ragStats.status === 'ONLINE' ? 'bg-emerald-500' : 'bg-rose-500'}`} />
                    </h3>
                    <p className="text-slate-500 text-[10px] font-black uppercase tracking-widest">{ragStats.engine}</p>
                </div>
            </div>

            <div className="flex items-center gap-12">
                <div className="text-center">
                    <div className="text-xl font-black text-white">{ragStats.latency_ms}ms</div>
                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Latency</div>
                </div>
                <div className="text-center">
                    <div className="text-xl font-black text-white">{ragStats.analyzed_leads}</div>
                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Analyzed</div>
                </div>
                <div className="text-center">
                    <div className="text-xl font-black text-white">{ragStats.reports_generated}</div>
                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Reports</div>
                </div>
            </div>

            <div className="flex gap-2">
                {(ragStats.active_tasks || []).map((task, i) => (
                    <span key={i} className="px-2 py-1 bg-white/5 border border-white/10 rounded text-[8px] font-black text-slate-400 uppercase tracking-widest">
                        {task}
                    </span>
                ))}
            </div>
        </div>
      )}

      {/* Main Database Table */}
      <div className="bg-[#0f111a] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl relative">
        {loading && leads.length > 0 && (
          <div className="absolute inset-0 z-[20] bg-black/20 backdrop-blur-[2px] flex items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <div className="w-8 h-8 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
              <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Updating...</span>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse border border-white/5">
            <thead>
              <tr className="bg-[#0f111a] border-b border-white/5 sticky top-0 z-10">
                {visibleColumns.has('name') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Name</th>}
                {visibleColumns.has('company') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Company</th>}
                {visibleColumns.has('email') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Email Address</th>}
                {visibleColumns.has('type') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Type</th>}
                {visibleColumns.has('sector') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Sector</th>}
                {visibleColumns.has('intent') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Intent</th>}
                {visibleColumns.has('rag') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">RAG Analysis</th>}
                {visibleColumns.has('check_size') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Check Size</th>}
                {visibleColumns.has('score') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Score</th>}
                {visibleColumns.has('stage') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Stage</th>}
                {visibleColumns.has('followups') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Followups</th>}
                {visibleColumns.has('rejection') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Rejection / Reason</th>}
                {visibleColumns.has('status') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Status</th>}
                {visibleColumns.has('sent_draft') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Sent/Draft</th>}
                {visibleColumns.has('owner') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Owner</th>}
                {visibleColumns.has('actions') && <th className="px-1 py-1 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {filteredLeads.map((lead) => (
                  <tr
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  className="hover:bg-white/[0.02] transition-colors cursor-pointer group"
                >
                   {visibleColumns.has('name') && <td className="px-1 py-1 border border-white/5">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-500/10 flex items-center justify-center border border-white/10 group-hover:border-indigo-500/30 transition-all shrink-0">
                        <span className="text-[11px] font-black text-indigo-400">
                          {lead.first_name?.[0]}{lead.last_name?.[0] || lead.first_name?.[1] || ''}
                        </span>
                      </div>
                      <div className="flex flex-col gap-0 min-w-0">
                        <div className="text-[12px] font-bold text-white group-hover:text-indigo-400 transition-colors whitespace-nowrap">{lead.first_name} {lead.last_name}</div>
                        <div className="flex items-center gap-0.5">
                          {(() => {
                            const sevenDays = 7 * 24 * 60 * 60 * 1000;
                            const lastAction = parseUtcDate(lead.last_outreach_at);
                            const isStalled = lastAction && (Date.now() - lastAction.getTime()) > sevenDays;
                            const isFinal = ['Meeting Scheduled', 'REJECTED', 'NOT_INTERESTED'].includes(lead.email_status) || ['MEETING_SCHEDULED', 'NOT_INTERESTED'].includes(lead.reply_intent);
                            if (isStalled && !isFinal) {
                              return (
                                <div className="flex items-center gap-1 px-1.5 py-0.5 bg-rose-500/20 border border-rose-500/30 rounded text-[9px] font-black text-rose-400 animate-pulse">
                                  <AlertTriangle className="w-2.5 h-2.5" /> STALLED
                                </div>
                              );
                            }
                            return null;
                          })()}
                          {lead.country === 'USA' && <span>🇺🇸</span>}
                          {lead.country === 'UK' && <span>🇬🇧</span>}
                          {lead.country === 'India' && <span>🇮🇳</span>}
                          {lead.country === 'UAE' && <span>🇦🇪</span>}
                          {lead.country === 'Singapore' && <span>🇸🇬</span>}
                        </div>
                      </div>
                    </div>
                  </td>}
                  {visibleColumns.has('company') && <td className="px-1 py-1 border border-white/5">
                    <div className="text-[11px] font-bold text-slate-400 uppercase tracking-tighter">
                      {(lead.company_name === 'Independent' || !lead.company_name) ? '—' : (lead.company_name || lead.family_office_name || '—')}
                    </div>
                    </td>}
                  {visibleColumns.has('email') && <td className="px-1 py-1 border border-white/5">
                    <div>
                      <div className="text-[12px] font-bold text-white break-words">{lead.email}</div>
                      {lead.phone && <div className="text-[9px] text-slate-500 font-medium">{lead.phone}</div>}
                    </div>
                  </td>}
                  {visibleColumns.has('type') && <td className="px-1 py-1 border border-white/5">
                    {(() => {
                      const name = (lead.owner_name || '').toLowerCase();
                      const isInvestorTeam = name.includes('yashika') || name.includes('kajal') || name.includes('ayush');
                      const isClientTeam = name.includes('palak');
                      
                      let derivedType = isInvestorTeam ? 'INVESTOR' : isClientTeam ? 'CLIENT' : (lead.lead_type || 'CLIENT');
                      
                      // Custom branding logic based on user request
                      if (name.includes('yashika')) {
                        const sectorLower = (lead.sector || '').toLowerCase();
                        const draftLower = (lead.email_draft || '').toLowerCase();
                        const personaLower = (lead.persona || '').toLowerCase();
                        const subjLower = (lead.first_outreach_subject || lead.last_outreach_subject || '').toLowerCase();
                        const isAiHiring = sectorLower.includes('hiring') || 
                                           draftLower.includes('hiring') || 
                                           personaLower.includes('hiring') || 
                                           subjLower.includes('hiring') || 
                                           sectorLower.includes('recruitment') || 
                                           draftLower.includes('recruitment') ||
                                           draftLower.includes('gigin');
                        if (isAiHiring) {
                          derivedType = 'Gigin AI';
                        } else {
                          derivedType = 'Agrivijay';
                        }
                      }

                      const isSpecial = derivedType === 'Agrivijay' || derivedType === 'Gigin AI';
                      const isInvestor = derivedType.toUpperCase() === 'INVESTOR';
                      
                      return (
                        <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${
                          derivedType === 'Agrivijay' ? 'bg-amber-500/10 border-amber-500/20 text-amber-500' : 
                          derivedType === 'Gigin AI' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' :
                          isInvestor ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 
                          'bg-white/5 border-white/10 text-slate-400'
                        }`}>
                          {isInvestor ? <Target className="w-3 h-3" /> : <Users className="w-3 h-3" />}
                          {derivedType}
                        </span>
                      );
                    })()}
                  </td>}
                  {visibleColumns.has('sector') && <td className="px-1 py-1 border border-white/5">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-indigo-500/5 border border-indigo-500/20 text-indigo-400">
                      <Briefcase className="w-3 h-3" />
                      {lead.sector || 'OTHER'}
                    </span>
                  </td>}
                  {visibleColumns.has('intent') && <td className="px-1 py-1 border border-white/5">
                    {lead.reply_intent ? (
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${lead.reply_intent === 'INTERESTED' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : lead.reply_intent === 'NOT_INTERESTED' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}>
                        {lead.reply_intent}
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 tracking-widest uppercase italic">Awaiting reply</span>
                    )}
                  </td>}
                  {visibleColumns.has('rag') && <td className="px-1 py-1 border border-white/5">
                    {lead.rag_intelligence?.verdict ? (
                      <div className="flex flex-col gap-1">
                        <span className={`text-[9px] font-black uppercase tracking-widest ${lead.rag_intelligence.verdict === 'POSITIVE' ? 'text-emerald-400' : lead.rag_intelligence.verdict === 'STRONG' ? 'text-blue-400' : 'text-amber-400'}`}>
                          {lead.rag_intelligence.verdict}
                        </span>
                        <span className="text-[10px] font-medium text-indigo-400">{lead.rag_intelligence.category || '—'}</span>
                      </div>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 uppercase tracking-widest italic">—</span>
                    )}
                  </td>}
                  {visibleColumns.has('check_size') && <td className="px-1 py-1 border border-white/5">
                    <div className="flex items-center gap-2">
                      <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                      <span className="text-[13px] font-black text-white">{lead.deal_size || '—'}</span>
                    </div>
                  </td>}
                  {visibleColumns.has('score') && <td className="px-1.5 py-1.5 text-center border border-white/5">
                    <div className={`text-[15px] font-black ${(lead.rag_intelligence?.sentiment_score || lead.sentiment_score) >= 80 ? 'text-emerald-400' : (lead.rag_intelligence?.sentiment_score || lead.sentiment_score) >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {lead.rag_intelligence?.sentiment_score || lead.sentiment_score || '—'}
                    </div>
                  </td>}
                  {visibleColumns.has('stage') && <td className="px-1.5 py-1.5 text-center border border-white/5">
                    {(() => {
                      const stageNum = parseInt(lead.followup_stage, 10) || 0;
                      return (
                        <div className="flex flex-col items-center gap-1">
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-black tracking-widest uppercase ${stageNum > 0 ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-slate-800 text-slate-500 border border-white/5'}`}>
                            {stageNum === 0 ? 'Initial' : `Stage ${stageNum}`}
                          </span>
                          {lead.last_outreach_at && (
                            <span className="text-[7px] font-bold text-slate-600 uppercase">
                              Sent {parseUtcDate(lead.last_outreach_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}
                            </span>
                          )}
                        </div>
                      );
                    })()}
                  </td>}
                  {visibleColumns.has('followups') && <td className="px-1.5 py-1.5 text-center border border-white/5">
                    {(() => {
                      const stageNum = parseInt(lead.followup_stage, 10) || 0;
                      const isPalak = (lead.owner_name || '').toLowerCase().includes('palak');
                      const maxStage = isPalak ? 2 : 3;
                      return (
                        <div className="flex flex-col items-center">
                          <span className={`px-2.5 py-1 rounded-xl text-[10px] font-black uppercase tracking-wider border ${
                            stageNum === 1 ? 'bg-indigo-500/10 border-indigo-500/20 text-indigo-400' :
                            stageNum === 2 ? 'bg-purple-500/10 border-purple-500/20 text-purple-400' :
                            stageNum >= maxStage ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' :
                            'bg-white/5 border-white/10 text-slate-400'
                          }`}>
                            {stageNum === 0 ? `0 / ${maxStage} Sent` :
                             stageNum === 1 ? `1 / ${maxStage} Sent` :
                             stageNum === 2 ? `2 / ${maxStage} Sent` :
                             stageNum >= maxStage ? `${maxStage} / ${maxStage} Sent` : `0 / ${maxStage} Sent`}
                          </span>
                          {lead.followup_status === 'ACTIVE' && stageNum < maxStage && (
                            <span className="text-[8px] text-indigo-400/90 font-black uppercase tracking-widest mt-1 animate-pulse">
                              ● Active
                            </span>
                          )}
                        </div>
                      );
                    })()}
                  </td>}
                  {visibleColumns.has('rejection') && <td className="px-1 py-1 border border-white/5">
                    {lead.reply_intent === 'NOT_INTERESTED' ? (
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 rounded-md w-fit">
                          <AlertCircle className="w-2.5 h-2.5 text-rose-400" />
                          <span className="text-[9px] font-black text-rose-400 uppercase tracking-widest">Rejected ({lead.deal_size || 'N/A'})</span>
                        </div>
                        <div className="text-[10px] font-medium text-slate-400 italic break-words">
                          "{stripHtml(lead.rag_advice).split('.')[0]}"
                        </div>
                      </div>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 uppercase tracking-widest">N/A</span>
                    )}
                  </td>}
                  {visibleColumns.has('status') && <td className="px-1 py-1 border border-white/5">
                    <div className="flex flex-col gap-1">
                      <div className="text-[11px] font-black text-white uppercase tracking-wider">{lead.email_status || 'NEW'}</div>
                      {lead.followup_status === 'ACTIVE' && (
                        <div className="flex items-center gap-1 text-[8px] font-black text-indigo-400 uppercase tracking-widest">
                          <Zap className="w-2.5 h-2.5 animate-pulse" /> Sequence Active
                        </div>
                      )}
                    </div>
                  </td>}
                  {visibleColumns.has('sent_draft') && <td className="px-1 py-1 border border-white/5">
                    {(() => {
                      const st = (lead.email_status || '').toUpperCase();
                      if (st === 'SENT' || (st === '' && lead.last_outreach_at)) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">Sent</span>;
                      if (st === 'PENDING_APPROVAL' || st === 'APPROVED') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-amber-500/10 border border-amber-500/20 text-amber-400">Draft</span>;
                      if (st === 'REJECTED') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-rose-500/10 border border-rose-500/20 text-rose-400">Rejected</span>;
                      if (st === 'BOUNCED') {
                        const raw = stripHtml(lead.bounce_reason || '').replace(/^Email bounced\s*[—–-]\s*/i, '').replace(/^Server Response:\s*/i, '').trim();
                        const short = !raw ? 'Inbox full' :
                          /doesn.*exist|5\.1\.1|no such user|invalid.*address/i.test(raw) ? "Email doesn't exist" :
                          /inbox.*full|over quota|5\.2\.2/i.test(raw) ? 'Inbox full' :
                          /spam|blocked|5\.7\.1/i.test(raw) ? 'Blocked by spam filter' :
                          /domain.*not|5\.1\.2|5\.4\.1/i.test(raw) ? "Domain doesn't exist" :
                          /temporar|try again|4\.\d/i.test(raw) ? 'Temporary issue' :
                          raw.length > 40 ? raw.slice(0, 40) + '…' : raw;
                        return <div className="flex flex-col gap-0.5"><span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-red-500/10 border border-red-500/20 text-red-400 w-fit">Bounced</span><span className="text-[8px] text-red-400/70 italic leading-tight max-w-[140px] truncate" title={raw || 'Inbox full'}>{short}</span></div>;
                      }
                      if (st === 'REPLIED') return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-blue-500/10 border border-blue-500/20 text-blue-400">Replied</span>;
                      if (lead.email_draft) return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[9px] font-black bg-amber-500/10 border border-amber-500/20 text-amber-400">Draft</span>;
                      return <span className="text-[10px] font-bold text-slate-700 italic">—</span>;
                    })()}
                  </td>}
                  {visibleColumns.has('owner') && <td className="px-1 py-1 border border-white/5">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center border border-white/5">
                        <Users className="w-3 h-3 text-slate-500" />
                      </div>
                      <span className="text-[11px] font-bold text-slate-400">{lead.owner_name}</span>
                    </div>
                  </td>}
                  {visibleColumns.has('actions') && <td className="px-1 py-1 border border-white/5">
                    {(() => {
                      const d = parseUtcDate(lead.last_outreach_at);
                      if (!d) return <span className="text-[11px] text-slate-600">—</span>;
                      return (
                        <div className="flex flex-col items-end gap-0.5 text-slate-500">
                          <div className="flex items-center gap-1.5">
                            <Clock className="w-3.5 h-3.5 text-slate-600" />
                            <span className="text-[11px] font-black text-slate-400 uppercase">{d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short' })}</span>
                          </div>
                          <span className="text-[9px] font-bold text-slate-600 tracking-tighter">
                            {d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })}
                          </span>
                        </div>
                      );
                    })()}
                  </td>}
                  {visibleColumns.has('actions') && <td className="px-1.5 py-1.5 text-right border border-white/5">
                    <div className="flex items-center justify-end gap-1">
                      <button 
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            setNotification({ type: 'success', message: 'Triggering Deep AI Analysis...' });
                            await api.post(`/api/intelligence/analyze-lead/${lead.id}`);
                            fetchData();
                            setNotification({ type: 'success', message: 'Analysis Complete! Data enriched.' });
                          } catch (err) {
                            setNotification({ type: 'error', message: 'Analysis failed. Check RAG connectivity.' });
                          }
                        }}
                        className="p-2 hover:bg-indigo-500/10 rounded-lg transition-colors text-indigo-400" 
                        title="Analyze Intelligence"
                      >
                        <Zap className="w-4 h-4" />
                      </button>
                      <button className="p-2 hover:bg-white/5 rounded-lg transition-colors text-slate-500 hover:text-white">
                        <MoreHorizontal className="w-4 h-4" />
                      </button>
                    </div>
                  </td>}
                </tr>
              ))}
            </tbody>
          </table>

          {filteredLeads.length === 0 && (
            <div className="p-20 text-center">
              <Search className="w-12 h-12 text-slate-700 mx-auto mb-4" />
              <div className="text-slate-500 font-bold uppercase tracking-widest">No matching leads found across the workspace</div>
            </div>
          )}

          {/* Pagination Controls */}
          {pagination.pages > 1 && (
            <div className="flex flex-col gap-6 p-8 border-t border-white/5 bg-[#0d0f16]/50">
              <div className="flex items-center justify-between">
                <div className="text-[10px] font-black text-slate-500 uppercase tracking-[3px]">
                  Workspace Index <span className="text-white mx-2">{(currentPage - 1) * pagination.limit + 1} – {Math.min(currentPage * pagination.limit, pagination.total)}</span> 
                  <span className="text-slate-700 mx-2">|</span> Total <span className="text-indigo-400">{pagination.total}</span> leads
                </div>
                
                <div className="flex items-center gap-4">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1 || loading}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-widest hover:bg-white/10 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                  >
                    Previous
                  </button>
                  
                  <div className="flex items-center gap-1 bg-black/20 p-1 rounded-xl border border-white/5">
                    {(() => {
                      const pages = [];
                      const start = Math.max(1, currentPage - 2);
                      const end = Math.min(pagination.pages, start + 4);
                      for (let i = start; i <= end; i++) {
                        pages.push(
                          <button
                            key={i}
                            onClick={() => setCurrentPage(i)}
                            className={`w-9 h-9 rounded-lg text-[10px] font-black transition-all ${currentPage === i ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/30 scale-110' : 'text-slate-500 hover:bg-white/5 hover:text-white'}`}
                          >
                            {i}
                          </button>
                        );
                      }
                      return pages;
                    })()}
                  </div>

                  <button
                    onClick={() => setCurrentPage(prev => Math.min(pagination.pages, prev + 1))}
                    disabled={currentPage === pagination.pages || loading}
                    className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-widest hover:bg-white/10 hover:text-white disabled:opacity-20 disabled:cursor-not-allowed transition-all"
                  >
                    Next
                  </button>
                </div>
              </div>

              {/* SLIDING NAVIGATION (NEW) */}
              <div className="flex items-center gap-6 px-2">
                <div className="text-[8px] font-black text-slate-600 uppercase tracking-[4px] shrink-0">Slide To Page</div>
                <div className="flex-1 relative group py-4">
                  <input
                    type="range"
                    min="1"
                    max={pagination.pages}
                    value={currentPage}
                    onChange={(e) => setCurrentPage(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-white/5 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:accent-indigo-400 transition-all"
                  />
                  <div 
                    className="absolute top-0 -translate-y-full px-2 py-1 bg-indigo-600 text-white text-[9px] font-black rounded pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ left: `${((currentPage - 1) / (pagination.pages - 1)) * 100}%`, transform: 'translate(-50%, -8px)' }}
                  >
                    PAGE {currentPage}
                  </div>
                </div>
                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest shrink-0 w-12 text-right">
                  {currentPage} / {pagination.pages}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail Side Panel */}
      {selectedLead && (
        <div className="fixed inset-0 z-[1000] flex justify-end">
          <div
            className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity"
            onClick={() => setSelectedLead(null)}
          ></div>
          <div className="relative w-full max-w-2xl bg-[#0d0f16] h-full shadow-2xl border-l border-white/5 flex flex-col animate-slide-in overflow-hidden">
            {/* Panel Header */}
            <div className="sticky top-0 z-20 bg-[#0d0f16]/90 backdrop-blur-xl p-8 border-b border-white/5 flex justify-between items-start">
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <div className="px-3 py-1 bg-indigo-500/10 border border-indigo-500/20 rounded-full text-[9px] font-black text-indigo-400 uppercase tracking-widest">
                    Lead Intelligence Deep-Dive
                  </div>
                  <div className="px-3 py-1 bg-white/5 border border-white/10 rounded-full text-[9px] font-bold text-slate-400 uppercase tracking-widest">
                    ID: #{selectedLead.id}
                  </div>
                </div>
                <h2 className="text-3xl font-black text-white uppercase mb-2">{selectedLead.first_name} {selectedLead.last_name}</h2>
                <p className="text-slate-400 font-bold uppercase text-[11px] tracking-widest flex items-center gap-2">
                  <Briefcase className="w-3.5 h-3.5 text-indigo-400" /> {selectedLead.company_name}
                </p>
              </div>
              <button
                onClick={() => setSelectedLead(null)}
                className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-400 hover:text-white border border-white/5"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
              {/* Top Intelligence Grid */}
              <div className="grid grid-cols-2 gap-4 mb-12">
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Sparkles className="w-4 h-4 text-violet-400" />
                    <span className="text-[10px] font-black text-violet-400 uppercase tracking-widest">Lead Score</span>
                  </div>
                  <div className="text-4xl font-black text-white">{selectedLead.sentiment_score || '—'}</div>
                  <div className="mt-2 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full bg-violet-500" style={{ width: `${selectedLead.sentiment_score}%` }}></div>
                  </div>
                </div>
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <DollarSign className="w-4 h-4 text-emerald-400" />
                    <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Check Size</span>
                  </div>
                  <div className="text-2xl font-black text-white">{selectedLead.deal_size || 'TBD'}</div>
                  <p className="mt-1 text-[9px] font-bold text-slate-500 uppercase tracking-widest">Estimated Deal Value</p>
                </div>
              </div>

              {/* Confidence & Signals */}
              <div className="grid grid-cols-2 gap-4 mb-12">
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <ShieldCheck className="w-4 h-4 text-indigo-400" />
                    <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">System Confidence</span>
                  </div>
                  <div className="text-2xl font-black text-white">{selectedLead.rag_intelligence?.confidence || '82'}%</div>
                </div>
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap className="w-4 h-4 text-amber-400" />
                    <span className="text-[10px] font-black text-amber-400 uppercase tracking-widest">Urgency</span>
                  </div>
                  <div className="text-xl font-black text-white uppercase">{selectedLead.urgency_level || 'MEDIUM'}</div>
                </div>
              </div>

              {/* Strategic Analysis */}
              <div className="mb-12">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <BarChart3 className="w-5 h-5 text-indigo-400" />
                    <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">Strategic Intelligence</h3>
                  </div>
                  {selectedLead.rag_advice && (
                    <span className="text-[9px] font-bold text-slate-500 uppercase tracking-widest bg-white/5 px-2 py-1 rounded-md border border-white/10">
                      RAG Analysis Complete
                    </span>
                  )}
                </div>

                <div className="bg-white/[0.02] border border-white/5 rounded-3xl overflow-hidden shadow-inner">
                  {selectedLead.rag_advice ? (
                    <div className="relative group">
                      <div className="p-8 max-h-[350px] overflow-y-auto custom-scrollbar">
                        <div className="prose prose-invert prose-sm max-w-none text-slate-400 leading-relaxed space-y-4">
                          {selectedLead.rag_advice.split('###').filter(s => s.trim()).map((section, idx) => {
                            const lines = section.trim().split('\n');
                            const title = lines[0].trim();
                            const content = lines.slice(1).join('\n').trim();

                            return (
                              <div key={idx} className="mb-6 last:mb-0 border-l-2 border-indigo-500/30 pl-6 py-1">
                                <h4 className="text-[11px] font-black text-indigo-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                                  <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 shadow-[0_0_5px_rgba(99,102,241,0.5)]" />
                                  {title}
                                </h4>
                                <div className="text-[13px] font-medium leading-relaxed text-slate-400 whitespace-pre-wrap">
                                  {content}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                      <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-[#0d0f16] to-transparent pointer-events-none group-hover:opacity-0 transition-opacity" />
                    </div>
                  ) : (
                    <div className="flex flex-col items-center py-16 opacity-30">
                      <div className="w-16 h-16 rounded-full border-2 border-dashed border-white/10 flex items-center justify-center mb-6">
                        <Clock className="w-8 h-8" />
                      </div>
                      <p className="text-[10px] font-black uppercase tracking-[0.3em]">Processing Analysis...</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Pre-Meeting Brief */}
              <div className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <FileText className="w-5 h-5 text-amber-400" />
                  <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">Pre-Meeting Brief</h3>
                </div>
                <div className="bg-amber-500/5 border border-amber-500/15 rounded-3xl p-6">
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Company</div>
                      <div className="text-[13px] font-bold text-white">{selectedLead.company_name || '—'}</div>
                    </div>
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Sector</div>
                      <div className="text-[13px] font-bold text-white">{selectedLead.sector || '—'}</div>
                    </div>
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Deal Size</div>
                      <div className="text-[13px] font-bold text-emerald-400">{selectedLead.deal_size || 'TBD'}</div>
                    </div>
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Lead Score</div>
                      <div className={`text-[13px] font-bold ${(selectedLead.rag_intelligence?.sentiment_score || selectedLead.sentiment_score) >= 80 ? 'text-emerald-400' : (selectedLead.rag_intelligence?.sentiment_score || selectedLead.sentiment_score) >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                        {selectedLead.rag_intelligence?.sentiment_score || selectedLead.sentiment_score || '—'}
                      </div>
                    </div>
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Intent</div>
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${selectedLead.reply_intent === 'INTERESTED' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : selectedLead.reply_intent === 'NOT_INTERESTED' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}>
                        {selectedLead.reply_intent || 'Awaiting'}
                      </span>
                    </div>
                    <div>
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Status</div>
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${selectedLead.email_status === 'SENT' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : selectedLead.email_status === 'REPLIED' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : 'bg-white/5 border-white/10 text-slate-400'}`}>
                        {selectedLead.email_status || 'NEW'}
                      </span>
                    </div>
                  </div>
                  {selectedLead.rag_intelligence?.signals && (
                    <div className="border-t border-amber-500/10 pt-4 mt-2">
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-2">Key Signals</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(Array.isArray(selectedLead.rag_intelligence.signals) ? selectedLead.rag_intelligence.signals : [selectedLead.rag_intelligence.signals]).map((s, i) => (
                          <span key={i} className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 rounded text-[9px] font-bold text-amber-400/90">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                  {selectedLead.rag_intelligence?.strategy && (
                    <div className="border-t border-amber-500/10 pt-4 mt-2">
                      <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Strategy</div>
                      <div className="text-[12px] font-medium text-slate-300 italic">"{selectedLead.rag_intelligence.strategy}"</div>
                    </div>
                  )}
                </div>
              </div>

              {/* Follow-up Sequence (NEW) */}
              <div className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <Clock className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">Outreach Lifecycle</h3>
                </div>
                
                <div className="bg-white/[0.02] border border-white/5 rounded-3xl p-6">
                  <div className="space-y-6">
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center border ${selectedLead.followup_stage >= 1 ? 'bg-indigo-500 border-indigo-400 text-white' : 'bg-slate-800 border-white/10 text-slate-600'}`}>
                          <Mail className="w-4 h-4" />
                        </div>
                        <div className="w-0.5 h-8 bg-white/5 my-1" />
                      </div>
                      <div className="flex-1 pt-1">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-black text-white uppercase tracking-widest">Initial Outreach</span>
                          {selectedLead.last_outreach_at && selectedLead.followup_stage >= 1 && (
                            <span className="text-[8px] font-bold text-slate-500">{parseUtcDate(selectedLead.last_outreach_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                          )}
                        </div>
                        <p className="text-[9px] text-slate-500 mt-1 uppercase font-bold">Primary email dispatch</p>
                      </div>
                    </div>

                    {[...Array(Math.max(0, selectedLead.followup_stage - 1))].map((_, idx) => (
                      <div key={idx} className="flex items-start gap-4">
                        <div className="flex flex-col items-center">
                          <div className="w-8 h-8 rounded-full flex items-center justify-center bg-emerald-500 border border-emerald-400 text-white">
                            <Zap className="w-4 h-4" />
                          </div>
                          {idx < selectedLead.followup_stage - 2 && <div className="w-0.5 h-8 bg-white/5 my-1" />}
                        </div>
                        <div className="flex-1 pt-1">
                          <div className="flex items-center justify-between">
                            <span className="text-[10px] font-black text-white uppercase tracking-widest">Follow-up {idx + 1}</span>
                          </div>
                          <p className="text-[9px] text-emerald-500/80 mt-1 uppercase font-bold italic">Sequence Step {idx + 2} Completed</p>
                        </div>
                      </div>
                    ))}

                    {selectedLead.followup_status === 'ACTIVE' && (
                      <div className="mt-4 p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-2xl flex items-center gap-3">
                        <div className="w-2 h-2 rounded-full bg-indigo-500 animate-ping" />
                        <span className="text-[9px] font-black text-indigo-400 uppercase tracking-widest">Automated sequence actively monitoring for replies</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* AI Deal Story Section */}
              <div className="mb-12">
                <div className="flex items-center gap-3 mb-4">
                  <Sparkles className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">AI Deal Story</h3>
                </div>

                {isTimelineLoading ? (
                  <div className="bg-indigo-500/5 border border-indigo-500/10 rounded-2xl p-6 animate-pulse">
                    <div className="h-3 w-3/4 bg-white/10 rounded mb-3" />
                    <div className="h-3 w-1/2 bg-white/10 rounded mb-3" />
                    <div className="h-3 w-2/3 bg-white/10 rounded" />
                  </div>
                ) : timelineData?.ai_summary ? (
                  <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-2xl p-6 shadow-xl shadow-indigo-500/5 relative overflow-hidden group">
                    <div className="absolute top-0 right-0 w-32 h-32 bg-indigo-500/10 blur-[60px] rounded-full -mr-16 -mt-16 group-hover:bg-indigo-500/20 transition-all" />
                    <div className="relative z-10 space-y-3">
                      {timelineData.ai_summary.split('\n').map((line, i) => (
                        <div key={i} className="text-[13px] font-bold text-indigo-100 leading-relaxed">
                          {line}
          </div>
        ))}
      </div>
      </div>
                ) : (
                  <div className="bg-white/5 border border-white/10 rounded-2xl p-6 text-center italic text-slate-500 text-xs">
                    No story highlights available yet.
                  </div>
                )}
                
                {/* Event Timeline Visualization */}
                {timelineData?.full_timeline && (
                  <div className="mt-8 ml-4 space-y-6 relative">
                    <div className="absolute left-[-17px] top-2 bottom-2 w-px bg-white/10" />
                    {timelineData.full_timeline.map((event, i) => (
                      <div key={i} className="relative pl-6">
                        <div className="absolute left-[-21px] top-1.5 w-2 h-2 rounded-full bg-indigo-500 border-2 border-[#0d0f16]" />
                        <div className="flex justify-between items-start mb-1">
                          <p className="text-[11px] font-black text-white uppercase tracking-wider">{event.action}</p>
                          <span className="text-[9px] font-bold text-slate-500">{event.date}</span>
                        </div>
                        <p className="text-[12px] text-slate-400 font-medium leading-relaxed">{event.details}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Thread History */}
              <div className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <MessageSquare className="w-5 h-5 text-blue-400" />
                  <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">Workspace Communication</h3>
                </div>
                <div className="space-y-4">
                  {/* Sent Email Draft */}
                  <div className="bg-indigo-500/5 border border-indigo-500/10 rounded-2xl p-6">
                    <div className="flex justify-between items-center mb-4">
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-indigo-400" />
                        <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Outgoing Outreach</span>
                      </div>
                      <span className="text-[9px] font-bold text-slate-500">{parseUtcDate(selectedLead.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="text-sm text-slate-300 line-clamp-4 italic">
                      {selectedLead.email_draft?.replace(/Subject:.*\n\n/, '') || 'Initial outreach sent via system.'}
                    </div>
                  </div>

                  {/* Owner Info */}
                  <div className="flex items-center gap-4 p-4 bg-white/[0.02] border border-white/5 rounded-xl">
                    <div className="w-10 h-10 rounded-full bg-slate-800 flex items-center justify-center text-slate-500 font-bold uppercase">
                      {selectedLead.owner_name?.[0]}
                    </div>
                    <div>
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Managed By</p>
                      <p className="text-[13px] font-bold text-white">{selectedLead.owner_full_name || selectedLead.owner_name}</p>
                    </div>
                    <div className="ml-auto flex items-center gap-1.5 px-3 py-1 bg-white/5 rounded-lg border border-white/10 text-[9px] font-black text-slate-400 uppercase tracking-widest">
                      <ShieldCheck className="w-3 h-3" /> Workspace User
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Panel Footer */}
            <div className="p-8 border-t border-white/5 bg-white/[0.01] flex flex-col gap-4">
              <button
                onClick={async () => {
                  if (!selectedLead?.id) return;
                  try {
                    const btn = document.getElementById('run-rag-btn');
                    const originalText = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="animate-pulse">Analyzing Document... (est. 60s)</span>';

                    const res = await api.post(`/api/intelligence/analyze-lead/${selectedLead.id}`);
                    if (res.data.success) {
                      // Refresh the lead data in the local state
                      const updatedLeads = leads.map(l =>
                        l.id === selectedLead.id ? { 
                          ...l, 
                          rag_advice: res.data.advice, 
                          sector: res.data.category,
                          rag_intelligence: res.data.rag_intel 
                        } : l
                      );
                      setLeads(updatedLeads);
                      setSelectedLead({ ...selectedLead, rag_advice: res.data.advice, sector: res.data.category, rag_intelligence: res.data.rag_intel });
                    }
                    btn.disabled = false;
                    btn.innerHTML = originalText;
                  } catch (err) {
                    console.error('Analysis failed', err);
                    alert('RAG Analysis failed. The server might be busy.');
                    const btn = document.getElementById('run-rag-btn');
                    btn.disabled = false;
                    btn.innerHTML = '<span class="text-rose-400">Retry Deep Analysis</span>';
                  }
                }}
                id="run-rag-btn"
                className="w-full flex items-center justify-center gap-2 py-4 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-500/50 text-white text-[11px] font-black uppercase tracking-[0.2em] rounded-2xl transition-all shadow-xl shadow-indigo-500/20"
              >
                <Sparkles className="w-4 h-4" /> Run AI Deep-Dive (RAG)
              </button>

              <div className="flex gap-3">
                <button
                  onClick={() => window.open(`mailto:${selectedLead.email}`)}
                  className="flex-1 flex items-center justify-center gap-2 py-4 bg-white/5 hover:bg-white/10 text-white text-[11px] font-black uppercase tracking-[0.2em] rounded-2xl transition-all border border-white/10"
                >
                  Direct Connect <ArrowUpRight className="w-4 h-4" />
                </button>
                <button className="px-6 py-4 bg-white/5 hover:bg-white/10 text-white border border-white/10 rounded-2xl transition-all">
                  <MoreHorizontal className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Action Toolbar */}
      {selectedLeadIds.size > 0 && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-50 bg-[#0f111a] border border-indigo-500/30 rounded-2xl px-6 py-4 shadow-2xl flex items-center gap-6 animate-in slide-in-from-bottom-4">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center text-xs font-black">
              {selectedLeadIds.size}
            </div>
            <span className="text-[11px] font-black text-white uppercase tracking-widest">Leads Selected</span>
          </div>
          <div className="h-6 w-px bg-white/10" />
          <div className="flex items-center gap-3">
            <button
              onClick={async () => {
                setIsBulkActionLoading(true);
                try {
                  await api.post('/api/admin/leads/bulk-approve', { lead_ids: Array.from(selectedLeadIds) });
                  showNotification('success', `Approved ${selectedLeadIds.size} leads successfully`);
                  setSelectedLeadIds(new Set());
                  fetchData();
                } catch (err) {
                  showNotification('error', 'Bulk approval failed');
                } finally {
                  setIsBulkActionLoading(false);
                }
              }}
              disabled={isBulkActionLoading}
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-all flex items-center gap-2 cursor-pointer"
            >
              {isBulkActionLoading ? <RefreshCcw className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
              Bulk Approve
            </button>
            <button
              onClick={() => setSelectedLeadIds(new Set())}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 text-slate-400 text-[10px] font-black uppercase tracking-widest rounded-lg transition-all cursor-pointer"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Global CSS for Animations & Custom Scrollbar */}
      <style dangerouslySetInnerHTML={{
        __html: `
        .animate-slide-in {
          animation: slide-in 0.4s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes slide-in {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.05);
          border-radius: 10px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.1);
        }
      `}} />
    </div>
    </>
  );
};

export default AdminDashboard;
