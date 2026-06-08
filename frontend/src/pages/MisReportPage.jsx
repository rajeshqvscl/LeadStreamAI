import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import html2canvas from 'html2canvas';
import jsPDF from 'jspdf';
import { PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

const COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'];

const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
];

const getMonthRange = (year, month) => {
  const start = `${year}-${String(month + 1).padStart(2, '0')}-01`;
  const lastDay = new Date(year, month + 1, 0).getDate();
  const end = `${year}-${String(month + 1).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
  return { start, end };
};

const MisReportPage = () => {
  const navigate = useNavigate();
  const now = new Date();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [selYear, setSelYear] = useState(now.getFullYear());
  const [selMonth, setSelMonth] = useState(now.getMonth());
  const reportRef = useRef();

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const { start, end } = getMonthRange(selYear, selMonth);
        const res = await api.get(`/api/metrics?period=all&date_from=${start}&date_to=${end}&_t=${Date.now()}`);
        setData(res.data);
      } catch (err) {
        console.error('Failed to load report data', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [selYear, selMonth]);

  const handleDownloadPDF = useCallback(async () => {
    if (!reportRef.current) return;
    setDownloading(true);
    try {
      const pages = reportRef.current.querySelectorAll('[data-page]');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pageW = 210;
      const pageH = 297;

      for (let i = 0; i < pages.length; i++) {
        const canvas = await html2canvas(pages[i], {
          scale: 2,
          useCORS: true,
          backgroundColor: '#ffffff',
          logging: false,
          foreignObjectRendering: true
        });
        const imgData = canvas.toDataURL('image/jpeg', 0.95);
        const imgW = pageW - 20;
        const imgH = (canvas.height / canvas.width) * imgW;

        if (i > 0) pdf.addPage();
        pdf.addImage(imgData, 'JPEG', 10, 10, imgW, imgH);
      }

      pdf.save(`MIS_Report_${MONTHS[selMonth]}_${selYear}.pdf`);
    } catch (err) {
      console.error('PDF generation failed', err);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setDownloading(false);
    }
  }, [selMonth, selYear]);

  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 font-semibold">Generating MIS Report...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <p className="text-red-500 font-semibold">Failed to load report data.</p>
      </div>
    );
  }

  const { report = [], reverted, today_sent, today_followups, daily_limit, total_registry, bounces, drafts_generated } = data;
  const personaData = data.persona_breakdown ? Object.entries(data.persona_breakdown).map(([k, v]) => ({ name: k, value: v })) : [];
  const industryData = data.industry_breakdown ? Object.entries(data.industry_breakdown).map(([k, v]) => ({ name: k, value: v })) : [];
  const countryData = data.country_breakdown ? Object.entries(data.country_breakdown).map(([k, v]) => ({ name: k, value: v })) : [];

  const actionCounts = {};
  report.forEach(r => { actionCounts[r.action] = (actionCounts[r.action] || 0) + 1; });
  const actionData = Object.entries(actionCounts).map(([k, v]) => ({ name: k, value: v }));

  const topLeads = [...report].filter(r => r.action !== 'Pending').slice(0, 10);
  const monthLabel = `${MONTHS[selMonth]} ${selYear}`;

  const years = [];
  for (let y = now.getFullYear() - 2; y <= now.getFullYear(); y++) years.push(y);

  return (
    <div className="bg-gray-50 min-h-screen">
      <div className="print:hidden fixed top-0 left-0 right-0 z-50 bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <button onClick={() => navigate(-1)} className="text-gray-500 hover:text-gray-700 text-sm font-medium">&larr; Back</button>
          <span className="text-gray-300">|</span>
          <select value={selYear} onChange={e => setSelYear(Number(e.target.value))}
            className="text-sm font-semibold text-gray-700 bg-gray-100 border border-gray-200 rounded-lg px-2 py-1">
            {years.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <select value={selMonth} onChange={e => setSelMonth(Number(e.target.value))}
            className="text-sm font-semibold text-gray-700 bg-gray-100 border border-gray-200 rounded-lg px-2 py-1">
            {MONTHS.map((m, i) => <option key={i} value={i}>{m}</option>)}
          </select>
          <span className="text-gray-300">|</span>
          <span className="text-gray-700 font-bold text-sm">MIS Report — {monthLabel}</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleDownloadPDF} disabled={downloading}
            className="px-5 py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold hover:bg-emerald-700 shadow-sm disabled:opacity-50">
            {downloading ? 'Downloading...' : 'Download PDF'}
          </button>
        </div>
      </div>

      <div ref={reportRef} className="max-w-[210mm] mx-auto bg-white shadow-lg" style={{ paddingTop: '60px' }}>
        <style>{`
          @page { size: A4; margin: 20mm 15mm; }
          @media print {
            body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
            .page-break { page-break-before: always; }
            .no-break { page-break-inside: avoid; }
          }
          .report-table { width: 100%; border-collapse: collapse; font-size: 10px; }
          .report-table th { background: #1e1b4b; color: white; padding: 8px 10px; text-align: left; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 8px; }
          .report-table td { padding: 7px 10px; border-bottom: 1px solid #e5e7eb; color: #374151; }
          .report-table tr:nth-child(even) td { background: #f9fafb; }
          .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 8px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; }
          .bar-bg { background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden; }
          .bar-fill { height: 100%; border-radius: 4px; }
          .kpi-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px 16px; text-align: center; }
          .kpi-value { font-size: 24px; font-weight: 800; color: #1e1b4b; }
          .kpi-label { font-size: 9px; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; font-weight: 600; margin-top: 2px; }
          .section-title { font-size: 16px; font-weight: 800; color: #1e1b4b; border-bottom: 3px solid #6366f1; padding-bottom: 6px; margin-bottom: 16px; }
          .cover-title { font-size: 36px; font-weight: 900; color: #1e1b4b; letter-spacing: -1px; }
          .cover-sub { font-size: 14px; color: #6b7280; margin-top: 8px; }
        `}</style>

        {/* PAGE 1: COVER */}
        <div data-page="cover" className="px-12 py-16" style={{ pageBreakAfter: 'always' }}>
          <div className="w-16 h-1 bg-indigo-600 mb-8" />
          <div className="cover-title">Management<br />Information<br />System Report</div>
          <div className="cover-sub mb-12">{monthLabel}</div>
          <div className="border-t border-gray-200 pt-6">
            <table className="text-sm text-gray-600" style={{ width: '100%' }}>
              <tbody>
                <tr><td className="font-semibold pr-8 py-1" style={{width: 140}}>Report Type</td><td>Monthly MIS Report</td></tr>
                <tr><td className="font-semibold pr-8 py-1">Period</td><td>{monthLabel}</td></tr>
                <tr><td className="font-semibold pr-8 py-1">Generated On</td><td>{new Date().toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</td></tr>
                <tr><td className="font-semibold pr-8 py-1">Prepared By</td><td>LeadStreamAI System</td></tr>
                <tr><td className="font-semibold pr-8 py-1">Classification</td><td>Internal — Management Only</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* PAGE 2: EXECUTIVE SUMMARY */}
        <div data-page="summary" className="page-break px-8 py-10">
          <h2 className="section-title">1. Executive Summary</h2>
          <p className="text-gray-600 text-sm leading-relaxed mb-6">
            This MIS report provides a comprehensive overview of the lead management and email outreach performance for {monthLabel}. 
            The data presented covers lead acquisition, engagement metrics, outreach effectiveness, and pipeline progression.
          </p>

          <div className="grid gap-4 mb-6 no-break" style={{display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px'}}>
            <div className="kpi-card"><div className="kpi-value">{reverted}</div><div className="kpi-label">Replied Leads</div></div>
            <div className="kpi-card"><div className="kpi-value">{data.sent || 0}</div><div className="kpi-label">Emails Sent</div></div>
            <div className="kpi-card"><div className="kpi-value">{today_followups || 0}</div><div className="kpi-label">Follow-ups</div></div>
            <div className="kpi-card"><div className="kpi-value">{drafts_generated}</div><div className="kpi-label">Drafts Pending</div></div>
            <div className="kpi-card"><div className="kpi-value">{bounces}</div><div className="kpi-label">Bounced</div></div>
          </div>

          <div className="no-break">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Key Highlights</h3>
            <ul className="text-sm text-gray-600 space-y-2" style={{listStyle: 'disc', paddingLeft: '20px'}}>
              <li><strong>{reverted}</strong> leads have responded to outreach — representing the active engagement pipeline.</li>
              <li><strong>{drafts_generated}</strong> drafts are pending in the review queue awaiting approval.</li>
              <li><strong>{data.sent || 0}</strong> emails dispatched during the reporting period.</li>
              <li><strong>{today_followups || 0}</strong> follow-up sequences triggered.</li>
              <li><strong>{total_registry}</strong> companies registered in the CRM database.</li>
              <li><strong>{bounces}</strong> emails bounced due to invalid or unreachable addresses.</li>
            </ul>
          </div>
        </div>

        {/* PAGE 3: LEAD PERFORMANCE */}
        <div data-page="leads" className="page-break px-8 py-10">
          <h2 className="section-title">2. Lead Performance Metrics</h2>

          <div className="no-break mb-8">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Lead Type Distribution</h3>
            <div className="flex gap-6 items-start">
              <div className="flex-1">
                <table className="report-table">
                  <thead><tr><th style={{width: '60%'}}>Type</th><th style={{textAlign: 'right'}}>Count</th><th style={{textAlign: 'right'}}>Share</th></tr></thead>
                  <tbody>
                    {personaData.map((item, i) => {
                      const total = personaData.reduce((s, x) => s + x.value, 0) || 1;
                      return (
                        <tr key={i}>
                          <td><span className="font-semibold text-gray-800">{item.name}</span></td>
                          <td style={{textAlign: 'right'}}>{item.value}</td>
                          <td style={{textAlign: 'right'}}>
                            <div style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px'}}>
                              <div className="bar-bg" style={{width: 80}}><div className="bar-fill" style={{width: `${(item.value/total)*100}%`, backgroundColor: COLORS[i % COLORS.length]}} /></div>
                              <span className="text-gray-500" style={{fontSize: 10}}>{((item.value/total)*100).toFixed(1)}%</span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                    {personaData.length === 0 && <tr><td colSpan="3" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No data available</td></tr>}
                  </tbody>
                </table>
              </div>
              {personaData.length > 0 && (
                <div className="w-[220px] h-[220px]" style={{ minWidth: 220 }}>
                  <PieChart width={220} height={220}>
                    <Pie data={personaData} dataKey="value" nameKey="name" cx={110} cy={110} outerRadius={80} innerRadius={40}>
                      {personaData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </div>
              )}
            </div>
          </div>

          <div className="no-break">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Pipeline Funnel</h3>
            <div className="flex gap-6 items-start">
              <div className="flex-1">
                <table className="report-table">
                  <thead><tr><th>Stage</th><th style={{textAlign: 'right'}}>Count</th></tr></thead>
                  <tbody>
                    {[
                      { label: 'Total Replied', value: reverted },
                      { label: 'Interested', value: data.unique_engaged || 0 },
                      { label: 'Drafts Generated', value: drafts_generated },
                      { label: 'Emails Sent', value: data.sent || 0 },
                      { label: 'Bounced', value: bounces },
                    ].filter(s => s.value > 0).map((s, i) => (
                      <tr key={i}><td><span className="font-semibold text-gray-800">{s.label}</span></td><td style={{textAlign: 'right'}}>{s.value}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {(() => {
                const funnel = [
                  { label: 'Total Replied', value: reverted },
                  { label: 'Interested', value: data.unique_engaged || 0 },
                  { label: 'Drafts Generated', value: drafts_generated },
                  { label: 'Emails Sent', value: data.sent || 0 },
                  { label: 'Bounced', value: bounces },
                ].filter(s => s.value > 0);
                return funnel.length > 0 ? (
                  <div className="w-[220px] h-[220px]" style={{ minWidth: 220 }}>
                    <BarChart width={220} height={220} data={funnel} layout="vertical" margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis type="category" dataKey="label" width={90} tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#6366f1" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </div>
                ) : null;
              })()}
            </div>
          </div>
        </div>

        {/* PAGE 4: ENGAGEMENT & SECTOR ANALYSIS */}
        <div data-page="engagement" className="page-break px-8 py-10">
          <h2 className="section-title">3. Engagement & Sector Analysis</h2>

          <div className="no-break mb-8">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Action Breakdown</h3>
            <div className="flex gap-6 items-start">
              <div className="flex-1">
                <table className="report-table">
                  <thead><tr><th>Status</th><th style={{textAlign: 'right'}}>Leads</th></tr></thead>
                  <tbody>
                    {actionData.map((item, i) => (
                      <tr key={i}><td><span className="font-semibold text-gray-800">{item.name}</span></td><td style={{textAlign: 'right'}}>{item.value}</td></tr>
                    ))}
                    {actionData.length === 0 && <tr><td colSpan="2" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No data available</td></tr>}
                  </tbody>
                </table>
              </div>
              {actionData.length > 0 && (
                <div className="w-[220px] h-[220px]" style={{ minWidth: 220 }}>
                  <PieChart width={220} height={220}>
                    <Pie data={actionData} dataKey="value" nameKey="name" cx={110} cy={110} outerRadius={80}>
                      {actionData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </div>
              )}
            </div>
          </div>

          <div className="no-break mb-8">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Sector / Industry Distribution</h3>
            <table className="report-table">
              <thead><tr><th style={{width: '60%'}}>Industry</th><th style={{textAlign: 'right'}}>Count</th><th style={{textAlign: 'right'}}>Share</th></tr></thead>
              <tbody>
                {industryData.map((item, i) => {
                  const total = industryData.reduce((s, x) => s + x.value, 0) || 1;
                  return (
                    <tr key={i}>
                      <td><span className="font-semibold text-gray-800">{item.name}</span></td>
                      <td style={{textAlign: 'right'}}>{item.value}</td>
                      <td style={{textAlign: 'right'}}>
                        <div style={{display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px'}}>
                          <div className="bar-bg" style={{width: 80}}><div className="bar-fill" style={{width: `${(item.value/total)*100}%`, backgroundColor: COLORS[(i + 2) % COLORS.length]}} /></div>
                          <span className="text-gray-500" style={{fontSize: 10}}>{((item.value/total)*100).toFixed(1)}%</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {industryData.length === 0 && <tr><td colSpan="3" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No data available</td></tr>}
              </tbody>
            </table>
          </div>

          <div className="no-break">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Geographic Coverage</h3>
            <table className="report-table">
              <thead><tr><th style={{width: '60%'}}>Country</th><th style={{textAlign: 'right'}}>Count</th><th style={{textAlign: 'right'}}>Share</th></tr></thead>
              <tbody>
                {countryData.map((item, i) => {
                  const total = countryData.reduce((s, x) => s + x.value, 0) || 1;
                  return (
                    <tr key={i}>
                      <td><span className="font-semibold text-gray-800">{item.name}</span></td>
                      <td style={{textAlign: 'right'}}>{item.value}</td>
                      <td style={{textAlign: 'right'}}>{((item.value/total)*100).toFixed(1)}%</td>
                    </tr>
                  );
                })}
                {countryData.length === 0 && <tr><td colSpan="3" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No data available</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        {/* PAGE 5: TOP LEADS */}
        <div data-page="topleads" className="page-break px-8 py-10">
          <h2 className="section-title">4. Top Responded Leads</h2>
          <p className="text-gray-600 text-sm leading-relaxed mb-4">
            The following leads have shown the highest engagement during this reporting period.
          </p>

          <table className="report-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Name</th>
                <th>Company</th>
                <th>Sector</th>
                <th>Action</th>
                <th>Follow-up</th>
              </tr>
            </thead>
            <tbody>
              {topLeads.map((lead, i) => (
                <tr key={i}>
                  <td style={{color: '#9ca3af', fontWeight: 600}}>{i + 1}</td>
                  <td className="font-semibold text-gray-800">{lead.name || '—'}</td>
                  <td>{lead.company || '—'}</td>
                  <td>{lead.sector}</td>
                  <td><span className="badge" style={{
                    backgroundColor: lead.action === 'Rejected' ? '#fef2f2' : lead.action === 'Bounced' ? '#fff7ed' : lead.action === 'Clicked' ? '#ecfdf5' : lead.action === 'Opened' ? '#eff6ff' : lead.action === 'Replied' ? '#f5f3ff' : '#f9fafb',
                    color: lead.action === 'Rejected' ? '#dc2626' : lead.action === 'Bounced' ? '#ea580c' : lead.action === 'Clicked' ? '#059669' : lead.action === 'Opened' ? '#2563eb' : lead.action === 'Replied' ? '#7c3aed' : '#6b7280',
                    border: `1px solid ${
                      lead.action === 'Rejected' ? '#fecaca' : lead.action === 'Bounced' ? '#fed7aa' : lead.action === 'Clicked' ? '#a7f3d0' : lead.action === 'Opened' ? '#bfdbfe' : lead.action === 'Replied' ? '#ddd6fe' : '#e5e7eb'
                    }`
                  }}>{lead.action}</span></td>
                  <td>{lead.followup}</td>
                </tr>
              ))}
              {topLeads.length === 0 && <tr><td colSpan="6" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No engaged leads found</td></tr>}
            </tbody>
          </table>
        </div>

        {/* PAGE 6: FOLLOW-UP PERFORMANCE */}
        <div data-page="followup" className="page-break px-8 py-10">
          <h2 className="section-title">5. Follow-Up Performance</h2>
          <p className="text-gray-600 text-sm leading-relaxed mb-4">
            Follow-up sequence performance across the pipeline.
          </p>

          <div className="no-break mb-6">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Follow-Up Stage Distribution</h3>
            <div className="flex gap-6 items-start">
              <div className="flex-1">
                <table className="report-table">
                  <thead><tr><th>Status</th><th style={{textAlign: 'right'}}>Leads</th></tr></thead>
                  <tbody>
                    {(() => {
                      const stages = {};
                      report.forEach(r => {
                        const key = r.followup;
                        stages[key] = (stages[key] || 0) + 1;
                      });
                      const sorted = Object.entries(stages).sort((a, b) => b[1] - a[1]);
                      return sorted.length ? sorted.map(([k, v], i) => (
                        <tr key={i}><td><span className="font-semibold text-gray-800">{k}</span></td><td style={{textAlign: 'right'}}>{v}</td></tr>
                      )) : <tr><td colSpan="2" style={{textAlign: 'center', padding: 20, color: '#9ca3af'}}>No follow-up data</td></tr>;
                    })()}
                  </tbody>
                </table>
              </div>
              {(() => {
                const stages = {};
                report.forEach(r => {
                  const key = r.followup;
                  stages[key] = (stages[key] || 0) + 1;
                });
                const sorted = Object.entries(stages).sort((a, b) => b[1] - a[1]);
                return sorted.length > 0 ? (
                  <div className="w-[220px] h-[220px]" style={{ minWidth: 220 }}>
                    <BarChart width={220} height={220} data={sorted.map(([k, v]) => ({ name: k, value: v }))} layout="vertical" margin={{ left: 10, right: 10, top: 5, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis type="category" dataKey="name" width={80} tick={{ fontSize: 10 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#10b981" radius={[0, 3, 3, 0]} />
                    </BarChart>
                  </div>
                ) : null;
              })()}
            </div>
          </div>

          <div className="no-break">
            <h3 className="text-sm font-bold text-gray-800 mb-3" style={{fontSize: '13px', fontWeight: 700}}>Engagement Rates</h3>
            <table className="report-table">
              <thead><tr><th>Metric</th><th style={{textAlign: 'right'}}>Value</th></tr></thead>
              <tbody>
                <tr><td><span className="font-semibold text-gray-800">Open Rate</span></td><td style={{textAlign: 'right'}}>{data.open_rate || 0}%</td></tr>
                <tr><td><span className="font-semibold text-gray-800">Engagement Rate</span></td><td style={{textAlign: 'right'}}>{data.engagement_rate || 0}%</td></tr>
                <tr><td><span className="font-semibold text-gray-800">Bounce Rate</span></td><td style={{textAlign: 'right'}}>{data.bounce_rate || 0}%</td></tr>
                <tr><td><span className="font-semibold text-gray-800">Conversion Rate</span></td><td style={{textAlign: 'right'}}>{data.conversion_rate || 0}%</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* PAGE 7: INSIGHTS */}
        <div data-page="insights" className="page-break px-8 py-10">
          <h2 className="section-title">6. Insights & Recommendations</h2>

          <div className="space-y-6">
            <div className="no-break border border-indigo-100 rounded-lg p-5 bg-indigo-50/50">
              <h3 className="text-sm font-bold text-indigo-800 mb-2" style={{fontSize: '13px'}}>Lead Engagement</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {reverted > 0
                  ? `${reverted} leads have responded to outreach efforts, indicating active interest in the pipeline. Focus on nurturing these leads through personalized follow-up sequences.`
                  : 'No leads have responded yet. Consider reviewing email copy quality, target list accuracy, and follow-up cadence.'}
              </p>
            </div>

            <div className="no-break border border-emerald-100 rounded-lg p-5 bg-emerald-50/50">
              <h3 className="text-sm font-bold text-emerald-800 mb-2" style={{fontSize: '13px'}}>Outreach Performance</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {data.sent > 0
                  ? `${data.sent} emails dispatched in the reporting period. ${bounces > 0 ? `${bounces} bounced — review email list hygiene.` : 'No bounces recorded — list quality is good.'}`
                  : 'No emails sent this period. Check auto-pilot settings and daily limit configuration.'}
              </p>
            </div>

            <div className="no-break border border-amber-100 rounded-lg p-5 bg-amber-50/50">
              <h3 className="text-sm font-bold text-amber-800 mb-2" style={{fontSize: '13px'}}>Pipeline Health</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {drafts_generated > 0
                  ? `${drafts_generated} drafts pending approval in the review queue. Approving and dispatching these will increase outreach volume.`
                  : 'No pending drafts. Generate new drafts from templates to maintain pipeline momentum.'}
              </p>
            </div>
          </div>
        </div>

        {/* PAGE 8: FOOTER */}
        <div data-page="footer" className="page-break px-8 py-10 flex flex-col justify-end min-h-[500px]">
          <div className="border-t-2 border-indigo-600 pt-6">
            <h3 className="text-lg font-bold text-gray-800 mb-2">LeadStreamAI</h3>
            <p className="text-sm text-gray-500">Automated Management Information System Report</p>
            <p className="text-sm text-gray-400 mt-1">Generated on {new Date().toLocaleString('en-IN', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</p>
          </div>
          <div className="mt-8 text-xs text-gray-400">
            <p>This report is computer-generated and does not require a signature. Data is based on system records as of the generation date.</p>
            <p className="mt-1">Confidential — For internal management use only.</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MisReportPage;
