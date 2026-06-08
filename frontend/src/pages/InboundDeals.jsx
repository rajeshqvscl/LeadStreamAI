import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import api from '../services/api';
import { 
  TrendingUp, DollarSign, ExternalLink, 
  Mail, Calendar, Search, Sparkles,
  ChevronRight, Clock, Video, Download,
  FileText, Brain, ChevronDown, ChevronUp, Link2, X,
  Activity, ShieldCheck, Zap, BarChart3, PieChart, Loader2
} from 'lucide-react';

const STATUS_STYLES = {
  MEETING_REQUESTED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  INTERESTED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  NEEDS_MORE_INFO: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  NOT_INTERESTED: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const STATUS_LABELS = {
  MEETING_REQUESTED: 'Meeting Requested',
  INTERESTED: 'Interested',
  NOT_INTERESTED: 'Not Interested',
  NEEDS_MORE_INFO: 'Needs Info',
};

const FILTERS = ['ALL', 'MEETING_REQUESTED', 'INTERESTED', 'NEEDS_MORE_INFO', 'NOT_INTERESTED'];

const stripHtml = (html) => {
  if (!html) return '';
  return html.replace(/<[^>]*>?/gm, '');
};

const extractReply = (text) => {
  if (!text) return '';
  const cleaned = stripHtml(text);
  const patterns = [
    /\n-+\s*Original Message\s*-+\s*\n/i,
    /\nOn\s+.*?\d{4},\s+at\s+.*?\d{2}:\d{2}.*?wrote:\s*\n/i,
    /\nOn\s+.*?\d{4}.*?\d{1,2}:\d{2}.*?wrote:\s*\n/i,
    /\n-+\s*Forwarded message\s*-+\s*\n/i,
    /\nFrom:.*?\nSent:.*?\nTo:.*?\n/i,
    /\n>+\s/,
  ];
  let result = cleaned;
  for (const p of patterns) {
    const match = result.match(p);
    if (match) {
      result = result.substring(0, match.index).trim();
      break;
    }
  }
  const lines = result.split('\n').filter(l => !l.trim().startsWith('>'));
  return lines.join('\n').trim() || cleaned;
};

const formatIST = (dateStr) => {
  if (!dateStr) return { date: '—', time: '' };
  try {
    let cleanStr = dateStr;
    if (typeof cleanStr === 'string' && !cleanStr.endsWith('Z') && !cleanStr.includes('+') && !/-[0-9]{2}:[0-9]{2}$/.test(cleanStr)) {
      cleanStr = cleanStr.replace(' ', 'T') + 'Z';
    }
    const d = new Date(cleanStr);
    if (isNaN(d.getTime())) return { date: dateStr, time: '' };
    return {
      date: d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' }),
      time: d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })
    };
  } catch { return { date: dateStr, time: '' }; }
};

const DealCard = React.memo(({ deal, onClick, formatIST, getStatusColor, getStatusLabel, stripHtml, extractReply }) => {
  const ist = formatIST(deal.updated_at);
  return (
    <div onClick={() => onClick(deal)} className="bg-[#131722] border border-white/5 rounded-[24px] p-1 group hover:border-emerald-500/30 transition-all cursor-pointer relative overflow-hidden hover:bg-white/[0.02]">
      <div className="p-5 flex flex-col md:flex-row items-center gap-8 relative z-10">
        <div className="w-full md:w-[280px] flex items-center gap-4 md:border-r border-white/5 md:pr-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xl font-black shadow-lg shrink-0">
            {deal.first_name?.[0]}{deal.last_name?.[0]}
          </div>
          <div className="min-w-0">
            <div className="text-[15px] font-black text-white truncate mb-0.5 group-hover:text-emerald-400 transition-colors uppercase">
              {deal.first_name} {deal.last_name}
            </div>
            <div className="text-[10px] font-bold text-slate-500 truncate mb-1.5">{deal.email}</div>
            <div className="flex gap-2 flex-wrap">
              <span className="px-2 py-0.5 bg-white/5 rounded-md text-[9px] font-black text-slate-400 uppercase tracking-tighter">
                {deal.company_name || 'Individual'}
              </span>
              {deal.sector && (
                <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded-md text-[9px] font-black uppercase tracking-tighter border border-emerald-500/20">
                  {deal.sector}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 flex flex-col gap-3 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <div className={`px-4 py-1.5 rounded-xl border text-[10px] font-black uppercase tracking-widest ${getStatusColor(deal)}`}>
              {getStatusLabel(deal)}
            </div>
            {deal.meeting_time && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-xl text-[10px] font-black text-blue-400 uppercase tracking-widest whitespace-nowrap">
                <Clock className="w-3.5 h-3.5" />
                {new Date(deal.meeting_time).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </div>
            )}
            {deal.sentiment_score != null && (
              <div className="flex items-center gap-3 bg-white/5 px-4 py-1.5 rounded-xl border border-white/5">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Sentiment</span>
                <div className="w-20 h-1.5 bg-white/10 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${deal.sentiment_score > 70 ? 'bg-emerald-500' : deal.sentiment_score > 40 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${deal.sentiment_score}%` }} />
                </div>
                <span className="text-[11px] font-black text-white">{deal.sentiment_score}%</span>
              </div>
            )}
            {deal.pitch_deck_url && (
              <div className="px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-xl text-[10px] font-black text-purple-400 uppercase tracking-widest flex items-center gap-2 whitespace-nowrap">
                <FileText className="w-3.5 h-3.5" /> Deck
              </div>
            )}
          </div>
          <p className="text-slate-400 text-sm line-clamp-2 italic font-medium leading-relaxed">
            "{extractReply(deal.remarks || deal.rag_advice).substring(0, 200) || 'Analyzing communication patterns...'}"
          </p>
        </div>

        <div className="w-full md:w-auto flex items-center gap-6 md:border-l border-white/5 md:pl-8">
          <div className="text-center">
            <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Est. Size</div>
            <div className="text-lg font-black text-white">{deal.deal_size || '—'}</div>
          </div>
          <div className="text-center">
            <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Activity</div>
            <div className="text-xs font-black text-white whitespace-nowrap">{ist.date}</div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">{ist.time}</div>
          </div>
          <ChevronRight className="w-6 h-6 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all shrink-0" />
        </div>
      </div>
    </div>
  );
});

const InboundDeals = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  const [selectedDeal, setSelectedDeal] = useState(null);
  const [schedulingDeal, setSchedulingDeal] = useState(null);
  const [meetingTime, setMeetingTime] = useState('');
  const [isScheduling, setIsScheduling] = useState(false);
  const [page, setPage] = useState(1);
  const [totalDeals, setTotalDeals] = useState(0);
  const perPage = 20;

  const fetchDeals = useCallback(async (silent = false) => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      if (!silent) setLoading(true);
      const { data } = await api.get(`/api/gmail/inbound-deals?page=${page}&per_page=${perPage}`, {
        headers: { 'X-User-Id': userId }
      });
      setDeals(data.leads || []);
      setTotalDeals(data.total || 0);
    } catch (err) {
      console.error('Error fetching deals:', err);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchDeals();
    const pollId = setInterval(() => fetchDeals(true), 30000);
    return () => clearInterval(pollId);
  }, [fetchDeals]);

  const filteredDeals = useMemo(() => {
    return deals.filter(deal => {
      const fullName = `${deal.first_name || ''} ${deal.last_name || ''} ${deal.company_name || ''}`.toLowerCase();
      const matchesSearch = fullName.includes(search.toLowerCase());
      const matchesFilter = filter === 'ALL' || deal.reply_intent === filter;
      return matchesSearch && matchesFilter;
    });
  }, [deals, filter, search]);

  const getStatusColor = useCallback((deal) => {
    if (deal.meeting_time) return 'bg-blue-600 text-white border-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.4)]';
    return STATUS_STYLES[deal.reply_intent] || 'bg-slate-500/10 text-slate-400 border-white/5';
  }, []);

  const getStatusLabel = useCallback((deal) => {
    if (deal.meeting_time) return 'Meeting Locked';
    return STATUS_LABELS[deal.reply_intent] || deal.reply_intent?.replace(/_/g, ' ') || 'New Deal';
  }, []);

  const handleRefresh = useCallback(async () => {
    try {
      setLoading(true);
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await Promise.all([
        api.post('/api/gmail/sync-inbound', {}, { headers: { 'X-User-Id': userId } }),
        api.post('/api/gmail/retro-sync-pdfs', {}, { headers: { 'X-User-Id': userId } })
      ]);
      await fetchDeals();
    } catch (err) {
      console.error('Sync failed:', err);
      fetchDeals();
    } finally {
      setLoading(false);
    }
  }, [fetchDeals]);

  const handleConfirmSchedule = useCallback(async () => {
    if (!meetingTime || !schedulingDeal) return;
    setIsScheduling(true);
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await api.post(`/api/gmail/schedule-meeting/${schedulingDeal.id}`, 
        { meeting_time: new Date(meetingTime).toISOString() },
        { headers: { 'X-User-Id': userId } }
      );
      setSchedulingDeal(null);
      setMeetingTime('');
      fetchDeals(true);
    } catch (e) {
      alert('Failed: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  }, [meetingTime, schedulingDeal, fetchDeals]);

  const stats = useMemo(() => [
    { label: 'Total Deal Volume', value: deals.length, icon: BarChart3, color: 'text-blue-400' },
    { label: 'High Intent', value: deals.filter(d => d.reply_intent === 'MEETING_REQUESTED').length, icon: Zap, color: 'text-emerald-400' },
    { label: 'Pitch Decks', value: deals.filter(d => d.pitch_deck_url).length, icon: FileText, color: 'text-purple-400' },
    { label: 'Avg Sentiment', value: deals.length ? `${Math.round(deals.reduce((acc, d) => acc + (d.sentiment_score || 50), 0) / deals.length)}%` : '—', icon: ShieldCheck, color: 'text-amber-400' }
  ], [deals]);

  const totalPages = Math.max(1, Math.ceil(totalDeals / perPage));

  return (
    <div className="min-h-screen bg-[#0b0f19] text-white">
      <div className="max-w-[1600px] mx-auto px-6 py-8 animate-in fade-in duration-500">
        
        {/* Header */}
        <div className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6 border-b border-white/5 pb-8">
          <div>
            <div className="flex items-center gap-3 mb-3">
              <div className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-500 uppercase tracking-[3px]">
                Inbound Intelligence
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">{deals.length} Active</span>
              </div>
            </div>
            <h1 className="text-[44px] font-black tracking-tight leading-none mb-3">
              Inbound <span className="text-emerald-400 italic">Deals</span>
            </h1>
            <p className="text-slate-400 text-base font-medium">Lead replies, pitch decks & meeting scheduling</p>
          </div>
          <button onClick={handleRefresh} disabled={loading} className="flex items-center gap-2 px-6 py-3.5 bg-indigo-600 hover:bg-indigo-500 rounded-2xl transition-all shadow-xl shadow-indigo-600/20 group cursor-pointer disabled:opacity-50">
            <Sparkles className={`w-4 h-4 ${loading ? 'animate-spin' : 'group-hover:scale-110 transition-transform'}`} />
            <span className="text-xs font-black uppercase tracking-widest">{loading ? 'Syncing...' : 'Sync Now'}</span>
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {stats.map((stat, i) => (
            <div key={i} className="bg-[#131722] border border-white/5 p-5 rounded-[20px] hover:border-white/10 transition-all">
              <div className="flex justify-between items-start mb-3">
                <div className={`p-2.5 rounded-xl bg-white/5 ${stat.color}`}>
                  <stat.icon className="w-4 h-4" />
                </div>
                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Live</div>
              </div>
              <div className="text-2xl font-black mb-1">{stat.value}</div>
              <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Filter Bar */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input type="text" placeholder="Search name, company..." value={search} onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[#131722] border border-white/5 rounded-2xl py-3.5 pl-12 pr-4 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500/30 transition-all" />
          </div>
          <div className="flex bg-[#131722] border border-white/5 p-1 rounded-2xl gap-1 overflow-x-auto">
            {FILTERS.map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-5 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer whitespace-nowrap ${filter === f ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}>
                {f.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Deals List */}
        <div className="space-y-3">
          {loading && deals.length === 0 ? (
            <div className="py-20 flex flex-col items-center justify-center gap-4">
              <Loader2 className="w-8 h-8 text-emerald-500 animate-spin" />
              <span className="text-emerald-500 font-black tracking-[6px] uppercase text-[10px] animate-pulse">Loading Deals...</span>
            </div>
          ) : filteredDeals.length > 0 ? (
            filteredDeals.map((deal) => (
              <DealCard key={deal.id} deal={deal} onClick={setSelectedDeal}
                formatIST={formatIST} getStatusColor={getStatusColor} getStatusLabel={getStatusLabel}
                stripHtml={stripHtml} extractReply={extractReply} />
            ))
          ) : (
            <div className="py-20 text-center bg-[#131722] border border-white/5 rounded-[32px]">
              <div className="text-slate-600 font-black tracking-widest uppercase text-sm">
                {deals.length === 0 ? 'No inbound deals yet' : 'No deals match your filter'}
              </div>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalDeals > perPage && (
          <div className="mt-8 flex items-center justify-between bg-[#131722] border border-white/5 p-5 rounded-[20px]">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/5 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-[2px] hover:text-white hover:border-white/10 transition-all disabled:opacity-20 cursor-pointer">
              <ChevronRight className="w-4 h-4 rotate-180" /> Previous
            </button>
            <span className="text-[10px] font-black text-slate-600 tracking-[0.3em] uppercase">Page {page} / {totalPages}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page >= totalPages}
              className="flex items-center gap-2 px-5 py-2.5 bg-white/5 border border-white/5 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-[2px] hover:text-white hover:border-white/10 transition-all disabled:opacity-20 cursor-pointer">
              Next <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Detail Panel */}
        {selectedDeal && (
          <div className="fixed inset-0 z-[1000] flex justify-end bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="absolute inset-0" onClick={() => setSelectedDeal(null)} />
            <div className="relative w-full max-w-2xl bg-[#0b0f19] border-l border-white/10 h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-500 z-10">
              <div className="sticky top-0 z-20 bg-[#0b0f19]/90 backdrop-blur-xl border-b border-white/10 p-6 flex justify-between items-start">
                <div className="flex items-center gap-5">
                  <div className="w-16 h-16 rounded-[24px] bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center text-2xl font-black shadow-2xl shrink-0">
                    {selectedDeal.first_name?.[0]}
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-1.5 flex-wrap">
                      <h2 className="text-2xl font-black uppercase tracking-tight leading-none">{selectedDeal.first_name} {selectedDeal.last_name}</h2>
                      <div className={`px-3 py-0.5 rounded-lg border text-[9px] font-black uppercase tracking-widest ${getStatusColor(selectedDeal)}`}>
                        {getStatusLabel(selectedDeal)}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-slate-400 text-xs">
                      <span className="font-bold uppercase tracking-widest">{selectedDeal.company_name}</span>
                      {selectedDeal.sector && <><span className="w-1 h-1 rounded-full bg-slate-700" /><span className="font-bold text-emerald-400 uppercase tracking-widest">{selectedDeal.sector}</span></>}
                    </div>
                  </div>
                </div>
                <button onClick={() => setSelectedDeal(null)} className="p-2.5 bg-white/5 hover:bg-white/10 rounded-xl text-slate-400 hover:text-white transition-all cursor-pointer">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-6 space-y-8 pb-20">
                {/* Intelligence Grid */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-[#131722] border border-white/5 p-5 rounded-2xl">
                    <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-3">Intent</div>
                    <div className="text-lg font-black text-emerald-400 uppercase">{getStatusLabel(selectedDeal)}</div>
                    <div className="text-[10px] text-slate-500 mt-1.5 font-medium">System Confidence: 94%</div>
                  </div>
                  <div className="bg-[#131722] border border-white/5 p-5 rounded-2xl">
                    <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-3">Sentiment</div>
                    <div className="text-2xl font-black text-white">{selectedDeal.sentiment_score || '—'}%</div>
                    <div className="h-1.5 w-full bg-white/5 rounded-full mt-3 overflow-hidden">
                      <div className={`h-full rounded-full ${(selectedDeal.sentiment_score || 0) > 70 ? 'bg-emerald-500' : (selectedDeal.sentiment_score || 0) > 40 ? 'bg-amber-500' : 'bg-rose-500'}`}
                        style={{ width: `${selectedDeal.sentiment_score || 0}%` }} />
                    </div>
                  </div>
                </div>

                {/* Strategy */}
                <div className="bg-emerald-500/5 border border-emerald-500/10 p-6 rounded-[24px]">
                  <div className="flex items-center gap-2.5 mb-4">
                    <Zap className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-xs font-black uppercase tracking-widest text-emerald-400">Strategy</h3>
                  </div>
                  <div className="text-xl font-black text-white mb-3 italic leading-tight">
                    "{selectedDeal.meeting_time ? 'Prepare for Strategy Session.' : selectedDeal.reply_intent === 'MEETING_REQUESTED' ? 'Schedule discovery session within 24 hours.' : 'Execute personalized follow-up with traction metrics.'}"
                  </div>
                  <p className="text-slate-400 text-sm font-medium leading-relaxed">
                    {extractReply(selectedDeal.remarks || selectedDeal.rag_advice)}
                  </p>
                </div>

                {/* Deep Dive */}
                {selectedDeal.rag_intelligence && (
                  <div className="animate-in fade-in slide-in-from-bottom duration-500">
                    <div className="flex items-center gap-2.5 mb-4">
                      <PieChart className="w-4 h-4 text-blue-400" />
                      <h3 className="text-xs font-black uppercase tracking-[3px] text-slate-400">Analyst Deep-Dive</h3>
                    </div>
                    
                    <div className="bg-[#131722] border border-white/5 rounded-[24px] overflow-hidden">
                      <div className="p-6 border-b border-white/5 bg-white/[0.02]">
                        <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-4 flex items-center gap-2">
                          <ShieldCheck className="w-3 h-3 text-blue-400" /> Actuals
                        </div>
                        <div className="grid grid-cols-2 gap-6">
                          <div>
                            <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Revenue</div>
                            <div className="text-lg font-black text-white">
                              {selectedDeal.rag_intelligence?.actuals?.revenue || selectedDeal.deal_size || '—'}
                            </div>
                          </div>
                          <div>
                            <div className="text-[8px] font-black text-slate-600 uppercase tracking-widest mb-1">Orders / Traction</div>
                            <div className="text-lg font-black text-white">
                              {selectedDeal.rag_intelligence?.actuals?.orders || '—'}
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="p-6 space-y-6">
                        <div>
                          <div className="text-[9px] font-black text-blue-400 uppercase tracking-widest mb-3">Unit Economics</div>
                          <div className="grid grid-cols-2 gap-4">
                            <div className="p-3 bg-white/5 rounded-xl">
                              <div className="text-[8px] font-black text-slate-500 uppercase mb-1">Margin</div>
                              <div className="text-base font-black text-white">{selectedDeal.rag_intelligence?.unit_economics?.margin || '—'}</div>
                            </div>
                            <div className="p-3 bg-white/5 rounded-xl">
                              <div className="text-[8px] font-black text-slate-500 uppercase mb-1">Ticket Size</div>
                              <div className="text-base font-black text-white">{selectedDeal.rag_intelligence?.unit_economics?.ticket_size || '—'}</div>
                            </div>
                          </div>
                        </div>

                        <div>
                          <div className="text-[9px] font-black text-blue-400 uppercase tracking-widest mb-3">Insights</div>
                          <div className="space-y-2">
                            {(selectedDeal.rag_intelligence?.insights || ['High scalability potential', 'Proven unit economics']).map((insight, idx) => (
                              <div key={idx} className="flex items-center gap-2.5 text-slate-400 text-xs font-medium p-3 bg-white/[0.02] rounded-xl border border-white/5">
                                <ChevronRight className="w-3 h-3 text-emerald-500 shrink-0" />
                                {insight}
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Footer Actions */}
                <div className="grid grid-cols-2 gap-4 pt-4">
                  {selectedDeal.pitch_deck_url && (
                    <a href={selectedDeal.pitch_deck_url} target="_blank" rel="noreferrer"
                      className="flex items-center justify-center gap-2.5 p-4 bg-purple-600 hover:bg-purple-500 rounded-2xl transition-all shadow-xl shadow-purple-600/20 group">
                      <FileText className="w-4 h-4 group-hover:scale-110 transition-transform" />
                      <span className="text-[10px] font-black uppercase tracking-widest">Pitch Deck</span>
                    </a>
                  )}
                  <button onClick={() => setSchedulingDeal(selectedDeal)}
                    className="flex items-center justify-center gap-2.5 p-4 bg-blue-600 hover:bg-blue-500 rounded-2xl transition-all shadow-xl shadow-blue-600/20 group cursor-pointer">
                    <Calendar className="w-4 h-4 group-hover:scale-110 transition-transform" />
                    <span className="text-[10px] font-black uppercase tracking-widest">Schedule Call</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Schedule Modal */}
        {schedulingDeal && (
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/90 backdrop-blur-sm p-4">
            <div className="bg-[#131722] border border-white/10 rounded-[32px] w-full max-w-md shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300">
              <div className="p-8 border-b border-white/5 text-center">
                <div className="w-16 h-16 bg-blue-500/10 rounded-2xl flex items-center justify-center mx-auto mb-5 border border-blue-500/20">
                  <Calendar className="w-8 h-8 text-blue-500" />
                </div>
                <h3 className="text-lg font-black text-white uppercase tracking-widest mb-1">Schedule Session</h3>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">with {schedulingDeal.first_name} {schedulingDeal.last_name}</p>
              </div>
              <div className="p-8 space-y-5">
                <div>
                  <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2.5 text-center">Select Time (IST)</label>
                  <input type="datetime-local" value={meetingTime} onChange={(e) => setMeetingTime(e.target.value)}
                    className="w-full bg-[#0b0f19] border border-white/10 rounded-xl px-5 py-3.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50" style={{ colorScheme: 'dark' }} />
                </div>
                <div className="flex gap-3 pt-2">
                  <button onClick={() => { setSchedulingDeal(null); setMeetingTime(''); }}
                    className="flex-1 bg-white/5 hover:bg-white/10 text-white font-black uppercase tracking-widest text-[10px] py-4 rounded-xl transition-all cursor-pointer border border-white/5">
                    Cancel
                  </button>
                  <button onClick={handleConfirmSchedule} disabled={isScheduling || !meetingTime}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-[10px] py-4 rounded-xl transition-all cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2 shadow-xl shadow-blue-600/20">
                    {isScheduling ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                    {isScheduling ? 'Scheduling...' : 'Confirm'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default InboundDeals;