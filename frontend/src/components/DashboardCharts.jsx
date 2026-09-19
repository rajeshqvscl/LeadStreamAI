import React from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

export function VelocityChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data}>
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
  );
}

export function ProductivityChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} barGap={4} barCategoryGap="30%">
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
  );
}
