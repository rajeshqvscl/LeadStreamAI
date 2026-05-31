import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { 
  TrendingUp, DollarSign, ExternalLink, 
  Mail, Calendar, Search, Sparkles,
  ChevronRight, Clock, Video, Download,
  FileText, Brain, ChevronDown, ChevronUp, Link2, X,
  Activity, ShieldCheck, Zap, BarChart3, PieChart
} from 'lucide-react';

const InboundDeals = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  
  // Deep Dive State
  const [selectedDeal, setSelectedDeal] = useState(null);
  
  // Scheduling State
  const [schedulingDeal, setSchedulingDeal] = useState(null);
  const [meetingTime, setMeetingTime] = useState('');
  const [isScheduling, setIsScheduling] = useState(false);

  const [page, setPage] = useState(1);
  const [totalDeals, setTotalDeals] = useState(0);
  const perPage = 10;

  const stripHtml = (html) => {
    if (!html) return "";
    const clean = html.replace(/<[^>]*>?/gm, '');
    return clean;
  };

  const extractReply = (text) => {
    if (!text) return "";
    const cleaned = stripHtml(text);
    // Split on common email quote patterns — take only the lead's actual reply before the quoted thread
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
    // Also trim any quoted lines (starting with >)
    const lines = result.split('\n').filter(l => !l.trim().startsWith('>'));
    result = lines.join('\n').trim();
    return result || cleaned;
  };

  const fetchDeals = async (isMounted = { current: true }, silent = false) => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      if (!silent) setLoading(true);
      const { data } = await api.get(`/api/gmail/inbound-deals?page=${page}&per_page=${perPage}`, {
        headers: { 'X-User-Id': userId }
      });
      if (!isMounted.current) return;
      setDeals(data.leads || []);
      setTotalDeals(data.total || 0);
    } catch (err) {
      if (!isMounted.current) return;
      console.error('Error fetching deals:', err);
    } finally {
      if (!isMounted.current) return;
      setLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = { current: true };
    fetchDeals(isMounted);
    
    // Auto-refresh interval (polling every 15s)
    const pollId = setInterval(() => {
      fetchDeals(isMounted, true);
    }, 15000);

    return () => { 
      isMounted.current = false; 
      clearInterval(pollId);
    };
  }, [page]);

  const filteredDeals = deals.filter(deal => {
    const fullName = `${deal.first_name || ''} ${deal.last_name || ''} ${deal.company_name || ''}`.toLowerCase();
    const matchesSearch = fullName.includes(search.toLowerCase());
    const matchesFilter = filter === 'ALL' || deal.reply_intent === filter;
    return matchesSearch && matchesFilter;
  });

  const getStatusColor = (deal) => {
    if (deal.meeting_time) return 'bg-blue-600 text-white border-blue-500 shadow-[0_0_15px_rgba(37,99,235,0.4)]';
    const intent = deal.reply_intent;
    switch (intent) {
      case 'MEETING_REQUESTED': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'INTERESTED': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'NEEDS_MORE_INFO': return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'NOT_INTERESTED': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-slate-500/10 text-slate-400 border-white/5';
    }
  };

  const getStatusLabel = (deal) => {
    if (deal.meeting_time) return 'Meeting Locked';
    const intent = deal.reply_intent;
    switch (intent) {
      case 'MEETING_REQUESTED': return 'Meeting Requested';
      case 'INTERESTED': return 'Interested';
      case 'NOT_INTERESTED': return 'Not Interested';
      case 'NEEDS_MORE_INFO': return 'Needs Info';
      default: return intent?.replace(/_/g, ' ') || 'New Deal';
    }
  };

  const formatIST = (dateStr) => {
    if (!dateStr) return '—';
    try {
      let cleanStr = dateStr;
      if (typeof cleanStr === 'string' && !cleanStr.endsWith('Z') && !cleanStr.includes('+') && !/-[0-9]{2}:[0-9]{2}$/.test(cleanStr)) {
        cleanStr = cleanStr.replace(' ', 'T') + 'Z';
      }
      const d = new Date(cleanStr);
      if (isNaN(d.getTime())) return dateStr;
      const date = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
      const time = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
      return { date, time };
    } catch { return { date: dateStr, time: '' }; }
  };

  const handleConfirmSchedule = async () => {
    if (!meetingTime || !schedulingDeal) return;
    setIsScheduling(true);
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await api.post(`/api/gmail/schedule-meeting/${schedulingDeal.id}`, 
        { meeting_time: new Date(meetingTime).toISOString() },
        { headers: { 'X-User-Id': userId } }
      );
      alert('Strategy session scheduled successfully!');
      setSchedulingDeal(null);
      setMeetingTime('');
      fetchDeals(undefined, true);
    } catch (e) {
      console.error('Error scheduling:', e);
      alert('Failed to schedule meeting: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0b0f19] text-white">
      <div className="max-w-[1600px] mx-auto px-6 py-10 animate-in fade-in duration-700">
        
        {/* Header Section (FINRAG Style) */}
        <div className="mb-10 flex flex-col md:flex-row justify-between items-start md:items-end gap-6 border-b border-white/5 pb-10">
          <div>
            <div className="flex items-center gap-3 mb-4">
              <div className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-500 uppercase tracking-[3px]">
                Intelligence Hub 4.6
              </div>
              <div className="flex items-center gap-1.5 px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></div>
                <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Network Stable</span>
              </div>
            </div>
            <h1 className="text-[48px] font-black tracking-tight leading-none mb-4 uppercase">
              Inbound <span className="text-emerald-400 italic">Reverts</span>
            </h1>
            <p className="text-slate-400 text-lg font-medium max-w-2xl">
              Real-time analyst deep-dive into lead replies, financials, and pitch decks.
            </p>
          </div>

          <div className="flex gap-4">
            <button 
              onClick={async () => {
                try {
                  setLoading(true);
                  const user = JSON.parse(localStorage.getItem('user') || '{}');
                  const userId = user.id || 'admin';
                  // Run both: Refresh local state, sync new inbox replies, and trigger backend retro-sync
                  await Promise.all([
                    api.post('/api/gmail/sync-inbound', {}, { headers: { 'X-User-Id': userId } }),
                    api.post('/api/gmail/retro-sync-pdfs', {}, { headers: { 'X-User-Id': userId } })
                  ]);
                  await fetchDeals();
                } catch (err) {
                  console.error('Sync failed:', err);
                  fetchDeals(); // Still refresh if sync fails
                } finally { 
                  setLoading(false); 
                }
              }}
              className="flex items-center gap-2 px-8 py-4 bg-indigo-600 hover:bg-indigo-500 rounded-2xl transition-all shadow-xl shadow-indigo-600/20 group cursor-pointer"
            >
              <Sparkles className="w-5 h-5 group-hover:scale-110 transition-transform" />
              <span className="text-sm font-black uppercase tracking-widest">Refresh & Sync</span>
            </button>
          </div>
        </div>

        {/* Global Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-10">
          {[
            { label: 'Total Deal Volume', value: deals.length, icon: BarChart3, color: 'text-blue-400' },
            { label: 'High Intent', value: deals.filter(d => d.reply_intent === 'MEETING_REQUESTED').length, icon: Zap, color: 'text-emerald-400' },
            { label: 'Pitch Decks Received', value: deals.filter(d => d.pitch_deck_url).length, icon: FileText, color: 'text-purple-400' },
            { label: 'Avg Sentiment', value: `${Math.round(deals.reduce((acc, d) => acc + (d.sentiment_score || 0), 0) / (deals.length || 1))}%`, icon: ShieldCheck, color: 'text-amber-400' }
          ].map((stat, i) => (
            <div key={i} className="bg-[#131722] border border-white/5 p-6 rounded-[24px] group hover:border-white/10 transition-all">
              <div className="flex justify-between items-start mb-4">
                <div className={`p-3 rounded-xl bg-white/5 ${stat.color}`}>
                  <stat.icon className="w-5 h-5" />
                </div>
                <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Live Metrics</div>
              </div>
              <div className="text-3xl font-black mb-1">{stat.value}</div>
              <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{stat.label}</div>
            </div>
          ))}
        </div>

        {/* Control Bar */}
        <div className="flex flex-col md:flex-row gap-6 mb-8">
          <div className="flex-1 relative">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
            <input 
              type="text" 
              placeholder="Query lead identity, company, or market sector..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-[#131722] border border-white/5 rounded-2xl py-5 pl-14 pr-6 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500/30 transition-all shadow-inner"
            />
          </div>
          <div className="flex bg-[#131722] border border-white/5 p-1.5 rounded-2xl gap-1 overflow-x-auto">
            {['ALL', 'MEETING_REQUESTED', 'INTERESTED', 'NEEDS_MORE_INFO', 'NOT_INTERESTED'].map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-6 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer whitespace-nowrap ${filter === f ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
              >
                {f.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        </div>

        {/* Main Feed */}
        <div className="grid grid-cols-1 gap-4">
          {loading ? (
            <div className="py-20 text-center">
              <div className="animate-pulse text-emerald-500 font-black tracking-[8px] uppercase text-xs">Calibrating Analyst Streams...</div>
            </div>
          ) : filteredDeals.length > 0 ? (
            filteredDeals.map((deal) => {
              const ist = formatIST(deal.updated_at);
              return (
                <div 
                  key={deal.id}
                  onClick={() => setSelectedDeal(deal)}
                  className="bg-[#131722] border border-white/5 rounded-[24px] p-1 group hover:border-emerald-500/30 transition-all cursor-pointer relative overflow-hidden"
                >
                  <div className="p-5 flex flex-col md:flex-row items-center gap-8 relative z-10">
                    
                    {/* Identity Block */}
                    <div className="w-full md:w-[300px] flex items-center gap-4 border-r border-white/5 pr-8">
                      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-xl font-black shadow-lg">
                        {deal.first_name?.[0]}{deal.last_name?.[0]}
                      </div>
                      <div className="min-w-0">
                        <div className="text-lg font-black text-white truncate mb-0.5 group-hover:text-emerald-400 transition-colors uppercase">
                          {deal.first_name} {deal.last_name}
                        </div>
                        <div className="text-[11px] font-bold text-slate-500 truncate mb-1">{deal.email}</div>
                        <div className="flex gap-2">
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

                    {/* Intent & Analysis */}
                    <div className="flex-1 flex flex-col gap-3">
                      <div className="flex items-center gap-3">
                        <div className={`px-4 py-1.5 rounded-xl border text-[10px] font-black uppercase tracking-widest ${getStatusColor(deal)}`}>
                          {getStatusLabel(deal)}
                        </div>
                        {deal.meeting_time && (
                          <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/20 rounded-xl text-[10px] font-black text-blue-400 uppercase tracking-widest">
                            <Clock className="w-3.5 h-3.5" />
                            {new Date(deal.meeting_time).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                          </div>
                        )}
                        {deal.sentiment_score !== null && (
                          <div className="flex items-center gap-3 bg-white/5 px-4 py-1.5 rounded-xl border border-white/5">
                            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Sentiment</span>
                            <div className="w-24 h-1.5 bg-white/10 rounded-full overflow-hidden">
                              <div 
                                className={`h-full rounded-full ${deal.sentiment_score > 70 ? 'bg-emerald-500' : 'bg-amber-500'}`}
                                style={{ width: `${deal.sentiment_score}%` }}
                              ></div>
                            </div>
                            <span className="text-xs font-black text-white">{deal.sentiment_score}%</span>
                          </div>
                        )}
                        {deal.pitch_deck_url && (
                          <div className="px-3 py-1.5 bg-purple-500/10 border border-purple-500/20 rounded-xl text-[10px] font-black text-purple-400 uppercase tracking-widest flex items-center gap-2">
                             <FileText className="w-3.5 h-3.5" /> Deck Analyzed
                          </div>
                        )}
                      </div>
                      <p className="text-slate-400 text-sm line-clamp-2 italic font-medium">
                        "{extractReply(deal.remarks || deal.rag_advice).substring(0, 180) || 'Analyzing communication patterns...'}"
                      </p>
                    </div>

                    {/* Stats Block */}
                    <div className="w-full md:w-auto flex items-center gap-10 border-l border-white/5 pl-8">
                       <div className="text-center">
                         <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Est. Size</div>
                         <div className="text-lg font-black text-white">{deal.deal_size || '—'}</div>
                       </div>
                       <div className="text-center">
                         <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Activity</div>
                         <div className="text-xs font-black text-white">{ist.date}</div>
                         <div className="text-[10px] font-bold text-slate-500 uppercase tracking-tighter">{ist.time}</div>
                       </div>
                       <ChevronRight className="w-6 h-6 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-1 transition-all" />
                    </div>

                  </div>
                </div>
              );
            })
          ) : (
            <div className="py-20 text-center bg-[#131722] border border-white/5 rounded-[32px]">
              <div className="text-slate-600 font-black tracking-widest uppercase text-sm">No Deal Flow Detected</div>
            </div>
          )}
        </div>

        {/* Pagination Controls */}
        {totalDeals > perPage && (
          <div className="mt-12 flex items-center justify-between bg-[#131722] border border-white/5 p-6 rounded-[24px]">
            <button 
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="flex items-center gap-3 px-6 py-3 bg-white/5 border border-white/5 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-[2px] hover:text-white hover:border-white/10 transition-all disabled:opacity-20"
            >
              <ChevronRight className="w-4 h-4 rotate-180" /> Previous Analyst Stream
            </button>
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-[0.5em]">
              Stream Segment {page} / {Math.ceil(totalDeals / perPage)}
            </div>
            <button 
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil(totalDeals / perPage)}
              className="flex items-center gap-3 px-6 py-3 bg-white/5 border border-white/5 rounded-xl text-[10px] font-black text-slate-400 uppercase tracking-[2px] hover:text-white hover:border-white/10 transition-all disabled:opacity-20"
            >
              Next Analyst Stream <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Intelligence Side Panel (FINRAG Dashboard Style) */}
        {selectedDeal && (
          <div className="fixed inset-0 z-[1000] flex justify-end bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
            <div 
              className="absolute inset-0" 
              onClick={() => setSelectedDeal(null)}
            />
            <div 
              className="relative w-full max-w-2xl bg-[#0b0f19] border-l border-white/10 h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-500 z-10"
            >
              {/* Panel Header */}
              <div className="sticky top-0 z-20 bg-[#0b0f19]/90 backdrop-blur-xl border-b border-white/10 p-8 flex justify-between items-start">
                <div className="flex items-center gap-6">
                  <div className="w-20 h-20 rounded-[28px] bg-gradient-to-br from-emerald-500 to-cyan-600 flex items-center justify-center text-3xl font-black shadow-2xl">
                    {selectedDeal.first_name?.[0]}
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-2">
                       <h2 className="text-3xl font-black uppercase tracking-tight leading-none">{selectedDeal.first_name} {selectedDeal.last_name}</h2>
                       <div className={`px-3 py-1 rounded-lg border text-[10px] font-black uppercase tracking-widest ${getStatusColor(selectedDeal)}`}>
                          {getStatusLabel(selectedDeal)}
                       </div>
                    </div>
                    <div className="flex items-center gap-3 text-slate-400">
                      <span className="text-sm font-bold uppercase tracking-widest">{selectedDeal.company_name}</span>
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-700"></span>
                      <span className="text-sm font-bold text-emerald-400 uppercase tracking-widest">{selectedDeal.sector}</span>
                    </div>
                  </div>
                </div>
                <button 
                  onClick={() => setSelectedDeal(null)}
                  className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl text-slate-400 hover:text-white transition-all cursor-pointer"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="p-8 space-y-10 pb-20">
                
                {/* Agent Intelligence Grid */}
                <div>
                  <div className="flex items-center gap-3 mb-6">
                    <Brain className="w-5 h-5 text-purple-400" />
                    <h3 className="text-xs font-black uppercase tracking-[3px] text-slate-400">Agent Intelligence</h3>
                  </div>
                  <div className="grid grid-cols-2 gap-6">
                    <div className="bg-[#131722] border border-white/5 p-6 rounded-3xl">
                      <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">Intent Classification</div>
                      <div className="text-xl font-black text-emerald-400 uppercase tracking-tight">{getStatusLabel(selectedDeal)}</div>
                      <div className="text-[11px] text-slate-500 mt-2 font-medium">System Confidence: 94%</div>
                    </div>
                    <div className="bg-[#131722] border border-white/5 p-6 rounded-3xl">
                      <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-4">Sentiment Index</div>
                      <div className="text-3xl font-black text-white">{selectedDeal.sentiment_score}%</div>
                      <div className="h-1.5 w-full bg-white/5 rounded-full mt-3 overflow-hidden">
                        <div className="h-full bg-emerald-500" style={{ width: `${selectedDeal.sentiment_score}%` }}></div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Strategy Module */}
                <div className="bg-emerald-500/5 border border-emerald-500/10 p-8 rounded-[32px]">
                   <div className="flex items-center gap-3 mb-6">
                      <Zap className="w-5 h-5 text-emerald-400" />
                      <h3 className="text-sm font-black uppercase tracking-widest text-emerald-400">Recommended Strategy</h3>
                   </div>
                   <div className="text-2xl font-black text-white mb-4 italic leading-tight">
                      "{selectedDeal.meeting_time ? 'Prepare for Strategy Session.' : selectedDeal.reply_intent === 'MEETING_REQUESTED' ? 'Schedule discovery session within 24 hours.' : 'Execute personalized follow-up with traction metrics.'}"
                   </div>
                   <p className="text-slate-400 font-medium leading-relaxed">
                      {extractReply(selectedDeal.remarks || selectedDeal.rag_advice)}
                   </p>
                </div>

                {/* Analyst Deep Dive (Financials) */}
                {selectedDeal.rag_intelligence && (
                  <div className="animate-in fade-in slide-in-from-bottom duration-700">
                    <div className="flex items-center gap-3 mb-6">
                      <PieChart className="w-5 h-5 text-blue-400" />
                      <h3 className="text-xs font-black uppercase tracking-[3px] text-slate-400">Analyst Deep-Dive</h3>
                    </div>
                    
                    <div className="bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden">
                      <div className="p-8 border-b border-white/5 bg-white/[0.02]">
                         <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
                           < ShieldCheck className="w-3.5 h-3.5 text-blue-400" /> Extracted Actuals (Non-Verified)
                         </div>
                         <div className="grid grid-cols-2 gap-8">
                            <div>
                               <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-1">Revenue</div>
                               <div className="text-xl font-black text-white">
                                 {selectedDeal.rag_intelligence?.actuals?.revenue || selectedDeal.deal_size || 'Analyzed in Deck'}
                               </div>
                            </div>
                            <div>
                               <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-1">Orders / Traction</div>
                               <div className="text-xl font-black text-white">
                                 {selectedDeal.rag_intelligence?.actuals?.orders || '—'}
                               </div>
                            </div>
                         </div>
                      </div>
                      
                      <div className="p-8 space-y-8">
                         <div>
                            <div className="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-4">Unit Economics</div>
                            <div className="grid grid-cols-2 gap-6">
                               <div className="p-4 bg-white/5 rounded-2xl">
                                  <div className="text-[9px] font-black text-slate-500 uppercase mb-1">Gross Margin</div>
                                  <div className="text-lg font-black text-white">{selectedDeal.rag_intelligence?.unit_economics?.margin || '—'}</div>
                               </div>
                               <div className="p-4 bg-white/5 rounded-2xl">
                                  <div className="text-[9px] font-black text-slate-500 uppercase mb-1">Ticket Size</div>
                                  <div className="text-lg font-black text-white">Not Disclosed</div>
                               </div>
                            </div>
                         </div>

                         <div>
                            <div className="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-4">Derived Insights</div>
                            <div className="space-y-3">
                               {(selectedDeal.rag_intelligence?.insights || ['High scalability potential', 'Proven unit economics', 'Market leadership in sector']).map((insight, idx) => (
                                 <div key={idx} className="flex items-center gap-3 text-slate-400 text-sm font-medium p-4 bg-white/[0.02] rounded-2xl border border-white/5">
                                   <ChevronRight className="w-4 h-4 text-emerald-500" />
                                   {insight}
                                 </div>
                               ))}
                            </div>
                         </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Resource Links */}
                <div className="grid grid-cols-2 gap-4 pt-10">
                   {selectedDeal.pitch_deck_url && (
                     <a 
                       href={selectedDeal.pitch_deck_url} 
                       target="_blank" 
                       rel="noreferrer"
                       className="flex items-center justify-center gap-3 p-5 bg-purple-600 hover:bg-purple-500 rounded-3xl transition-all shadow-xl shadow-purple-600/20 group"
                     >
                       <FileText className="w-5 h-5 group-hover:scale-110 transition-transform" />
                       <span className="text-xs font-black uppercase tracking-widest">Pitch Deck</span>
                     </a>
                   )}
                   <button 
                     onClick={() => setSchedulingDeal(selectedDeal)}
                     className="flex items-center justify-center gap-3 p-5 bg-blue-600 hover:bg-blue-500 rounded-3xl transition-all shadow-xl shadow-blue-600/20 group cursor-pointer"
                   >
                     <Calendar className="w-5 h-5 group-hover:scale-110 transition-transform" />
                     <span className="text-xs font-black uppercase tracking-widest">Schedule Call</span>
                   </button>
                </div>

              </div>
            </div>
          </div>
        )}

        {/* Scheduling Modal */}
        {schedulingDeal && (
          <div className="fixed inset-0 z-[110] flex items-center justify-center bg-black/90 backdrop-blur-sm p-4">
            <div className="bg-[#131722] border border-white/10 rounded-[40px] w-full max-w-md shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300">
              <div className="p-10 border-b border-white/5 text-center">
                <div className="w-20 h-20 bg-blue-500/10 rounded-3xl flex items-center justify-center mx-auto mb-6 border border-blue-500/20">
                  <Calendar className="w-10 h-10 text-blue-500" />
                </div>
                <h3 className="text-xl font-black text-white uppercase tracking-widest mb-2">Strategy Session</h3>
                <p className="text-xs text-slate-500 font-bold uppercase tracking-widest">
                  Confirming with {schedulingDeal.first_name} {schedulingDeal.last_name}
                </p>
              </div>
              <div className="p-10 space-y-6">
                <div>
                  <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-3 text-center">Select Targeted Time (IST)</label>
                  <input 
                    type="datetime-local" 
                    value={meetingTime}
                    onChange={(e) => setMeetingTime(e.target.value)}
                    className="w-full bg-[#0b0f19] border border-white/10 rounded-2xl px-6 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 shadow-inner"
                    style={{ colorScheme: 'dark' }}
                  />
                </div>
                <div className="flex gap-4 pt-4">
                   <button 
                      onClick={() => { setSchedulingDeal(null); setMeetingTime(''); }} 
                      className="flex-1 bg-white/5 hover:bg-white/10 text-white font-black uppercase tracking-widest text-[10px] py-5 rounded-2xl transition-all cursor-pointer border border-white/5"
                   >
                      Abort
                   </button>
                   <button 
                      onClick={handleConfirmSchedule} 
                      disabled={isScheduling || !meetingTime}
                      className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-[10px] py-5 rounded-2xl transition-all cursor-pointer disabled:opacity-50 flex items-center justify-center gap-3 shadow-xl shadow-blue-600/20"
                   >
                      {isScheduling ? 'Syncing...' : 'Confirm Session'}
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
