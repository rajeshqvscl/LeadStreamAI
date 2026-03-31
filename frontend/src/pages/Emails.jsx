import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, Edit3, Loader2, Send, ChevronLeft, ChevronRight, X } from 'lucide-react';
import api from '../services/api';

const Emails = () => {
  const navigate = useNavigate();
  const [emails, setEmails] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total: 0 });
  const [filterStatus, setFilterStatus] = useState('');
  const [isBatchSending, setIsBatchSending] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchEmails = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/emails', {
        params: { 
          page: pagination.page, 
          status: filterStatus || undefined,
          per_page: 20 
        }
      });
      setEmails(response.data.drafts || []);
      setPagination(prev => ({ ...prev, total: response.data.total }));
    } catch {
      console.error('Failed to fetch emails');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchEmails();
  }, [pagination.page, filterStatus]);

  const handleApprove = async (id) => {
    try {
      await api.post(`/api/approve-email/${id}`, { approved_by: 'admin' });
      showNotification('success', 'Email approved successfully');
      fetchEmails();
    } catch {
      showNotification('error', 'Approval failed');
    }
  };

  const handleReject = async (id) => {
    const reason = window.prompt('Enter rejection reason:');
    if (reason === null) return;
    try {
      await api.post(`/api/reject-email/${id}`, { rejected_reason: reason });
      showNotification('success', 'Email draft rejected');
      fetchEmails();
    } catch {
      showNotification('error', 'Rejection failed');
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
              <option value="SENT">STATUS: Sent</option>
              <option value="REJECTED">STATUS: Rejected</option>
              <option value="FAILED">STATUS: Failed</option>
              <option value="ARCHIVED">STATUS: Archived</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <div className="relative">
            <select className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 pr-8 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50">
              <option>REGION: All Regions</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <div className="relative">
            <select className="appearance-none bg-[#0f121b] border border-[#ffffff10] rounded-md px-3 py-1.5 pr-8 text-[10px] font-bold text-slate-300 uppercase tracking-widest outline-none focus:border-blue-500/50">
              <option>GEO: Global Coverage</option>
            </select>
            <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none text-slate-500 text-[8px]">▼</div>
          </div>

          <button 
            onClick={() => setFilterStatus('')}
            className="px-3 py-1.5 rounded-md text-[10px] font-bold text-slate-400 hover:text-white uppercase tracking-widest transition-colors ml-1"
          >
            Reset
          </button>
        </div>

        {/* Full-width Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0f121b]/80">
                <th className="px-6 py-4 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] border-b border-[#ffffff08]">LEAD / COMPANY</th>
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
                <tr key={email.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-4">
                     <div className="font-bold text-white text-[12px] group-hover:text-blue-400 transition-colors cursor-pointer" onClick={() => navigate(`/dashboard/leads/${email.lead_id}`)}>{email.lead_name}</div>
                     <div className="text-[10px] text-[#64748b] font-medium tracking-wide mt-0.5">{email.lead_email}</div>
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
                    {email.status === 'FAILED' && (
                      <span className="text-[8px] font-black uppercase tracking-[1px] text-red-500">FAILED</span>
                    )}
                    {email.status === 'ARCHIVED' && (
                      <span className="px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-[1px] border border-[#3b82f6] text-[#3b82f6]">ARCHIVED</span>
                    )}
                    {(!['REJECTED', 'PENDING_APPROVAL', 'SENT', 'APPROVED', 'FAILED', 'ARCHIVED'].includes(email.status)) && (
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
                         <span className="block text-[#64748b] mt-0.5">{new Date(email.updated_at).toLocaleDateString('en-US', {month:'2-digit', day:'2-digit', year:'2-digit'})}</span>
                       </div>
                     ) : (
                       <span className="text-[#64748b]">—</span>
                     )}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2 items-center">
                      {email.status === 'PENDING_APPROVAL' ? (
                        <>
                          <button onClick={() => navigate(`/dashboard/emails/${email.id}/edit`)} className="px-3 py-1 bg-transparent border border-white/10 rounded text-slate-300 text-[10px] font-bold hover:bg-white/5 transition-colors">Edit</button>
                          <button onClick={() => handleApprove(email.id)} className="px-3 py-1 bg-transparent border border-[#10b981] rounded text-[#10b981] text-[10px] font-bold hover:bg-[#10b981]/10 transition-colors">Approve</button>
                          <button onClick={() => handleReject(email.id)} className="px-3 py-1 bg-transparent border border-red-500 rounded text-red-500 text-[10px] font-bold hover:bg-red-500/10 transition-colors">Reject</button>
                        </>
                      ) : email.status === 'REJECTED' ? (
                        <button onClick={() => navigate(`/dashboard/emails/${email.id}/edit`)} className="px-3 py-1 bg-transparent border border-white/10 rounded text-slate-300 text-[10px] font-bold hover:bg-white/5 transition-colors">View</button>
                      ) : (email.status === 'SENT' || email.status === 'APPROVED') ? (
                        <>
                          <button onClick={() => navigate(`/dashboard/emails/${email.id}/edit`)} className="px-3 py-1 bg-transparent border border-white/10 rounded text-slate-300 text-[10px] font-bold hover:bg-white/5 transition-colors">View</button>
                          <button className="px-3 py-1 bg-transparent rounded text-red-500 text-[10px] font-bold hover:underline transition-colors">Opt-out</button>
                        </>
                      ) : (
                        <button onClick={() => navigate(`/dashboard/emails/${email.id}/edit`)} className="px-3 py-1 bg-transparent border border-white/10 rounded text-slate-300 text-[10px] font-bold hover:bg-white/5 transition-colors">View</button>
                      )}
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

      {/* Toast Notification */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4 duration-300`}>
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${
            notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            <p className="text-[12px] font-bold tracking-tight">{notification.message}</p>
            <button onClick={() => setNotification(null)} className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Emails;
