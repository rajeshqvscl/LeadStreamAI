
import React, { useState, useEffect, useMemo } from 'react';
import api from '../services/api';
import { 
  Users, Target, MessageSquare, Calendar, 
  TrendingUp, BarChart3, Search, Filter, 
  Download, MoreHorizontal, ChevronRight, 
  Sparkles, ShieldCheck, Mail, ArrowUpRight,
  Clock, CheckCircle2, AlertCircle, X,
  FileText, Briefcase, Zap, Info, DollarSign
} from 'lucide-react';

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
  const [filters, setFilters] = useState({
    type: 'ALL',
    status: 'ALL',
    intent: 'ALL',
    owner: 'ALL'
  });

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [leadsRes, statsRes] = await Promise.all([
        api.get('/api/admin/leads/all'),
        api.get('/api/admin/stats/global')
      ]);
      setLeads(leadsRes.data || []);
      setStats(statsRes.data || {});
    } catch (err) {
      console.error('Failed to fetch admin data', err);
    } finally {
      setLoading(false);
    }
  };

  const filteredLeads = useMemo(() => {
    return leads.filter(l => {
      const matchesSearch = 
        (l.first_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (l.last_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (l.company_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (l.email?.toLowerCase().includes(searchTerm.toLowerCase()));
      
      const matchesType = filters.type === 'ALL' || l.sector?.toUpperCase() === filters.type;
      const matchesStatus = filters.status === 'ALL' || l.email_status === filters.status;
      const matchesIntent = filters.intent === 'ALL' || l.reply_intent === filters.intent;
      const matchesOwner = filters.owner === 'ALL' || l.owner_name === filters.owner;

      return matchesSearch && matchesType && matchesStatus && matchesIntent && matchesOwner;
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
    <div className="min-h-screen bg-[#0a0c10] p-8">
      {/* Header Section */}
      <div className="flex justify-between items-end mb-12">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
              <ShieldCheck className="w-4 h-4 text-indigo-400" />
            </div>
            <span className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.3em]">Control Center</span>
          </div>
          <h1 className="text-4xl font-black text-white uppercase tracking-tight">Admin <span className="text-indigo-500">Intelligence</span></h1>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            onClick={() => {
              const headers = [
                'Name', 'Email', 'Phone', 'Designation', 'Company', 'Type', 'Status', 
                'Intent', 'Score', 'Check Size', 'Rejection Reason', 'Sector/Industry', 'LinkedIn', 'Owner', 
                'Last Interaction', 'AI Strategy', 'Analyst Report', 'Key Signals', 'Confidence %'
              ].join(',');
              
              const rows = leads.map(l => {
                const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
                const rejectionReason = l.reply_intent === 'NOT_INTERESTED' ? (l.rag_advice?.split('.')[0] || 'No specific reason') : 'N/A';
                return [
                  clean(`${l.first_name} ${l.last_name}`),
                  clean(l.email),
                  clean(l.phone),
                  clean(l.designation),
                  clean(l.company_name || l.family_office_name),
                  clean(l.sector),
                  clean(l.email_status),
                  clean(l.reply_intent),
                  clean(l.sentiment_score),
                  clean(l.deal_size),
                  clean(rejectionReason),
                  clean(l.industry),
                  clean(l.linkedin_url),
                  clean(l.owner_name),
                  clean(new Date(l.updated_at).toLocaleDateString()),
                  clean(l.rag_intelligence?.strategy || ''),
                  clean(l.rag_advice),
                  clean(JSON.stringify(l.rag_intelligence?.signals || '')),
                  clean(l.rag_intelligence?.confidence || '82')
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
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-12">
        {[
          { label: 'Total Leads', value: stats.total_leads, icon: Users, color: 'indigo' },
          { label: 'Interested', value: stats.interested_leads, icon: Target, color: 'emerald' },
          { label: 'Meetings', value: stats.meetings_scheduled, icon: Calendar, color: 'blue' },
          { label: 'Conv. Rate', value: `${stats.conversion_rate}%`, icon: TrendingUp, color: 'violet' },
          { label: 'Avg Score', value: stats.avg_score, icon: BarChart3, color: 'amber' },
          { label: 'Followups', value: stats.active_followups, icon: Clock, color: 'rose' },
        ].map((stat, i) => (
          <div key={i} className="bg-white/[0.02] border border-white/5 rounded-2xl p-6 hover:border-white/10 transition-all group">
            <div className={`w-10 h-10 rounded-xl bg-${stat.color}-500/10 flex items-center justify-center border border-${stat.color}-500/20 mb-4 group-hover:scale-110 transition-transform`}>
              <stat.icon className={`w-5 h-5 text-${stat.color}-400`} />
            </div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">{stat.label}</div>
            <div className="text-2xl font-black text-white tracking-tight">{stat.value}</div>
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
            onChange={(e) => setFilters({...filters, type: e.target.value})}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            <option value="ALL">All Types</option>
            <option value="INVESTOR">Investors</option>
            <option value="CLIENT">Clients</option>
          </select>

          <select 
            value={filters.status}
            onChange={(e) => setFilters({...filters, status: e.target.value})}
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
            onChange={(e) => setFilters({...filters, owner: e.target.value})}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50"
          >
            {owners.map(o => (
              <option key={o} value={o}>{o === 'ALL' ? 'All Owners' : o}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Database Table */}
      <div className="bg-[#0f111a] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl relative">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/5 sticky top-0 z-10">
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Name & Company</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Email Address</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Type</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Intent</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Check Size</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Score</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Rejection / Reason</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Status</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest">Owner</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredLeads.map((lead) => (
                <tr 
                  key={lead.id} 
                  onClick={() => setSelectedLead(lead)}
                  className="hover:bg-white/[0.02] transition-colors cursor-pointer group"
                >
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-violet-500/10 flex items-center justify-center border border-white/10 group-hover:border-indigo-500/30 transition-all">
                        <span className="text-[14px] font-black text-indigo-400">{lead.first_name?.[0]}{lead.last_name?.[0]}</span>
                      </div>
                      <div>
                        <div className="text-[14px] font-bold text-white mb-0.5 group-hover:text-indigo-400 transition-colors">{lead.first_name} {lead.last_name}</div>
                        <div className="text-[11px] font-medium text-slate-500">{lead.company_name || lead.family_office_name}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex flex-col gap-1">
                      <div className="text-[13px] font-bold text-white">{lead.email}</div>
                      {lead.phone && <div className="text-[10px] text-slate-500 font-medium">{lead.phone}</div>}
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${lead.sector === 'INVESTOR' ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400' : 'bg-blue-500/5 border-blue-500/20 text-blue-400'}`}>
                      {lead.sector === 'INVESTOR' ? <Target className="w-3 h-3" /> : <Briefcase className="w-3 h-3" />}
                      {lead.sector || 'CLIENT'}
                    </span>
                  </td>
                  <td className="px-6 py-5">
                    {lead.reply_intent ? (
                      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${lead.reply_intent === 'INTERESTED' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : lead.reply_intent === 'NOT_INTERESTED' ? 'bg-rose-500/10 border-rose-500/20 text-rose-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}>
                        {lead.reply_intent}
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold text-slate-700 tracking-widest uppercase italic">Awaiting reply</span>
                    )}
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-2">
                       <DollarSign className="w-3.5 h-3.5 text-emerald-500" />
                       <span className="text-[13px] font-black text-white">{lead.deal_size || '—'}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-center">
                    <div className={`text-[15px] font-black ${lead.sentiment_score >= 80 ? 'text-emerald-400' : lead.sentiment_score >= 50 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {lead.sentiment_score || '—'}
                    </div>
                  </td>
                  <td className="px-6 py-5">
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
                  <td className="px-6 py-5">
                    <div className="flex flex-col gap-1">
                      <div className="text-[11px] font-black text-white uppercase tracking-wider">{lead.email_status || 'NEW'}</div>
                      {lead.followup_status === 'ACTIVE' && (
                        <div className="flex items-center gap-1 text-[8px] font-black text-indigo-400 uppercase tracking-widest">
                          <Zap className="w-2.5 h-2.5 animate-pulse" /> Sequence Active
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-slate-800 flex items-center justify-center border border-white/5">
                        <Users className="w-3 h-3 text-slate-500" />
                      </div>
                      <span className="text-[11px] font-bold text-slate-400">{lead.owner_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-2 text-slate-500">
                      <Clock className="w-3.5 h-3.5" />
                      <span className="text-[11px] font-medium">{new Date(lead.updated_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-right">
                    <button className="p-2 hover:bg-white/5 rounded-lg transition-colors text-slate-500 hover:text-white">
                      <MoreHorizontal className="w-4 h-4" />
                    </button>
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

              {/* RAG Insights */}
              <div className="mb-12">
                <div className="flex items-center gap-3 mb-6">
                  <BarChart3 className="w-5 h-5 text-indigo-400" />
                  <h3 className="text-[12px] font-black text-white uppercase tracking-[0.2em]">Strategic Analysis</h3>
                </div>
                <div className="bg-white/[0.02] border border-white/5 rounded-2xl p-8">
                  {selectedLead.rag_advice ? (
                    <div className="prose prose-invert max-w-none text-sm text-slate-400 leading-relaxed">
                      {selectedLead.rag_advice}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center py-10 opacity-50">
                      <Clock className="w-10 h-10 mb-4" />
                      <p className="text-[10px] font-bold uppercase tracking-widest">No strategic analysis available yet</p>
                    </div>
                  )}
                </div>
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
                        l.id === selectedLead.id ? { ...l, rag_advice: res.data.advice, sector: res.data.category } : l
                      );
                      setLeads(updatedLeads);
                      setSelectedLead({ ...selectedLead, rag_advice: res.data.advice, sector: res.data.category });
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

      {/* Global CSS for Animations & Custom Scrollbar */}
      <style dangerouslySetInnerHTML={{ __html: `
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
