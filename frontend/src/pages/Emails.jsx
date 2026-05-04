import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Eye, Edit3, Loader2, Send, ChevronLeft, ChevronRight, X, Archive, CheckCircle2, Sparkles, History, User, Globe, Calendar, Trash2 } from 'lucide-react';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import api from '../services/api';

const Emails = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const initialStatus = searchParams.get('status') || '';
  
  const [emails, setEmails] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total: 0 });
  const [selectedIds, setSelectedIds] = useState([]);
  const [filterStatus, setFilterStatus] = useState(initialStatus);
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
  const [sendingId, setSendingId] = useState(null);
  const [approvingId, setApprovingId] = useState(null);
  const [approveStep, setApproveStep] = useState(0);
  const [isBulkSending, setIsBulkSending] = useState(false);
  const [bulkSendResult, setBulkSendResult] = useState(null); // { sent, failed, total }
  
  // ✨ Generation Logic State
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState('ai');
  const [isTemplateGenerating, setIsTemplateGenerating] = useState(false);
  const [customTemplates, setCustomTemplates] = useState([]);

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
    const status = searchParams.get('status') || '';
    setFilterStatus(status);
    setPagination(prev => ({ ...prev, page: 1 }));
  }, [searchParams]);

  useEffect(() => {
    api.get('/api/custom-draft-templates').then(r => setCustomTemplates(r.data || [])).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchEmails();
    }, 500);
    return () => clearTimeout(timer);
  }, [pagination.page, filterStatus, filterRegion, filterGeo, filterCompany]);

  const handleApprove = async (id) => {
    try {
      setSendingId(id);
      setApprovingId(id);
      setApproveStep(0);
      await api.post(`/api/approve-email/${id}`, { approved_by: 'admin' });
      setApproveStep(1);
      // Remove instantly from list for snappy UX
      setEmails(prev => prev.filter(e => e.id !== id));
      // Keep success popup visible for 1.8s then close
      setTimeout(() => {
        setApprovingId(null);
        setApproveStep(0);
        showNotification('success', '✅ Email dispatched & Gmail draft deleted');
      }, 1800);
    } catch (err) {
      setApprovingId(null);
      setApproveStep(0);
      showNotification('error', err?.response?.data?.detail || 'Approval failed. Check Gmail connection.');
    } finally {
      setSendingId(null);
    }
  };

  const handleBulkSend = async () => {
    if (selectedIds.length === 0) return;
    setIsBulkSending(true);
    setBulkSendResult(null);
    try {
      const res = await api.post('/api/send-selected-batch', { lead_ids: selectedIds });
      const { sent_count, failed_count, results } = res.data;
      setBulkSendResult({ sent: sent_count, failed: failed_count, total: selectedIds.length, results: results });
      // Remove sent leads from the queue list
      fetchEmails();
      // Don't auto-close if there are failures, let the user see the report
      if (failed_count === 0) {
        setTimeout(() => { setBulkSendResult(null); setIsBulkSending(false); }, 3500);
      }
    } catch (err) {
      setIsBulkSending(false);
      setBulkSendResult(null);
      showNotification('error', err?.response?.data?.detail || 'Bulk send failed. Check Gmail connection.');
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
  
  const handleDelete = async (id) => {
    if (!window.confirm("Permanently delete this lead and its draft? This action is non-reversible.")) return;
    try {
      await api.delete(`/api/leads/${id}`);
      showNotification('success', 'Lead permanently deleted');
      setEmails(prev => prev.filter(e => e.id !== id));
      setSelectedIds(prev => prev.filter(i => i !== id));
    } catch {
      showNotification('error', 'Deletion failed');
    }
  };

  const handleBulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Permanently delete all ${selectedIds.length} selected leads? This action is non-reversible.`)) return;
    
    setIsBatchSending(true);
    try {
      await api.post('/api/leads/bulk-delete', selectedIds);
      showNotification('success', `${selectedIds.length} leads deleted`);
      setEmails(prev => prev.filter(e => !selectedIds.includes(e.id)));
      setSelectedIds([]);
    } catch {
      showNotification('error', 'Bulk deletion failed');
    } finally {
      setIsBatchSending(false);
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

  const handleGenerateWithTemplate = async () => {
    if (selectedIds.length === 0) return;
    setShowTemplatePicker(false);
    setIsTemplateGenerating(true);
    const leadIds = selectedIds;
    try {
      if (selectedTemplate === 'ai') {
        await api.post('/api/generate-bulk-domain-drafts', { lead_ids: leadIds });
        showNotification('success', `AI drafts generated for ${leadIds.length} lead(s).`);
      } else {
        // Generate for each lead sequentially using the chosen template
        let ok = 0;
        for (const lid of leadIds) {
          try {
            await api.post('/api/generate-draft-from-template', { lead_id: lid, template_name: selectedTemplate });
            ok++;
          } catch {}
        }
        showNotification('success', `Template "${selectedTemplate}" applied to ${ok} lead(s).`);
      }
      setSelectedIds([]);
      fetchEmails();
    } catch (err) {
      showNotification('error', 'Draft generation failed: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsTemplateGenerating(false);
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
          <h1 className="text-[28px] font-bold text-white tracking-tight">
            {filterStatus === 'SENT' ? 'Sent Mail' : filterStatus === 'PENDING_APPROVAL' ? 'Email Drafts' : 'Review Queue'}
          </h1>
          <div className="flex items-center gap-3 mt-1">
            <p className="text-[#64748b] text-[12px] font-medium">
              <span className="font-bold text-slate-400">{pagination.total} {filterStatus === 'SENT' ? 'sent' : 'drafts'} total</span> — {filterStatus === 'SENT' ? 'History of dispatched outreach.' : 'Human-in-the-loop verification.'}
            </p>
            {localStorage.getItem('user') && JSON.parse(localStorage.getItem('user')).google_linked_at && (
              <div className="px-2.5 py-1 bg-blue-500/10 border border-blue-500/20 rounded-lg text-[9px] font-black text-blue-500 uppercase tracking-widest flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                Sending From: {JSON.parse(localStorage.getItem('user')).google_email || 'Linked Account'}
              </div>
            )}
          </div>
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
                          <button 
                            onClick={() => handleApprove(email.id)} 
                            disabled={sendingId === email.id}
                            className={`p-2 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-all cursor-pointer ${sendingId === email.id ? 'opacity-50' : ''}`} 
                            title="Approve & Send"
                          >
                            {sendingId === email.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
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

                      <button 
                        onClick={() => handleDelete(email.id)} 
                        className="p-2 rounded bg-red-500/10 hover:bg-red-500/20 text-red-500 transition-all cursor-pointer" 
                        title="Delete Lead & Draft"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer — always visible */}
        <div className="px-6 py-4 border-t border-[#ffffff08] flex justify-between items-center">
          <span className="text-[11px] font-bold uppercase tracking-widest text-[#64748b]">
            Page <span className="text-white">{pagination.page}</span> of <span className="text-white">{pagination.total || 1}</span>
            &nbsp;&mdash;&nbsp;{emails.length} records shown
          </span>
          <div className="flex items-center gap-2">
            <button
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 text-[10px] font-black text-slate-400 hover:text-white uppercase tracking-widest transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              disabled={pagination.page === 1}
              onClick={() => setPagination(v => ({ ...v, page: v.page - 1 }))}
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Prev
            </button>

            {/* Page number pills */}
            {Array.from({ length: Math.min(pagination.total || 1, 5) }, (_, i) => {
              const pg = pagination.page <= 3
                ? i + 1
                : pagination.page + i - 2;
              if (pg < 1 || pg > (pagination.total || 1)) return null;
              return (
                <button
                  key={pg}
                  onClick={() => setPagination(v => ({ ...v, page: pg }))}
                  className={`w-8 h-8 rounded-lg text-[10px] font-black transition-all cursor-pointer border ${
                    pg === pagination.page
                      ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-500/20'
                      : 'bg-white/5 border-white/5 text-slate-400 hover:text-white hover:bg-white/10'
                  }`}
                >
                  {pg}
                </button>
              );
            })}

            <button
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/10 text-[10px] font-black text-slate-400 hover:text-white uppercase tracking-widest transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
              disabled={pagination.page >= (pagination.total || 1)}
              onClick={() => setPagination(v => ({ ...v, page: v.page + 1 }))}
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
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
                onClick={() => setShowTemplatePicker(true)}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-blue-400/30 shadow-lg shadow-blue-500/20"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Generate Drafts
              </button>
              <button 
                onClick={handleBulkSend}
                disabled={isBulkSending}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-emerald-400/30 disabled:opacity-50 shadow-lg shadow-emerald-500/20"
              >
                {isBulkSending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                {isBulkSending ? 'Sending...' : `Send ${selectedIds.length} Selected`}
              </button>
              <button 
                onClick={() => handleBulkAction('APPROVED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-white/5 hover:bg-emerald-500/10 text-emerald-400 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-white/10"
              >
                Mark Approved
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
                onClick={() => handleBulkAction('ARCHIVED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-white/5 hover:bg-white/20 text-slate-400 text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-white/10"
              >
                Archive
              </button>
              <button 
                onClick={() => handleBulkAction('REJECTED')}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-red-500/20"
              >
                Reject
              </button>
              <button 
                onClick={handleBulkDelete}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-red-600 hover:bg-red-500 text-white text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer border border-red-400/30 shadow-lg shadow-red-500/20"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
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

      {/* Bulk Send Progress Popup */}
      {isBulkSending && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-950/80 backdrop-blur-2xl animate-in fade-in duration-300">
          <div className="w-full max-w-md bg-[#0b0f1a] border border-white/10 rounded-[40px] p-12 shadow-[0_0_100px_rgba(0,0,0,0.8)] flex flex-col items-center gap-8 text-center animate-in zoom-in-95 duration-500">
            {!bulkSendResult ? (
              <>
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-emerald-500/10 flex items-center justify-center">
                    <Send className="w-10 h-10 text-emerald-400 animate-pulse" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-2 border-emerald-500/30 animate-ping" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black text-white tracking-tight">Dispatching {selectedIds.length} Emails</h3>
                  <p className="text-slate-500 text-[12px] font-bold uppercase tracking-[3px]">Sending via your Gmail account...</p>
                </div>
                <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-emerald-500 to-blue-500 rounded-full animate-pulse" style={{ width: '60%' }} />
                </div>
              </>
            ) : (
              <>
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-emerald-500/10 flex items-center justify-center">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-2 border-emerald-500/30 animate-ping" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black text-white tracking-tight">Batch Complete! 🎉</h3>
                  <p className="text-slate-500 text-[12px] font-bold uppercase tracking-[3px]">Emails sent via your Gmail account</p>
                </div>
                <div className="w-full space-y-3">
                  <div className="flex items-center justify-between px-4 py-3 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                    <span className="text-[11px] font-black text-emerald-400 uppercase tracking-widest">✅ Sent Successfully</span>
                    <span className="text-xl font-black text-emerald-400">{bulkSendResult.sent}</span>
                  </div>
                  {bulkSendResult.failed > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center justify-between px-4 py-3 rounded-2xl bg-red-500/10 border border-red-500/20">
                        <span className="text-[11px] font-black text-red-400 uppercase tracking-widest">❌ Failed</span>
                        <span className="text-xl font-black text-red-400">{bulkSendResult.failed}</span>
                      </div>
                      <div className="max-h-32 overflow-y-auto custom-scrollbar space-y-1 pr-2">
                        {bulkSendResult.results?.filter(r => r.status === 'failed').map((r, idx) => (
                          <div key={idx} className="text-left p-2 bg-red-500/5 rounded-lg border border-red-500/10">
                            <div className="text-[10px] font-black text-red-400 uppercase tracking-tighter truncate">{r.email}</div>
                            <div className="text-[9px] text-red-300/60 leading-tight mt-0.5">{r.error || 'Unknown error'}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  <p className="text-[10px] text-slate-600 font-bold uppercase tracking-widest pt-1">Check your Gmail Sent folder to verify</p>
                  <button 
                    onClick={() => { setBulkSendResult(null); setIsBulkSending(false); }}
                    className="w-full py-3 bg-white/5 hover:bg-white/10 text-slate-400 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all border border-white/5"
                  >
                    Close Report
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ✨ Approve & Send Loading Popup */}
      {approvingId && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-950/80 backdrop-blur-2xl animate-in fade-in duration-300">
          <div className="w-full max-w-md bg-[#0b0f1a] border border-white/10 rounded-[40px] p-12 shadow-[0_0_100px_rgba(0,0,0,0.8)] flex flex-col items-center gap-8 text-center animate-in zoom-in-95 duration-500">
            
            {approveStep === 0 ? (
              <>
                {/* Sending Animation */}
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-blue-500/10 flex items-center justify-center">
                    <Send className="w-10 h-10 text-blue-400 animate-pulse" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-2 border-blue-500/30 animate-ping" />
                  <div className="absolute inset-[-8px] rounded-full border border-blue-500/10 animate-ping" style={{ animationDelay: '0.3s' }} />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black text-white tracking-tight">Dispatching Outreach</h3>
                  <p className="text-slate-500 text-[12px] font-bold uppercase tracking-[3px]">Sending email & deleting draft</p>
                </div>
                <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-violet-500 rounded-full animate-pulse" style={{ width: '70%' }} />
                </div>
                <div className="flex flex-col gap-3 w-full">
                  {[
                    { label: 'Sending via Gmail API', done: true },
                    { label: 'Deleting Gmail Draft', done: false },
                    { label: 'Updating Review Queue', done: false },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-3 text-left">
                      <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                        step.done ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/5 text-slate-600'
                      }`}>
                        {step.done ? <CheckCircle2 className="w-3 h-3" /> : <Loader2 className="w-3 h-3 animate-spin" />}
                      </div>
                      <span className={`text-[11px] font-bold uppercase tracking-widest ${
                        step.done ? 'text-emerald-400' : 'text-slate-500'
                      }`}>{step.label}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                {/* Success State */}
                <div className="relative">
                  <div className="w-24 h-24 rounded-full bg-emerald-500/10 flex items-center justify-center">
                    <CheckCircle2 className="w-10 h-10 text-emerald-400" />
                  </div>
                  <div className="absolute inset-0 rounded-full border-2 border-emerald-500/30 animate-ping" />
                </div>
                <div className="space-y-2">
                  <h3 className="text-2xl font-black text-white tracking-tight">Email Sent! 🎉</h3>
                  <p className="text-slate-500 text-[12px] font-bold uppercase tracking-[3px]">Draft removed from Gmail & queue</p>
                </div>
                <div className="flex flex-col gap-3 w-full">
                  {[
                    { label: 'Email Dispatched', done: true },
                    { label: 'Gmail Draft Deleted', done: true },
                    { label: 'Review Queue Updated', done: true },
                  ].map((step, i) => (
                    <div key={i} className="flex items-center gap-3 text-left">
                      <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 bg-emerald-500/20 text-emerald-400">
                        <CheckCircle2 className="w-3 h-3" />
                      </div>
                      <span className="text-[11px] font-bold uppercase tracking-widest text-emerald-400">{step.label}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Template Selection Modal */}
      {showTemplatePicker && (
        <div className="fixed inset-0 z-[4000] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-300">
          <div className="w-full max-w-xl bg-[#0d1117] border border-blue-500/20 rounded-[32px] overflow-hidden shadow-2xl flex flex-col max-h-[85vh]">
            <div className="p-8 border-b border-white/5 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-blue-500/10 flex items-center justify-center">
                  <Sparkles className="w-6 h-6 text-blue-400" />
                </div>
                <div>
                  <h3 className="text-xl font-black text-white tracking-tight">Choose Draft Template</h3>
                  <p className="text-slate-500 text-[11px] font-black uppercase tracking-[2px]">Generating for {selectedIds.length} selected items</p>
                </div>
              </div>
              <button onClick={() => setShowTemplatePicker(false)} className="p-2 hover:bg-white/5 rounded-full text-slate-500 transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8 space-y-4 custom-scrollbar">
              {/* AI Default Option */}
              <div 
                onClick={() => setSelectedTemplate('ai')}
                className={`p-6 rounded-[24px] border-2 transition-all cursor-pointer relative group ${selectedTemplate === 'ai' ? 'bg-blue-600/10 border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.1)]' : 'bg-white/[0.02] border-white/5 hover:border-white/10'}`}
              >
                <div className="flex items-center gap-5">
                  <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${selectedTemplate === 'ai' ? 'border-blue-500' : 'border-slate-700'}`}>
                    {selectedTemplate === 'ai' && <div className="w-3 h-3 rounded-full bg-blue-500" />}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-black text-white">🤖 Regular AI Draft</span>
                      <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-[9px] font-black uppercase tracking-widest rounded-md">Default</span>
                    </div>
                    <p className="text-slate-400 text-[13px] font-medium leading-relaxed mt-1">AI generates a personalized email based on the lead's profile, industry, and persona.</p>
                  </div>
                </div>
              </div>

              {/* Custom Templates */}
              {customTemplates.map(template => (
                <div 
                  key={template.name}
                  onClick={() => setSelectedTemplate(template.name)}
                  className={`p-6 rounded-[24px] border-2 transition-all cursor-pointer relative group ${selectedTemplate === template.name ? 'bg-blue-600/10 border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.1)]' : 'bg-white/[0.02] border-white/5 hover:border-white/10'}`}
                >
                  <div className="flex items-center gap-5">
                    <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center transition-all ${selectedTemplate === template.name ? 'border-blue-500' : 'border-slate-700'}`}>
                      {selectedTemplate === template.name && <div className="w-3 h-3 rounded-full bg-blue-500" />}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-black text-white">📝 {template.name}</span>
                        <span className="px-2 py-0.5 bg-violet-500/20 text-violet-400 text-[9px] font-black uppercase tracking-widest rounded-md">Custom</span>
                      </div>
                      <p className="text-slate-400 text-[13px] font-medium leading-relaxed mt-1 line-clamp-1">{template.description || `Custom outreach template: ${template.name}`}</p>
                      <div className="mt-3 flex items-center gap-2">
                        <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Subject:</span>
                        <span className="text-[10px] font-bold text-slate-400 truncate max-w-[300px]">
                          {template.content.split('\n')[0].replace('Subject:', '').trim()}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-8 bg-black/20 border-t border-white/5 flex gap-4">
              <button 
                onClick={() => setShowTemplatePicker(false)}
                className="flex-1 py-4 bg-white/5 hover:bg-white/10 text-slate-300 text-[11px] font-black uppercase tracking-widest rounded-[20px] transition-all"
              >
                Cancel
              </button>
              <button 
                onClick={handleGenerateWithTemplate}
                className="flex-[2] py-4 bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-500 hover:to-violet-500 text-white text-[11px] font-black uppercase tracking-widest rounded-[20px] transition-all shadow-xl shadow-blue-500/20 flex items-center justify-center gap-3"
              >
                <Sparkles className="w-4 h-4" />
                Generate {selectedIds.length} Drafts
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ✨ Generation Animation (ActionLoader) */}
      {isTemplateGenerating && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-[#030711]/90 backdrop-blur-2xl animate-in fade-in duration-500">
          <div className="flex flex-col items-center gap-10 max-w-md text-center p-12">
            {/* Holographic Sparkle Animation */}
            <div className="relative">
              <div className="w-32 h-32 rounded-full bg-gradient-to-tr from-blue-500 to-violet-500 opacity-20 blur-2xl animate-pulse"></div>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="relative">
                  <Sparkles className="w-16 h-16 text-blue-400 animate-bounce" />
                  <div className="absolute inset-0 w-16 h-16 text-blue-400 animate-ping opacity-20">
                    <Sparkles className="w-16 h-16" />
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <h2 className="text-3xl font-black text-white tracking-tight animate-in slide-in-from-bottom-4">
                Engineering <span className="bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">AI Excellence</span>
              </h2>
              <p className="text-slate-500 text-[13px] font-bold uppercase tracking-[4px] leading-relaxed">
                Applying <span className="text-blue-400 font-black">{selectedTemplate.toUpperCase()}</span> logic to {selectedIds.length} leads
              </p>
            </div>

            {/* Progress Visualization */}
            <div className="w-full space-y-6 pt-4">
              <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden border border-white/5 shadow-inner">
                <div className="h-full bg-gradient-to-r from-blue-600 via-blue-400 to-violet-600 rounded-full animate-progress-fast" style={{ width: '100%' }}></div>
              </div>
              
              <div className="flex flex-col gap-4 text-left">
                {[
                  { icon: <User className="w-3.5 h-3.5" />, text: "Mapping Personal Identity" },
                  { icon: <Globe className="w-3.5 h-3.5" />, text: "Contextualizing Global Outreach" },
                  { icon: <Calendar className="w-3.5 h-3.5" />, text: "Finalizing Dispatch Schedule" }
                ].map((item, i) => (
                  <div key={i} className={`flex items-center gap-4 transition-all duration-700 delay-[${i*300}ms] animate-in fade-in slide-in-from-left-4`}>
                    <div className="w-8 h-8 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                      {item.icon}
                    </div>
                    <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest">{item.text}</span>
                    <div className="ml-auto flex items-center gap-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981]"></div>
                      <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Active</span>
                    </div>
                  </div>
                ))}
              </div>
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
