import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, Users, Mail, MousePointer2, AlertCircle, CheckCircle2, PieChart, Activity, Globe, Zap, ArrowUpRight, ArrowDownRight, Loader2 } from 'lucide-react';
import api from '../services/api';

const Metrics = () => {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await api.get('/api/metrics');
        setData(response.data);
      } catch (err) {
        console.error('Failed to fetch metrics', err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // Auto-refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-48 opacity-50">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-medium">Aggregating system-wide intelligence...</p>
      </div>
    );
  }

  if (!data) return null;

  const stats = [
    { label: 'Total Leads', value: data.total_leads, icon: Users, color: 'text-blue-400', barColor: 'bg-blue-500' },
    { label: 'Validated', value: data.valid_leads, icon: CheckCircle2, color: 'text-green-400', barColor: 'bg-green-500' },
    { label: 'Emails Sent', value: data.sent, icon: Send, color: 'text-purple-400', barColor: 'bg-purple-500' },
    { label: 'Engagements', value: data.total_emails_generated, icon: Zap, color: 'text-amber-400', barColor: 'bg-amber-500' },
    { label: 'Conversion', value: `${data.conversion_rate}%`, icon: TrendingUp, color: 'text-cyan-400', barColor: 'bg-cyan-500' },
  ];

  const engagementMetrics = [
    { label: 'Open Rate', value: `${data.open_rate}%`, sub: `${data.unique_opens} Unique`, icon: Mail, color: 'text-blue-400' },
    { label: 'Click Rate', value: `${data.click_rate}%`, sub: `${data.unique_clicks} Unique`, icon: MousePointer2, color: 'text-purple-400' },
    { label: 'Engagement', value: `${data.engagement_rate}%`, sub: 'Open + Click', icon: Activity, color: 'text-green-400' },
    { label: 'Bounce Rate', value: `${data.bounce_rate}%`, sub: `${data.bounce_count} Failed`, icon: AlertCircle, color: 'text-red-400' },
  ];

  return (
    <div className="animate-in fade-in duration-700">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Reports & Analytics</h1>
          <p className="text-slate-400 text-sm mt-1">Comprehensive system performance and conversion intelligence.</p>
        </div>
        <div className="flex gap-3">
          <div className="bg-slate-800/50 border border-white/5 px-4 py-2 rounded-xl flex items-center gap-3">
            <Globe className="w-4 h-4 text-slate-500" />
            <select className="bg-transparent text-xs font-bold text-white outline-none cursor-pointer pr-4">
              <option>Last 30 Days</option>
              <option>Last 7 Days</option>
              <option>All Time</option>
            </select>
          </div>
          <button className="btn btn-primary px-6 shadow-blue-500/20">
            Export PDF
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        {stats.map((stat, i) => (
          <div key={i} className="stat-card group">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>
            <div className="flex justify-between items-start mb-4">
              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{stat.label}</span>
              <stat.icon className={`w-4 h-4 ${stat.color} group-hover:scale-125 transition-transform`} />
            </div>
            <div className="text-3xl font-black text-white leading-tight">{stat.value}</div>
            <div className="mt-3 flex items-center gap-2">
              <div className="h-1 flex-1 bg-slate-900 rounded-full overflow-hidden">
                <div className={`h-full ${stat.barColor}`} style={{ width: '70%', opacity: 0.6 }}></div>
              </div>
              <span className="text-[9px] font-bold text-slate-500">+12%</span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-8">
        <div className="lg:col-span-8">
          <div className="card h-full bg-slate-800/40 border-white/5 p-6 backdrop-blur-md">
            <div className="flex justify-between items-center mb-8">
              <h3 className="text-white font-bold flex items-center gap-2 uppercase tracking-tight text-sm">
                <BarChart3 className="w-4 h-4 text-blue-400" /> Outreach Velocity
              </h3>
              <div className="flex gap-2">
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase">Sent</span>
                </div>
                <div className="flex items-center gap-1.5 ml-3">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase">Delivered</span>
                </div>
              </div>
            </div>
            
            <div className="h-[280px] flex items-end justify-between gap-4 px-2">
               {/* Mock Chart Bars */}
               {[40, 65, 30, 85, 45, 95, 55, 75, 50, 60, 80, 70].map((h, i) => (
                 <div key={i} className="flex-1 flex flex-col gap-1 items-center group">
                   <div className="w-full relative">
                     <div className="absolute bottom-0 left-0 right-0 bg-blue-500/10 rounded-t-lg transition-all group-hover:bg-blue-500/30" style={{ height: `${h}%` }}></div>
                     <div className="relative bg-blue-600 rounded-t-lg transition-all group-hover:scale-105" style={{ height: `${h * 0.7}%` }}></div>
                   </div>
                   <span className="text-[8px] font-bold text-slate-600 uppercase mt-2">D{i+1}</span>
                 </div>
               ))}
            </div>
          </div>
        </div>

        <div className="lg:col-span-4">
          <div className="card h-full bg-slate-800/40 border-white/5 p-6 backdrop-blur-md relative overflow-hidden group">
            <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
              <TrendingUp className="w-32 h-32 text-blue-400" />
            </div>
            
            <h3 className="text-white font-bold flex items-center gap-2 uppercase tracking-tight text-sm mb-8">
              <PieChart className="w-4 h-4 text-purple-400" /> Lead Segmentation
            </h3>
            
            <div className="space-y-6">
              {Object.entries(data.persona_breakdown).map(([persona, count], i) => (
                <div key={persona} className="space-y-2">
                  <div className="flex justify-between items-end">
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{persona}</span>
                    <span className="text-xs font-black text-white">{count} ({Math.round((count / data.total_leads) * 100)}%)</span>
                  </div>
                  <div className="h-2 bg-slate-900 rounded-full overflow-hidden">
                    <div className={`h-full ${['bg-blue-500', 'bg-purple-500', 'bg-green-500', 'bg-amber-500'][i % 4]}`} style={{ width: `${(count / data.total_leads) * 100}%` }}></div>
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-10 p-4 bg-slate-900/50 rounded-2xl border border-white/5">
              <p className="text-[11px] text-slate-500 font-medium leading-relaxed">
                <span className="text-blue-400 font-bold">Insight:</span> Most leads are classified as <span className="text-white font-bold">MANAGEMENT</span>, followed by <span className="text-white font-bold">OPERATIONS</span>. Consider shifting outreach tone to match executive personas.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {engagementMetrics.map((m, i) => (
          <div key={i} className="card bg-slate-800/40 border-white/5 p-5 group hover:-translate-y-1 transition-all">
            <div className="flex justify-between items-center mb-4">
              <div className={`w-10 h-10 rounded-xl bg-slate-900 border border-white/5 flex items-center justify-center ${m.color}`}>
                <m.icon className="w-5 h-5" />
              </div>
              <div className="text-right">
                <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none mb-1">Growth</div>
                <div className="flex items-center justify-end text-green-400 font-black text-xs">
                  <ArrowUpRight className="w-3 h-3" /> 2.4%
                </div>
              </div>
            </div>
            <div className="text-2xl font-black text-white">{m.value}</div>
            <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">{m.label}</div>
            <div className="mt-4 pt-4 border-t border-white/5 flex justify-between items-center">
              <span className="text-[10px] font-medium text-slate-500 italic">{m.sub}</span>
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse"></div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const Send = ({ className }) => (
  <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></svg>
);

export default Metrics;
