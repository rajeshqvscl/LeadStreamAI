import React, { useState, useEffect, useMemo } from 'react';
import { Search, RefreshCw, Mail, MousePointerClick, Eye, XCircle, Clock, AlertTriangle, ChevronDown, ChevronUp, BarChart3, PieChart as PieChartIcon, TrendingUp, Download, FileText } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend } from 'recharts';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

const ACTION_STYLES = {
  'Rejected': { icon: XCircle, color: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/20' },
  'Bounced': { icon: AlertTriangle, color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' },
  'Clicked': { icon: MousePointerClick, color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  'Opened': { icon: Eye, color: 'text-blue-400', bg: 'bg-blue-500/10', border: 'border-blue-500/20' },
  'Replied': { icon: Mail, color: 'text-violet-400', bg: 'bg-violet-500/10', border: 'border-violet-500/20' },
  'Sent': { icon: Mail, color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' },
  'Pending': { icon: Clock, color: 'text-slate-500', bg: 'bg-slate-500/5', border: 'border-slate-500/20' },
};

const FOLLOWUP_STYLES = {
  'Active': { color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' },
  'Completed': { color: 'text-indigo-400', bg: 'bg-indigo-500/10', border: 'border-indigo-500/20' },
  'Stage': { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  'Not started': { color: 'text-slate-500', bg: 'bg-slate-500/5', border: 'border-slate-500/20' },
};

const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
];

const RANGES = [
  { key: 'daily', label: 'Daily' },
  { key: 'weekly', label: 'Weekly' },
  { key: 'monthly', label: 'Monthly' },
  { key: 'all', label: 'All' },
];

const todayStr = () => new Date().toISOString().split('T')[0];

const getMonthRange = (year, month) => {
  const start = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const end = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { start, end };
};

const Metrics = () => {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [view, setView] = useState('table');
  const [range, setRange] = useState('all');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const _now = new Date();
  const [selYear, setSelYear] = useState(_now.getFullYear());
  const [selMonth, setSelMonth] = useState(_now.getMonth());

  const fetchReport = async () => {
    try {
      let url = `/api/metrics?period=${range}&_t=${Date.now()}`;
      if (dateFrom) url += `&date_from=${dateFrom}`;
      if (dateTo) url += `&date_to=${dateTo}`;
      const res = await api.get(url);
      setData(res.data);
    } catch (err) {
      console.error('Failed to fetch report', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(true);
    fetchReport();
    const interval = setInterval(fetchReport, 30000);
    return () => clearInterval(interval);
  }, [range, dateFrom, dateTo]);

  const handleSort = (key) => {
    if (sortKey === key) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const SortIcon = ({ column }) => {
    if (sortKey !== column) return null;
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />;
  };

  const report = useMemo(() => {
    if (!data?.report) return [];
    let rows = [...data.report];
    if (search) {
      const q = search.toLowerCase();
      rows = rows.filter(r =>
        r.name.toLowerCase().includes(q) ||
        r.email.toLowerCase().includes(q) ||
        r.company.toLowerCase().includes(q) ||
        r.sector.toLowerCase().includes(q)
      );
    }
    if (sortKey) {
      rows.sort((a, b) => {
        const va = (a[sortKey] || '').toLowerCase();
        const vb = (b[sortKey] || '').toLowerCase();
        return sortDir === 'asc' ? va.localeCompare(vb) : vb.localeCompare(va);
      });
    }
    return rows;
  }, [data, search, sortKey, sortDir]);

  const stats = data ? [
    { label: 'Replies', value: data.reverted },
    { label: 'Emails Sent', value: data.today_sent },
    { label: 'Follow-ups', value: data.today_followups },
    { label: 'Drafts', value: data.drafts_generated },
    { label: 'Registry', value: data.total_registry },
    { label: 'Bounces', value: data.bounces },
  ] : [];

  const engagementMetrics = data ? [
    { label: 'Open Rate', value: `${data.open_rate}%` },
    { label: 'Engagement Rate', value: `${data.engagement_rate}%` },
    { label: 'Bounce Rate', value: `${data.bounce_rate}%` },
    { label: 'Conversion Rate', value: `${data.conversion_rate}%` },
  ] : [];

  const personaData = data ? Object.entries(data.persona_breakdown || {}).map(([k, v]) => ({ name: k, value: v })) : [];
  const industryData = data ? Object.entries(data.industry_breakdown || {}).map(([k, v]) => ({ name: k, value: v })) : [];
  const countryData = data ? Object.entries(data.country_breakdown || {}).map(([k, v]) => ({ name: k, value: v })) : [];

  const pipelineData = data ? [
    { name: 'Total', value: data.total_leads },
    { name: 'Sent', value: data.sent },
    { name: 'Delivered', value: data.delivered },
    { name: 'Opened', value: data.unique_opens },
    { name: 'Engaged', value: data.unique_engaged },
    { name: 'Bounced', value: data.bounces },
  ] : [];

  const actionBreakdown = useMemo(() => {
    if (!data?.report) return [];
    const counts = {};
    data.report.forEach(r => { counts[r.action] = (counts[r.action] || 0) + 1; });
    return Object.entries(counts).map(([k, v]) => ({ name: k, value: v }));
  }, [data]);

  const exportCSV = () => {
    if (!data?.report?.length) return;
    const headers = ['Name', 'Email', 'Company', 'Sector', 'Action', 'Follow-up', 'Date'];
    const rows = data.report.map(r => [
      `"${r.name}"`, `"${r.email}"`, `"${r.company}"`, `"${r.sector}"`, `"${r.action}"`, `"${r.followup}"`, `"${r.date || ''}"`
    ].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `lead_report_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
  };

  const renderTableView = () => (
    <>
      <div className="relative mb-4">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input type="text" placeholder="Search by name, email, company, sector..." value={search} onChange={e => setSearch(e.target.value)} className="w-full bg-[#111521] border border-white/5 rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 transition-all" />
      </div>
      <div className="bg-[#0f111a] border border-white/5 rounded-[32px] overflow-hidden relative">
        {loading && (
          <div className="absolute inset-0 z-10 bg-[#0f111a]/80 backdrop-blur-sm flex items-center justify-center">
            <div className="flex flex-col items-center gap-3">
              <div className="w-10 h-10 border-3 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
              <span className="text-[9px] font-black text-indigo-400 uppercase tracking-[3px] animate-pulse">Loading...</span>
            </div>
          </div>
        )}
        {(() => {
          if (!data || !data.report || data.report.length === 0) {
            return (
              <div className="flex flex-col items-center justify-center h-64">
                <AlertTriangle className="w-8 h-8 text-slate-700 mb-3" />
                <div className="text-slate-500 font-bold uppercase tracking-widest text-xs">No leads found for this period</div>
              </div>
            );
          }
          return (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-white/[0.02] border-b border-white/5">
                      {[
                        { key: 'name', label: 'Name' }, { key: 'email', label: 'Email' },
                        { key: 'company', label: 'Company' }, { key: 'sector', label: 'Sector' },
                        { key: 'action', label: 'Action' }, { key: 'followup', label: 'Follow-up' },
                        { key: 'date', label: 'Date' },
                      ].map(col => (
                        <th key={col.key} onClick={() => handleSort(col.key)} className="px-4 py-4 text-[10px] font-black text-slate-500 uppercase tracking-widest cursor-pointer hover:text-white transition-colors select-none">
                          {col.label} <SortIcon column={col.key} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {report.map((row, i) => {
                      const actionStyle = ACTION_STYLES[row.action] || ACTION_STYLES['Pending'];
                      const ActionIcon = actionStyle.icon;
                      const isActive = row.followup.toLowerCase().startsWith('active');
                      const fsStyle = isActive ? FOLLOWUP_STYLES['Active'] :
                        row.followup.toLowerCase().startsWith('completed') ? FOLLOWUP_STYLES['Completed'] :
                        row.followup.toLowerCase().startsWith('stage') ? FOLLOWUP_STYLES['Stage'] : FOLLOWUP_STYLES['Not started'];
                      return (
                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-500/10 flex items-center justify-center border border-white/10">
                                <span className="text-[12px] font-black text-indigo-400">{row.name ? row.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : '?'}</span>
                              </div>
                              <span className="text-sm font-bold text-white">{row.name || '—'}</span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-sm text-slate-400">{row.email || '—'}</td>
                          <td className="px-4 py-3 text-sm text-slate-300 font-medium">{row.company || '—'}</td>
                          <td className="px-4 py-3">
                            <span className="inline-flex px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest bg-indigo-500/5 border border-indigo-500/20 text-indigo-400">{row.sector}</span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${actionStyle.bg} ${actionStyle.border} ${actionStyle.color}`}>
                              <ActionIcon className="w-3 h-3" /> {row.action}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${fsStyle.bg} ${fsStyle.border} ${fsStyle.color}`}>
                              {isActive && <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />}
                              {row.followup}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-[11px] text-slate-500 font-mono">
                            {row.date ? new Date(row.date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                          </td>
                        </tr>
                      );
                    })}
                    {report.length === 0 && (
                      <tr><td colSpan="7" className="p-12 text-center"><AlertTriangle className="w-8 h-8 text-slate-700 mx-auto mb-3" /><div className="text-slate-500 font-bold uppercase tracking-widest text-xs">No leads found</div></td></tr>
                    )}
                  </tbody>
                </table>
              </div>
              <div className="px-4 py-3 border-t border-white/5 bg-[#0d0f16]/50">
                <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{report.length} {report.length === 1 ? 'lead' : 'leads'} shown</div>
              </div>
            </>
          );
        })()}
      </div>
    </>
  );

  const renderMisView = () => {
    if (loading && !data) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="w-8 h-8 border-2 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
        </div>
      );
    }
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {engagementMetrics.map((m, i) => (
            <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-4 text-center">
              <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">{m.label}</div>
              <div className="text-2xl font-black text-white">{m.value}</div>
            </div>
          ))}
        </div>
        <div className="bg-[#111521] border border-white/5 rounded-2xl p-6">
          <div className="flex items-center gap-2 mb-6">
            <TrendingUp className="w-5 h-5 text-indigo-400" />
            <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Pipeline Funnel</h3>
          </div>
          <div className="space-y-4">
            {pipelineData.map((item, i) => {
              const maxVal = pipelineData[0]?.value || 1;
              const pct = Math.round((item.value / maxVal) * 100);
              const colors = ['#6366f1', '#818cf8', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444'];
              return (
                <div key={i} className="space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="font-bold text-slate-300">{item.name}</span>
                    <span className="font-black text-white">{item.value}</span>
                  </div>
                  <div className="h-3 bg-white/5 rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: colors[i] }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-[#111521] border border-white/5 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-6">
              <PieChartIcon className="w-5 h-5 text-violet-400" />
              <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Lead Type</h3>
            </div>
            {personaData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={personaData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                    {personaData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', borderRadius: '8px' }} />
                  <Legend wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : <div className="text-slate-500 text-xs text-center py-12">No data</div>}
          </div>
          <div className="bg-[#111521] border border-white/5 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-6">
              <BarChart3 className="w-5 h-5 text-indigo-400" />
              <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Sector Distribution</h3>
            </div>
            {industryData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={industryData} layout="vertical" margin={{ left: 100, right: 20 }}>
                  <XAxis type="number" hide />
                  <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', borderRadius: '8px' }} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={16}>
                    {industryData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <div className="text-slate-500 text-xs text-center py-12">No data</div>}
          </div>
          <div className="bg-[#111521] border border-white/5 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-6">
              <PieChartIcon className="w-5 h-5 text-emerald-400" />
              <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Country Coverage</h3>
            </div>
            {countryData.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <PieChart>
                  <Pie data={countryData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={3} dataKey="value" label={({ name, value }) => `${name}: ${value}`} labelLine={false}>
                    {countryData.map((_, i) => <Cell key={i} fill={COLORS[(i + 3) % COLORS.length]} />)}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', borderRadius: '8px' }} />
                  <Legend wrapperStyle={{ fontSize: '10px', color: '#94a3b8' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : <div className="text-slate-500 text-xs text-center py-12">No data</div>}
          </div>
          <div className="bg-[#111521] border border-white/5 rounded-2xl p-6">
            <div className="flex items-center gap-2 mb-6">
              <BarChart3 className="w-5 h-5 text-amber-400" />
              <h3 className="text-[11px] font-black text-white uppercase tracking-widest">Action Breakdown</h3>
            </div>
            {actionBreakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={actionBreakdown} margin={{ left: 20, right: 20 }}>
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 9 }} />
                  <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#111521', border: '1px solid rgba(255,255,255,0.1)', fontSize: '11px', borderRadius: '8px' }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]} barSize={30}>
                    {actionBreakdown.map((_, i) => <Cell key={i} fill={COLORS[(i + 5) % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : <div className="text-slate-500 text-xs text-center py-12">No data</div>}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-[#0a0c10] p-4 lg:p-6">
      <div className="max-w-[1600px] mx-auto">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-black text-white uppercase tracking-tight">Reports & Analytics</h1>
            <p className="text-[11px] text-slate-500 font-bold uppercase tracking-[2px] mt-1">Lead engagement report</p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={exportCSV} className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600/10 hover:bg-emerald-600/20 text-emerald-400 border border-emerald-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all">
              <Download className="w-3.5 h-3.5" /> Export CSV
            </button>
            <button onClick={() => window.open('/mis-report', '_blank')} className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all">
              <FileText className="w-3.5 h-3.5" /> MIS PDF
            </button>
            <button onClick={() => { setLoading(true); fetchReport(); }} className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600/10 hover:bg-indigo-600/20 text-indigo-400 border border-indigo-500/20 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Stats Strip */}
        <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
          {stats.map((s, i) => (
            <div key={i} className="bg-[#111521] border border-white/5 rounded-xl p-4">
              <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">{s.label}</div>
              <div className="text-xl font-black text-white">{s.value}</div>
            </div>
          ))}
        </div>

        {/* View Toggle + Range Filter */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex items-center gap-2">
            <button onClick={() => setView('table')} className={`px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'table' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30' : 'bg-white/[0.03] text-slate-400 border border-white/5 hover:border-white/20'}`}>
              Lead Report
            </button>
            <button onClick={() => setView('mis')} className={`px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${view === 'mis' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30' : 'bg-white/[0.03] text-slate-400 border border-white/5 hover:border-white/20'}`}>
              MIS Report
            </button>
          </div>
          <div className="w-px h-6 bg-white/10" />
          <div className="flex items-center gap-2">
            {RANGES.map(r => (
              <button key={r.key} onClick={() => { setRange(r.key); setDateFrom(''); setDateTo(''); }} className={`px-4 py-2 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${range === r.key ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30' : 'bg-white/[0.03] text-slate-500 border border-white/5 hover:border-white/20'}`}>
                {r.label}
              </button>
            ))}
            <div className="w-px h-6 bg-white/10" />
            <select value={selYear} onChange={e => { setSelYear(Number(e.target.value)); const {start, end} = getMonthRange(Number(e.target.value), selMonth); setDateFrom(start); setDateTo(end); setRange('all'); }}
              className="bg-[#111521] border border-white/5 rounded-lg px-3 py-2 text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50">
              {(() => { const y = []; for (let i = _now.getFullYear() - 2; i <= _now.getFullYear(); i++) y.push(i); return y; })().map(y => <option key={y} value={y}>{y}</option>)}
            </select>
            <select value={selMonth} onChange={e => { setSelMonth(Number(e.target.value)); const {start, end} = getMonthRange(selYear, Number(e.target.value)); setDateFrom(start); setDateTo(end); setRange('all'); }}
              className="bg-[#111521] border border-white/5 rounded-lg px-3 py-2 text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50">
              {MONTHS.map((m, i) => <option key={i} value={i}>{m}</option>)}
            </select>
            <div className="flex items-center gap-2">
              <input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setRange('all'); }} className="bg-[#111521] border border-white/5 rounded-lg px-3 py-2 text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50" />
              <span className="text-[9px] text-slate-600 font-black uppercase tracking-widest">to</span>
              <input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setRange('all'); }} className="bg-[#111521] border border-white/5 rounded-lg px-3 py-2 text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50" />
            </div>
          </div>
        </div>

        {view === 'table' ? (renderTableView()) : (renderMisView())}
      </div>
    </div>
  );
};

export default Metrics;
