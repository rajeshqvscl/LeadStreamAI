
import React, { useState, useEffect, useMemo } from 'react';
import api from '../services/api';
import {
  Users, Target, MessageSquare, Calendar,
  TrendingUp, BarChart3, Search, Filter,
  Download, MoreHorizontal, ChevronRight,
  Sparkles, ShieldCheck, Mail, ArrowUpRight,
  Clock, CheckCircle2, AlertCircle, X, AlertTriangle,
  FileText, Briefcase, Zap, Info, DollarSign,
  PieChart as PieIcon, Globe, RefreshCcw, Database, Terminal
} from 'lucide-react';
import { 
  PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend,
  BarChart, Bar, XAxis, YAxis, CartesianGrid
} from 'recharts';

const AdminDashboard = () => {
  const [leads, setLeads] = useState([]);
  const [stats, setStats] = useState({
    total_leads: 0,
    interested_leads: 0,
    meetings_scheduled: 0,
    conversion_rate: 0,
    avg_score: 0,
    active_followups: 0
  });
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedLead, setSelectedLead] = useState(null);
  const [timelineData, setTimelineData] = useState(null);
  const [isTimelineLoading, setIsTimelineLoading] = useState(false);
  const [ragStats, setRagStats] = useState(null);
  const [isRagLoading, setIsRagLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pagination, setPagination] = useState({ total: 0, pages: 1, limit: 50 });

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
  const [selectedLeadIds, setSelectedLeadIds] = useState(new Set());
  const [isBulkActionLoading, setIsBulkActionLoading] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  useEffect(() => {
    fetchData(currentPage);
  }, [currentPage]);

  const fetchData = async (page = 1) => {
    try {
      setLoading(true);
      const [leadsRes, statsRes] = await Promise.all([
        api.get(`/api/admin/leads/all?page=${page}&limit=50`),
        api.get('/api/admin/stats/global')
      ]);
      
      if (leadsRes.data.leads) {
        setLeads(leadsRes.data.leads);
        setPagination(leadsRes.data.pagination);
      } else {
        setLeads(leadsRes.data || []);
      }
      
      setStats(statsRes.data || {});
      
      // Fetch RAG Debug Stats
      setIsRagLoading(true);
      const debugRes = await api.get('/api/intelligence/admin/rag-debug');
      setRagStats(debugRes.data);
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    } finally {
      setLoading(false);
      setIsRagLoading(false);
    }
  };

  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      const matchesSearch = !searchTerm || [
        l.first_name, 
        l.last_name, 
        l.company_name, 
        l.email,
        l.designation
      ].some(val => val?.toLowerCase().includes(searchTerm.toLowerCase()));
 
      const matchesType = filters.type === 'ALL' || l.lead_type?.toUpperCase() === filters.type;
      const matchesSector = !filters.sector || filters.sector === 'ALL' || l.sector?.toUpperCase() === filters.sector?.toUpperCase();
      const matchesStatus = filters.status === 'ALL' || l.email_status === filters.status;
      const matchesIntent = filters.intent === 'ALL' || l.reply_intent === filters.intent;
      const matchesOwner = filters.owner === 'ALL' || l.owner_name === filters.owner;
 
      return matchesSearch && matchesType && matchesSector && matchesStatus && matchesIntent && matchesOwner;
    });
  }, [leads, searchTerm, filters]);

  const owners = useMemo(() => {
    return ['ALL', ...new Set(leads.map(l => l.owner_name).filter(Boolean))];
  }, [leads]);

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
    <div className="flex flex-col min-h-screen bg-[#0a0c10] p-2 lg:p-4 overflow-x-hidden">
      {notification && (
        <div className={`fixed top-8 right-8 z-[100] flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl animate-in slide-in-from-right-8 ${notification.type === 'success' ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'}`}>
          {notification.type === 'success' ? <CheckCircle2 className="w-4 h-4 font-black" /> : <AlertCircle className="w-4 h-4 font-black" />}
          <span className="font-black text-[11px] uppercase tracking-widest">{notification.message}</span>
        </div>
      )}
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

        <div className="flex items-center gap-4">
          <button
            onClick={() => {
              const headers = [
                'Name', 'Email', 'Designation', 'Company', 'Type', 'Status',
                'Intent', 'Score', 'Check Size', 'Rejection Reason', 'Sector/Industry', 'Owner',
                'Last Interaction', 'AI Strategy', 'Analyst Report', 'Key Signals', 'Confidence %'
              ].join(',');

              const rows = leads.map(l => {
                const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
                const rejectionReason = l.reply_intent === 'NOT_INTERESTED' ? (l.rag_advice?.split('.')[0] || 'No specific reason') : 'N/A';
                return [
                  clean(`${l.first_name} ${l.last_name}`),
                  clean(l.email),
                  clean(l.designation),
                  clean(l.company_name || l.family_office_name),
                  clean(l.lead_type),
                  clean(l.email_status),
                  clean(l.reply_intent),
                  clean(l.sentiment_score),
                  clean(l.deal_size),
                  clean(rejectionReason),
                  clean(l.sector || 'Other'),
                  clean(l.owner_name),
                  clean(new Date(l.updated_at).toLocaleDateString()),
                  clean(l.rag_intelligence?.strategy || 'General Outreach'),
                  clean(l.rag_advice || 'Analyst Review Pending'),
                  clean(Array.isArray(l.rag_intelligence?.signals) ? l.rag_intelligence.signals.join(' | ') : (l.rag_intelligence?.signals || 'N/A')),
                  clean(l.rag_intelligence?.confidence || 'N/A')
                ].join(',');
              });

              const csv = [headers, ...rows].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.setAttribute('hidden', ''); a.setAttribute('href', url); a.setAttribute('download', `MASTER_WORKSPACE_DATA_${new Date().toISOString().split('T')[0]}.csv`);
              document.body.appendChild(a); a.click(); document.body.removeChild(a);
            }}
            className="flex items-center gap-2 px-6 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all"
          >
            <Download className="w-3.5 h-3.5" /> Full Master Export
          </button>

          <button
            onClick={async () => {
              try {
                const btn = document.getElementById('ai-classify-btn');
                const original = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="animate-pulse">🧠</span> Analyzing...';
                
                const res = await api.post('/api/intelligence/leads/ai-deep-classify');
                showNotification('success', `AI successfully categorized ${res.data.updated || 0} leads!`);
                fetchData();
                
                btn.disabled = false;
                btn.innerHTML = original;
              } catch (err) {
                console.error('AI Refresh failed', err);
                const btn = document.getElementById('ai-classify-btn');
                btn.disabled = false;
                btn.innerHTML = '❌ AI Classification Failed';
                setTimeout(() => {
                  btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sparkles w-3.5 h-3.5"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"></path><path d="M5 3v4"></path><path d="M19 17v4"></path><path d="M3 5h4"></path><path d="M17 19h4"></path></svg> AI Deep Classify';
                }, 3000);
              }
            }}
            id="ai-classify-btn"
            className="flex items-center gap-2 px-6 py-3 bg-violet-600/10 hover:bg-violet-600/20 text-violet-400 border border-violet-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all"
          >
            <Sparkles className="w-3.5 h-3.5" /> AI Deep Classify
          </button>

          <button
            onClick={async () => {
              try {
                const btn = document.getElementById('refresh-sectors-btn');
                const original = btn.innerHTML;
                btn.disabled = true;
                btn.innerHTML = '<span class="animate-spin">🔄</span> Processing...';
                
                await api.post('/api/intelligence/leads/auto-enrich-sectors');
                showNotification('success', 'Workspace sectors re-classified successfully!');
                fetchData();
                
                btn.disabled = false;
                btn.innerHTML = original;
              } catch (err) {
                console.error('Refresh failed', err);
                const btn = document.getElementById('refresh-sectors-btn');
                btn.disabled = false;
                btn.innerHTML = 'Sector Refresh Failed';
              }
            }}
            id="refresh-sectors-btn"
            className="flex items-center gap-2 px-6 py-3 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all"
          >
            <RefreshCcw className="w-3.5 h-3.5" /> Refresh All Sectors
          </button>

          <button
            onClick={() => {
              const rejections = leads.filter(l => l.reply_intent === 'NOT_INTERESTED');
              const headers = ['Name', 'Company', 'Email', 'Check Size', 'Rejection Reason', 'Full Analyst Feedback'].join(',');
              const rows = rejections.map(l => {
                const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
                return [
                  clean(`${l.first_name} ${l.last_name}`),
                  clean(l.company_name || l.family_office_name),
                  clean(l.email),
                  clean(l.deal_size),
                  clean(l.rag_advice?.split('.')[0] || 'Unknown'),
                  clean(l.rag_advice)
                ].join(',');
              });
              const csv = [headers, ...rows].join('\n');
              const blob = new Blob([csv], { type: 'text/csv' });
              const url = window.URL.createObjectURL(blob);
              const a = document.createElement('a');
              a.setAttribute('hidden', ''); a.setAttribute('href', url); a.setAttribute('download', `REJECTION_ANALYSIS_${new Date().toISOString().split('T')[0]}.csv`);
              document.body.appendChild(a); a.click(); document.body.removeChild(a);
            }}
            className="flex items-center gap-2 px-6 py-3 bg-rose-600 hover:bg-rose-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all shadow-xl shadow-rose-500/20"
          >
            <AlertCircle className="w-3.5 h-3.5" /> Export Rejections
          </button>
        </div>
      </div>

      {/* Analytics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 mb-4">
        {[
          { label: 'Total Leads', value: stats.total_leads, icon: Users, color: 'indigo' },
          { label: 'Engaged', value: stats.engaged_leads, icon: Target, color: 'emerald' },
          { label: 'Followups', value: stats.active_followups, icon: Clock, color: 'rose' },
          { label: 'Active Flows', value: stats.active_flows, icon: Zap, color: 'amber' },
          { label: 'Meetings', value: stats.meetings_scheduled, icon: Calendar, color: 'blue' },
          { label: 'Conv. Rate', value: `${stats.conversion_rate}%`, icon: TrendingUp, color: 'violet' },
        ].map((stat, i) => (
          <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-3 hover:border-white/10 transition-all group relative overflow-hidden">
            <div className={`absolute top-0 right-0 w-16 h-16 bg-${stat.color}-500/5 blur-2xl rounded-full -mr-8 -mt-8`} />
            <div className="flex items-start justify-between relative z-10 mb-2">
              <div className={`w-8 h-8 rounded-lg bg-${stat.color}-500/10 flex items-center justify-center border border-${stat.color}-500/20`}>
                <stat.icon className={`w-4 h-4 text-${stat.color}-400`} />
              </div>
            </div>
            <div className="relative z-10">
              <div className="text-[18px] font-black text-white leading-tight mb-0.5">{stat.value}</div>
              <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest leading-none">{stat.label}</div>
            </div>
          </div>
        ))}
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

        <div className="flex items-center gap-3">
          <select
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            <option value="ALL">All Types</option>
            <option value="INVESTOR">Investors</option>
            <option value="CLIENT">Clients</option>
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
            onChange={(e) => setFilters({ ...filters, owner: e.target.value })}
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
            <option value="ALL">All Sectors</option>
            {Array.from(new Set(leads.map(l => l.sector).filter(s => s && !['INVESTOR', 'CLIENT'].includes(s.toUpperCase())))).map(s => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Visual Analytics Section */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-3 mb-6">
        {[
          { title: 'Lead Intent', sub: 'Pipeline State', icon: PieIcon, color: 'indigo', data: stats.intent_breakdown, type: 'pie' },
          { title: 'Sectors', sub: 'Industry Volume', icon: Globe, color: 'purple', data: stats.sector_breakdown, type: 'bar' },
          { title: 'Sources', sub: 'Acquisition', icon: Database, color: 'blue', data: stats.source_breakdown, type: 'pie' },
          { title: 'Lead Type', sub: 'Investor/Client', icon: Users, color: 'emerald', data: stats.type_breakdown, type: 'pie' }
        ].map((item, i) => (
          <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-3 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-[11px] font-black text-white uppercase tracking-wider">{item.title}</h3>
                <p className="text-[8px] text-slate-500 font-bold uppercase tracking-widest leading-none">{item.sub}</p>
              </div>
              <div className={`w-6 h-6 rounded-lg bg-${item.color}-500/10 flex items-center justify-center border border-${item.color}-500/20`}>
                <item.icon className={`w-3 h-3 text-${item.color}-400`} />
              </div>
            </div>
            <div className="h-[120px]">
              <ResponsiveContainer width="100%" height="100%">
                {item.type === 'pie' ? (
                  <PieChart>
                    <Pie
                      data={item.data || []}
                      innerRadius={35}
                      outerRadius={50}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {(item.data || []).map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={item.color === 'emerald' ? (entry.label === 'INVESTOR' ? '#10b981' : '#64748b') : ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'][index % 6]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '9px' }} />
                  </PieChart>
                ) : (
                  <BarChart data={item.data || []} layout="vertical">
                    <XAxis type="number" hide />
                    <YAxis dataKey="label" type="category" hide />
                    <Tooltip cursor={{ fill: 'rgba(255,255,255,0.02)' }} contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '9px' }} />
                    <Bar dataKey="value" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={8} />
                  </BarChart>
                )}
              </ResponsiveContainer>
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
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/5 sticky top-0 z-10">
                <th className="px-3 py-5 w-12">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded border-white/10 bg-black/20 accent-indigo-500 cursor-pointer"
                    checked={selectedLeadIds.size === filteredLeads.length && filteredLeads.length > 0}
                    onChange={() => {
                      if (selectedLeadIds.size === filteredLeads.length) {
                        setSelectedLeadIds(new Set());
                      } else {
                        setSelectedLeadIds(new Set(filteredLeads.map(l => l.id)));
                      }
                    }}
                  />
                </th>
                  <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Name & Company</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Email Address</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Type</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Sector</th>
<th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Intent</th>
                  <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">RAG Analysis</th>
                  <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Check Size</th>
                  <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Score</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Rejection / Reason</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Status</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest">Owner</th>
                <th className="px-2 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredLeads.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => setSelectedLead(lead)}
                  className={`hover:bg-white/[0.02] transition-colors cursor-pointer group ${selectedLeadIds.has(lead.id) ? 'bg-indigo-500/10' : ''}`}
                >
                  <td className="px-2 py-2" onClick={e => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-white/10 bg-black/20 accent-indigo-500 cursor-pointer"
                      checked={selectedLeadIds.has(lead.id)}
                      onChange={(e) => {
                        const next = new Set(selectedLeadIds);
                        if (next.has(lead.id)) next.delete(lead.id);
                        else next.add(lead.id);
                        setSelectedLeadIds(next);
                      }}
                    />
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/10 flex items-center justify-center border border-white/10 group-hover:border-indigo-500/30 transition-all">
                        <span className="text-[14px] font-black text-indigo-400">
                          {lead.first_name?.[0]}{lead.last_name?.[0] || lead.first_name?.[1] || ''}
                        </span>
                      </div>
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <div className="text-[14px] font-bold text-white group-hover:text-indigo-400 transition-colors">{lead.first_name} {lead.last_name}</div>
                          {(() => {
                            const sevenDays = 7 * 24 * 60 * 60 * 1000;
                            const isStalled = (Date.now() - new Date(lead.updated_at).getTime()) > sevenDays;
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
                        <div className="text-[11px] font-medium text-slate-500">{lead.company_name || lead.family_office_name}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex flex-col gap-1">
                      <div className="text-[13px] font-bold text-white">{lead.email}</div>
                      {lead.phone && <div className="text-[10px] text-slate-500 font-medium">{lead.phone}</div>}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${lead.lead_type?.toUpperCase() === 'INVESTOR' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-white/5 border-white/10 text-slate-400'}`}>
                      {lead.lead_type?.toUpperCase() === 'INVESTOR' ? <Target className="w-3 h-3" /> : <Users className="w-3 h-3" />}
                      {lead.lead_type || 'CLIENT'}
                    </span>
                  </td>
                  <td className="px-2 py-2">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-indigo-500/5 border border-indigo-500/20 text-indigo-400">
                      <Briefcase className="w-3 h-3" />
                      {lead.sector || 'OTHER'}
                    </span>
                  </td>
                  <td className="px-2 py-2">
                    {lead.reply_intent ? (
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${lead.reply_intent === 'INTERESTED' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : lead.reply_intent === 'NOT_INTERESTED' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}>
                        {lead.reply_intent}
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 tracking-widest uppercase italic">Awaiting reply</span>
                    )}
                  </td>
                  <td className="px-2 py-2">
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
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                      <span className="text-[13px] font-black text-white">{lead.deal_size || '—'}</span>
                    </div>
                  </td>
                  <td className="px-3 py-5 text-center">
                    <div className={`text-[15px] font-black ${(lead.rag_intelligence?.sentiment_score || lead.sentiment_score) >= 80 ? 'text-emerald-400' : (lead.rag_intelligence?.sentiment_score || lead.sentiment_score) >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {lead.rag_intelligence?.sentiment_score || lead.sentiment_score || '—'}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    {lead.reply_intent === 'NOT_INTERESTED' ? (
                      <div className="flex flex-col gap-1">
                        <div className="flex items-center gap-1.5 px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 rounded-md w-fit">
                          <AlertCircle className="w-2.5 h-2.5 text-rose-400" />
                          <span className="text-[9px] font-black text-rose-400 uppercase tracking-widest">Rejected ({lead.deal_size || 'N/A'})</span>
                        </div>
                        <div className="text-[10px] font-medium text-slate-400 max-w-[200px] line-clamp-2 italic">
                          "{lead.rag_advice?.split('.')[0].substring(0, 80)}..."
                        </div>
                      </div>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 uppercase tracking-widest">N/A</span>
                    )}
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex flex-col gap-1">
                      <div className="text-[11px] font-black text-white uppercase tracking-wider">{lead.email_status || 'NEW'}</div>
                      {lead.followup_status === 'ACTIVE' && (
                        <div className="flex items-center gap-1 text-[8px] font-black text-indigo-400 uppercase tracking-widest">
                          <Zap className="w-2.5 h-2.5 animate-pulse" /> Sequence Active
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center border border-white/5">
                        <Users className="w-3 h-3 text-slate-500" />
                      </div>
                      <span className="text-[11px] font-bold text-slate-400">{lead.owner_name}</span>
                    </div>
                  </td>
                  <td className="px-2 py-2">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Clock className="w-3.5 h-3.5" />
                      <span className="text-[11px] font-medium">{new Date(lead.updated_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span>
                    </div>
                  </td>
                  <td className="px-3 py-5 text-right">
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
                  </td>
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
            <div className="flex items-center justify-between p-6 border-t border-white/5 bg-[#0d0f16]/50">
              <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
                Showing <span className="text-white">{((currentPage - 1) * pagination.limit) + 1}</span> to <span className="text-white">{Math.min(currentPage * pagination.limit, pagination.total)}</span> of <span className="text-white">{pagination.total}</span> leads
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                  disabled={currentPage === 1 || loading}
                  className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-widest hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
                >
                  Previous
                </button>
                <div className="flex items-center gap-1">
                  {[...Array(Math.min(5, pagination.pages))].map((_, i) => {
                    const pageNum = i + 1;
                    return (
                      <button
                        key={pageNum}
                        onClick={() => setCurrentPage(pageNum)}
                        disabled={loading}
                        className={`w-8 h-8 rounded-lg text-[10px] font-black transition-all cursor-pointer ${currentPage === pageNum ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/20' : 'text-slate-500 hover:bg-white/5 hover:text-white disabled:opacity-50'}`}
                      >
                        {pageNum}
                      </button>
                    );
                  })}
                </div>
                <button
                  onClick={() => setCurrentPage(prev => Math.min(pagination.pages, prev + 1))}
                  disabled={currentPage === pagination.pages || loading}
                  className="px-4 py-2 bg-white/5 border border-white/10 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-widest hover:bg-white/10 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all cursor-pointer"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Detail Side Panel */}
      {selectedLead && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={() => setSelectedLead(null)}
          ></div>
          <div className="relative w-full max-w-2xl bg-[#0d0f16] h-full shadow-2xl border-l border-white/5 flex flex-col animate-slide-in">
            {/* Panel Header */}
            <div className="p-8 border-b border-white/5 flex justify-between items-start">
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
                className="p-2 hover:bg-white/5 rounded-xl transition-all text-slate-500 hover:text-white border border-transparent hover:border-white/10"
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
                      <span className="text-[9px] font-bold text-slate-500">{new Date(selectedLead.created_at).toLocaleDateString()}</span>
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
  );
};

export default AdminDashboard;
