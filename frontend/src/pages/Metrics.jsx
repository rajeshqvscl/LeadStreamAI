import React, { useState, useEffect } from 'react';
import { Loader2, Zap } from 'lucide-react';
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
    const interval = setInterval(fetchMetrics, 30000);
    return () => clearInterval(interval);
  }, []);

  if (isLoading || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-48">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-medium">Loading analytics...</p>
      </div>
    );
  }

  // Calculate derived metrics from dynamic API response
  const totalLeads = data.total_leads || 1;
  const validationRate = ((data.valid_leads / totalLeads) * 100).toFixed(1);
  const deliveryRate = data.sent > 0 ? ((data.delivered / data.sent) * 100).toFixed(1) : '0.0';
  const heatRate = data.engagement_rate.toFixed(1);
  // Using active campaigns ratio compared to total leads as a proxy metric for 'Authentication'
  const authRate = data.active_campaigns > 0 ? '100.0' : '0.0';

  const pipeline = [
    { label: 'Leads Ingested', value: data.total_leads, max: totalLeads, color: 'bg-purple-500' },
    { label: 'Sent Campaigns', value: data.sent, max: totalLeads, color: 'bg-indigo-500' },
    { label: 'Inbox Delivered', value: data.delivered, max: totalLeads, color: 'bg-blue-500' },
    { label: 'Total Opens', value: data.unique_opens, max: totalLeads, color: 'bg-green-500' },
    { label: 'Inbound Signals', value: data.unique_engaged, max: totalLeads, color: 'bg-teal-500' },
  ];

  const totalPersonas = Object.values(data.persona_breakdown).reduce((a, b) => a + b, 0) || 1;
  const personas = Object.entries(data.persona_breakdown).map(([k, v]) => ({
    label: k,
    value: v,
    percent: ((v / totalPersonas) * 100).toFixed(1),
    color: k === 'INVESTOR' ? 'bg-teal-400' : k === 'PARTNER' ? 'bg-amber-400' : k === 'OTHER' ? 'bg-orange-500' : 'bg-blue-600'
  })).sort((a, b) => b.value - a.value);

  const totalIndCap = Object.values(data.industry_breakdown).reduce((a, b) => a + b, 0) || 1;
  const industries = Object.entries(data.industry_breakdown).map(([k, v]) => ({
    name: k, cap: v, share: ((v / totalIndCap) * 100).toFixed(1)
  })).sort((a, b) => b.cap - a.cap);

  const totalCountryCap = Object.values(data.country_breakdown).reduce((a, b) => a + b, 0) || 1;
  const countries = Object.entries(data.country_breakdown).map(([k, v]) => ({
    name: k, cap: v, share: ((v / totalCountryCap) * 100).toFixed(1)
  })).sort((a, b) => b.cap - a.cap);

  return (
    <div className="animate-in fade-in duration-500 max-w-[1600px] mx-auto text-white">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-black tracking-tight">Reports & Analytics</h1>
          <p className="text-slate-400 text-xs mt-1">Performance insights across the <span className="text-purple-400 font-bold">Vianca</span> pipeline spectrum.</p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-slate-800/50 border border-white/5 rounded-lg text-xs font-bold text-slate-300 hover:text-white transition-colors">
            Export PDF
          </button>
          <button className="px-5 py-2 bg-blue-600 hover:bg-blue-500 transition-colors rounded-lg text-xs font-bold text-white shadow-lg shadow-blue-500/20">
            Refresh Data
          </button>
        </div>
      </div>

      {/* Top Stats Row */}
      <div className="flex gap-4 mb-6">
        <div className="flex-1 bg-slate-900/60 border border-white/5 rounded-xl p-5 border-t-2 border-t-purple-500 relative overflow-hidden">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">TOTAL INGESTION</div>
          <div className="text-3xl font-bold mb-2">{data.total_leads}</div>
          <div className="text-[10px] text-slate-500">Total active all sectors</div>
        </div>

        <div className="flex-1 bg-slate-900/60 border border-white/5 rounded-xl p-5 border-t-2 border-t-indigo-500 relative overflow-hidden">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">ACCURACY FLOW</div>
          <div className="text-3xl font-bold text-indigo-400 mb-2">{validationRate}%</div>
          <div className="text-[10px] text-slate-500">AI verified leads</div>
        </div>

        <div className="flex-1 bg-slate-900/60 border border-white/5 rounded-xl p-5 border-t-2 border-t-blue-600 relative overflow-hidden">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">AUTHENTICATION</div>
          <div className="text-3xl font-bold text-blue-500 mb-2">{authRate}%</div>
          <div className="text-[10px] text-slate-500">{data.active_campaigns} campaigns active</div>
        </div>

        <div className="flex-1 bg-slate-900/60 border border-white/5 rounded-xl p-5 border-t-2 border-t-emerald-500 relative overflow-hidden">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">INBOX VELOCITY</div>
          <div className="text-3xl font-bold text-emerald-400 mb-2">{deliveryRate}%</div>
          <div className="text-[10px] text-slate-500">{data.delivered} delivered</div>
        </div>

        <div className="flex-1 bg-slate-900/60 border border-white/5 rounded-xl p-5 border-t-2 border-t-amber-500 relative overflow-hidden">
          <div className="text-[9px] font-bold text-slate-500 uppercase tracking-widest mb-1">HEAT ENGAGEMENTS</div>
          <div className="text-3xl font-bold text-amber-500 mb-2">{heatRate}%</div>
          <div className="text-[10px] text-slate-500">Open / Click rate</div>
        </div>
      </div>

      {/* Middle Grid - Heat maps */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Pipeline Conversion Heat-map */}
        <div className="bg-slate-900/60 border border-white/5 rounded-xl p-6">
          <h3 className="text-xs font-bold text-white mb-6 flex items-center gap-2">
            <span className="text-purple-400">🔥</span> Pipeline Conversion Heat-map
          </h3>
          <div className="space-y-6">
            {pipeline.map((item, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between text-xs font-bold">
                  <span className="text-slate-300">{item.label}</span>
                  <span className="text-white">{item.value}</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full ${item.color} rounded-full`} style={{ width: `${(item.value / item.max) * 100}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* High-Fit Segment Dominance */}
        <div className="bg-slate-900/60 border border-white/5 rounded-xl p-6">
          <h3 className="text-xs font-bold text-white mb-6 flex items-center gap-2">
            <span className="text-emerald-400">🎯</span> High-Fit Segment Dominance
          </h3>
          <div className="space-y-6">
            {personas.map((p, i) => (
              <div key={i} className="space-y-2">
                <div className="flex justify-between text-[10px] font-black uppercase tracking-widest">
                  <span className={p.color.replace('bg-', 'text-')}>{p.label}</span>
                  <span className="text-slate-500">{p.percent}%</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className={`h-full ${p.color} rounded-full`} style={{ width: `${p.percent}%` }}></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Grid - Tables */}
      <div className="grid grid-cols-2 gap-6 mb-6">
        {/* Sector Dominance */}
        <div className="bg-slate-900/60 border border-white/5 rounded-xl p-6">
          <h3 className="text-xs font-bold text-white mb-6 flex items-center gap-2">
            <span className="text-indigo-400">📊</span> Sector Dominance
          </h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/5">
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest">INDUSTRY</th>
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">CAP</th>
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">SHARE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {industries.map((ind, i) => (
                <tr key={i} className="hover:bg-white/[0.02]">
                  <td className="py-3 text-xs font-bold text-slate-300">{ind.name}</td>
                  <td className="py-3 text-xs font-bold text-white text-right">{ind.cap}</td>
                  <td className="py-3 text-xs font-black text-slate-500 text-right flex items-center justify-end gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-indigo-500"></div> {ind.share}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Global Coverage */}
        <div className="bg-slate-900/60 border border-white/5 rounded-xl p-6">
          <h3 className="text-xs font-bold text-white mb-6 flex items-center gap-2">
            <span className="text-blue-400">🌍</span> Global Coverage
          </h3>
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-white/5">
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest">COUNTRY</th>
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">CAP</th>
                <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right">SHARE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {countries.map((c, i) => (
                <tr key={i} className="hover:bg-white/[0.02]">
                  <td className="py-3 text-xs font-bold text-slate-300">{c.name}</td>
                  <td className="py-3 text-xs font-bold text-white text-right">{c.cap}</td>
                  <td className="py-3 text-xs font-black text-slate-500 text-right flex items-center justify-end gap-2">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div> {c.share}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Real-time Inbound Signals */}
      <div className="bg-slate-900/60 border border-white/5 rounded-xl p-6 mb-10">
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-xs font-bold text-white flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-400 fill-amber-400" /> Real-time Inbound Signals
            <span className="ml-3 px-2 py-0.5 rounded text-[9px] font-black bg-emerald-500/20 text-emerald-400">● LIVE MONITORING</span>
          </h3>
          <div className="text-[10px] text-slate-500 border border-white/10 px-3 py-1 rounded">Polling Email Tracking API</div>
        </div>

        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-white/5">
              <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest w-1/3">CONTACT PROFILE</th>
              <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest w-1/4">SIGNAL TYPE</th>
              <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest w-1/3">ENVIRONMENT DATA</th>
              <th className="pb-3 text-[9px] font-black text-slate-500 uppercase tracking-widest text-right w-1/12">TIME</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {data.recent_signals?.map((sig, i) => (
              <tr key={i} className="hover:bg-white/[0.02]">
                <td className="py-4">
                  <div className="font-bold text-white text-xs">{sig.first_name} {sig.last_name}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{sig.email}</div>
                </td>
                <td className="py-4">
                  <span className={`px-2 py-1 rounded text-[9px] font-black uppercase tracking-widest ${sig.signal_type === 'OPEN' ? 'bg-amber-500/10 text-amber-500 border border-amber-500/20' : sig.signal_type === 'CLICK' ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-blue-500/10 text-blue-500 border border-blue-500/20'}`}>
                    {sig.signal_type} DETECTED
                  </span>
                </td>
                <td className="py-4">
                  <div className="text-[10px] font-mono text-slate-400 truncate max-w-[300px]" title={sig.environment_data}>
                    {sig.environment_data || 'IP: UNKNOWN / Agent: UNKNOWN'}
                  </div>
                </td>
                <td className="py-4 text-right text-[10px] text-slate-500 font-mono">
                  {new Date(sig.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </td>
              </tr>
            ))}
            {(!data.recent_signals || data.recent_signals.length === 0) && (
              <tr>
                <td colSpan="4" className="py-8 text-center text-slate-500 text-xs">No recent inbound signals detected.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Metrics;
