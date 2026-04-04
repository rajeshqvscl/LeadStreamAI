import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import { Link } from 'react-router-dom';
import { 
  Users, CheckSquare, Rocket, BarChart3, Sparkles, Activity, 
  ShieldAlert, Mail, Loader2, Zap, Clock, Globe, Target
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
    daily_limit: 1000,
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
    persona_data: { FOUNDER: 0, 'C-SUITE': 0, INVESTOR: 0, EXECUTIVE: 0, OTHER: 0 }
  });
  
  const [adminStats, setAdminStats] = useState(null);
  const [velocity, setVelocity] = useState([]);
  const [productivity, setProductivity] = useState([]);
  const [activeUsers, setActiveUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sendingReport, setSendingReport] = useState(false);
  const [period, setPeriod] = useState('daily');

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = user.role === 'ADMIN';

  const [isDispatching, setIsDispatching] = useState(false);

  const handleDispatchReport = async () => {
    setIsDispatching(true);
    try {
      await axios.post('/api/admin/dispatch-report');
      alert('Intelligence Report Dispatched Successfully');
    } catch (err) {
      alert('Failed to dispatch report: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsDispatching(false);
    }
  };

  const fetchData = async () => {
    try {
      const response = await axios.get('/api/dashboard/stats');
      if (response.data) {
        setData(prev => ({ ...prev, ...response.data }));
      }

      if (isAdmin) {
        const [admRes, prodRes, activeRes] = await Promise.all([
          axios.get('/api/admin/stats'),
          axios.get('/api/users/productivity'),
          axios.get('/api/users/active')
        ]);
        setAdminStats(admRes.data);
        setProductivity(prodRes.data);
        setActiveUsers(activeRes.data);
      }
      
      setLoading(false);
    } catch (err) {
      console.error('Data fetch error:', err);
      setLoading(false);
    }
  };

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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [isAdmin]);

  useEffect(() => {
    fetchVelocity();
  }, [isAdmin, period]);

  const triggerReport = async () => {
    setSendingReport(true);
    try {
      const resp = await axios.post('/api/users/report');
      alert(resp.data?.message || 'System activity report has been generated.');
    } catch (err) {
      alert('Failed to send report: ' + (err.response?.data?.detail || 'Global Server Error'));
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
          { label: 'Refined Emails', val: data.sent, sub: 'Drafted and enriched', class: 'card-g', border: 'border-l-emerald-500' },
          { label: 'Unsubscribed', val: `${data.unsub_rate.toFixed(1)}%`, sub: 'At-risk leads', class: 'card-y', border: 'border-l-amber-500' },
          { label: 'Outbound Limit', val: `${data.daily_sent_count}/${data.daily_limit}`, sub: 'Daily limits reset', class: 'card-o', border: 'border-l-orange-500' }
        ].map((stat, i) => (
          <div key={i} className={`bg-[#131722] border border-white/5 border-l-4 ${stat.border} rounded-2xl p-6 shadow-xl transition-all hover:scale-105`}>
            <div className="text-[10px] font-black uppercase tracking-[2px] text-slate-500 mb-3">{stat.label}</div>
            <div className="text-[32px] font-black text-white mb-1 leading-none">{stat.val}</div>
            <div className="text-[11px] font-bold text-slate-600 uppercase tracking-tighter">{stat.sub}</div>
          </div>
        ))}
      </div>

      {/* Engagement bar */}
      <div className="bg-[#151a26] border border-[#ffffff08] rounded-[24px] shadow-2xl mb-10 overflow-hidden">
        <div className="flex items-center justify-between p-6 border-b border-white/5">
           <h3 className="text-sm font-black text-white uppercase tracking-widest flex items-center gap-2">
             <Activity className="w-4 h-4 text-blue-500" /> Real-time Engagement Pulse
           </h3>
           <Link to="/dashboard/metrics" className="text-[11px] font-black text-blue-500 uppercase tracking-widest hover:text-white transition-colors">Full Intelligence →</Link>
        </div>
        <div className="p-6 grid grid-cols-2 md:grid-cols-5 gap-6">
            {[
              { label: 'Open Rate', val: `${data.open_rate}%`, sub: `${data.unique_opens} unique`, color: 'text-blue-500' },
              { label: 'Click Rate', val: `${data.click_rate}%`, sub: `${data.unique_clicks} unique`, color: 'text-emerald-500' },
              { label: 'Heat Delta', val: `${data.engagement_rate}%`, sub: 'System Reach', color: 'text-purple-500' },
              { label: 'Bounce', val: `${data.bounce_rate}%`, sub: `${data.total_bounces} events`, color: 'text-orange-500' },
              { label: 'Opt-outs', val: data.total_unsubs, sub: `${data.unsub_rate.toFixed(1)}% volatility`, color: 'text-red-500' }
            ].map((p, i) => (
              <div key={i} className="text-center group">
                <div className="text-[9px] text-[#475569] uppercase font-black tracking-widest mb-2 group-hover:text-slate-400 transition-colors">{p.label}</div>
                <div className={`text-[26px] font-black ${p.color}`}>{p.val}</div>
                <div className="text-[10px] text-[#64748b] mt-1 font-bold uppercase tracking-tighter">{p.sub}</div>
              </div>
            ))}
        </div>
      </div>

      {/* High-Velocity Stream & Persona Dominance Row */}
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

        <div className="bg-[#131722] border border-white/5 rounded-[32px] p-8 shadow-2xl flex flex-col h-[450px]">
           <div className="flex items-center gap-2 mb-8">
              <Globe className="w-4 h-4 text-rose-500" />
              <h3 className="text-xs font-black text-white uppercase tracking-widest">Persona Dominance</h3>
           </div>
           <div className="flex-1 space-y-8 overflow-y-auto custom-scrollbar pr-2">
              {Object.entries(data.persona_data || {}).map(([persona, count], i) => {
                const colors = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444'];
                const percentage = data.total_leads > 0 ? (count / data.total_leads) * 100 : 0;
                return (
                  <div key={persona}>
                    <div className="flex justify-between items-center mb-3">
                      <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest flex items-center gap-2">
                        <div className="w-1.5 h-1.5 rounded-full" style={{ background: colors[i % colors.length] }}></div>
                        {persona}
                      </span>
                      <span className="text-xs font-black text-white">{count} <span className="text-slate-600 font-bold ml-1 uppercase">Leads</span></span>
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

      {/* Mission Orchestra Hub */}
      <div className="bg-[#131722] border border-white/10 rounded-[32px] overflow-hidden shadow-2xl shadow-blue-500/5">
        <div className="px-10 py-8 border-b border-white/5 flex items-center gap-3">
            <Sparkles className="w-5 h-5 text-rose-500" />
            <h3 className="text-sm font-black text-white uppercase tracking-[4px]">Mission Orchestra</h3>
        </div>
        <div className="p-10 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
            <Link to="/dashboard/leads" className="group p-8 bg-white/2 hover:bg-blue-600/10 border border-white/5 rounded-[24px] transition-all">
                <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Users className="w-7 h-7 text-blue-500" /></div>
                <h4 className="text-white font-black text-lg mb-2">Lead Pipeline</h4>
                <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Ingest, discover, and prune high-fit prospects.</p>
            </Link>
            <Link to="/dashboard/emails" className="group p-8 bg-white/2 hover:bg-emerald-600/10 border border-white/5 rounded-[24px] transition-all">
                <div className="w-14 h-14 bg-emerald-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><CheckSquare className="w-7 h-7 text-emerald-500" /></div>
                <h4 className="text-white font-black text-lg mb-2">Approval Queue</h4>
                <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Audit and authorize AI-generated outreach sequences.</p>
            </Link>
            <Link to="/dashboard/campaigns" className="group p-8 bg-white/2 hover:bg-rose-600/10 border border-white/5 rounded-[24px] transition-all">
                <div className="w-14 h-14 bg-rose-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><Rocket className="w-7 h-7 text-rose-500" /></div>
                <h4 className="text-white font-black text-lg mb-2">Campaign Hub</h4>
                <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Calibrate high-performance outreach experiments.</p>
            </Link>
            <Link to="/dashboard/metrics" className="group p-8 bg-white/2 hover:bg-amber-600/10 border border-white/5 rounded-[24px] transition-all">
                <div className="w-14 h-14 bg-amber-500/10 rounded-2xl flex items-center justify-center mb-6 group-hover:scale-110 transition-transform"><BarChart3 className="w-7 h-7 text-amber-500" /></div>
                <h4 className="text-white font-black text-lg mb-2">BI Reports</h4>
                <p className="text-slate-500 text-xs font-bold leading-relaxed uppercase tracking-tighter">Deep-dive into industry and region performance.</p>
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
                  onClick={triggerReport}
                  disabled={sendingReport}
                  className="flex items-center gap-3 px-10 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white rounded-2xl text-[11px] font-black uppercase tracking-widest transition-all shadow-xl shadow-blue-500/20 group"
                >
                  {sendingReport ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4 group-hover:scale-110 transition-transform" />}
                  Dispatch System Pulse
                </button>
              </div>
           </div>
           <div className="absolute top-1/2 -right-10 -translate-y-1/2 w-[350px] h-[350px] opacity-10 bg-blue-500 blur-[100px] rounded-full pointer-events-none"></div>
        </div>

        {/* Global Key Metrics summary */}
        <div className="grid grid-cols-2 gap-4">
           {[
             { label: 'System Integrity', val: `${(100 - data.bounce_rate).toFixed(1)}%`, icon: <CheckSquare className="w-5 h-5 text-emerald-500" /> },
             { label: 'Global Velocity', val: `+${velocity[velocity.length-1]?.leads || 0}`, icon: <Target className="w-5 h-5 text-blue-500" /> },
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

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-[1.8fr_1fr] gap-8 mb-10">
         <div className="bg-[#111827] border border-white/5 rounded-[32px] p-8 shadow-2xl relative overflow-hidden">
           <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 mb-10">
            <div>
              <div className="flex items-center gap-3 mb-2">
                <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[9px] font-black text-blue-500 uppercase tracking-widest leading-none">Admin Authority</div>
                <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
              </div>
              <h1 className="text-3xl font-black text-white tracking-tight">Command <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent italic">Center</span></h1>
            </div>
            
            <div className="flex flex-wrap items-center gap-4">
              <button 
                onClick={handleDispatchReport}
                disabled={isDispatching}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white font-black px-6 py-3 rounded-2xl text-[10px] uppercase tracking-[2px] transition-all shadow-xl shadow-blue-500/20 active:scale-95 shrink-0"
              >
                {isDispatching ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3 text-amber-300" />
                )}
                {isDispatching ? 'Transmitting Intelligence...' : 'Dispatch System Report'}
              </button>

              <div className="flex bg-[#131722] border border-white/10 rounded-2xl p-1 gap-1">
                {['daily', 'weekly', 'monthly', 'quarterly'].map((p) => (
                  <button
                    key={p}
                    onClick={() => setPeriod(p)}
                    className={`px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${
                      period === p ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' : 'text-slate-500 hover:text-white hover:bg-white/5'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>
            <div className="h-[350px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={velocity}>
                    <defs>
                      <linearGradient id="colorLeads" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
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

         <div className="bg-[#111827] border border-white/5 rounded-[32px] p-8 shadow-2xl">
            <h3 className="text-sm font-black text-white uppercase tracking-widest mb-8">User Productivity Pulse</h3>
            <div className="h-[300px] w-full">
               <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={productivity} layout="vertical">
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" stroke="#475569" fontSize={10} axisLine={false} tickLine={false} width={80} />
                    <Tooltip cursor={{fill: '#ffffff05'}} contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #ffffff10' }} />
                    <Bar name="Leads Generated" dataKey="leads" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={15} />
                    <Bar name="Emails/Outreach" dataKey="outreach" fill="#8b5cf6" radius={[0, 4, 4, 0]} barSize={15} />
                    <Bar name="Validation/Auth" dataKey="valid" fill="#10b981" radius={[0, 4, 4, 0]} barSize={15} />
                  </BarChart>
               </ResponsiveContainer>
            </div>
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
    <div className="animate-in fade-in duration-700">
      {isAdmin ? renderAdminUI() : renderUserUI()}
    </div>
  );
};

export default Dashboard;
