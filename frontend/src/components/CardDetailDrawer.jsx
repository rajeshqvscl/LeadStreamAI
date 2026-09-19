import React from 'react';
import { FileText, Loader2, X } from 'lucide-react';

const MONTHS = [
  { value: 0, label: 'All Months' },
  { value: 1, label: 'January' }, { value: 2, label: 'February' }, { value: 3, label: 'March' },
  { value: 4, label: 'April' }, { value: 5, label: 'May' }, { value: 6, label: 'June' },
  { value: 7, label: 'July' }, { value: 8, label: 'August' }, { value: 9, label: 'September' },
  { value: 10, label: 'October' }, { value: 11, label: 'November' }, { value: 12, label: 'December' }
];

const EMPTY_MESSAGES = {
  ingested: ['No leads ingested yet', 'The system hasn\'t sourced any leads yet. Run a bulk search or enable AI discovery to populate your pipeline.'],
  pipeline: ['No replies received', 'No leads have responded to your outreach yet. Follow up with leads in your pipeline to start conversations.'],
  classified: ['No leads classified', 'AI classification hasn\'t processed any leads yet. Enable auto-classification in settings to analyze lead personas automatically.'],
  pending: ['Approval queue is clear', 'No emails are pending your review. All caught up! New drafts will appear here once generated.'],
  refined: ['No drafts generated', 'No email drafts have been created yet. Generate drafts for your leads to start your outreach campaigns.'],
  unsubscribed: ['No unsubscribes recorded', 'Your unsubscribe list is clean. No leads have opted out of your communications.'],
  outbound: ['No emails sent yet', 'Your outbound limit hasn\'t been used yet. Start sending emails to track your daily usage here.'],
  followups: ['No follow-ups dispatched', 'No follow-up sequences have been triggered yet. They will appear here once scheduled.'],
  open_rate_detail: ['No opens tracked yet', 'No email opens have been recorded. Ensure your emails include tracking pixels to measure open rates accurately.'],
  click_rate_detail: ['No clicks tracked yet', 'No link clicks have been recorded. Add trackable links to your emails to measure engagement.'],
  bounce_detail: ['No bounces detected', 'Your deliverability looks healthy! No emails have bounced back.'],
  optouts_detail: ['No opt-outs recorded', 'No leads have opted out. Your email content is resonating well with your audience.'],
  meeting_requests: ['No meeting requests', 'No leads have proposed a meeting time yet. Replies with meeting requests will appear here automatically.']
};

const formatIST = (dateStr, short) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (short) {
      return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
    }
    return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' })
      + ', ' + d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })
      + ' IST';
  } catch { return dateStr; }
};

const CardDetailDrawer = React.memo(({ detailModal, detailData, detailLoading, filterMonth, filterYear, detailPage, onFilterMonthChange, onFilterYearChange, onPageChange, onClose, onFetchCardDetail }) => {
  if (!detailModal.open) return null;

  return (
    <div className="fixed inset-0 z-[500] flex justify-end animate-in fade-in duration-300" role="dialog" aria-label={detailModal.title}>
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-md" onClick={onClose}></div>
      <div className="relative w-full max-w-[700px] bg-[#0b0f1a] border-l border-white/5 shadow-[0_0_80px_rgba(0,0,0,0.9)] flex flex-col h-full animate-in slide-in-from-right duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]">
        {/* Header */}
        <div className="p-8 border-b border-white/[0.03] flex items-center justify-between bg-gradient-to-r from-blue-500/[0.02] to-transparent">
          <div className="flex items-center gap-5">
            <div className="w-14 h-14 rounded-[20px] bg-gradient-to-br from-blue-600/20 to-indigo-600/20 border border-blue-500/10 flex items-center justify-center text-blue-400">
              <FileText size={26} strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-[20px] font-black text-white tracking-tight leading-none mb-2">{detailModal.title}</h2>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-bold text-slate-500 uppercase tracking-[3px]">
                  {detailData.total} Records
                </span>
                <div className="w-px h-3 bg-white/10" />
                <span className="text-[10px] font-bold text-blue-500 uppercase tracking-[3px]">
                  Page {detailData.page} of {Math.max(1, Math.ceil(detailData.total / 100))}
                </span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={onClose} aria-label="Close details" className="p-4 bg-rose-500/10 hover:bg-rose-500/20 rounded-2xl transition-all text-rose-500 hover:text-rose-400 active:scale-95 shadow-xl border border-rose-500/10 cursor-pointer">
              <X size={20} />
            </button>
          </div>
        </div>

        {/* Month Filter */}
        {detailModal.type !== 'meeting_requests' && (
          <div className="px-8 py-4 border-b border-white/5 flex items-center gap-3">
            <label htmlFor="detail-filter-month" className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Filter by Month:</label>
            <select
              id="detail-filter-month"
              aria-label="Filter by month"
              value={filterMonth}
              onChange={(e) => onFilterMonthChange(Number(e.target.value))}
              className="bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50"
            >
              {MONTHS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
            <label htmlFor="detail-filter-year" className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Year:</label>
            <select
              id="detail-filter-year"
              aria-label="Filter by year"
              value={filterYear}
              onChange={(e) => onFilterYearChange(Number(e.target.value))}
              className="bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50"
            >
              {[2024, 2025, 2026, 2027].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        )}

        {/* Records Table */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
          {detailLoading ? (
            <div className="flex items-center justify-center h-full">
              <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
            </div>
          ) : detailData.records.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center px-8">
              <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-5">
                <FileText className="w-7 h-7 text-slate-600" />
              </div>
              <p className="text-[13px] font-black text-slate-400 uppercase tracking-widest mb-2">
                {(EMPTY_MESSAGES[detailModal.type] || ['No records found'])[0]}
              </p>
              <p className="text-[10px] text-slate-600 font-medium max-w-[300px] leading-relaxed">
                {(EMPTY_MESSAGES[detailModal.type] || ['', 'No data available for this period.'])[1]}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {detailModal.type === 'classified' && detailData.followup_summary && (
                <div className="p-4 bg-white/[0.02] border border-white/5 rounded-xl flex items-center gap-4 flex-wrap">
                  <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Follow-up Status:</span>
                  {detailData.followup_summary.map((s, i) => (
                    <span key={i} className="text-[10px] font-bold px-3 py-1 rounded-full border text-white/80" style={{
                      borderColor: s.followup_status === 'ACTIVE' ? 'rgba(59,130,246,0.3)' : s.followup_status === 'COMPLETED' ? 'rgba(16,185,129,0.3)' : s.followup_status === 'STOPPED' ? 'rgba(245,158,11,0.3)' : 'rgba(100,116,139,0.3)',
                      background: s.followup_status === 'ACTIVE' ? 'rgba(59,130,246,0.1)' : s.followup_status === 'COMPLETED' ? 'rgba(16,185,129,0.1)' : s.followup_status === 'STOPPED' ? 'rgba(245,158,11,0.1)' : 'rgba(100,116,139,0.1)'
                    }}>
                      {s.followup_status || 'NONE'}: {s.cnt}
                    </span>
                  ))}
                </div>
              )}

              {detailModal.type === 'bounce_detail' && detailData.company_breakdown && detailData.company_breakdown.length > 0 && (
                <div className="p-4 bg-white/[0.02] border border-white/5 rounded-xl">
                  <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest block mb-3">Top Companies Bounced:</span>
                  <div className="flex flex-wrap gap-2">
                    {detailData.company_breakdown.map((c, i) => (
                      <span key={i} className="text-[10px] font-bold px-3 py-1.5 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-400">
                        {c.company_name}: {c.count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {detailModal.type === 'meeting_requests' && detailData.records.map((rec, i) => (
                <div key={rec.id || i} className="p-4 bg-white/[0.02] border border-white/[0.03] rounded-xl hover:bg-white/[0.04] transition-all group">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-rose-600/20 to-pink-600/20 border border-rose-500/10 flex items-center justify-center text-[10px] font-black text-rose-400 shrink-0">
                        {(rec.title || 'MR').charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <span className="text-[11px] font-bold text-white truncate block">{rec.title || 'Meeting Request'}</span>
                        <span className="text-[9px] font-medium text-slate-500">{rec.priority || 'MEDIUM'} Priority</span>
                      </div>
                    </div>
                    <div className="text-[8px] font-bold text-slate-600 uppercase tracking-widest shrink-0">
                      {rec.due_at ? formatIST(rec.due_at, true) : ''}
                    </div>
                  </div>
                  <div className="text-[9px] text-slate-400 leading-relaxed mt-1 whitespace-pre-wrap line-clamp-2">
                    {rec.description || ''}
                  </div>
                  <div className="flex items-center gap-2 mt-2">
                    <span className={`px-2 py-0.5 rounded-full text-[8px] font-black ${
                      rec.status === 'PENDING' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      rec.status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                      'bg-slate-500/10 text-slate-400 border border-slate-500/20'
                    }`}>
                      {rec.status || 'PENDING'}
                    </span>
                    {rec.user_name && (
                      <span className="text-[8px] font-medium text-slate-600">by {rec.user_name}</span>
                    )}
                  </div>
                </div>
              ))}

              {detailModal.type !== 'meeting_requests' && detailData.records.map((rec, i) => (
                <div key={rec.id || i} className="p-4 bg-white/[0.02] border border-white/[0.03] rounded-xl hover:bg-white/[0.04] transition-all group">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-600/20 to-indigo-600/20 border border-blue-500/10 flex items-center justify-center text-[10px] font-black text-blue-400 shrink-0">
                        {((rec.first_name || '?').charAt(0) + (rec.last_name || '?').charAt(0)).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <span className="text-[11px] font-bold text-white">{[rec.first_name, rec.last_name].filter(Boolean).join(' ') || rec.email?.split('@')[0] || 'Unknown'}</span>
                        <span className="text-[9px] font-medium text-slate-500 ml-2">{rec.email || ''}</span>
                      </div>
                    </div>
                    <div className="text-[8px] font-bold text-slate-600 uppercase tracking-widest shrink-0">
                      {rec.created_at ? formatIST(rec.created_at, true) : ''}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-[9px] font-bold text-slate-500 uppercase tracking-wider flex-wrap">
                    {rec.company_name && <span>{rec.company_name}</span>}
                    {rec.persona && <span className="text-blue-500/80">{rec.persona}</span>}
                    {rec.email_status && <span>{rec.email_status?.replace(/_/g, ' ')}</span>}
                    {rec.source && !rec.email_status && <span className="text-slate-600">{rec.source.replace(/_/g, ' ')}</span>}
                    {rec.reason && <span className="text-amber-500">{rec.reason}</span>}
                    {rec.is_unsubscribed && <span className="text-rose-500">Unsubscribed</span>}
                    {rec.followup_status && rec.followup_status !== 'IDLE' && (
                      <span className={`px-2 py-0.5 rounded text-[8px] font-black ${
                        rec.followup_status === 'ACTIVE' ? 'bg-blue-500/10 text-blue-400' :
                        rec.followup_status === 'COMPLETED' ? 'bg-emerald-500/10 text-emerald-400' :
                        rec.followup_status === 'STOPPED' ? 'bg-amber-500/10 text-amber-400' :
                        'bg-slate-500/10 text-slate-400'
                      }`}>
                        Follow-up: Stage {rec.followup_stage || 0} ({rec.followup_status})
                      </span>
                    )}
                    {rec.bounce_reason && (
                      <span className="text-rose-400/80 max-w-[250px] truncate" title={rec.bounce_reason}>
                        {rec.bounce_reason.replace(/^Email bounced\s*[—–-]\s*/i, '')}
                      </span>
                    )}
                    {rec.updated_at && rec.updated_at !== rec.created_at && (
                      <span className="text-slate-600">Updated {formatIST(rec.updated_at, true)}</span>
                    )}
                  </div>
                  {rec.draft_preview && (
                    <div className="mt-2 text-[9px] text-slate-600 italic line-clamp-1 border-l-2 border-blue-500/20 pl-2">{rec.draft_preview}...</div>
                  )}
                  {rec.details && (
                    <div className="mt-1 text-[8px] text-slate-600 font-mono truncate">{rec.details}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pagination */}
        {detailModal.type !== 'meeting_requests' && detailData.total > 100 && (
          <div className="px-8 py-5 border-t border-white/5 flex items-center justify-between bg-black/20">
            <button
              onClick={() => onPageChange(detailPage - 1)}
              disabled={detailPage <= 1}
              className="px-4 py-2 bg-white/5 rounded-xl text-[10px] font-black text-slate-300 uppercase tracking-widest hover:bg-white/10 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              Previous
            </button>
            <span className="text-[10px] font-bold text-slate-500">
              Page {detailData.page} of {Math.max(1, Math.ceil(detailData.total / 100))}
            </span>
            <button
              onClick={() => onPageChange(detailPage + 1)}
              disabled={detailPage >= Math.ceil(detailData.total / 100)}
              className="px-4 py-2 bg-white/5 rounded-xl text-[10px] font-black text-slate-300 uppercase tracking-widest hover:bg-white/10 transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </div>
  );
});

export default CardDetailDrawer;
