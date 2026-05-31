import React, { useState, useEffect } from 'react';
import api from '../services/api';
import { 
  Mail, MessageSquare, User, Clock, ArrowRight, 
  ExternalLink, RefreshCw, X, ChevronRight, 
  ShieldAlert, Sparkles, Search, Filter 
} from 'lucide-react';

const Inbox = () => {
    const [messages, setMessages] = useState([]);
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState({ total: 0, unread: 0 });
    const [selectedMsg, setSelectedMsg] = useState(null);
    const [msgDetail, setMsgDetail] = useState(null);
    const [loadingDetail, setLoadingDetail] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const [connected, setConnected] = useState(true);
    
    const decodeHtml = (html) => {
        const txt = document.createElement("textarea");
        txt.innerHTML = html;
        return txt.value;
    };

    // Format any date to IST (Indian Standard Time)
    const formatIST = (dateStr, showTime = true) => {
        if (!dateStr) return 'Recently';
        try {
            let cleanStr = dateStr;
            if (typeof cleanStr === 'string' && !cleanStr.endsWith('Z') && !cleanStr.includes('+') && !/-[0-9]{2}:[0-9]{2}$/.test(cleanStr)) {
                cleanStr = cleanStr.replace(' ', 'T') + 'Z';
            }
            const date = new Date(cleanStr);
            if (isNaN(date.getTime())) return dateStr;
            const opts = {
                timeZone: 'Asia/Kolkata',
                day: '2-digit',
                month: 'short',
                year: 'numeric',
                ...(showTime ? { hour: '2-digit', minute: '2-digit', hour12: true } : {})
            };
            return date.toLocaleString('en-IN', opts).replace(',', ' •');
        } catch { return dateStr; }
    };

    const renderClickableText = (text) => {
        if (!text) return text;
        const urlRegex = /(https?:\/\/[^\s]+)/g;
        return text.split(urlRegex).map((part, i) => {
            if (part.match(urlRegex)) {
                return <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:text-blue-400 underline decoration-blue-500/30 transition-colors cursor-pointer break-all">{part}</a>;
            }
            return part;
        });
    };

    const fetchInbox = async (isMounted = { current: true }, forceRefresh = false) => {
        setLoading(true);
        try {
            const { data } = await api.get(`/api/gmail/inbox${forceRefresh ? '?refresh=true' : ''}`);
            if (!isMounted.current) return;
            setMessages(data.messages || []);
            setConnected(data.connected !== false);
            setStats({
                total: data.messages?.length || 0,
                unread: data.messages?.filter(m => !m.is_read).length || 0
            });
        } catch (err) {
            if (!isMounted.current) return;
            console.error('Failed to fetch inbox', err);
            setConnected(false);
        } finally {
            if (isMounted.current) setLoading(false);
        }
    };

    const fetchMessageDetail = async (id) => {
        setLoadingDetail(true);
        setMsgDetail(null);
        try {
            const { data } = await api.get(`/api/gmail/message/${id}`);
            setMsgDetail(data);
        } catch (err) {
            console.error('Failed to fetch message detail', err);
            setMsgDetail({ error: 'FETCH_ERROR', message: 'Failed to retrieve message content.' });
        } finally {
            setLoadingDetail(false);
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
        const lines = content.split('\n');
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

    const handleUpgrade = async () => {
        try {
            const { data } = await api.get('/api/auth/google/link');
            if (data.url) window.location.href = data.url;
        } catch (err) {
            console.error('Failed to init upgrade', err);
        }
    };

    useEffect(() => {
        let isMounted = { current: true };
        fetchInbox(isMounted);
        
        const interval = setInterval(() => {
            fetchInbox(isMounted);
        }, 60000);

        return () => {
            isMounted.current = false;
            clearInterval(interval);
        };
    }, []);

    const handleMsgClick = (msg) => {
        setSelectedMsg(msg);
        fetchMessageDetail(msg.id);
    };

    const filteredMessages = messages.filter(m => 
      m.from.toLowerCase().includes(searchTerm.toLowerCase()) || 
      m.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
      m.snippet.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="max-w-[1400px] mx-auto px-4 py-8 animate-in fade-in duration-700 relative">
            <header className="mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div>
                    <div className="flex items-center gap-3 mb-2">
                        <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] font-black text-blue-500 uppercase tracking-widest">Communication Hub</div>
                        <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                    </div>
                    <h1 className="text-[36px] font-black text-white tracking-tight leading-none">Unified <span className="text-blue-500 italic">Inbox</span></h1>
                    <p className="text-slate-500 text-[13px] font-bold uppercase tracking-wider mt-2 opacity-60">Synchronized Intelligence Layer v4.0</p>
                </div>
                
                <div className="flex items-center gap-4">
                    <div className="relative group">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
                        <input 
                            type="text" 
                            placeholder="Search correspondence..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="bg-[#131722] border border-white/5 focus:border-blue-500/50 rounded-2xl pl-12 pr-6 py-3 text-sm text-white w-full md:w-[300px] transition-all outline-none shadow-xl"
                        />
                    </div>
                    <button 
                        onClick={() => fetchInbox({ current: true }, true)}
                        className="flex items-center gap-2 px-6 py-3 bg-white/5 hover:bg-white/10 border border-white/10 rounded-2xl text-[11px] font-black uppercase tracking-widest text-white transition-all active:scale-95 shadow-xl cursor-pointer"
                    >
                        <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                        Sync
                    </button>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-10">
                {[
                    { label: 'Intelligence Feed', val: stats.total, sub: 'Total Records', icon: <Mail className="text-blue-500" />, bg: 'from-blue-500/10' },
                    { label: 'Active Attention', val: stats.unread, sub: 'Unread Points', icon: <MessageSquare className="text-emerald-500" />, bg: 'from-emerald-500/10' },
                    { label: 'System Health', val: '99.2%', sub: 'Ingestion Rate', icon: <Sparkles className="text-purple-500" />, bg: 'from-purple-500/10' },
                    { label: 'Latency', val: '24ms', sub: 'Sync Velocity', icon: <Clock className="text-amber-500" />, bg: 'from-amber-500/10' }
                ].map((stat, i) => (
                    <div key={i} className={`bg-[#131722] border border-white/5 bg-gradient-to-br ${stat.bg} to-transparent rounded-[24px] p-6 shadow-2xl transition-all hover:bg-white/[0.05] hover:scale-[1.02] cursor-pointer group/stat`}>
                        <div className="flex items-center justify-between mb-4">
                            <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center shadow-lg transition-transform group-hover/stat:rotate-12 group-hover/stat:scale-110">{stat.icon}</div>
                            <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">{stat.label}</span>
                        </div>
                        <div className="text-3xl font-black text-white mb-1 drop-shadow-md">{stat.val}</div>
                        <div className="text-[10px] font-bold text-slate-600 uppercase tracking-tighter">{stat.sub}</div>
                    </div>
                ))}
            </div>

            <div className="bg-[#111827] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl">
                <div className="p-6 border-b border-white/5 bg-white/[0.02] flex items-center justify-between">
                    <h3 className="text-[11px] font-black text-white uppercase tracking-[4px] flex items-center gap-3">
                        <Filter className="w-3.5 h-3.5 text-blue-500 cursor-pointer hover:text-blue-400 transition-colors" /> Recent Correspondence
                    </h3>
                    <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">Verified Channels Only</div>
                </div>

                {loading && messages.length === 0 ? (
                    <div className="p-32 flex flex-col items-center justify-center gap-6">
                        <div className="relative">
                            <div className="w-16 h-16 border-4 border-blue-500/20 border-t-blue-500 rounded-full animate-spin"></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <Mail className="w-6 h-6 text-blue-500" />
                            </div>
                        </div>
                        <p className="text-slate-500 text-[11px] font-black uppercase tracking-[5px] animate-pulse">Scanning Global Inboxes...</p>
                    </div>
                ) : !connected ? (
                    <div className="p-32 text-center">
                        <div className="w-24 h-24 bg-indigo-500/10 rounded-[40px] flex items-center justify-center mx-auto mb-8 text-indigo-500 shadow-[0_0_50px_rgba(79,70,229,0.1)]">
                            <ShieldAlert size={48} strokeWidth={1.5} />
                        </div>
                        <h4 className="text-white text-2xl font-black mb-3 tracking-tight">Intelligence Layer <span className="text-indigo-500 italic">Offline</span></h4>
                        <p className="text-slate-500 text-[14px] font-bold max-w-sm mx-auto uppercase tracking-tighter leading-relaxed mb-10 opacity-80">Your Gmail account is not synchronized. Activate the intelligence layer to enable real-time sentiment analysis and automated lead responses.</p>
                        <a 
                            href="/dashboard"
                            className="inline-block px-12 py-5 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-black uppercase tracking-[4px] rounded-[20px] transition-all shadow-2xl shadow-indigo-600/30 active:scale-95"
                        >
                            🚀 Activate Gmail Sync
                        </a>
                    </div>
                ) : filteredMessages.length === 0 ? (
                    <div className="p-32 text-center">
                        <div className="w-20 h-20 bg-white/5 rounded-[32px] flex items-center justify-center mx-auto mb-6 text-slate-700 shadow-inner">
                            <Mail size={40} />
                        </div>
                        <h4 className="text-white text-xl font-black mb-2 tracking-tight">No intelligence detected</h4>
                        <p className="text-slate-500 text-[13px] font-bold max-w-xs mx-auto uppercase tracking-tighter leading-relaxed">System is active. Correspondence from lead generation campaigns will appear here in real-time.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-white/5">
                        {filteredMessages.map((msg, idx) => (
                            <div 
                                key={idx} 
                                onClick={() => handleMsgClick(msg)}
                                className={`group p-6 hover:bg-white/[0.03] transition-all cursor-pointer flex items-center gap-6 border-l-2 ${selectedMsg?.id === msg.id ? 'bg-blue-500/5 border-l-blue-500' : 'border-l-transparent text-slate-300'}`}
                            >
                                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-white font-black shrink-0 transition-transform group-hover:scale-110 shadow-lg ${msg.is_read ? 'bg-white/5 text-slate-400' : 'bg-gradient-to-br from-blue-500 to-indigo-600'}`}>
                                    {msg.from?.[0]?.toUpperCase() || '?'}
                                </div>
                                <div className="flex-1 min-w-0">
                                    <div className="flex items-center justify-between mb-1.5">
                                        <div className="flex items-center gap-2">
                                            <h4 className={`text-[16px] font-black truncate max-w-[250px] ${msg.is_read ? 'text-slate-400' : 'text-white'}`}>{msg.from.split('<')[0]}</h4>
                                            {!msg.is_read && <div className="w-2 h-2 rounded-full bg-blue-500 shadow-[0_0_8px_theme(colors.blue.500)]"></div>}
                                        </div>
                                        <span className="text-[10px] text-blue-400 font-black uppercase tracking-widest tabular-nums">{formatIST(msg.date)}</span>
                                    </div>
                                    <div className="text-[13px] font-black text-blue-500/70 mb-1.5 truncate uppercase tracking-tighter">{decodeHtml(msg.subject)}</div>
                                    <p className="text-[13px] text-slate-500 line-clamp-1 leading-relaxed italic opacity-80">
                                        {decodeHtml(msg.snippet)}
                                    </p>
                                </div>
                                <div className="hidden md:flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-all translate-x-2 group-hover:translate-x-0">
                                    <div className="p-2 border border-white/10 rounded-xl text-slate-500 hover:text-white transition-colors">
                                        <ChevronRight size={18} />
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Message Detail Sidebar Drawer */}
            {selectedMsg && (
                <div className="fixed inset-0 z-[500] flex justify-end animate-in fade-in duration-300">
                    <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-md cursor-zoom-out" onClick={() => setSelectedMsg(null)}></div>
                    <div className="relative w-full max-w-[650px] bg-[#0f172a] border-l border-white/10 shadow-[0_0_100px_rgba(0,0,0,0.8)] flex flex-col h-full animate-in slide-in-from-right duration-500 ease-out">
                        <div className="p-8 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 rounded-2xl bg-blue-500/10 flex items-center justify-center text-blue-500">
                                    <Mail size={24} />
                                </div>
                                <div>
                                    <h2 className="text-xl font-black text-white tracking-tight">Email Intelligence</h2>
                                    <p className="text-[10px] font-black text-slate-500 uppercase tracking-[3px]">Message ID: {selectedMsg.id.substring(0, 8)}...</p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <button 
                                    onClick={() => fetchMessageDetail(selectedMsg.id)}
                                    className="p-3 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-400 hover:text-white active:scale-95 border border-white/5 cursor-pointer"
                                    title="Reload Message Content"
                                >
                                    <RefreshCw size={18} className={loadingDetail ? 'animate-spin' : ''} />
                                </button>
                                <button 
                                    onClick={() => setSelectedMsg(null)}
                                    className="p-3 bg-rose-500/10 hover:bg-rose-500/20 rounded-2xl transition-all text-rose-500 hover:text-rose-400 active:scale-95 shadow-xl cursor-pointer border border-rose-500/10"
                                >
                                    <X size={20} />
                                </button>
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto custom-scrollbar p-10">
                            {loadingDetail ? (
                                <div className="space-y-8">
                                    <div className="space-y-3">
                                        <div className="h-8 w-[60%] bg-white/5 rounded-xl animate-pulse"></div>
                                        <div className="h-4 w-[40%] bg-white/5 rounded-xl animate-pulse delay-75"></div>
                                    </div>
                                    <div className="pt-8 border-t border-white/5 space-y-4">
                                        <div className="h-4 w-full bg-white/5 rounded-xl animate-pulse"></div>
                                        <div className="h-4 w-full bg-white/5 rounded-xl animate-pulse delay-100"></div>
                                        <div className="h-4 w-[80%] bg-white/5 rounded-xl animate-pulse delay-200"></div>
                                        <div className="h-4 w-[90%] bg-white/5 rounded-xl animate-pulse delay-300"></div>
                                    </div>
                                </div>
                            ) : (
                                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    <div className="mb-10">
                                        <div className="text-[10px] font-black text-blue-500 uppercase tracking-[4px] mb-4">Subject Matter</div>
                                        <h1 className="text-2xl font-black text-white leading-tight mb-8 drop-shadow-sm">{msgDetail?.subject}</h1>
                                        
                                        <div className="grid grid-cols-2 gap-4 p-6 bg-white/[0.02] border border-white/5 rounded-3xl mb-10">
                                            <div>
                                                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Sender Authority</div>
                                                <div className="text-[13px] font-bold text-white truncate">{msgDetail?.from}</div>
                                            </div>
                                            <div>
                                                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Received Pulse</div>
                                                <div className="text-[13px] font-black text-blue-400">{formatIST(msgDetail?.date)}</div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="pt-10 border-t border-white/5">
                                        <div className="text-[10px] font-black text-emerald-500 uppercase tracking-[4px] mb-6 flex items-center gap-2">
                                            <Sparkles size={12} className="animate-pulse" /> Content Intelligence
                                        </div>
                                        <div className="bg-[#0f172a] p-8 rounded-[32px] shadow-2xl overflow-hidden border border-white/5">
                                            <div className="text-slate-300 whitespace-pre-wrap break-words text-[15px] leading-[1.8] font-sans email-content-container">
                                                {renderEmailContent(msgDetail?.body)}
                                            </div>
                                            {!msgDetail?.body && (
                                                <div className="py-10 text-center opacity-40 italic text-sm text-slate-400">
                                                    No message content available in this format.
                                                </div>
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
                                                    Google is blocking the email body. You must grant "Full Intelligence" access to view the whole email.
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
                                    
                                    <div className="mt-16 p-8 bg-blue-600/10 border border-blue-500/20 rounded-3xl flex items-center justify-between gap-6">
                                        <div>
                                            <h4 className="text-white font-black text-sm mb-1 uppercase tracking-widest">Warp Reply</h4>
                                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Draft AI response with context</p>
                                        </div>
                                        <button className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white font-black text-[10px] uppercase tracking-widest rounded-xl transition-all shadow-xl shadow-blue-500/20 active:scale-95 cursor-pointer">
                                            Execute Draft
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Inbox;
