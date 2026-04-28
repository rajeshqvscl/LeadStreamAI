import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import { 
  TrendingUp, DollarSign, ExternalLink, 
  Mail, Calendar, Search, Sparkles,
  ChevronRight, Clock, Video, Download,
  FileText, Brain, ChevronDown, ChevronUp, Link2, X
} from 'lucide-react';

const InboundDeals = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [search, setSearch] = useState('');
  
  // Scheduling State
  const [schedulingDeal, setSchedulingDeal] = useState(null);
  const [meetingTime, setMeetingTime] = useState('');
  const [isScheduling, setIsScheduling] = useState(false);

  const fetchDeals = async () => {
    try {
      const { data } = await axios.get('/api/gmail/inbound-deals');
      setDeals(data);
      setLoading(false);
    } catch (err) {
      console.error('Error fetching deals:', err);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeals();
    const interval = setInterval(fetchDeals, 30000);
    return () => clearInterval(interval);
  }, []);

  const filteredDeals = deals.filter(deal => {
    const matchesSearch = (deal.first_name + ' ' + deal.last_name + ' ' + deal.company_name).toLowerCase().includes(search.toLowerCase());
    const matchesFilter = filter === 'ALL' || deal.reply_intent === filter;
    return matchesSearch && matchesFilter;
  });

  const getStatusColor = (intent) => {
    switch (intent) {
      case 'MEETING_REQUESTED': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'INTERESTED': return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'NEEDS_MORE_INFO': return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
      case 'NOT_INTERESTED': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-slate-500/10 text-slate-400 border-white/5';
    }
  };

  const getStatusLabel = (intent) => {
    switch (intent) {
      case 'MEETING_REQUESTED': return 'Meeting Requested';
      case 'INTERESTED': return 'Potential Client (Interested)';
      case 'NOT_INTERESTED': return 'Not Interested';
      case 'NEEDS_MORE_INFO': return 'Needs Info';
      default: return intent?.replace(/_/g, ' ') || 'Reply Detected';
    }
  };

  // Format date to IST
  const formatIST = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const date = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
      const time = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
      return { date, time };
    } catch { return { date: dateStr, time: '' }; }
  };

  const exportToCSV = () => {
    const headers = ['First Name', 'Last Name', 'Email', 'Company Name', 'Sector', 'LinkedIn', 'Sentiment', 'Estimated Size', 'Meeting Time', 'Meeting Link', 'Pitch Deck', 'Last Activity'];
    const csvContent = [
      headers.join(','),
      ...filteredDeals.map(d => [
        `"${d.first_name || ''}"`,
        `"${d.last_name || ''}"`,
        `"${d.email || ''}"`,
        `"${d.company_name || ''}"`,
        `"${d.sector || ''}"`,
        `"${d.linkedin_url || ''}"`,
        `"${getStatusLabel(d.reply_intent)}"`,
        `"${d.deal_size || ''}"`,
        `"${d.meeting_time ? new Date(d.meeting_time).toLocaleString() : ''}"`,
        `"${d.meeting_link || ''}"`,
        `"${d.pitch_deck_url || ''}"`,
        `"${d.updated_at ? new Date(d.updated_at).toLocaleDateString() : ''}"`
      ].join(','))
    ].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `inbound_deals_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleConfirmSchedule = async () => {
    if (!meetingTime || !schedulingDeal) return;
    setIsScheduling(true);
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await axios.post(`/api/gmail/schedule-meeting/${schedulingDeal.id}`, 
        { meeting_time: new Date(meetingTime).toISOString() },
        { headers: { 'X-User-Id': userId } }
      );
      alert('Strategy session scheduled successfully!');
      setSchedulingDeal(null);
      setMeetingTime('');
      fetchDeals();
    } catch (e) {
      console.error('Error scheduling:', e);
      alert('Failed to schedule meeting: ' + (e.response?.data?.detail || e.message));
    } finally {
      setIsScheduling(false);
    }
  };

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10 animate-in fade-in duration-700">
      {/* Header */}
      <div className="mb-10">
        <div className="flex items-center gap-3 mb-4">
          <div className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-500 uppercase tracking-[3px]">
            Deal Intelligence V2.0
          </div>
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
        </div>
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6">
          <div>
            <h1 className="text-[38px] font-black text-white tracking-tight leading-none mb-4">
              Inbound <span className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent italic">Deals</span>
            </h1>
            <p className="text-slate-400 text-lg font-medium">
              High-intent replies, meeting requests and pitch decks — all in one view.
            </p>
          </div>
          <div className="flex bg-[#131722] border border-white/5 p-2 rounded-[20px] shadow-2xl gap-3">
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-2 text-center">
              <div className="text-[9px] font-black text-emerald-500/60 uppercase tracking-widest mb-1">Live Pipeline</div>
              <div className="text-xl font-black text-emerald-400">{deals.length}</div>
            </div>
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl px-4 py-2 text-center">
              <div className="text-[9px] font-black text-blue-500/60 uppercase tracking-widest mb-1">With Pitch Decks</div>
              <div className="text-xl font-black text-blue-400">{deals.filter(d => d.pitch_deck_url).length}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Action Bar */}
      <div className="flex justify-end gap-3 mb-4">
        <button 
          onClick={async () => {
            try {
              setLoading(true);
              const user = JSON.parse(localStorage.getItem('user') || '{}');
              const userId = user.id || 'admin';
              await axios.post('/api/gmail/sync-inbound', {}, { headers: { 'X-User-Id': userId } });
              fetchDeals();
              alert('Inbox scan complete! Any new lead replies have been processed.');
            } catch (err) {
              alert(err.response?.data?.detail || 'Sync failed. Please ensure your Gmail is linked.');
            } finally { setLoading(false); }
          }}
          disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg shadow-indigo-600/20 cursor-pointer"
        >
          <Sparkles className="w-4 h-4" /> Sync Inbound
        </button>
        <button onClick={exportToCSV} className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg shadow-emerald-600/20 cursor-pointer">
          <Download className="w-4 h-4" /> Export Data
        </button>
      </div>

      {/* Control Bar */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="md:col-span-2 relative group">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-emerald-400 transition-colors" />
          <input 
            type="text" 
            placeholder="Filter by Lead, Company, or Email..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-[#131722] border border-white/5 rounded-2xl py-4 pl-12 pr-6 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500/30 transition-all"
          />
        </div>
        <div className="flex gap-2 bg-[#131722] border border-white/5 p-1 rounded-2xl">
          {['ALL', 'MEETING_REQUESTED', 'INTERESTED', 'NOT_INTERESTED'].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`flex-1 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${filter === f ? 'bg-emerald-600 text-white shadow-lg' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
            >
              {f === 'MEETING_REQUESTED' ? 'MEETINGS' : f === 'NOT_INTERESTED' ? 'NOT INT.' : f}
            </button>
          ))}
        </div>
      </div>

      {/* Deals Table */}
      <div className="bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/5">
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Lead Identity</th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Company & Sector</th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Sentiment / AI Intent</th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Est. Size</th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Last Activity (IST)</th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-widest">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {loading ? (
                <tr><td colSpan="6" className="px-8 py-20 text-center">
                  <div className="animate-pulse text-slate-600 font-black tracking-[4px] uppercase text-[10px]">Assembling Deal Flow...</div>
                </td></tr>
              ) : filteredDeals.length > 0 ? (
                filteredDeals.map((deal) => {
                  const ist = formatIST(deal.updated_at);
                  const hasRag = deal.rag_advice || deal.pitch_deck_url;
                  return (
                    <React.Fragment key={deal.id}>
                      <tr className="hover:bg-white/[0.02] transition-colors group">
                        {/* Lead Identity */}
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-4">
                            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center text-indigo-400 font-black flex-shrink-0">
                              {deal.first_name?.[0] || '?'}{deal.last_name?.[0] || ''}
                            </div>
                            <div>
                              <div className="text-sm font-black text-white mb-0.5 group-hover:text-emerald-400 transition-colors uppercase">{deal.first_name} {deal.last_name}</div>
                              <div className="text-[10px] font-bold text-slate-500 tracking-tight lowercase">{deal.email}</div>
                              {deal.linkedin_url && (
                                <a href={deal.linkedin_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[9px] text-blue-500 hover:text-blue-400 mt-0.5 font-bold cursor-pointer">
                                  <Link2 className="w-2.5 h-2.5" /> LinkedIn
                                </a>
                              )}
                            </div>
                          </div>
                        </td>

                        {/* Company */}
                        <td className="px-6 py-5">
                          <div className="text-sm font-black text-white mb-0.5 uppercase">{deal.company_name || 'Individual'}</div>
                          <div className="text-[10px] font-bold text-indigo-400 uppercase tracking-tight">{deal.sector || 'Unknown Sector'}</div>
                        </td>

                        {/* Intent */}
                        <td className="px-6 py-5">
                          <div className="flex flex-col items-start gap-2">
                            <div className={`inline-flex items-center px-3 py-1 rounded-lg border text-[9px] font-black uppercase tracking-widest ${getStatusColor(deal.reply_intent)}`}>
                              {getStatusLabel(deal.reply_intent)}
                            </div>
                            {hasRag && (
                              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 bg-violet-500/10 border border-violet-500/20 rounded-md text-[8px] font-black text-violet-400 uppercase tracking-widest">
                                <Brain className="w-2.5 h-2.5" /> Pitch Deck Attached
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Deal Size */}
                        <td className="px-6 py-5">
                          <div className="flex items-center gap-2">
                            <DollarSign className="w-4 h-4 text-emerald-500" />
                            <span className="text-sm font-black text-white">{deal.deal_size || '—'}</span>
                          </div>
                        </td>

                        {/* Date IST */}
                        <td className="px-6 py-5">
                          <div className="flex flex-col gap-1">
                            <span className="text-[14px] font-black text-white tabular-nums">{ist.date}</span>
                            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{ist.time} IST</span>
                          </div>
                        </td>

                        {/* Actions */}
                        <td className="px-6 py-5">
                          <div className="flex flex-col gap-2">
                            {/* Meeting Schedule Button */}
                            {deal.meeting_time ? (
                              <div className="flex items-center gap-2">
                                <div className="px-2 py-1 bg-blue-500/10 border border-blue-500/20 rounded-md text-[8px] font-black text-blue-500 uppercase">
                                  Meet: {(() => { const m = formatIST(deal.meeting_time); return m.date; })()}
                                </div>
                                <a href={deal.meeting_link} target="_blank" rel="noreferrer" className="text-emerald-500 hover:text-emerald-400">
                                  <Video className="w-3.5 h-3.5" />
                                </a>
                              </div>
                            ) : (
                              <button 
                                onClick={() => setSchedulingDeal(deal)}
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-[9px] font-black uppercase tracking-widest rounded-lg transition-all shadow-lg shadow-blue-600/20 w-fit cursor-pointer"
                              >
                                <Calendar className="w-3 h-3" /> Schedule Call
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    </React.Fragment>
                  );
                })
              ) : (
                <tr>
                  <td colSpan="6" className="px-8 py-20 text-center text-slate-600 italic text-xs tracking-widest uppercase">
                    No inbound replies detected yet. Click "Sync Inbound" to scan your inbox.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {/* Scheduling Modal */}
      {schedulingDeal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#131722] border border-white/10 rounded-3xl w-full max-w-sm shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-white/5">
              <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-2">
                <Calendar className="w-4 h-4 text-blue-500" /> Schedule Strategy Session
              </h3>
              <p className="text-[10px] text-slate-500 mt-2 font-bold uppercase tracking-tighter">
                Lead: {schedulingDeal.first_name} {schedulingDeal.last_name} ({schedulingDeal.company_name})
              </p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">Pick Date & Time</label>
                <input 
                  type="datetime-local" 
                  value={meetingTime}
                  onChange={(e) => setMeetingTime(e.target.value)}
                  className="w-full bg-[#0b0f19] border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  style={{ colorScheme: 'dark' }}
                />
              </div>
              <div className="flex gap-3 pt-4">
                 <button 
                    onClick={() => { setSchedulingDeal(null); setMeetingTime(''); }} 
                    className="flex-1 bg-white/5 hover:bg-white/10 text-white font-black uppercase tracking-widest text-[10px] py-3 rounded-xl transition-all cursor-pointer border border-white/5"
                 >
                    Cancel
                 </button>
                 <button 
                    onClick={handleConfirmSchedule} 
                    disabled={isScheduling || !meetingTime}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-[10px] py-3 rounded-xl transition-all cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-blue-600/20"
                 >
                    {isScheduling ? 'Scheduling...' : 'Confirm'}
                 </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
      </div>
    </div>
  );
};

export default InboundDeals;
