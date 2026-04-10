import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, Edit3, Loader2, Send, ChevronLeft, ChevronRight, X, Archive, CheckCircle2 } from 'lucide-react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import api from '../services/api';

const Emails = () => {
  const navigate = useNavigate();
  const [emails, setEmails] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total: 0 });
  const [selectedIds, setSelectedIds] = useState([]);
  const [filterStatus, setFilterStatus] = useState('');
  const [filterRegion, setFilterRegion] = useState('');
  const [filterGeo, setFilterGeo] = useState('');
  const [filterCompany, setFilterCompany] = useState('');
  const [isBatchSending, setIsBatchSending] = useState(false);
  const [notification, setNotification] = useState(null);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectingIds, setRejectingIds] = useState([]);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showScheduleModal, setShowScheduleModal] = useState(false);
  const [scheduledAt, setScheduledAt] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchEmails = async () => {
    try {
      setIsLoading(true);
      const res = await api.get(`/api/emails?page=${pagination.page}&status=${filterStatus}&region=${filterRegion}&geo=${filterGeo}&company=${filterCompany}`);
      setEmails(res.data.drafts);
      setPagination(prev => ({ ...prev, total: res.data.pages }));
    } catch {
      showNotification('error', 'Failed to fetch emails');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchEmails();
    }, 500);
    return () => clearTimeout(timer);
  }, [pagination.page, filterStatus, filterRegion, filterGeo, filterCompany]);

  const handleApprove = async (id) => {
    try {
      await api.post(`/api/approve-email/${id}`, { approved_by: 'admin' });
      showNotification('success', 'Email approved successfully');
      fetchEmails();
    } catch {
      showNotification('error', 'Approval failed');
    }
  };

  const handleReject = (id) => {
    setRejectingIds([id]);
    setRejectionReason('');
    setShowRejectModal(true);
  };

  const confirmReject = async () => {
    if (!rejectionReason.trim()) {
      showNotification('error', 'Please provide a reason');
      return;
    }
    
    try {
      if (rejectingIds.length === 1) {
        await api.post(`/api/reject-email/${rejectingIds[0]}`, { rejected_reason: rejectionReason });
      } else {
        await api.post('/api/emails/bulk-action', {
          lead_ids: rejectingIds,
          action: 'REJECTED',
          reason: rejectionReason
        });
      }
      showNotification('success', `${rejectingIds.length > 1 ? 'Drafts' : 'Draft'} rejected`);
      setShowRejectModal(false);
      setSelectedIds([]);
      fetchEmails();
    } catch {
      showNotification('error', 'Rejection failed');
    }
  };

  const handleBulkAction = async (action) => {
    if (selectedIds.length === 0) return;
    
    if (action === 'REJECTED') {
      setRejectingIds(selectedIds);
      setRejectionReason('');
      setShowRejectModal(true);
      return;
    }

    try {
      await api.post('/api/emails/bulk-action', {
        lead_ids: selectedIds,
        action: action
      });
      showNotification('success', `Successfully updated ${selectedIds.length} leads to ${action}`);
      setSelectedIds([]);
      fetchEmails();
    } catch {
      showNotification('error', 'Bulk action failed');
    }
  };

  const confirmBulkSchedule = async () => {
    if (!scheduledAt) {
      showNotification('error', 'Please select a date and time');
      return;
    }
    try {
      const isoString = new Date(scheduledAt).toISOString();
      await api.post('/api/emails/bulk-schedule', {
        lead_ids: selectedIds,
        scheduled_at: isoString
      });
      showNotification('success', `Successfully scheduled ${selectedIds.length} emails`);
      setSelectedIds([]);
      setShowScheduleModal(false);
      fetchEmails();
    } catch {
      showNotification('error', 'Bulk scheduling failed');
    }
  };

  const toggleSelectRow = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === emails.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(emails.map(e => e.id));
    }
  };

  const handleOptOut = (leadId) => {
    setPendingOptOut(leadId);
  };

  const confirmOptOut = async () => {
    const leadId = pendingOptOut;
    setPendingOptOut(null);
    try {
      await api.post(`/api/leads/${leadId}/unsubscribe`);
      showNotification('success', 'Lead opted out and blacklisted');
      fetchEmails();
    } catch {
      showNotification('error', 'Opt-out failed');
    }
  };

  const sendApprovedBatch = async () => {
    if (!window.confirm('Send all approved emails now?')) return;
    setIsBatchSending(true);
    try {
      const response = await api.post('/api/send-approved-batch');
      showNotification('success', response.data.message || 'Batch dispatched successfully');
      fetchEmails();
    } catch {
      showNotification('error', 'Batch send failed');
    } finally {
      setIsBatchSending(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-[28px] font-bold text-white tracking-tight">Review Queue</h1>
          <p className="text-[#64748b] text-[12px] font-medium mt-1">
            <span className="font-bold text-slate-400">{pagination.total} drafts total</span> — Human-in-the-loop verification for AI outreach.
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={sendApprovedBatch}
            disabled={isBatchSending}
            className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 font-bold text-[11px] px-4 py-2 rounded-md transition-colors disabled:opacity-50"
          >
            {isBatchSending ? 'Dispatching...' : 'Send All Approved'}
          </button>
          <span className="text-[#64748b] text-[10px] font-bold tracking-widest uppercase">Total campaigns: 6/10</span>
        </div>
      </div>

      <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl">
        {/* Filter Bar */}
        <div className="px-6 py-4 border-b border-[#ffffff08] flex items-center gap-3 bg-[#0f121b]/50">
          <div className="relative">
            <select
              className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 pr-8 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="">STATUS: All Stages</option>
              <option value="PENDING_APPROVAL">STATUS: Pending</option>
              <option value="APPROVED">STATUS: Approved</option>
              <option value="SCHEDULED">STATUS: Scheduled</option>
              <option value="SENT">STATUS: Sent</option>
              <option value="REJECTED">STATUS: Rejected</option>
              <option value="FAILED">STATUS: Failed</option>
              <option value="ARCHIVED">STATUS: Archived</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <div className="relative">
            <select
              className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 pr-8 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50 cursor-pointer"
              value={filterRegion}
              onChange={(e) => setFilterRegion(e.target.value)}
            >
              <option value="">REGION: All Regions</option>
              <option value="US">US / Canada</option>
              <option value="EU">Europe</option>
              <option value="APAC">APAC</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <div className="relative">
            <select
              className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 pr-8 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50 cursor-pointer"
              value={filterGeo}
              onChange={(e) => setFilterGeo(e.target.value)}
            >
              <option value="">GEO: Global Coverage</option>
              <option value="Tier1">Tier 1 Markets</option>
              <option value="Emerging">Emerging Markets</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <div className="relative">
            <input
              type="text"
              placeholder="COMPANY / INVESTOR..."
              className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50 w-[140px]"
              value={filterCompany}
              onChange={(e) => setFilterCompany(e.target.value)}
            />
          </div>

          <button
            onClick={() => { setFilterStatus(''); setFilterRegion(''); setFilterGeo(''); setFilterCompany(''); }}
            className="px-3 py-1.5 rounded-md text-[10px] font-bold text-slate-400 hover:text-white uppercase tracking-widest transition-colors ml-1 cursor-pointer"
          >
            Reset
          </button>
        </div>

        {/* Full-width Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0f121b]/80">
                <th className="w-16 px-6 py-4 border-b border-[#ffffff08] text-center">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                    checked={selectedIds.length === emails.length && emails.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">LEAD</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">COMPANY / INVESTOR</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">SUBJECT LINE</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">STATE</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">OPENS/BOUNCE</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">VERIFIED</th>
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08] text-right">ACTIONS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ffffff08]">
              {isLoading ? (
                <tr><td colSpan="6" className="px-6 py-20 text-center"><Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto" /></td></tr>
              ) : emails.length === 0 ? (
                <tr><td colSpan="6" className="px-6 py-20 text-center text-[#64748b] font-bold uppercase tracking-[2px] text-[10px]">No outreach drafts found.</td></tr>
              ) : emails.map(email => (
                <tr key={email.id} className={`hover:bg-white/[0.02] transition-colors group ${selectedIds.includes(email.id) ? 'bg-blue-500/[0.03]' : ''}`}>
                  <td className="px-6 py-4 text-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                      checked={selectedIds.includes(email.id)}
                      onChange={() => toggleSelectRow(email.id)}
                    />
                  </td>
                  <td className="px-6 py-4">
                    <div className="font-bold text-white text-[12px] group-hover:text-blue-400 transition-colors cursor-pointer" onClick={() => navigate(`/dashboard/leads/${email.lead_id}`)}>{email.lead_name}</div>
                    <div className="text-[9px] text-[#64748b] font-medium tracking-wide mt-0.5">{email.lead_email}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-[11px] text-[#94a3b8] font-bold tracking-wide">{email.company_name || '—'}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-[#94a3b8] font-medium text-[11px] max-w-[300px] truncate">{email.subject || '—'}</div>
                  </td>
                  <td className="px-6 py-4">
                    {email.status === 'REJECTED' && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] bg-red-500 border border-red-500 text-white">REJECTED</span>
                    )}
                    {email.status === 'PENDING_APPROVAL' && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-[#f59e0b] text-[#f59e0b]">PENDING_APPROVAL</span>
                    )}
                    {(email.status === 'SENT' || email.status === 'APPROVED') && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-[#10b981] text-[#10b981]">{email.status}</span>
                    )}
                    {email.status === 'SCHEDULED' && (
                      <div className="flex flex-col gap-1 items-start">
                        <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-blue-400 text-blue-400">SCHEDULED</span>
                        {email.scheduled_at && (
                          <span className="text-[9px] text-[#94a3b8] font-bold">
                            {new Date(email.scheduled_at).toLocaleDateString('en-US', {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})}
                          </span>
                        )}
                      </div>
                    )}
                    {email.status === 'FAILED' && (
                      <span className="text-[8px] font-black uppercase tracking-[1px] text-red-500">FAILED</span>
                    )}
                    {email.status === 'ARCHIVED' && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-[#3b82f6] text-[#3b82f6]">ARCHIVED</span>
                    )}
                    {(!['REJECTED', 'PENDING_APPROVAL', 'SENT', 'APPROVED', 'SCHEDULED', 'FAILED', 'ARCHIVED'].includes(email.status)) && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-slate-500 text-slate-400">{email.status}</span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3 text-[10px] text-[#64748b] font-black">
                      <span className="flex items-center gap-1"><Eye className="w-3.5 h-3.5" /> 0</span>
                      <span className="flex items-center gap-1"><X className="w-3 h-3 text-red-500/50" /> 0</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {email.verifier ? (
                      <div className="text-[10px]">
                        <span className="text-white font-black">{email.verifier}</span>
                        <span className="block text-[#64748b] mt-0.5">{new Date(email.updated_at).toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: '2-digit' })}</span>
                      </div>
                    ) : (
                      <span className="text-[#64748b]">—</span>
                    )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2 items-center">
                      <button onClick={() => navigate(`/dashboard/emails/${email.id}/edit`)} className="p-2 rounded bg-white/5 hover:bg-white/10 text-slate-300 transition-all cursor-pointer" title="Edit/View Draft">
                        <Edit3 className="w-3.5 h-3.5" />
                      </button>
                      
                      {email.status === 'PENDING_APPROVAL' && (
                        <>
                          <button onClick={() => handleApprove(email.id)} className="p-2 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-all cursor-pointer" title="Approve & Send">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={() => handleReject(email.id)} className="p-2 rounded bg-red-500/10 hover:bg-red-500/20 text-red-400 transition-all cursor-pointer" title="Reject Draft">
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}

                      <button 
                        onClick={() => {
                          setSelectedIds([email.id]);
                          handleBulkAction('ARCHIVED');
                        }} 
                        className="p-2 rounded bg-white/5 hover:bg-white/10 text-slate-400 transition-all cursor-pointer" 
                        title="Archive Draft"
                      >
                        <Archive className="w-3.5 h-3.5" />
                      </button>

                      <button 
                        onClick={() => {
                          setSelectedIds([email.id]);
                          handleBulkAction('SENT');
                        }} 
                        className="p-2 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition-all cursor-pointer" 
                        title="Mark as Sent"
                      >
                        <Send className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Foot */}
        {pagination.total > 20 && (
          <div className="px-6 py-4 border-t border-[#ffffff08] flex justify-between items-center text-[11px] font-bold uppercase tracking-widest text-[#64748b]">
            <span>Showing {emails.length} of {pagination.total} drafts</span>
            <div className="flex gap-2">
              <button className="p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors text-white disabled:opacity-30" disabled={pagination.page === 1} onClick={() => setPagination(v => ({ ...v, page: v.page - 1 }))}><ChevronLeft className="w-4 h-4" /></button>
              <button className="p-1.5 rounded bg-white/5 hover:bg-white/10 transition-colors text-white disabled:opacity-30" disabled={emails.length < 20} onClick={() => setPagination(v => ({ ...v, page: v.page + 1 }))}><ChevronRight className="w-4 h-4" /></button>
            </div>
          </div>
        )}
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 z-[4000] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
          <div className="w-full max-w-md bg-[#0d1117] border border-red-500/20 rounded-[28px] overflow-hidden shadow-[0_0_50px_rgba(239,68,68,0.1)] p-8 space-y-6">
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-red-500/10 rounded-2xl flex items-center justify-center text-red-500 mx-auto">
                <X className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-black text-white uppercase tracking-tight">Reject {rejectingIds.length > 1 ? 'Batch' : 'Draft'}</h3>
              <p className="text-slate-500 text-[11px] font-black uppercase tracking-[2px]">Provide a reason for the AI to refine future drafts</p>
            </div>
            
            <textarea
              className="w-full bg-[#131722] border border-white/10 rounded-2xl p-4 text-white text-[12px] min-h-[120px] focus:outline-none focus:border-red-500/30 transition-all font-medium placeholder:text-slate-700"
              placeholder="e.g. Tone is too aggressive, company name is incorrect..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
            />
            
            <div className="flex flex-col gap-3">
              <button 
                onClick={confirmReject}
                className="w-full py-4 bg-red-600 hover:bg-red-500 text-white text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all shadow-lg shadow-red-500/20 active:scale-[0.98] cursor-pointer"
              >
                Confirm Rejection
              </button>
              <button 
                onClick={() => setShowRejectModal(false)}
                className="w-full py-4 bg-white/5 hover:bg-white/10 text-slate-400 text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 z-[4000] flex items-center justify-center p-4 bg-black/60 backdrop-blur-md animate-in fade-in duration-300">
          <div className="w-full max-w-md bg-[#0d1117] border border-blue-500/20 rounded-[28px] overflow-hidden shadow-[0_0_50px_rgba(59,130,246,0.1)] p-8 space-y-6">
            <div className="text-center space-y-4">
              <div className="w-14 h-14 bg-blue-500/10 rounded-2xl flex items-center justify-center text-blue-500 mx-auto">
                <Send className="w-7 h-7" />
              </div>
              <h3 className="text-lg font-black text-white uppercase tracking-tight">Schedule Bulk Dispatch</h3>
              <p className="text-slate-500 text-[11px] font-black uppercase tracking-[2px]">Select dispatch time for {selectedIds.length} drafts.</p>
            </div>
            
            <DatePicker
              selected={scheduledAt}
              onChange={(date) => setScheduledAt(date)}
              showTimeSelect
              timeFormat="HH:mm"
              timeIntervals={15}
              timeCaption="Time"
              dateFormat="MMMM d, yyyy h:mm aa"
              placeholderText="Select dispatch time"
              className="w-full bg-[#131722] border border-white/10 rounded-2xl p-4 text-white text-[13px] focus:outline-none focus:border-blue-500/50 transition-all font-medium"
              wrapperClassName="w-full"
              minDate={new Date()}
            />
            
            <div className="flex flex-col gap-3">
              <button 
                onClick={confirmBulkSchedule}
                disabled={!scheduledAt}
                className="w-full py-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all shadow-lg shadow-blue-500/20 active:scale-[0.98] cursor-pointer"
              >
                Confirm Schedule
              </button>
              <button 
                onClick={() => setShowScheduleModal(false)}
                className="w-full py-4 bg-white/5 hover:bg-white/10 text-slate-400 text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all cursor-pointer"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Bulk Action Bar */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-[3000] animate-in slide-in-from-bottom-10 duration-500">
          <div className="bg-[#131722]/90 border border-blue-500/30 px-8 py-5 rounded-[32px] shadow-[0_20px_50px_rgba(0,0,0,0.5)] backdrop-blur-2xl flex items-center gap-10 border-t-white/10">
            <div className="flex items-center gap-4 border-r border-white/10 pr-10">
              <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 font-black text-xs">
                {selectedIds.length}
              </div>
              <span className="text-[10px] font-black text-white uppercase tracking-widest">Drafts Selected</span>
            </div>
            
            <div className="flex items-center gap-4">
              <button 
                onClick={() => handleBulkAction('APPROVED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500 text-emerald-400 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-emerald-500/20"
              >
                Approve
              </button>
              <button 
                onClick={() => {
                  setScheduledAt(null);
                  setShowScheduleModal(true);
                }}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-[#1e293b]/50 hover:bg-[#1e293b] text-slate-300 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-white/10"
              >
                Schedule
              </button>
              <button 
                onClick={() => handleBulkAction('SENT')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-500/10 hover:bg-blue-500 text-blue-400 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-blue-500/20"
              >
                Mark Sent
              </button>
              <button 
                onClick={() => handleBulkAction('ARCHIVED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/20 text-slate-400 text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-white/10"
              >
                Archive
              </button>
              <button 
                onClick={() => handleBulkAction('REJECTED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500 text-red-400 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-red-500/20"
              >
                Reject
              </button>
              <button 
                onClick={() => setSelectedIds([])}
                className="ml-4 p-2 text-slate-500 hover:text-white transition-colors cursor-pointer"
                title="Deselect All"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast Notification */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4 duration-300`}>
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
            }`}>
            <p className="text-[12px] font-bold tracking-tight">{notification.message}</p>
            <button onClick={() => setNotification(null)} className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Emails;
