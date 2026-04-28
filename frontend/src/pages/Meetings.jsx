import React, { useState, useEffect } from 'react';
import axios from '../services/api';
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
  CalendarDays
} from 'lucide-react';

const Meetings = () => {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMeeting, setSelectedMeeting] = useState(null);
  
  // Reschedule state
  const [rescheduleMeeting, setRescheduleMeeting] = useState(null);
  const [newMeetingTime, setNewMeetingTime] = useState('');
  const [isRescheduling, setIsRescheduling] = useState(false);
  
  // Dropdown state
  const [dropdownOpen, setDropdownOpen] = useState(null);

  useEffect(() => {
    fetchMeetings();
  }, []);

  const fetchMeetings = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      // Use standard axios instance which likely has baseURL configured
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

  const handleReschedule = async () => {
    if (!newMeetingTime || !rescheduleMeeting) return;
    setIsRescheduling(true);
    try {
      const user = JSON.parse(localStorage.getItem('user') || '{}');
      const userId = user.id || 'admin';
      await axios.post(`/api/gmail/reschedule/${rescheduleMeeting.id}`, 
        { new_time: new Date(newMeetingTime).toISOString() },
        { headers: { 'X-User-Id': userId } }
      );
      // Refresh list
      await fetchMeetings();
      setRescheduleMeeting(null);
      setNewMeetingTime('');
    } catch (error) {
      console.error('Error rescheduling:', error);
      alert('Failed to reschedule. Please try again.');
    } finally {
      setIsRescheduling(false);
    }
  };

  // Format date to IST helper
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
    <div className="min-h-screen bg-[#06080f] text-slate-200">
      <div className="max-w-[1400px] mx-auto p-4 lg:p-8">
        
        {/* Header Section */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8 gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20">
                <CalendarDays className="w-6 h-6 text-blue-400" />
              </div>
              <h1 className="text-3xl font-black tracking-tight text-white uppercase italic">
                Deal <span className="text-blue-500">Calendar</span>
              </h1>
            </div>
            <p className="text-slate-500 text-sm font-medium">Tracking all inbound meeting requests and scheduled strategy calls.</p>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative group">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-blue-400 transition-colors" />
              <input 
                type="text" 
                placeholder="Search attendees or companies..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900/50 border border-slate-800 rounded-xl py-2.5 pl-10 pr-4 text-sm w-full lg:w-72 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/50 transition-all placeholder:text-slate-600"
              />
            </div>
            <button className="p-2.5 bg-slate-900/50 border border-slate-800 rounded-xl hover:bg-slate-800 transition-colors">
              <Filter className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Upcoming Meetings', value: filteredMeetings.length, color: 'blue', icon: Clock },
            { label: 'Potential Deals', value: filteredMeetings.length, color: 'emerald', icon: CheckCircle2 },
            { label: 'Next Call (IST)', value: getNextCallTime(), color: 'indigo', icon: CalendarIcon }
          ].map((stat, i) => (
            <div key={i} className="bg-slate-900/40 border border-slate-800/50 p-5 rounded-2xl relative overflow-hidden group">
              <div className={`absolute top-0 right-0 w-24 h-24 bg-${stat.color}-500/5 rounded-full -mr-8 -mt-8 group-hover:scale-150 transition-transform duration-700`}></div>
              <div className="flex items-start justify-between relative z-10">
                <div>
                  <p className="text-slate-500 text-[10px] uppercase font-black tracking-widest mb-1">{stat.label}</p>
                  <p className="text-2xl font-black text-white">{stat.value}</p>
                </div>
                <stat.icon className={`w-5 h-5 text-${stat.color}-400/60`} />
              </div>
            </div>
          ))}
        </div>

        {/* Meetings List */}
        <div className="bg-slate-900/30 border border-slate-800/50 rounded-2xl backdrop-blur-xl">
          <div className="p-6 border-b border-slate-800/50 flex items-center justify-between bg-slate-900/20 rounded-t-2xl">
            <h3 className="text-sm font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
              <Clock className="w-4 h-4 text-blue-500" />
              Schedule Timeline
            </h3>
            <span className="text-[10px] font-bold text-slate-500 bg-slate-800/50 px-2 py-1 rounded uppercase">Auto-Synced</span>
          </div>

          <div className="">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-slate-950/50 border-b border-slate-800/50">
                  <th className="p-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Lead Identity</th>
                  <th className="p-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Time & Date</th>
                  <th className="p-4 text-[10px] font-black text-slate-500 uppercase tracking-widest">Conference</th>
                  <th className="p-4 text-[10px] font-black text-slate-500 uppercase tracking-widest text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan="4" className="p-20 text-center">
                      <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
                      <p className="text-slate-500 text-sm font-medium animate-pulse uppercase tracking-widest">Accessing Google Calendar...</p>
                    </td>
                  </tr>
                ) : filteredMeetings.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="p-20 text-center">
                      <div className="w-16 h-16 bg-slate-900/50 rounded-full flex items-center justify-center mx-auto mb-4 border border-slate-800">
                        <CalendarIcon className="w-8 h-8 text-slate-700" />
                      </div>
                      <p className="text-slate-400 text-lg font-bold">No High-Intent Meetings Found</p>
                      <p className="text-slate-600 text-sm mt-1">Once a lead requests a meeting, it will appear here automatically.</p>
                    </td>
                  </tr>
                ) : (
                  filteredMeetings.map((meeting) => (
                    <tr key={meeting.id} className="border-b border-slate-800/30 hover:bg-slate-800/20 transition-colors group">
                      <td className="p-4 cursor-pointer" onClick={() => setSelectedMeeting(meeting)}>
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center border border-white/5 text-blue-400 font-bold text-sm shadow-lg">
                            {meeting.lead_name?.charAt(0) || <User className="w-4 h-4" />}
                          </div>
                          <div>
                            <p className="text-white font-bold text-sm group-hover:text-blue-400 transition-colors">{meeting.lead_name || 'Individual Prospect'}</p>
                            <p className="text-slate-500 text-xs font-medium">{meeting.company_name || 'Verified Company'}</p>
                          </div>
                        </div>
                      </td>
                      <td className="p-4">
                        {(() => {
                          const ist = formatIST(meeting.meeting_time);
                          return (
                            <div className="flex flex-col items-center">
                              <p className="text-[11px] font-black text-blue-500 uppercase tracking-tighter mb-1">
                                {ist.date}
                              </p>
                              <div className="flex items-center gap-2 px-3 py-1 bg-slate-900/50 rounded-lg border border-slate-800">
                                <Clock className="w-3 h-3 text-slate-500" />
                                <p className="text-xs font-bold text-white uppercase italic">
                                  {ist.time} IST
                                </p>
                              </div>
                            </div>
                          );
                        })()}
                      </td>
                      <td className="p-4">
                        {meeting.meeting_link ? (
                          <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 flex items-center justify-center border border-emerald-500/20">
                              <Video className="w-4 h-4 text-emerald-400" />
                            </div>
                            <a 
                              href={meeting.meeting_link} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-[10px] font-black text-emerald-400 hover:text-emerald-300 transition-colors uppercase tracking-widest flex items-center gap-1"
                            >
                              Join Meet <ChevronRight className="w-3 h-3" />
                            </a>
                          </div>
                        ) : (
                          <div className="flex items-center gap-3 opacity-40">
                            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-slate-700">
                              <Video className="w-4 h-4 text-slate-500" />
                            </div>
                            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest italic">Link Pending</p>
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-right relative">
                        <div className="flex items-center justify-end gap-2">
                          <button 
                            onClick={(e) => { e.stopPropagation(); setRescheduleMeeting(meeting); }}
                            className="px-3 py-1.5 bg-slate-800/50 hover:bg-slate-700 text-slate-300 text-[10px] font-black uppercase tracking-widest rounded-lg border border-slate-700 transition-all cursor-pointer"
                          >
                            Reschedule
                          </button>
                          <div className="relative">
                            <button 
                              onClick={(e) => { e.stopPropagation(); toggleDropdown(meeting.id); }}
                              className="p-1.5 bg-slate-800/50 hover:bg-slate-700 group/cancel rounded-lg border border-slate-700 transition-all cursor-pointer"
                            >
                              <MoreVertical className="w-4 h-4 text-slate-500 group-hover/cancel:text-slate-300" />
                            </button>
                            {dropdownOpen === meeting.id && (
                              <div className="absolute right-0 bottom-full mb-2 w-48 bg-[#0f121d] border border-slate-800 rounded-xl shadow-2xl py-2 z-20">
                                <button className="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-800/50 hover:text-white transition-colors cursor-pointer" onClick={(e) => { e.stopPropagation(); setSelectedMeeting(meeting); setDropdownOpen(null); }}>
                                  View Full Details
                                </button>
                                <button className="w-full text-left px-4 py-2 text-xs font-bold text-slate-300 hover:bg-slate-800/50 hover:text-white transition-colors cursor-pointer">
                                  Send Reminder
                                </button>
                                <div className="h-px bg-slate-800/50 my-1"></div>
                                <button className="w-full text-left px-4 py-2 text-xs font-bold text-red-400 hover:bg-red-500/10 transition-colors cursor-pointer">
                                  Cancel Meeting
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
          
          <div className="p-4 bg-slate-950/50 border-t border-slate-800/50 flex justify-between items-center rounded-b-2xl">
            <p className="text-[10px] font-bold text-slate-600 uppercase tracking-widest">
              Showing {filteredMeetings.length} strategy sessions
            </p>
            <div className="flex items-center gap-2">
               <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
               <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Live Sync Active</span>
            </div>
          </div>
        </div>
      </div>

      {/* Lead Details Modal */}
      {selectedMeeting && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#131722] border border-slate-800 rounded-3xl w-full max-w-md shadow-2xl relative overflow-hidden">
            <div className="p-6 border-b border-slate-800/50 flex items-center justify-between">
              <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-2">
                <User className="w-4 h-4 text-blue-500" /> Lead Details
              </h3>
              <button onClick={() => setSelectedMeeting(null)} className="text-slate-500 hover:text-white cursor-pointer transition-colors">
                 <MoreVertical className="w-5 h-5 opacity-0" /> {/* Placeholder to balance layout */}
                 <span className="absolute top-6 right-6 font-bold cursor-pointer hover:text-red-400 text-slate-400">✕</span>
              </button>
            </div>
            <div className="p-6 space-y-5">
              <div className="flex items-center gap-4">
                 <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 flex items-center justify-center border border-white/5 text-blue-400 font-black text-xl shadow-lg">
                    {selectedMeeting.lead_name?.charAt(0) || <User className="w-6 h-6" />}
                 </div>
                 <div>
                    <h4 className="text-xl font-black text-white">{selectedMeeting.lead_name || 'Individual Prospect'}</h4>
                    <p className="text-slate-400 text-sm font-bold">{selectedMeeting.company_name || 'Verified Company'}</p>
                 </div>
              </div>
              <div className="bg-slate-900/50 rounded-xl p-4 border border-slate-800 space-y-3">
                 <div>
                   <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Email</p>
                   <p className="text-sm font-bold text-slate-300">{selectedMeeting.lead_email || 'No email provided'}</p>
                 </div>
                 {selectedMeeting.linkedin_url && (
                   <div>
                     <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">LinkedIn</p>
                     <a href={selectedMeeting.linkedin_url} target="_blank" rel="noopener noreferrer" className="text-sm font-bold text-blue-400 hover:text-blue-300 hover:underline flex items-center gap-1 cursor-pointer">
                        View Profile <ExternalLink className="w-3 h-3" />
                     </a>
                   </div>
                 )}
                 {selectedMeeting.phone && (
                    <div>
                     <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Phone</p>
                     <p className="text-sm font-bold text-slate-300">{selectedMeeting.phone}</p>
                   </div>
                 )}
                 {selectedMeeting.persona && (
                    <div>
                     <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Persona</p>
                     <p className="text-xs font-black text-indigo-400 bg-indigo-500/10 px-2 py-1 rounded inline-block uppercase tracking-widest">{selectedMeeting.persona}</p>
                   </div>
                 )}
              </div>
              <div className="flex gap-3 pt-2">
                 {selectedMeeting.meeting_link && (
                    <a href={selectedMeeting.meeting_link} target="_blank" rel="noopener noreferrer" className="flex-1 text-center bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-xs py-3 rounded-xl transition-colors cursor-pointer">
                      Join Meeting
                    </a>
                 )}
                 <button onClick={() => setSelectedMeeting(null)} className="flex-1 bg-slate-800 hover:bg-slate-700 text-white font-black uppercase tracking-widest text-xs py-3 rounded-xl transition-colors cursor-pointer border border-slate-700">
                    Close
                 </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {/* Reschedule Modal */}
      {rescheduleMeeting && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-[#131722] border border-slate-800 rounded-3xl w-full max-w-sm shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="p-6 border-b border-slate-800/50">
              <h3 className="text-sm font-black text-white uppercase tracking-widest">Reschedule Meeting</h3>
              <p className="text-xs text-slate-500 mt-1">Select a new date and time for {rescheduleMeeting.lead_name}</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-[10px] font-black text-slate-500 uppercase tracking-widest mb-2">New Date & Time</label>
                <input 
                  type="datetime-local" 
                  value={newMeetingTime}
                  onChange={(e) => setNewMeetingTime(e.target.value)}
                  className="w-full bg-slate-900/50 border border-slate-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  style={{ colorScheme: 'dark' }}
                />
              </div>
              <div className="flex gap-3 pt-4">
                 <button 
                    onClick={() => { setRescheduleMeeting(null); setNewMeetingTime(''); }} 
                    className="flex-1 bg-slate-800 hover:bg-slate-700 text-white font-black uppercase tracking-widest text-xs py-3 rounded-xl transition-colors cursor-pointer border border-slate-700"
                 >
                    Cancel
                 </button>
                 <button 
                    onClick={handleReschedule} 
                    disabled={isRescheduling || !newMeetingTime}
                    className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-black uppercase tracking-widest text-xs py-3 rounded-xl transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                 >
                    {isRescheduling ? 'Saving...' : 'Confirm'}
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
