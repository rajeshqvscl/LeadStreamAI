import React, { useState, useEffect, useRef } from 'react';
import axios from '../services/api';
import DatePicker from 'react-datepicker';
import "react-datepicker/dist/react-datepicker.css";
import { 
  Calendar as CalendarIcon, 
  Video, 
  User, 
  Clock, 
  ChevronRight, 
  ExternalLink,
  MoreVertical,
  Search,
  Filter,
  CheckCircle2,
  CalendarDays,
  Trash2,
  AlertCircle,
  X,
  Layers,
  ArrowUpRight
} from 'lucide-react';

const Meetings = () => {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  
  // Reschedule state
  const [rescheduleMeeting, setRescheduleMeeting] = useState(null);
  const [newMeetingDate, setNewMeetingDate] = useState(null);
  const [isRescheduling, setIsRescheduling] = useState(false);
  
  // Dropdown state
  const [dropdownOpen, setDropdownOpen] = useState(null);
  const [showBulkConfirm, setShowBulkConfirm] = useState(false);

  const datePickerRef = useRef(null);

  useEffect(() => {
    fetchMeetings();
  }, []);

  const fetchMeetings = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      const response = await axios.get('/api/gmail/meetings', {
        headers: { 'X-User-Id': userId }
      });
      setMeetings(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      console.error('Error fetching meetings:', error);
      setMeetings([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredMeetings = Array.isArray(meetings) ? meetings.filter(m => 
    (m.lead_name?.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (m.company_name?.toLowerCase().includes(searchTerm.toLowerCase()))
  ) : [];

  const toggleSelectAll = () => {
    if (selectedIds.size === filteredMeetings.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredMeetings.map(m => m.id)));
    }
  };

  const toggleSelect = (id) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const handleBulkCancel = async () => {
    if (selectedIds.size === 0) return;
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await axios.post('/api/gmail/meetings/bulk-cancel', 
        { lead_ids: Array.from(selectedIds) },
        { headers: { 'X-User-Id': userId } }
      );
      setSelectedIds(new Set());
      setShowBulkConfirm(false);
      await fetchMeetings();
    } catch (error) {
      console.error('Error bulk cancelling:', error);
      alert('Failed to cancel meetings. Please try again.');
    }
  };

  const handleReschedule = async () => {
    if (!newMeetingDate || !rescheduleMeeting) return;
    setIsRescheduling(true);
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await axios.post(`/api/gmail/reschedule/${rescheduleMeeting.id}`, 
        { new_time: newMeetingDate.toISOString() },
        { headers: { 'X-User-Id': userId } }
      );
      await fetchMeetings();
      setRescheduleMeeting(null);
      setNewMeetingDate(null);
    } catch (error) {
      console.error('Error rescheduling:', error);
      alert('Failed to reschedule. Please try again.');
    } finally {
      setIsRescheduling(false);
    }
  };

  const formatIST = (dateStr) => {
    if (!dateStr) return { date: '—', time: '—' };
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return { date: dateStr, time: '' };
      const date = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
      const time = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
      return { date, time };
    } catch { return { date: dateStr, time: '' }; }
  };

  const getNextCallTime = () => {
    if (!filteredMeetings[0]) return 'None';
    const ist = formatIST(filteredMeetings[0].meeting_time);
    return ist.time;
  };

  const toggleDropdown = (id) => {
    setDropdownOpen(dropdownOpen === id ? null : id);
  };

  return (
    <div className="min-h-screen bg-[#06080f] text-slate-200 selection:bg-blue-500/30">
      {/* Background Decorative Elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-blue-600/5 blur-[120px] rounded-full"></div>
        <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-indigo-600/5 blur-[120px] rounded-full"></div>
      </div>

      <div className="max-w-[1400px] mx-auto p-4 lg:p-8 relative z-10">
        
        {/* Header Section: God Mode Style */}
        <div className="flex flex-col lg:flex-row lg:items-end justify-between mb-12 gap-6">
          <div className="space-y-1">
            <div className="flex items-center gap-4 mb-3">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center border border-blue-500/20 shadow-[0_0_20px_rgba(59,130,246,0.1)]">
                <Layers className="w-8 h-8 text-blue-400" />
              </div>
              <div>
                <h1 className="text-4xl font-black tracking-tight text-white uppercase italic leading-none">
                  STRATEGY <span className="text-blue-500">MEETINGS</span>
                </h1>
                <p className="text-blue-400/60 text-[10px] font-black uppercase tracking-[0.3em] mt-1">Calendar Intelligence Hub</p>
              </div>
            </div>
            <p className="text-slate-500 text-sm font-medium border-l-2 border-blue-500/30 pl-4">Orchestrating high-intent strategy sessions with precision.</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative group">
              <div className="absolute inset-0 bg-blue-500/10 blur-xl opacity-0 group-focus-within:opacity-100 transition-opacity"></div>
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-blue-400 transition-colors z-10" />
              <input 
                type="text" 
                placeholder="Find session..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900/40 backdrop-blur-md border border-slate-800 rounded-2xl py-3 pl-12 pr-6 text-sm w-full lg:w-80 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/40 transition-all placeholder:text-slate-600 relative z-10"
              />
            </div>
            <button className="p-3 bg-slate-900/40 backdrop-blur-md border border-slate-800 rounded-2xl hover:bg-slate-800 transition-all hover:border-slate-700 active:scale-95">
              <Filter className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Stats Grid: Premium Glassmorphism */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
          {[
            { label: 'Upcoming Sessions', value: meetings.length, color: 'blue', icon: Clock, trend: '+12% from last week' },
            { label: 'Active Pipeline', value: filteredMeetings.length, color: 'emerald', icon: CheckCircle2, trend: 'High Conversion Potential' },
            { label: 'Next Engagement', value: getNextCallTime(), color: 'indigo', icon: CalendarIcon, trend: 'Synchronized with IST' }
          ].map((stat, i) => (
            <div key={i} className="bg-slate-900/30 backdrop-blur-md border border-slate-800/50 p-6 rounded-3xl relative overflow-hidden group hover:border-blue-500/30 transition-all duration-500">
              <div className={`absolute top-0 right-0 w-32 h-32 bg-${stat.color}-500/5 rounded-full -mr-12 -mt-12 group-hover:scale-150 transition-transform duration-700 blur-2xl`}></div>
              <div className="flex items-start justify-between relative z-10 mb-4">
                <div className={`p-2.5 rounded-xl bg-${stat.color}-500/10 border border-${stat.color}-500/20`}>
                  <stat.icon className={`w-5 h-5 text-${stat.color}-400`} />
                </div>
                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">{stat.trend}</div>
              </div>
              <div className="relative z-10">
                <p className="text-slate-400 text-[10px] uppercase font-black tracking-widest mb-1">{stat.label}</p>
                <p className="text-3xl font-black text-white">{stat.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Floating Bulk Action Bar */}
        {selectedIds.size > 0 && (
          <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-6 px-8 py-4 bg-slate-900/90 backdrop-blur-2xl border border-blue-500/30 rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] animate-in fade-in slide-in-from-bottom-10 duration-500">
            <div className="flex items-center gap-3 pr-6 border-r border-slate-800">
              <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs font-black shadow-[0_0_15px_rgba(59,130,246,0.5)]">
                {selectedIds.size}
              </div>
              <p className="text-sm font-bold text-white uppercase tracking-tighter">Sessions Selected</p>
            </div>
            <div className="flex items-center gap-3">
              <button 
                onClick={() => setShowBulkConfirm(true)}
                className="flex items-center gap-2 px-6 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 rounded-xl text-red-400 text-xs font-black uppercase tracking-widest transition-all hover:scale-105 active:scale-95"
              >
                <Trash2 className="w-4 h-4" /> Cancel Selected
              </button>
              <button 
                onClick={() => setSelectedIds(new Set())}
                className="p-2.5 hover:bg-slate-800 rounded-xl text-slate-500 hover:text-white transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        {/* Meetings List Table */}
        <div className="bg-slate-900/20 backdrop-blur-md border border-slate-800/50 rounded-[2.5rem] overflow-hidden shadow-2xl">
          <div className="p-8 border-b border-slate-800/50 flex items-center justify-between bg-slate-950/20">
            <div className="flex items-center gap-3">
              <div className="w-1.5 h-8 bg-blue-500 rounded-full shadow-[0_0_10px_rgba(59,130,246,0.5)]"></div>
              <h3 className="text-sm font-black text-white uppercase tracking-[0.2em] flex items-center gap-2">
                Operational Timeline
              </h3>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]"></div>
                <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Global Sync Active</span>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-950/40 border-b border-slate-800/50">
                  <th className="p-6 w-12">
                    <button 
                      onClick={toggleSelectAll}
                      className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center cursor-pointer ${
                        selectedIds.size === filteredMeetings.length && filteredMeetings.length > 0
                          ? 'bg-blue-600 border-blue-600' 
                          : 'border-slate-700 hover:border-blue-500'
                      }`}
                    >
                      {selectedIds.size === filteredMeetings.length && filteredMeetings.length > 0 && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                    </button>
                  </th>
                  <th className="p-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Asset Identity</th>
                  <th className="p-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] text-center">Temporal Coordinates</th>
                  <th className="p-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em]">Conference Protocol</th>
                  <th className="p-6 text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] text-right">Directives</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/30">
                {loading ? (
                  <tr>
                    <td colSpan="5" className="p-32 text-center">
                      <div className="relative w-16 h-16 mx-auto mb-6">
                        <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full"></div>
                        <div className="absolute inset-0 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                      </div>
                      <p className="text-slate-400 text-xs font-black uppercase tracking-[0.3em] animate-pulse">Initializing Data Stream...</p>
                    </td>
                  </tr>
                ) : filteredMeetings.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="p-32 text-center">
                      <div className="w-20 h-20 bg-slate-900/50 rounded-[2rem] flex items-center justify-center mx-auto mb-6 border border-slate-800 shadow-inner">
                        <CalendarIcon className="w-8 h-8 text-slate-700" />
                      </div>
                      <h4 className="text-white text-xl font-black uppercase italic tracking-tight">Zero Sessions Detected</h4>
                      <p className="text-slate-500 text-sm mt-2 max-w-xs mx-auto">Standby for inbound high-intent leads to synchronize with your calendar.</p>
                    </td>
                  </tr>
                ) : (
                  filteredMeetings.map((meeting) => (
                    <tr 
                      key={meeting.id} 
                      className={`group transition-all duration-300 ${
                        selectedIds.has(meeting.id) 
                          ? 'bg-blue-600/5' 
                          : 'hover:bg-slate-800/20'
                      }`}
                    >
                      <td className="p-6">
                        <button 
                          onClick={() => toggleSelect(meeting.id)}
                          className={`w-5 h-5 rounded-md border-2 transition-all flex items-center justify-center cursor-pointer ${
                            selectedIds.has(meeting.id)
                              ? 'bg-blue-600 border-blue-600 shadow-[0_0_10px_rgba(59,130,246,0.3)]' 
                              : 'border-slate-800 group-hover:border-slate-600'
                          }`}
                        >
                          {selectedIds.has(meeting.id) && <CheckCircle2 className="w-3.5 h-3.5 text-white" />}
                        </button>
                      </td>
                      <td className="p-6 cursor-pointer" onClick={() => setSelectedMeeting(meeting)}>
                        <div className="flex items-center gap-4">
                          <div className="relative">
                            <div className="absolute inset-0 bg-blue-500/20 blur-md opacity-0 group-hover:opacity-100 transition-opacity rounded-full"></div>
                            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-slate-800 to-slate-900 flex items-center justify-center border border-white/5 text-blue-400 font-black text-base shadow-xl relative z-10 group-hover:scale-110 transition-transform">
                              {meeting.lead_name?.charAt(0) || <User className="w-5 h-5" />}
                            </div>
                          </div>
                          <div>
                            <p className="text-white font-black text-sm uppercase tracking-tight group-hover:text-blue-400 transition-colors">{meeting.lead_name || 'Anonymous Alpha'}</p>
                            <p className="text-slate-500 text-[10px] font-black uppercase tracking-widest mt-0.5">{meeting.company_name || 'Venture Entity'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-6">
                        {(() => {
                          const ist = formatIST(meeting.meeting_time);
                          return (
                            <div className="flex flex-col items-center">
                              <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full mb-2">
                                <p className="text-[9px] font-black text-blue-400 uppercase tracking-widest">
                                  {ist.date}
                                </p>
                              </div>
                              <div className="flex items-center gap-2 px-4 py-1.5 bg-slate-950/50 rounded-xl border border-slate-800 shadow-inner">
                                <Clock className="w-3.5 h-3.5 text-slate-500" />
                                <p className="text-xs font-black text-white uppercase italic tracking-tighter">
                                  {ist.time} <span className="text-blue-500">IST</span>
                                </p>
                              </div>
                            </div>
                          );
                        })()}
                      </td>
                      <td className="p-6">
                        {meeting.meeting_link ? (
                          <div className="flex items-center gap-4 group/meet">
                            <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20 group-hover/meet:scale-110 transition-transform">
                              <Video className="w-5 h-5 text-emerald-400" />
                            </div>
                            <a 
                              href={meeting.meeting_link} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="group flex flex-col cursor-pointer"
                            >
                              <span className="text-[10px] font-black text-emerald-400 group-hover:text-emerald-300 transition-colors uppercase tracking-[0.2em]">Secure Link</span>
                              <span className="text-[9px] font-bold text-slate-600 uppercase flex items-center gap-1 group-hover:text-slate-400">Join Protocol <ArrowUpRight className="w-2.5 h-2.5" /></span>
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-4 opacity-30 grayscale">
                            <div className="w-10 h-10 rounded-xl bg-slate-800 flex items-center justify-center border border-slate-700">
                              <Video className="w-5 h-5 text-slate-500" />
                            </div>
                            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.2em] italic">Encryption Pending</p>
                          </div>
                        )}
                      </td>
                      <td className="p-6 text-right relative">
                        <div className="flex items-center justify-end gap-3">
                          <button 
                            onClick={(e) => { e.stopPropagation(); setRescheduleMeeting(meeting); }}
                            className="px-4 py-2 bg-blue-600/10 hover:bg-blue-600 border border-blue-500/20 hover:border-blue-500 text-blue-400 hover:text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all active:scale-95 cursor-pointer shadow-lg"
                          >
                            Reschedule
                          </button>
                          <div className="relative">
                            <button 
                              onClick={(e) => { e.stopPropagation(); toggleDropdown(meeting.id); }}
                              className="p-2.5 bg-slate-900/50 hover:bg-slate-800 rounded-xl border border-slate-800 transition-all cursor-pointer group/more"
                            >
                              <MoreVertical className="w-5 h-5 text-slate-500 group-hover/more:text-white transition-colors" />
                            </button>
                            {dropdownOpen === meeting.id && (
                              <div className="absolute right-0 top-full mt-2 w-56 bg-[#0f121d]/95 backdrop-blur-2xl border border-slate-800 rounded-2xl shadow-[0_20px_50px_rgba(0,0,0,0.5)] py-2 z-[60] overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                                <button className="w-full text-left px-5 py-3 text-[10px] font-black uppercase tracking-widest text-slate-400 hover:bg-blue-500/10 hover:text-blue-400 transition-all flex items-center justify-between group/item" onClick={(e) => { e.stopPropagation(); setSelectedMeeting(meeting); setDropdownOpen(null); }}>
                                  View Meta Data <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover/item:opacity-100 -translate-x-2 group-hover:translate-x-0 transition-all" />
                                </button>
                                <div className="h-px bg-slate-800/50 my-1"></div>
                                <button 
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedIds(new Set([meeting.id]));
                                    setShowBulkConfirm(true);
                                    setDropdownOpen(null);
                                  }}
                                  className="w-full text-left px-5 py-3 text-[10px] font-black uppercase tracking-widest text-red-500/70 hover:bg-red-500/10 hover:text-red-400 transition-all flex items-center justify-between group/item"
                                >
                                  Terminate Session <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          
          <div className="p-8 bg-slate-950/40 border-t border-slate-800/50 flex justify-between items-center">
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-[0.3em]">
              Showing {filteredMeetings.length} strategy units
            </p>
            <div className="flex items-center gap-3">
               <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Authorized Access Only</span>
               <div className="w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_10px_rgba(59,130,246,1)]"></div>
            </div>
          </div>
        </div>
      </div>

      {/* Confirmation Modal for Bulk Action */}
      {showBulkConfirm && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-md p-4">
          <div className="bg-[#131722] border border-red-500/20 rounded-[2.5rem] w-full max-w-md shadow-[0_30px_100px_rgba(239,68,68,0.15)] relative overflow-hidden p-8 text-center space-y-6 animate-in zoom-in-95 duration-300">
            <div className="w-20 h-20 bg-red-500/10 rounded-full flex items-center justify-center mx-auto border border-red-500/20 shadow-[0_0_30px_rgba(239,68,68,0.1)]">
              <AlertCircle className="w-10 h-10 text-red-500" />
            </div>
            <div className="space-y-2">
              <h3 className="text-2xl font-black text-white uppercase italic tracking-tighter">Terminate Protocol?</h3>
              <p className="text-slate-500 text-sm font-medium">You are about to cancel {selectedIds.size} session(s). This action will clear the calendar data and cannot be undone.</p>
            </div>
            <div className="flex gap-4 pt-4">
              <button 
                onClick={() => { setShowBulkConfirm(false); setSelectedIds(new Set()); }}
                className="flex-1 px-6 py-4 bg-slate-900 border border-slate-800 rounded-2xl text-slate-400 text-xs font-black uppercase tracking-widest hover:bg-slate-800 transition-all cursor-pointer"
              >
                Aborted
              </button>
              <button 
                onClick={handleBulkCancel}
                className="flex-1 px-6 py-4 bg-red-600 hover:bg-red-500 text-white text-xs font-black uppercase tracking-widest rounded-2xl shadow-[0_10px_20px_rgba(239,68,68,0.2)] transition-all hover:scale-105 active:scale-95 cursor-pointer"
              >
                Confirm Deletion
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Lead Details Modal: Premium Layout */}
      {selectedMeeting && (
        <div className="fixed inset-0 z-[150] flex items-center justify-center bg-black/90 backdrop-blur-xl p-4 animate-in fade-in duration-300">
          <div className="bg-[#0f121d] border border-slate-800/50 rounded-[3rem] w-full max-w-2xl shadow-[0_50px_100px_rgba(0,0,0,0.7)] relative overflow-hidden flex flex-col md:flex-row h-auto max-h-[90vh]">
            {/* Left Decorative Sidebar */}
            <div className="w-full md:w-48 bg-gradient-to-b from-blue-600/10 to-indigo-600/10 border-r border-slate-800/50 p-8 flex flex-col items-center justify-center gap-6 relative">
               <div className="absolute top-0 left-0 w-full h-full opacity-10 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-from)_0%,_transparent_70%)] from-blue-500"></div>
               <div className="w-24 h-24 rounded-[2rem] bg-slate-900 border border-white/5 flex items-center justify-center text-blue-400 font-black text-3xl shadow-2xl relative z-10">
                  {selectedMeeting.lead_name?.charAt(0) || <User className="w-8 h-8" />}
               </div>
               <div className="text-center relative z-10">
                  <div className="text-[10px] font-black text-blue-400/60 uppercase tracking-[0.3em] mb-1">Status</div>
                  <div className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-400 uppercase tracking-widest">Synchronized</div>
               </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 p-10 space-y-8 overflow-y-auto">
              <div className="flex justify-between items-start">
                <div>
                  <h4 className="text-3xl font-black text-white uppercase italic tracking-tight">{selectedMeeting.lead_name || 'Anonymous Alpha'}</h4>
                  <p className="text-blue-500 font-black text-[10px] uppercase tracking-[0.2em] mt-1">{selectedMeeting.company_name || 'Venture Entity'}</p>
                </div>
                <button onClick={() => setSelectedMeeting(null)} className="p-3 hover:bg-slate-800 rounded-2xl text-slate-500 hover:text-white transition-all cursor-pointer">
                  <X className="w-6 h-6" />
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
                <div className="space-y-6">
                  <div>
                    <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] mb-2">Primary Contact</p>
                    <p className="text-sm font-bold text-slate-300 flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                      {selectedMeeting.lead_email || 'Secured'}
                    </p>
                  </div>
                  {selectedMeeting.phone && (
                    <div>
                      <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] mb-2">Comms Line</p>
                      <p className="text-sm font-bold text-slate-300 flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                        {selectedMeeting.phone}
                      </p>
                    </div>
                  )}
                </div>
                <div className="space-y-6">
                   {selectedMeeting.linkedin_url && (
                    <div>
                      <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] mb-2">Professional Pulse</p>
                      <a href={selectedMeeting.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-3 px-4 py-2 bg-blue-500/10 border border-blue-500/20 rounded-xl text-blue-400 text-xs font-black uppercase tracking-widest hover:bg-blue-500 hover:text-white transition-all group/link cursor-pointer">
                         Explore Profile <ExternalLink className="w-3.5 h-3.5 group-hover/link:translate-x-0.5 group-hover/link:-translate-y-0.5 transition-transform" />
                      </a>
                    </div>
                  )}
                  {selectedMeeting.persona && (
                    <div>
                      <p className="text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] mb-2">Entity Persona</p>
                      <p className="text-[10px] font-black text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 rounded-lg inline-block uppercase tracking-[0.2em]">{selectedMeeting.persona}</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="pt-8 border-t border-slate-800/50 flex gap-4">
                 {selectedMeeting.meeting_link && (
                    <a href={selectedMeeting.meeting_link} target="_blank" rel="noopener noreferrer" className="flex-1 flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-[0.2em] text-xs py-5 rounded-2xl transition-all shadow-[0_15px_30px_rgba(59,130,246,0.3)] hover:-translate-y-1 cursor-pointer">
                      Enter War Room <ArrowUpRight className="w-4 h-4" />
                    </a>
                 )}
                 <button onClick={() => setSelectedMeeting(null)} className="flex-1 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-white font-black uppercase tracking-[0.2em] text-xs py-5 rounded-2xl transition-all cursor-pointer">
                    Dismiss Meta
                 </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Reschedule Modal: God Mode Refinement */}
      {rescheduleMeeting && (
        <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/90 backdrop-blur-md p-4 animate-in fade-in zoom-in-95 duration-200">
          <div className="bg-[#131722] border border-blue-500/30 rounded-[2.5rem] w-full max-w-[500px] shadow-2xl p-8 space-y-8">
            <div className="text-center space-y-2">
              <div className="w-16 h-16 bg-blue-500/10 rounded-2xl flex items-center justify-center mx-auto border border-blue-500/20 mb-4">
                <Clock className="w-8 h-8 text-blue-400" />
              </div>
              <h3 className="text-xl font-black text-white uppercase italic tracking-tight">Time Distortion</h3>
              <p className="text-xs text-slate-500 font-medium">Re-allocating temporal slot for {rescheduleMeeting.lead_name}</p>
            </div>
            <div className="space-y-4">
              <div className="relative group">
                <label className="block text-[10px] font-black text-slate-600 uppercase tracking-[0.2em] mb-3">Target Coordinate (Local Time)</label>
                <div className="relative">
                  <DatePicker
                    ref={datePickerRef}
                    selected={newMeetingDate}
                    onChange={(date) => setNewMeetingDate(date)}
                    showTimeSelect
                    timeFormat="HH:mm"
                    timeIntervals={15}
                    timeCaption="time"
                    dateFormat="MMMM d, yyyy h:mm aa"
                    className="w-full bg-slate-950 border border-slate-800 rounded-2xl px-5 py-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500/40 transition-all cursor-pointer shadow-inner"
                    placeholderText="Select Date & Time"
                    popperPlacement="bottom-start"
                    popperModifiers={[
                      {
                        name: "flip",
                        options: {
                          fallbackPlacements: [],
                          flipVariations: false,
                          allowedAutoPlacements: [],
                        },
                      },
                    ]}
                  >
                    <div className="p-3 border-t border-slate-800 bg-slate-900 flex justify-center">
                      <button
                        onClick={() => datePickerRef.current?.setOpen(false)}
                        className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all shadow-[0_0_15px_rgba(59,130,246,0.4)]"
                      >
                        OK
                      </button>
                    </div>
                  </DatePicker>
                </div>
              </div>
              <div className="flex gap-4 pt-4">
                 <button 
                    onClick={() => { setRescheduleMeeting(null); setNewMeetingDate(null); }} 
                    className="flex-1 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-400 font-black uppercase tracking-widest text-[10px] py-4 rounded-2xl transition-all cursor-pointer"
                 >
                    Abort
                 </button>
                 <button 
                    onClick={handleReschedule} 
                    disabled={isRescheduling || !newMeetingDate}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-[10px] py-4 rounded-2xl transition-all shadow-[0_10px_20px_rgba(59,130,246,0.2)] hover:scale-105 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed flex items-center justify-center gap-2 cursor-pointer"
                 >
                    {isRescheduling ? 'Rescheduling...' : 'Confirm Update'}
                 </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Meetings;
