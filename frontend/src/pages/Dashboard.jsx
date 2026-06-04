import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import { Link } from 'react-router-dom';
import {
  Users, CheckSquare, Rocket, BarChart3, Sparkles, Activity,
  ShieldAlert, Mail, Loader2, Zap, Clock, Globe, Target, CheckCircle2, XCircle, X, RefreshCw, FileText
} from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar, Cell, PieChart, Pie, Legend
} from 'recharts';

const Dashboard = () => {
  const [data, setData] = useState({
    total_leads: 0,
    valid_leads: 0,
    classified: 0,
    pending: 0,
    sent: 0,
    conversion_rate: 0,
    daily_sent_count: 0,
    daily_limit: 2000,
    open_rate: 0,
    unique_opens: 0,
    click_rate: 0,
    unique_clicks: 0,
    engagement_rate: 0,
    bounce_rate: 0,
    total_bounces: 0,
    total_unsubs: 0,
    unsub_rate: 0,
    recent_logs: [],
    persona_data: { FOUNDER: 0, 'C-SUITE': 0, INVESTOR: 0, EXECUTIVE: 0, OTHER: 0 },
    inboxMessages: []
  });

  const [adminStats, setAdminStats] = useState(null);
  const [velocity, setVelocity] = useState([]);
  const [productivity, setProductivity] = useState([]);
  const [activeUsers, setActiveUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sendingReport, setSendingReport] = useState(false);
  const [period, setPeriod] = useState('daily');
  const [toast, setToast] = useState(null);
  const [selectedMsg, setSelectedMsg] = useState(null);
  const [msgDetail, setMsgDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

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

  const [user, setUser] = useState(JSON.parse(localStorage.getItem('user') || '{}'));
  const isAdmin = user.role === 'ADMIN';

  const [isDispatching, setIsDispatching] = useState(false);

  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  };

  const handleDispatchReport = async () => {
    setIsDispatching(true);
    try {
      await axios.post('/api/admin/dispatch-report');
      showToast('success', `System activity report dispatched to ${user.email || 'your registered email'}`);
    } catch (err) {
      showToast('error', 'Failed to dispatch report: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsDispatching(false);
    }
  };

  const fetchMessageDetail = async (id) => {
    setLoadingDetail(true);
    setMsgDetail(null);
    try {
      const { data } = await axios.get(`/api/gmail/message/${id}`);
      setMsgDetail(data);
    } catch (err) {
      console.error('Failed to fetch message detail', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleGoogleLink = async () => {
    try {
      const { data } = await axios.get('/api/auth/google/link');
      if (data.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      showToast('error', 'Failed to initialize Google security layer');
    }
  };

  const handleDisconnect = async () => {
    if (!window.confirm('NUCLEAR RESET: This will completely wipe all Google tokens. Are you sure you want to proceed?')) return;
    try {
      await axios.post('/api/auth/google/disconnect');
      showToast('success', 'Intelligence Layer completely reset.');
      // Update local state to reflect disconnection
      setUser(prev => ({ ...prev, google_linked_at: null, google_email: null }));
      setData(prev => ({ ...prev, inboxMessages: [] }));
    } catch (err) {
      showToast('error', 'Failed to reset Intelligence Layer');
    }
  };

  const decodeHtml = (html) => {
    const txt = document.createElement("textarea");
    txt.innerHTML = html;
    return txt.value;
  };

  // Format any date string to Indian Standard Time (IST)
  const formatIST = (dateStr, compact = false) => {
    if (!dateStr) return 'Recently';
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      if (compact) {
        return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short' })
          + ' ' + d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true });
      }
      return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' })
        + ', ' + d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })
        + ' IST';
    } catch { return dateStr; }
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
  const fetchData = async () => {
    try {
      const response = await axios.get('/api/dashboard/stats');
      if (response.data) {
        setData(prev => ({ ...prev, ...response.data }));
      }

      // Fetch Gmail Intelligence if linked
      if (user.google_linked_at) {
        try {
          const gmailRes = await axios.get('/api/gmail/inbox');
          setData(prev => ({ ...prev, inboxMessages: gmailRes.data.messages || [] }));
        } catch (err) {
          console.error('Gmail sync error:', err);
        }
      }

      setLoading(false);
    } catch (err) {
      console.error('Data fetch error:', err);
      setLoading(false);
    }
  };

  // Sync user profile if coming back from successful Gmail link
  useEffect(() => {
    const checkParams = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      
      if (urlParams.get('error') === 'permissions_denied') {
        showToast('error', 'PERMISSION DENIED: You must check the boxes on the Google screen to allow email access.');
        // Clear param without reload
        window.history.replaceState({}, document.title, "/dashboard");
      }

      if (urlParams.get('link') === 'success' || urlParams.get('google') === 'linked') {
        try {
          const { data: updatedUser } = await axios.get('/api/auth/me');
          if (updatedUser) {
            localStorage.setItem('user', JSON.stringify(updatedUser));
            setUser(updatedUser); // This triggers the UI update
            showToast('success', 'Intelligence layer successfully integrated!');
            // Refresh page data with new permissions
            fetchData();
            // Clear param
            window.history.replaceState({}, document.title, "/dashboard");
          }
        } catch (err) {
          console.error('Profile sync error:', err);
        }
      }
    };
    checkParams();
  }, []);

  const fetchVelocity = async () => {
    if (!isAdmin) return;
    try {
      const response = await axios.get('/api/admin/velocity', { params: { period } });
      setVelocity(response.data);
    } catch (err) {
      console.error('Velocity fetch error:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // High-frequency 10s polling for real-time Command Center
    return () => clearInterval(interval);
  }, [isAdmin]);

  useEffect(() => {
    fetchVelocity();
  }, [isAdmin, period]);

  const triggerReport = async () => {
    setSendingReport(true);
    try {
      const resp = await axios.post('/api/users/report');
      showToast('success', resp.data?.message || 'System pulse report has been generated.');
    } catch (err) {
      showToast('error', 'Failed to send report: ' + (err.response?.data?.detail || 'Global Server Error'));
    } finally {
      setSendingReport(false);
    }
  };

  const displayName = user.full_name || user.username || 'User';

  // --- UI COMPONENTS ---

  const renderUserUI = () => (
    <div className="max-w-[1400px] mx-auto px-4 py-8">
      {/* Welcome Section */}
      <div className="bg-gradient-to-br from-blue-600/15 to-purple-500/15 border border-white/10 rounded-[32px] py-[60px] px-10 mb-10 flex flex-col justify-center items-center text-center shadow-[0_20px_40px_rgba(0,0,0,0.3)] relative overflow-hidden">
        <div className="absolute inset-0 opacity-[0.03] pointer-events-none bg-[url('https://www.transparenttextures.com/patterns/carbon-fibre.png')]"></div>
        <h1 className="text-[44px] font-black mb-3 tracking-tight text-white relative z-10">
          Welcome back, <span className="bg-gradient-to-r from-purple-400 to-blue-400 text-transparent bg-clip-text italic">{displayName}</span>
        </h1>
        <p className="text-slate-400 text-lg max-w-[600px] relative z-10">
          Your pipeline is soaring. AI discovery has identified <span className="text-blue-400 font-extrabold underline decoration-blue-500/50">{data.total_leads}</span> targets today.
        </p>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-6 mb-10">
        {[
          { label: 'Primary Pipeline', val: data.total_leads, sub: 'Lead targets sourced', class: 'card-v', border: 'border-l-blue-500' },
          { label: 'AI Processed', val: data.classified, sub: 'Ingestion automation', class: 'card-i', border: 'border-l-purple-500' },
          { label: 'Approval Queue', val: data.pending, sub: 'Pending Review', class: 'card-b', border: 'border-l-indigo-500' },
          { label: 'Refined Emails', val: data.refined !== undefined ? data.refined : 0, sub: 'Drafted and enriched', class: 'card-g', border: 'border-l-emerald-500' },
          { label: 'Unsubscribed', val: `${data.unsub_rate.toFixed(1)}%`, sub: 'At-risk leads', class: 'card-y', border: 'border-l-amber-500' },
          { label: 'Outbound Limit', val: `${data.daily_sent_count}/${data.daily_limit}`, sub: 'Daily limits reset', class: 'card-o', border: 'border-l-orange-500' }
        ].map((stat, i) => (
          <div key={i} className={`bg-[#131722] border border-white/5 border-l-4 ${stat.border} rounded-2xl p-6 shadow-xl transition-all hover:scale-105`}>
            <div className="flex items-center justify-between mb-3">
              <div className="text-[10px] font-black uppercase tracking-[2px] text-slate-500">{stat.label}</div>
              <div className="w-2 h-2 rounded-full bg-blue-500/50 animate-pulse"></div>
            </div>
            <div className="text-[32px] font-black text-white mb-1">{stat.val}</div>
            <div className="text-[11px] font-bold text-slate-600 uppercase tracking-tighter">{stat.sub}</div>
          </div>
        ))}
      </div>
      {/* Gmail Connectivity Card - Prominent Position */}
      <div className={`mb-10 p-8 rounded-[32px] border transition-all shadow-2xl relative overflow-hidden group ${user.google_linked_at ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-indigo-600/10 border-indigo-500/30'}`}>
        <div className="relative z-10 flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex items-center gap-6">
            <div className={`w-16 h-16 rounded-2xl flex items-center justify-center shadow-lg ${user.google_linked_at ? 'bg-emerald-500/20 text-emerald-500' : 'bg-indigo-500/20 text-indigo-400'}`}>
              <Mail size={32} />
            </div>
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className={`text-[10px] font-black uppercase tracking-[3px] ${user.google_linked_at ? 'text-emerald-500' : 'text-indigo-400'}`}>
                  {user.google_linked_at ? 'Google Integrity: Active' : 'Action Required: Intelligence Layer'}
                </span>
                {user.google_linked_at && (
                   <div className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center gap-1">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                  </div>
                )}
              </div>
              <h2 className="text-2xl font-black text-white mb-2">
                {user.google_linked_at ? 'Unified Inbox Syncing' : 'Activate Real-time Gmail Sync'}
              </h2>
              <p className="text-slate-400 text-sm max-w-[500px] leading-relaxed">
                Connect your account to enable AI-powered sentiment analysis and automated meeting scheduling for every lead reply.
              </p>
              {user.google_linked_at && (
                  <div className="mt-2 space-y-1">
                    <div className="text-[9px] font-black text-blue-500/80 uppercase tracking-widest flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                      Connected: {user.google_email || 'Verified Account'}
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="text-[8px] font-bold text-slate-500 uppercase tracking-tighter">
                        All replies will be sent via this address
                      </div>
                      <button 
                        onClick={handleDisconnect}
                        className="text-[8px] font-black text-rose-500 hover:text-rose-400 uppercase tracking-widest cursor-pointer underline underline-offset-4"
                      >
                        Disconnect Intelligence
                      </button>
                    </div>
                  </div>
                )}
            </div>
          </div>
          <div className="flex items-center gap-3">
                {user.google_linked_at ? (
                  <button 
                    onClick={handleDisconnect}
                    className="px-4 py-2 bg-red-500/10 border border-red-500/20 rounded-xl text-[9px] font-black text-red-500 uppercase tracking-widest hover:bg-red-500/20 transition-all active:scale-95 shadow-xl cursor-pointer"
                  >
                    Disconnect
                  </button>
                ) : (
                  <button 
                    onClick={handleGoogleLink}
                    className="px-10 py-5 rounded-2xl text-xs font-black uppercase tracking-[3px] transition-all active:scale-95 shadow-xl bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-600/30 cursor-pointer"
                  >
                    🚀 Connect Gmail Now
                  </button>
                )}
          </div>
        </div>
      </div>

      {/* Engagement Pulse Grid */}
      <div className="bg-[#151a26] border border-[#ffffff08] rounded-[32px] mb-10 shadow-2xl overflow-hidden">
          <div className="flex items-center justify-between p-8 border-b border-white/5">
            <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-3">
              <Activity className="w-5 h-5 text-blue-500" /> Real-time Engagement Pulse
            </h3>
            <Link to="/dashboard/metrics" className="text-[11px] font-black text-blue-500 uppercase tracking-widest hover:text-white transition-colors">Full Intelligence Dashboard →</Link>
          </div>
          <div className="p-8 grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { label: 'Open Rate', val: `${data.open_rate}%`, sub: `${data.unique_opens} unique`, color: 'text-blue-500' },
              { label: 'Click Rate', val: `${data.click_rate}%`, sub: `${data.unique_clicks} unique`, color: 'text-emerald-500' },
              { label: 'Bounce', val: `${data.bounce_rate}%`, sub: `${data.total_bounces} events`, color: 'text-orange-500' },
              { label: 'Opt-outs', val: data.total_unsubs, sub: `${data.unsub_rate.toFixed(1)}% volatility`, color: 'text-red-500' }
            ].map((p, i) => (
              <div key={i} className="text-center group">
                <div className="text-[10px] text-[#475569] uppercase font-black tracking-widest mb-3 group-hover:text-slate-400 transition-colors">{p.label}</div>
                <div className={`text-[32px] font-black ${p.color}`}>{p.val}</div>
                <div className="text-[11px] text-[#64748b] mt-1 font-bold uppercase tracking-tighter">{p.sub}</div>
              </div>
            ))}
          </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-8 mb-10">
        <div className="bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl h-[450px] flex flex-col">
          <div className="p-6 border-b border-white/5 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="text-xs font-black text-white uppercase tracking-widest">High-Velocity Stream</h3>
          </div>
          <div className="p-6 flex-1 overflow-y-auto custom-scrollbar space-y-4">
            {(data.recent_logs || []).length > 0 ? (
              data.recent_logs.map((log, i) => (
                <div key={i} className="p-4 bg-white/[0.02] border border-white/[0.03] rounded-2xl flex items-center justify-between">
                  <div>
                    <div className="text-[11px] font-black text-white uppercase mb-0.5">{log.action.replace(/_/g, ' ')}</div>
                    <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest">Performed {new Date(log.created_at).toLocaleTimeString()}</div>
                  </div>
                  <div className="px-3 py-1 bg-blue-500/10 text-blue-500 text-[9px] font-black rounded-lg uppercase tracking-widest">Online</div>
                </div>
              ))
            ) : (
              <div className="h-full flex items-center justify-center text-slate-600 italic text-xs tracking-widest uppercase">No activity detected.</div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-8 h-[450px]">
          {/* Live Intelligence Stream */}
          <div className="bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl flex-1 flex flex-col">
            <div className="p-5 border-b border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Mail className="w-3.5 h-3.5 text-emerald-500" />
                <h3 className="text-[10px] font-black text-white uppercase tracking-widest">Intelligence Stream</h3>
              </div>
              {data.inboxMessages.length > 0 && (
                <div className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[8px] font-black text-emerald-500 uppercase">
                  {data.inboxMessages.length} Live
                </div>
              )}
            </div>
            <div className="p-5 flex-1 overflow-y-auto custom-scrollbar space-y-2.5">
              {data.inboxMessages.length > 0 ? (
                data.inboxMessages.map((msg, i) => (
                  <div 
                    key={i} 
                    onClick={() => { setSelectedMsg(msg); fetchMessageDetail(msg.id); }}
                    className="p-3.5 bg-white/[0.02] border border-white/[0.03] rounded-xl hover:bg-white/[0.04] transition-all group cursor-pointer border-l-2 border-l-transparent hover:border-l-blue-500"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[9px] font-black text-emerald-500 uppercase truncate max-w-[120px]">{msg.from.split('<')[0]}</span>
                      <span className="text-[8px] font-black text-blue-500 uppercase tabular-nums">{formatIST(msg.date, true)}</span>
                    </div>
                    <h4 className="text-[10px] font-bold text-white mb-1 line-clamp-1 opacity-80">{decodeHtml(msg.subject)}</h4>
                    <p className="text-[10px] text-slate-500 line-clamp-1 leading-relaxed opacity-60 italic">{decodeHtml(msg.snippet)}</p>
                  </div>
                ))
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center opacity-40">
                  <Clock className="w-5 h-5 text-slate-700 mb-2" />
                  <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Syncing Stream</div>
                </div>
              )}
            </div>
          </div>

          {/* Persona Dominance */}
          <div className="bg-[#131722] border border-white/5 rounded-[32px] p-6 shadow-2xl flex flex-col min-h-[160px]">
            <div className="flex items-center gap-2 mb-5">
              <Globe className="w-3.5 h-3.5 text-rose-500" />
              <h3 className="text-[10px] font-black text-white uppercase tracking-widest">Persona Dominance</h3>
            </div>
            <div className="flex-1 space-y-4 overflow-y-auto custom-scrollbar pr-2">
              {Object.entries(data.persona_data || {}).map(([persona, count], i) => {
                const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'];
                const percentage = data.total_leads > 0 ? (count / data.total_leads) * 100 : 0;
                return (
                  <div key={persona}>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <div className="w-1 h-1 rounded-full" style={{ background: colors[i % colors.length] }}></div>
                        {persona}
                      </span>
                      <span className="text-[10px] font-black text-white">{count}</span>
                    </div>
                    <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                      <div className="h-full transition-all duration-1000" style={{ width: `${percentage}%`, background: colors[i % colors.length] }}></div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Reports Section */}
      <div className="bg-[#131722] border border-white/10 rounded-[32px] overflow-hidden shadow-2xl shadow-blue-500/5">
        <div className="px-10 py-8 border-b border-white/5 flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-amber-500" />
          <h3 className="text-sm font-black text-white uppercase tracking-[4px]">Reports</h3>
        </div>
        <div className="p-10 grid grid-cols-1 md:grid-cols-2 gap-8">
          <Link to="/dashboard/mis-report" className="group p-8 bg-white/2 hover:bg-amber-600/10 border border-white/5 rounded-[24px] transition-all">
            <div className="w-14 h-14 bg-amber-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><FileText className="w-7 h-7 text-amber-500" /></div>
            <h4 className="text-white font-black text-lg mb-2">MIS Report</h4>
            <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Generate 5–8 page PDF report for management presentation.</p>
          </Link>
          <Link to="/dashboard/metrics" className="group p-8 bg-white/2 hover:bg-blue-600/10 border border-white/5 rounded-[24px] transition-all">
            <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><BarChart3 className="w-7 h-7 text-blue-500" /></div>
            <h4 className="text-white font-black text-lg mb-2">Analytics</h4>
            <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Deep-dive into open rates, bounce rates, and engagement trends.</p>
          </Link>
        </div>
      </div>
    </div>
  );

  const renderAdminUI = () => (
    <div className="max-w-[1400px] mx-auto px-4 py-8 animate-in fade-in duration-700">

      {/* Personnel Bar (Online Now) */}
      <div className="flex flex-col lg:flex-row items-center justify-between gap-6 mb-10">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-700 flex items-center justify-center shadow-lg">
            <Rocket className="w-7 h-7 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2">
              Command <span className="text-blue-500">Center</span>
            </h1>
            <p className="text-slate-500 text-xs font-bold uppercase tracking-[2px]">Workspace Oversight v4.0</p>
          </div>
        </div>

        <div className="flex items-center gap-2 bg-[#131722] border border-white/5 p-1 rounded-2xl shadow-xl">
          <div className="px-4 py-2 flex items-center gap-2">
            <div className="relative">
              <Activity className="w-4 h-4 text-emerald-500" />
              <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping"></span>
            </div>
            <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Active Personnel</span>
          </div>
          <div className="h-8 w-[1px] bg-white/5"></div>
          <div className="flex items-center gap-2 px-3">
            {activeUsers.map((au, i) => (
              <div key={i} className="group relative">
                <div className="w-8 h-8 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-[10px] font-black text-blue-500 hover:bg-blue-600 hover:text-white transition-all cursor-help uppercase">
                  {au.username.substring(0, 2)}
                </div>
                <div className="absolute top-10 left-1/2 -translate-x-1/2 bg-slate-900 border border-white/10 px-2 py-1 rounded-lg text-[8px] font-bold text-white opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
                  {au.username.toUpperCase()} (Online)
                </div>
              </div>
            ))}
            {activeUsers.length === 0 && <span className="text-[10px] italic text-slate-600 px-4">System Idle</span>}
          </div>
        </div>
      </div>

      {/* Admin Hero Header - Enhanced with Upgrade Highlights */}
      <div className="grid grid-cols-1 xl:grid-cols-[1.5fr_1fr] gap-8 mb-10">
        <div className="bg-gradient-to-br from-[#1a202c] via-[#111827] to-[#1a202c] border border-white/10 rounded-[32px] p-10 relative overflow-hidden flex flex-col justify-center items-start shadow-2xl">
          <div className="relative z-10 flex flex-col gap-6 w-full">
            <div className="flex items-center gap-4">
              <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] font-black text-blue-500 uppercase tracking-[3px]">Elite Oversight</div>
              <span className="flex items-center gap-1 text-[10px] font-black text-emerald-500 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
                <ShieldAlert className="w-3 h-3" /> COMMAND AUTHORIZED
              </span>
            </div>

            <div className="flex flex-col gap-4">
              <h2 className="text-[44px] font-black text-white leading-tight tracking-tight">
                Welcome back, <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">{displayName}</span>
              </h2>

              <div className="grid grid-cols-2 gap-x-8 gap-y-4 pt-4 border-t border-white/5">
                {[
                  { label: 'Visual Intelligence', icon: <BarChart3 className="w-3 h-3 text-blue-400" />, desc: 'Elite charting via Recharts' },
                  { label: 'Personnel Pulse', icon: <Activity className="w-3 h-3 text-emerald-400" />, desc: '24h Real-time monitoring' },
                  { label: 'Automated Reports', icon: <Mail className="w-3 h-3 text-purple-400" />, desc: 'One-click SMTP dispatch' },
                  { label: 'Advanced Metrics', icon: <Globe className="w-3 h-3 text-rose-400" />, desc: 'Sector & Persona analytics' }
                ].map((highlight, idx) => (
                  <div key={idx} className="flex items-start gap-2">
                    <div className="mt-1">{highlight.icon}</div>
                    <div>
                      <div className="text-[10px] font-black text-white uppercase tracking-widest">{highlight.label}</div>
                      <p className="text-[9px] font-bold text-slate-500 uppercase">{highlight.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-8 flex gap-4">
              <button
                onClick={handleDispatchReport}
                disabled={isDispatching}
                className="flex items-center gap-3 px-10 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white rounded-2xl text-[11px] font-black uppercase tracking-widest cursor-pointer disabled:cursor-not-allowed transition-all shadow-xl shadow-blue-500/20 group active:scale-95"
              >
                {isDispatching ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 text-amber-300 group-hover:scale-110 transition-transform" />}
                {isDispatching ? 'Transmitting Intelligence...' : 'Dispatch System Report'}
              </button>
            </div>
          </div>
          <div className="absolute top-1/2 -right-10 -translate-y-1/2 w-[350px] h-[350px] opacity-10 bg-blue-500 blur-[100px] rounded-full pointer-events-none"></div>
        </div>

        {/* Global Key Metrics summary */}
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: 'System Integrity', val: `${(100 - data.bounce_rate).toFixed(1)}%`, icon: <CheckSquare className="w-5 h-5 text-emerald-500" /> },
            { label: 'Global Velocity', val: `+${velocity[velocity.length - 1]?.leads || 0}`, icon: <Target className="w-5 h-5 text-blue-500" /> },
            { label: 'Active Flows', val: adminStats?.active_campaigns, icon: <Globe className="w-5 h-5 text-purple-500" /> },
            { label: 'Engagement', val: `${data.engagement_rate.toFixed(1)}%`, icon: <Activity className="w-5 h-5 text-amber-500" /> }
          ].map((stat, i) => (
            <div key={i} className="p-6 bg-[#131722] border border-white/5 rounded-[24px] shadow-xl flex flex-col justify-between transition-all hover:bg-white/[0.03]">
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center">{stat.icon}</div>
                <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">{stat.label}</div>
              </div>
              <div className="text-[28px] font-black text-white">{stat.val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Velocity Chart */}
      <div className="mb-8">
        <div className="bg-[#111827] border border-white/5 rounded-[32px] p-8 shadow-2xl relative overflow-hidden">
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 mb-8">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[9px] font-black text-blue-500 uppercase tracking-widest leading-none">Admin Authority</div>
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
              </div>
              <h1 className="text-3xl font-black text-white tracking-tight">Command <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent italic">Center</span></h1>
            </div>
            <div className="flex bg-[#131722] border border-white/10 rounded-2xl p-1 gap-1">
              {['daily', 'weekly', 'monthly', 'quarterly'].map((p) => (
                <button
                  key={p}
                  onClick={() => setPeriod(p)}
                  className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${period === p ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={velocity}>
                <defs>
                  <linearGradient id="colorLeads" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                <XAxis dataKey="day" stroke="#475569" fontSize={10} axisLine={false} tickLine={false} />
                <YAxis stroke="#475569" fontSize={10} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10', borderRadius: '12px', fontSize: '11px' }} />
                <Area name="Leads Generated" type="monotone" dataKey="leads" stroke="#3b82f6" fillOpacity={1} fill="url(#colorLeads)" strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Team Performance Graph — Leads / Emails / Credits per User */}
      <div className="bg-[#111827] border border-white/5 rounded-[32px] p-8 shadow-2xl mb-10">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <div className="text-[9px] font-black text-slate-500 uppercase tracking-[3px] mb-1">Real-Time Intelligence</div>
            <h3 className="text-xl font-black text-white tracking-tight">Team Performance <span className="bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">Breakdown</span></h3>
          </div>
          {/* Legend */}
          <div className="flex items-center gap-6">
            {[
              { color: '#3b82f6', label: 'Leads Generated' },
              { color: '#8b5cf6', label: 'Emails Sent' },
              { color: '#ef4444', label: 'Credits Used (RR)' },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-2">
                <div className="w-2.5 h-2.5 rounded-full" style={{ background: color }} />
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Summary Totals Row */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Leads Generated', val: productivity.reduce((s, u) => s + (u.leads || 0), 0), color: 'text-blue-400', bg: 'bg-blue-500/10 border-blue-500/20' },
            { label: 'Total Emails Sent', val: productivity.reduce((s, u) => s + (u.outreach || 0), 0), color: 'text-purple-400', bg: 'bg-purple-500/10 border-purple-500/20' },
            { label: 'Total Credits Used', val: productivity.reduce((s, u) => s + (u.credits || 0), 0), color: 'text-red-400', bg: 'bg-red-500/10 border-red-500/20' },
          ].map(({ label, val, color, bg }) => (
            <div key={label} className={`p-4 rounded-2xl border ${bg} flex items-center justify-between`}>
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{label}</span>
              <span className={`text-2xl font-black ${color}`}>{val}</span>
            </div>
          ))}
        </div>

        <div className="h-[340px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={productivity} barGap={4} barCategoryGap="30%">
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
              <XAxis dataKey="name" stroke="#475569" fontSize={11} axisLine={false} tickLine={false} />
              <YAxis stroke="#475569" fontSize={10} axisLine={false} tickLine={false} />
              <Tooltip
                cursor={{ fill: '#ffffff04' }}
                contentStyle={{ backgroundColor: '#0d1117', border: '1px solid #ffffff15', borderRadius: '12px', fontSize: '12px' }}
                formatter={(value, name) => [value, name]}
              />
              <Legend
                wrapperStyle={{ paddingTop: '20px', fontSize: '10px', fontWeight: '800', textTransform: 'uppercase', letterSpacing: '2px' }}
              />
              <Bar name="Leads Generated" dataKey="leads" fill="#3b82f6" radius={[6, 6, 0, 0]} maxBarSize={40} />
              <Bar name="Emails Sent" dataKey="outreach" fill="#8b5cf6" radius={[6, 6, 0, 0]} maxBarSize={40} />
              <Bar name="Credits Used (RR)" dataKey="credits" fill="#ef4444" radius={[6, 6, 0, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-black tracking-[4px] uppercase text-[10px]">Syncing Workspace Analytics...</p>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-700 relative">
      {/* Premium Toast Notification */}
      {toast && (
        <div className={`fixed top-16 left-1/2 -translate-x-1/2 z-[9999] min-w-[380px] max-w-[550px] flex items-center gap-6 px-8 py-6 rounded-[32px] border border-white/10 backdrop-blur-3xl animate-in slide-in-from-top-12 duration-700 ease-out fill-mode-forwards shadow-[0_30px_70px_-15px_rgba(0,0,0,0.6)] ${toast.type === 'success'
            ? 'bg-gradient-to-br from-emerald-500/20 via-slate-950/60 to-slate-950/80 border-t-emerald-400/40'
            : 'bg-gradient-to-br from-rose-500/20 via-slate-950/60 to-slate-950/80 border-t-rose-400/40'
          }`}>
          <div className="relative">
            <div className={`absolute inset-0 blur-2xl opacity-40 ${toast.type === 'success' ? 'bg-emerald-500' : 'bg-rose-500'}`}></div>
            <div className={`relative p-4 rounded-[20px] ${toast.type === 'success' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'} border border-white/5 shadow-inner`}>
              {toast.type === 'success' ? <CheckCircle2 className="w-6 h-6 ml-0.5" /> : <XCircle className="w-6 h-6 ml-0.5" />}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <span className={`text-[10px] font-black uppercase tracking-[5px] ${toast.type === 'success' ? 'text-emerald-500/60' : 'text-rose-500/60'}`}>Intelligence Update</span>
            <span className="text-[16px] font-black tracking-tight text-white leading-tight drop-shadow-sm">{toast.message}</span>
          </div>

          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 w-[80%] h-[1px] bg-white/5 overflow-hidden rounded-full">
            <div className={`h-full bg-current shadow-[0_0_10px_currentColor] transition-all duration-[5000ms] ease-linear animate-toast-glow`}></div>
          </div>
          <div className={`absolute inset-0 rounded-[32px] pointer-events-none border border-white/5 ${toast.type === 'success' ? 'group-hover:border-emerald-500/20' : 'group-hover:border-rose-500/20'} transition-colors`}></div>
        </div>
      )}
      <style>{`
        @keyframes toast-glow {
          0% { width: 0%; opacity: 0.2; }
          20% { opacity: 1; }
          100% { width: 100%; opacity: 0.1; }
        }
        .animate-toast-glow {
          animation: toast-glow 5000ms linear forwards;
        }
      `}</style>
      {isAdmin ? renderAdminUI() : renderUserUI()}

      {/* Message Detail Sidebar Drawer */}
      {selectedMsg && (
        <div className="fixed inset-0 z-[500] flex justify-end animate-in fade-in duration-300">
            <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-md" onClick={() => setSelectedMsg(null)}></div>
            <div className="relative w-full max-w-[600px] bg-[#0b0f1a] border-l border-white/5 shadow-[0_0_80px_rgba(0,0,0,0.9)] flex flex-col h-full animate-in slide-in-from-right duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]">
                {/* Premium Header */}
                <div className="p-8 border-b border-white/[0.03] flex items-center justify-between bg-gradient-to-r from-blue-500/[0.02] to-transparent">
                    <div className="flex items-center gap-5">
                        <div className="w-14 h-14 rounded-[20px] bg-gradient-to-br from-blue-600/20 to-indigo-600/20 border border-blue-500/10 flex items-center justify-center text-blue-400">
                            <Mail size={26} strokeWidth={1.5} />
                        </div>
                        <div>
                            <h2 className="text-[20px] font-black text-white tracking-tight leading-none mb-2">Message Intelligence</h2>
                            <div className="flex items-center gap-2">
                              <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                              <p className="text-[10px] font-black text-slate-500 uppercase tracking-[4px]">SECURE CHANNEL</p>
                            </div>
                        </div>
                    </div>
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={() => fetchMessageDetail(selectedMsg.id)}
                            className="p-4 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-400 hover:text-white active:scale-95 border border-white/5 cursor-pointer"
                            title="Reload Message Content"
                        >
                            <RefreshCw size={20} className={loadingDetail ? 'animate-spin' : ''} />
                        </button>
                        <button 
                            onClick={() => setSelectedMsg(null)}
                            className="p-4 bg-rose-500/10 hover:bg-rose-500/20 rounded-2xl transition-all text-rose-500 hover:text-rose-400 active:scale-95 shadow-xl border border-rose-500/10 cursor-pointer"
                        >
                            <X size={20} />
                        </button>
                    </div>
                </div>

                <div className="flex-1 overflow-y-auto custom-scrollbar p-10 bg-gradient-to-b from-transparent to-[#080b13]">
                    {loadingDetail ? (
                        <div className="space-y-12">
                            <div className="space-y-4">
                                <div className="h-10 w-[70%] bg-white/5 rounded-2xl animate-pulse"></div>
                                <div className="h-6 w-[40%] bg-white/5 rounded-2xl animate-pulse delay-75"></div>
                            </div>
                            <div className="pt-12 border-t border-white/5 space-y-6">
                                <div className="h-4 w-full bg-white/5 rounded-full animate-pulse"></div>
                                <div className="h-4 w-full bg-white/5 rounded-full animate-pulse delay-100"></div>
                                <div className="h-4 w-[60%] bg-white/5 rounded-full animate-pulse delay-200"></div>
                            </div>
                        </div>
                    ) : (
                        <div className="animate-in fade-in slide-in-from-bottom-6 duration-700">
                            {/* Subject & Info */}
                            <div className="mb-12">
                              <div className="text-[10px] font-black text-blue-500 uppercase tracking-[6px] mb-6">Verified Transmission</div>
                              <h1 className="text-[32px] font-black text-white leading-[1.1] mb-10 tracking-tighter drop-shadow-lg">{msgDetail?.subject}</h1>
                              
                              <div className="flex items-center justify-between p-6 bg-white/[0.02] border border-white/5 rounded-[32px]">
                                  <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-white font-black shadow-lg">
                                      {msgDetail?.from[0]}
                                    </div>
                                    <div>
                                      <div className="text-[14px] font-black text-white">{msgDetail?.from.split('<')[0]}</div>
                                      <div className="text-[10px] font-bold text-slate-600 uppercase tracking-widest leading-none mt-1">{msgDetail?.from.split('<')[1]?.replace('>', '')}</div>
                                    </div>
                                  </div>
                                  <div className="text-right">
                                    <div className="text-[13px] font-black text-blue-400 tabular-nums">{formatIST(msgDetail?.date)}</div>
                                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest mt-1">IST Timestamp</div>
                                  </div>
                              </div>
                            </div>

                            {/* Email Body */}
                            <div className="pt-10 mb-20">
                                <div className="bg-[#0f172a] p-10 rounded-[40px] shadow-2xl overflow-hidden border border-white/5">
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
                                    <div className="mt-8 p-8 bg-amber-500/10 border border-amber-500/20 rounded-[32px] flex flex-col gap-6 shadow-2xl">
                                        <div className="flex items-center gap-4">
                                            <div className="w-12 h-12 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
                                                <ShieldAlert size={24} />
                                            </div>
                                            <div>
                                                <div className="text-[11px] font-black text-amber-200 uppercase tracking-[4px] leading-none mb-1">Intelligence Restricted</div>
                                                <p className="text-[12px] text-amber-200/50 font-medium">Full email body requires re-authorization.</p>
                                            </div>
                                        </div>
                                        <button 
                                            onClick={handleGoogleLink}
                                            className="w-full py-4 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-black uppercase tracking-[4px] rounded-2xl transition-all shadow-xl shadow-amber-500/20 active:scale-95 cursor-pointer"
                                        >
                                            🚀 Fix Gmail Permissions Now
                                        </button>
                                    </div>
                                )}
                                </div>
                            
                            {/* Action Float Card */}
                            <div className="p-10 bg-gradient-to-r from-blue-600/10 to-indigo-600/10 border border-white/10 rounded-[40px] flex flex-col sm:flex-row items-center justify-between gap-8 mb-10 relative overflow-hidden group">
                                <div className="relative z-10">
                                    <h4 className="text-white font-black text-xl mb-1 tracking-tight">Warp <span className="text-blue-500 italic">Reply</span></h4>
                                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Generate intelligent, context-aware email responses in seconds.</p>
                                </div>
                                <button className="relative z-10 px-8 py-4 bg-white text-slate-950 font-black text-[11px] uppercase tracking-[3px] rounded-2xl transition-all hover:scale-105 active:scale-95 shadow-2xl cursor-pointer">
                                    Initialize Draft
                                </button>
                                <Sparkles className="absolute -right-4 -bottom-4 w-32 h-32 text-blue-500/10 group-hover:scale-110 transition-transform duration-1000" />
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

export default Dashboard;
