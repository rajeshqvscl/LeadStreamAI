import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import { Link } from 'react-router-dom';
import { Users, CheckSquare, Rocket, BarChart3, Sparkles } from 'lucide-react';

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
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('/api/dashboard/stats');
        if (response.data) {
          setData(prev => ({ ...prev, ...response.data }));
          setLoading(false);
        }
      } catch {
        console.log('Using mock dashboard data...');
        // Mock fallback if endpoint unavailable
        setData({
          total_leads: 124, valid_leads: 98, classified: 105, pending: 45, sent: 88,
          conversion_rate: 12.5, daily_sent_count: 88, daily_limit: 1000, open_rate: 45.2,
          unique_opens: 39, click_rate: 15.6, unique_clicks: 13, engagement_rate: 22.4,
          bounce_rate: 2.1, total_bounces: 1, total_unsubs: 3, unsub_rate: 0.8,
          recent_logs: [], persona_data: { FOUNDER: 50, INVESTOR: 40, PARTNER: 34 }
        });
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="bg-gradient-to-br from-blue-600/15 to-purple-500/15 border border-white/10 rounded-[20px] py-[60px] px-10 mb-8 flex flex-col justify-center items-center text-center shadow-[0_20px_40px_rgba(0,0,0,0.3)]">
        <h1 className="text-[36px] font-extrabold mb-3 tracking-[-0.5px] text-white">
          Welcome back, <span className="bg-gradient-to-r from-purple-500 to-blue-500 text-transparent bg-clip-text">Admin</span>
        </h1>
        <p className="text-[#94a3b8] text-[16px] max-w-[600px]">
          Your pipeline is soaring. We've identified <span className="text-white font-extrabold underline decoration-blue-500">{data.total_leads}</span> potential leads today.
        </p>
      </div>

      {loading ? (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-5 mb-8">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="bg-white/5 border border-white/10 rounded-2xl p-6 h-[140px] relative overflow-hidden">
              <div className="w-24 h-3 bg-white/5 rounded mb-4"></div>
              <div className="w-16 h-8 bg-white/5 rounded mb-2"></div>
              <div className="w-20 h-3 bg-white/5 rounded"></div>
              <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer"></div>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-5 mb-8">
          <div className="card-v card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">Primary Pipeline</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.total_leads}</div>
            <div className="text-[12px] font-bold text-accent-purple">Lead targets sourced</div>
          </div>
          <div className="card-i card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">AI Processed</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.classified}</div>
            <div className="text-[12px] font-bold text-accent-indigo">Ingestion automation</div>
          </div>
          <div className="card-b card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">Approval Queue</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.pending}</div>
            <div className="text-[12px] font-bold text-accent-blue">Pending Review</div>
          </div>
          <div className="card-g card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">Refined Emails</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.sent}</div>
            <div className="text-[12px] font-bold text-accent-emerald">Drafted and enriched</div>
          </div>
          <div className="card-y card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">Unsubscribed</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.unsub_rate.toFixed(1)}%</div>
            <div className="text-[12px] font-bold text-accent-amber">At-risk leads</div>
          </div>
          <div className="card-o card rounded-2xl p-6 cursor-default">
            <div className="text-[11px] font-extrabold uppercase tracking-[1.5px] text-[#475569] mb-3">Outbound Limit</div>
            <div className="text-[36px] font-black text-white mb-1.5 leading-none">{data.daily_sent_count}/{data.daily_limit}</div>
            <div className="text-[12px] font-bold text-accent-orange">Daily limits reset</div>
          </div>
        </div>
      )}

      <div className="bg-[#151a26] border border-[#ffffff15] rounded-[20px] shadow-[0_10px_40px_rgba(0,0,0,0.6)] mb-8">
        <div className="flex items-center justify-between p-6 border-b border-transparent">
          <div className="flex items-center gap-3">
            <h3 className="text-[18px] font-extrabold text-white">🔥 Real-time Engagement Pulse</h3>
            <div className="bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 px-2.5 py-1 text-[10px] font-black tracking-[1px] rounded-full flex items-center shadow-[0_0_10px_rgba(16,185,129,0.2)]">
              <span className="w-2 h-2 bg-white rounded-full mr-1.5 animate-pulse"></span>
              LIVE STREAM
            </div>
          </div>
          <Link to="/dashboard/metrics" className="text-[13px] font-bold text-blue-500 flex items-center gap-1 hover:text-blue-400">Full Intelligence <span className="text-[16px]">→</span></Link>
        </div>
        <div className="p-6 pt-0">
          <div className="grid grid-cols-5 gap-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="bg-black/20 rounded-[10px] p-4 border border-white/5 text-center relative overflow-hidden">
                {loading ? (
                  <>
                    <div className="w-16 h-2 bg-white/5 rounded mx-auto mb-3"></div>
                    <div className="w-12 h-6 bg-white/5 rounded mx-auto mb-2"></div>
                    <div className="w-20 h-2 bg-white/5 rounded mx-auto"></div>
                    <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer"></div>
                  </>
                ) : (
                  <>
                    <div className="text-[10px] text-[#475569] uppercase font-bold mb-2">
                      {i === 0 ? 'Open Rate' : i === 1 ? 'Click Performance' : i === 2 ? 'Heat Delta' : i === 3 ? 'Leakage (Bounce)' : 'Opt-outs'}
                    </div>
                    <div className={`text-[24px] font-black ${i === 0 ? 'text-blue-500' : i === 1 ? 'text-emerald-500' : i === 2 ? 'text-purple-500' : i === 3 ? 'text-orange-500' : 'text-red-500'}`}>
                      {i === 0 ? `${data.open_rate}%` : i === 1 ? `${data.click_rate}%` : i === 2 ? `${data.engagement_rate}%` : i === 3 ? `${data.bounce_rate}%` : data.total_unsubs}
                    </div>
                    <div className="text-[11px] text-[#64748b] mt-1.5 font-semibold">
                      {i === 0 ? `${data.unique_opens} unique` : i === 1 ? `${data.unique_clicks} unique` : i === 2 ? 'System Reach' : i === 3 ? `${data.total_bounces} Events` : `${data.unsub_rate}% Volatility`}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-6 mb-8">
        {/* Left Column: High-Velocity Stream */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden flex flex-col h-[500px]">
          <div className="px-6 py-5 flex items-center gap-2 border-b border-transparent">
            <span className="text-amber-500 text-[14px]">⚡</span>
            <h3 className="text-[13px] font-bold text-slate-300 tracking-wide">High-Velocity Stream</h3>
          </div>
          <div className="p-6 pt-0 flex-1 overflow-y-auto custom-scrollbar">
            <div className="space-y-3">
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <div key={i} className="p-4 rounded-[12px] bg-[#1a202c] border border-[#ffffff08] animate-pulse h-[68px]"></div>
                ))
              ) : data.recent_logs?.length > 0 ? (
                data.recent_logs.map((log, i) => (
                  <div key={i} className="p-4 rounded-[12px] bg-[#1a202c] border border-[#ffffff08] flex justify-between items-center transition-colors">
                    <div className="flex flex-col gap-1.5">
                      <div className="text-[11px] font-black text-white tracking-widest uppercase">
                        {log.action.replace(/_/g, ' ')}
                      </div>
                      <div className="text-[10px] text-[#64748b] font-medium flex items-center gap-1.5">
                        <span>{log.performed_by || 'system'}</span>
                        <span className="text-[#334155]">→</span>
                        <span>{log.lead_id ? `Lead #${log.lead_id}` : 'system'}</span>
                      </div>
                    </div>
                    <div className="text-[10px] font-black text-[#64748b] bg-[#0f121b] px-2.5 py-1.5 rounded-md border border-[#ffffff05] tabular-nums tracking-wider">
                      {(() => {
                        const dateStr = log.created_at.endsWith('Z') ? log.created_at : log.created_at + 'Z';
                        const diff = Date.now() - new Date(dateStr).getTime();
                        const mins = Math.floor(diff / 60000);
                        if (mins < 1) return 'JUST NOW';
                        if (mins < 60) return `${mins}M AGO`;
                        const hours = Math.floor(mins / 60);
                        if (hours < 24) return `${hours}H AGO`;
                        return `${Math.floor(hours / 24)}D AGO`;
                      })()}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-10 text-[#64748b] italic text-sm">No activity detected.</div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Persona Dominance */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden flex flex-col h-[500px]">
          <div className="px-6 py-5 flex items-center gap-2 border-b border-transparent">
            <span className="text-rose-500 text-[14px]">🎯</span>
            <h3 className="text-[13px] font-bold text-slate-300 tracking-wide">Persona Dominance</h3>
          </div>
          <div className="p-6 pt-2 flex-1 overflow-y-auto custom-scrollbar space-y-7">
            {Object.entries(
               Object.entries(data.persona_data || {}).reduce((acc, [k, v]) => {
                 let norm = k || 'OTHER';
                 if (norm === 'C-SUITE' || norm === 'EXECUTIVE') norm = 'FOUNDER';
                 if (!['FOUNDER', 'INVESTOR', 'PARTNER', 'OTHER'].includes(norm)) norm = 'OTHER';
                 acc[norm] = (acc[norm] || 0) + v;
                 return acc;
               }, {})
            ).map(([persona, count]) => {
              const personaColors = {
                'FOUNDER': { badge: 'bg-blue-600/20 text-blue-500', bar: 'bg-blue-600' },
                'PARTNER': { badge: 'text-white', bar: 'bg-white' },
                'INVESTOR': { badge: 'bg-emerald-500/10 text-emerald-400', bar: 'bg-emerald-500' },
                'OTHER': { badge: 'bg-amber-500/20 text-amber-500', bar: 'bg-amber-500' }
              };
              
              const config = personaColors[persona] || personaColors['OTHER'];
              const percentage = data.total_leads ? (count / data.total_leads) * 100 : 0;
              
              return (
                <div key={persona} className="group">
                  <div className="flex justify-between items-center mb-3">
                    <span className={`px-2 py-0.5 text-[9px] font-black uppercase tracking-[1.5px] rounded ${config.badge}`}>
                      {persona}
                    </span>
                    <span className="text-[13px] font-black text-white tabular-nums flex items-baseline gap-1">
                      {count} <span className="font-bold text-slate-500 text-[10px]">Leads</span>
                    </span>
                  </div>
                  <div className="h-1 bg-[#1e2433] rounded-full overflow-hidden relative">
                     <div 
                       className={`h-full rounded-full transition-all duration-1000 ease-out ${config.bar}`} 
                       style={{ width: `${percentage}%` }}
                     ></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Mission Orchestra Section */}
      <div className="bg-[#131722] border border-[#ffffff08] rounded-[20px] overflow-hidden shadow-[0_10px_40px_rgba(0,0,0,0.6)]">
        <div className="px-8 py-6 border-b border-[#ffffff05] flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-rose-500" />
            </div>
            <h3 className="text-[16px] font-black text-white uppercase tracking-wider">Mission Orchestra</h3>
          </div>
        </div>
        
        <div className="p-8">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {/* Lead Pipeline */}
            <Link to="/dashboard/leads" className="bg-[#0f121b] border border-[#ffffff08] rounded-[16px] p-6 transition-all group glow-blue block no-underline decoration-transparent">
              <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                <Users className="w-6 h-6 text-blue-500" />
              </div>
              <h4 className="text-white font-bold text-[14px] mb-2">Lead Pipeline</h4>
              <p className="text-[#64748b] text-[11px] leading-relaxed font-medium">Ingest, discover, and prune high-fit prospects.</p>
            </Link>

            {/* Approval Queue */}
            <Link to="/dashboard/emails" className="bg-[#0f121b] border border-[#ffffff08] rounded-[16px] p-6 transition-all group glow-emerald block no-underline decoration-transparent">
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                <CheckSquare className="w-6 h-6 text-emerald-500" />
              </div>
              <h4 className="text-white font-bold text-[14px] mb-2">Approval Queue</h4>
              <p className="text-[#64748b] text-[11px] leading-relaxed font-medium">Audit and authorize AI-generated outreach sequences.</p>
            </Link>

            {/* Campaign Hub */}
            <Link to="/dashboard/campaigns" className="bg-[#0f121b] border border-[#ffffff08] rounded-[16px] p-6 transition-all group glow-rose block no-underline decoration-transparent">
              <div className="w-12 h-12 rounded-xl bg-rose-500/10 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                <Rocket className="w-6 h-6 text-rose-500" />
              </div>
              <h4 className="text-white font-bold text-[14px] mb-2">Campaign Hub</h4>
              <p className="text-[#64748b] text-[11px] leading-relaxed font-medium">Calibrate high-performance outreach experiments.</p>
            </Link>

            {/* BI Reports */}
            <Link to="/dashboard/metrics" className="bg-[#0f121b] border border-[#ffffff08] rounded-[16px] p-6 transition-all group glow-amber block no-underline decoration-transparent">
              <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center mb-5 group-hover:scale-110 transition-transform">
                <BarChart3 className="w-6 h-6 text-amber-500" />
              </div>
              <h4 className="text-white font-bold text-[14px] mb-2">BI reports</h4>
              <p className="text-[#64748b] text-[11px] leading-relaxed font-medium">Deep-dive into industry and region performance.</p>
            </Link>
          </div>
        </div>
      </div>
    </>
  );
};

export default Dashboard;
