import React, { useState, useEffect } from 'react';
import { Mail, Loader2, RefreshCw, ExternalLink, Search, X, User, Send, ShieldAlert, Sparkles } from 'lucide-react';
import api from '../services/api';
import axios from 'axios'; // For direct auth calls

const GmailSent = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [msgDetail, setMsgDetail] = useState(null);
  const [error, setError] = useState(null);

  const decodeHtml = (html) => {
    const txt = document.createElement("textarea");
    txt.innerHTML = html;
    return txt.value;
  };

  // Format any date string to IST
  const formatIST = (dateStr) => {
    if (!dateStr) return 'Recently';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const datePart = d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
      const timePart = d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
      return `${datePart}, ${timePart} IST`;
    } catch { return dateStr; }
  };

  const fetchGmailSent = async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    else setIsRefreshing(true);
    
    try {
      setError(null);
      const res = await api.get(`/api/gmail/sync-sent${quiet ? '?refresh=true' : ''}`);
      if (Array.isArray(res.data)) {
        setMessages(res.data);
      } else {
        setMessages([]);
        if (res.data.error) setError(res.data.error);
      }
    } catch (err) {
      console.error('Failed to fetch Gmail sent messages:', err);
      setError('Connection failed. Please ensure your Google account is properly linked.');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const fetchMessageDetail = async (id) => {
    setIsDetailLoading(true);
    setMsgDetail(null);
    try {
      const res = await api.get(`/api/gmail/message/${id}`);
      setMsgDetail(res.data);
    } catch (err) {
      console.error('Failed to fetch message detail:', err);
    } finally {
      setIsDetailLoading(false);
    }
  };

  const handleUpgrade = async () => {
    try {
      const { data } = await api.get('/api/auth/google/link');
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      console.error('Failed to initiate Google link', err);
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('NUCLEAR RESET: This will completely wipe all Google tokens. Are you sure?')) return;
    try {
      await axios.post('/api/auth/google/disconnect', {}, { headers: { 'X-User-Id': localStorage.getItem('user_id') } });
      window.location.reload();
    } catch (err) {
      console.error('Failed to disconnect', err);
    }
  };

  const renderEmailContent = (content) => {
    if (!content) return null;
    
    // Detect if content is likely HTML
    const isHtml = /<[a-z][\s\S]*>/i.test(content);
    
    if (isHtml) {
      return <div className="email-html-content" dangerouslySetInnerHTML={{ __html: content }} />;
    }

    // Helper to render inline formatting like *bold*
    const renderLine = (text) => {
      const parts = text.split(/(\*[^*]+\*)/g);
      return parts.map((part, i) => {
        if (part.startsWith('*') && part.endsWith('*')) {
          return <strong key={i} className="font-black text-blue-400">{part.slice(1, -1)}</strong>;
        }
        return part;
      });
    };

    // Process plain text for quotes
    const lines = content.trim().split('\n');
    return lines.map((line, idx) => {
      const trimmedLine = line.trim();
      const isQuote = trimmedLine.startsWith('>');
      
      // Clean the line (remove the > arrow)
      let cleanLine = line;
      if (isQuote) {
        cleanLine = line.replace(/^\s*> ?/, '');
      }

      if (isQuote) {
        return (
          <div key={idx} className="pl-4 border-l-2 border-slate-700 text-slate-500 my-1 py-0.5">
            {renderLine(cleanLine)}
          </div>
        );
      }
      return <div key={idx} className="min-h-[1.5em]">{renderLine(cleanLine)}</div>;
    });
  };

  useEffect(() => {
    fetchGmailSent();
  }, []);

  const filteredMessages = messages.filter(m => 
    (m.subject || '').toLowerCase().includes(searchTerm.toLowerCase()) || 
    (m.to || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (m.snippet || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="animate-in fade-in duration-700">
      <div className="flex justify-between items-end mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-[28px] font-bold text-white tracking-tight">Sent Hub</h1>
            <div className="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-[9px] font-black text-emerald-500 uppercase tracking-widest">Gmail Connected</div>
          </div>
          <p className="text-[#64748b] text-[12px] font-medium">
            Complete history of dispatched outreach directly from your Gmail account.
          </p>
        </div>
        
        <button 
          onClick={() => fetchGmailSent(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[11px] font-bold text-white uppercase tracking-widest transition-all disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-emerald-400' : ''}`} />
          {isRefreshing ? 'Updating...' : 'Sync Sent Mails'}
        </button>
      </div>

      {/* Search Bar */}
      <div className="relative mb-8">
        <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
        <input 
          type="text" 
          placeholder="Search within sent history..." 
          className="w-full bg-[#131722] border border-white/5 rounded-[20px] py-4 pl-14 pr-6 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-emerald-500/30 focus:shadow-[0_0_20px_rgba(16,185,129,0.05)] transition-all"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="bg-[#131722] border border-[#ffffff08] rounded-[32px] overflow-hidden shadow-2xl relative">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-separate border-spacing-0">
            <thead>
              <tr className="bg-[#0f121b]/80 border-b border-[#ffffff08]">
                <th className="px-8 py-6 text-[10px] font-black text-[#64748b] uppercase tracking-[2px]">Recipient</th>
                <th className="px-8 py-6 text-[10px] font-black text-[#64748b] uppercase tracking-[2px]">Subject Line</th>
                <th className="px-8 py-6 text-[10px] font-black text-[#64748b] uppercase tracking-[2px]">Preview</th>
                <th className="px-8 py-6 text-[10px] font-black text-[#64748b] uppercase tracking-[2px]">Sent Date</th>
                <th className="px-8 py-6 text-[10px] font-black text-[#64748b] uppercase tracking-[2px] text-right">View</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ffffff08]">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="px-8 py-32 text-center">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-12 h-12 text-emerald-500 animate-spin" />
                        <p className="text-[11px] font-black text-slate-500 uppercase tracking-[4px]">Syncing Outbound Data...</p>
                    </div>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan="5" className="px-8 py-32 text-center text-red-400 font-bold uppercase tracking-[2px] text-[11px]">
                    {error}
                  </td>
                </tr>
              ) : filteredMessages.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-8 py-32 text-center text-[#64748b] font-bold uppercase tracking-[2px] text-[11px]">
                    No dispatched emails found. Try sending an outreach first!
                  </td>
                </tr>
              ) : (
                filteredMessages.map(msg => (
                  <tr 
                    key={msg.id} 
                    className="hover:bg-white/[0.02] transition-all group cursor-pointer"
                    onClick={() => { setSelectedMessage(msg); fetchMessageDetail(msg.id); }}
                  >
                    <td className="px-8 py-6">
                      <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-2xl bg-emerald-500/10 flex items-center justify-center text-emerald-400 font-black text-[12px] group-hover:scale-110 transition-transform">
                              <User className="w-5 h-5" />
                          </div>
                          <div>
                              <div className="text-[13px] font-bold text-white group-hover:text-emerald-400 transition-colors truncate max-w-[180px]">{msg.to || 'No Recipient'}</div>
                              <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter mt-0.5">Dispatched</div>
                          </div>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <div className="text-[13px] text-white font-bold tracking-tight mb-1">{decodeHtml(msg.subject || '(No Subject)')}</div>
                      <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-[8px] font-black text-emerald-500 uppercase tracking-tighter border border-emerald-500/20">Verified</span>
                      </div>
                    </td>
                    <td className="px-8 py-6">
                      <p className="text-[11px] text-[#94a3b8] font-medium line-clamp-1 max-w-[350px] italic">
                        "{decodeHtml(msg.snippet || 'No preview available.')}"
                      </p>
                    </td>
                    <td className="px-8 py-6">
                      <div className="flex flex-col">
                          <span className="text-[12px] font-black text-white">{formatIST(msg.date)}</span>

                      </div>
                    </td>
                    <td className="px-8 py-6 text-right">
                      <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/5 group-hover:bg-white/10 text-slate-400 group-hover:text-white rounded-xl text-[10px] font-black uppercase tracking-widest transition-all border border-transparent group-hover:border-white/10">
                        Read Mail
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Message View Modal */}
      {selectedMessage && (
        <div className="fixed inset-0 z-[5000] flex items-center justify-center p-6 bg-black/80 backdrop-blur-xl animate-in fade-in duration-300">
            <div className="w-full max-w-4xl bg-[#0b0f19] border border-white/10 rounded-[40px] overflow-hidden shadow-[0_0_100px_rgba(0,0,0,0.8)] flex flex-col max-h-[90vh]">
                <div className="p-8 border-b border-white/5 flex items-center justify-between bg-gradient-to-r from-emerald-500/10 to-transparent">
                    <div className="flex items-center gap-5">
                        <div className="w-14 h-14 rounded-2xl bg-emerald-500/20 flex items-center justify-center text-emerald-400">
                            <Send className="w-7 h-7" />
                        </div>
                        <div>
                            <h2 className="text-xl font-black text-white tracking-tight mb-1">{msgDetail?.subject || '(No Subject)'}</h2>
                            <p className="text-[11px] text-slate-400 font-bold uppercase tracking-widest flex items-center gap-2">
                                Sent To: <span className="text-emerald-400 lowercase font-medium">{msgDetail?.to || selectedMessage.to}</span>
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={() => fetchMessageDetail(selectedMessage.id)}
                            className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-400 hover:text-white active:scale-95 border border-white/5 cursor-pointer"
                        >
                            <RefreshCw size={20} className={isDetailLoading ? 'animate-spin' : ''} />
                        </button>
                        <button 
                            onClick={() => setSelectedMessage(null)}
                            className="p-3 bg-white/5 hover:bg-white/10 rounded-full text-slate-400 hover:text-white transition-all cursor-pointer"
                        >
                            <X className="w-6 h-6" />
                        </button>
                    </div>
                </div>
                
                <div className="flex-1 overflow-y-auto p-10 custom-scrollbar relative">
                    <div className="max-w-[800px] mx-auto">
                        <div className="flex items-center justify-between mb-8 pb-8 border-b border-white/5">
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-emerald-500 flex items-center justify-center text-white font-black text-xs">Y</div>
                                <div>
                                    <div className="text-[13px] font-bold text-white">Your Account</div>
                                    <div className="text-[10px] text-slate-500 font-medium">via Gmail API</div>
                                </div>
                            </div>
                            <div className="text-[11px] text-slate-500 font-bold uppercase tracking-widest tabular-nums">
                                <span className="text-[13px] font-black text-blue-400">{formatIST(msgDetail?.date || selectedMessage?.date)}</span>
                            </div>
                        </div>
                        
                        <div className="text-[10px] font-black text-emerald-500 uppercase tracking-[4px] mb-6 flex items-center gap-2">
                            <Sparkles size={12} className="animate-pulse" /> Outbound Intelligence
                        </div>

                        <div className="bg-[#0f172a] p-8 rounded-[32px] shadow-2xl overflow-hidden border border-white/5">
                            <div className="text-slate-300 whitespace-pre-wrap break-words text-[15px] leading-[1.8] font-sans email-content-container">
                                {renderEmailContent(msgDetail?.body)}
                            </div>
                            {!msgDetail?.body && (
                                <div className="text-slate-400 whitespace-pre-wrap break-words text-[14px] font-sans opacity-60 italic">{selectedMessage.snippet}</div>
                            )}
                        </div>

                        {msgDetail?.is_restricted && (
                          <div className="mt-8 p-6 bg-amber-500/10 border border-amber-500/20 rounded-3xl flex flex-col gap-5 shadow-2xl">
                              <div className="flex items-center gap-3">
                                  <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-500">
                                      <ShieldAlert size={20} />
                                  </div>
                                  <div className="text-[10px] font-black text-amber-200 uppercase tracking-widest leading-none">Security Restricted</div>
                              </div>
                              <p className="text-[12px] text-amber-200/60 leading-relaxed font-medium">
                                  Google is blocking the full sent body. You must grant "Full Intelligence" access to see complete outbound history.
                              </p>
                              <button 
                                  onClick={handleUpgrade}
                                  className="w-full py-4 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[10px] font-black uppercase tracking-[3px] rounded-2xl transition-all shadow-xl shadow-amber-500/20 active:scale-95 cursor-pointer"
                              >
                                  🚀 Fix Gmail Permissions Now
                              </button>
                          </div>
                        )}
                    </div>
                </div>

                <div className="p-8 bg-white/[0.02] border-t border-white/5 flex items-center justify-between">
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Sync Source: Gmail Outbound History</div>
                    <div className="flex items-center gap-4">
                        <button onClick={handleDisconnect} className="text-[9px] font-black text-rose-500 uppercase underline cursor-pointer">Nuclear Reset</button>
                        <a 
                          href={`https://mail.google.com/mail/u/0/#sent/${selectedMessage.id}`} 
                          target="_blank" 
                          rel="noreferrer"
                          className="px-6 py-3 bg-white/5 hover:bg-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-2xl transition-all border border-white/5 flex items-center gap-2 cursor-pointer"
                        >
                          View in Google <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                    </div>
                </div>
            </div>
        </div>
      )}
    </div>
  );
};

export default GmailSent;
