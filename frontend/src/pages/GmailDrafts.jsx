import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, Loader2, RefreshCw, ExternalLink, Search, Edit3, Send, X, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const GmailDrafts = () => {
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [notification, setNotification] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchGmailDrafts = async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    else setIsRefreshing(true);
    try {
      const res = await api.get(`/api/gmail/sync-drafts${quiet ? '?refresh=true' : ''}`);
      setDrafts(res.data);
    } catch (err) {
      console.error('Failed to fetch Gmail drafts:', err);
      showNotification('error', 'Failed to load Gmail drafts');
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGmailDrafts();
  }, []);

  const handleEditClick = (draft) => {
    navigate(`/dashboard/gmail-drafts/${draft.id}/edit`);
  };

  const handleSendDraft = async (draftId) => {
    if (!window.confirm('Are you sure you want to send this draft now?')) return;
    setIsProcessing(true);
    try {
      await api.post(`/api/gmail/send-draft/${draftId}`);
      showNotification('success', 'Email sent successfully via Gmail');
      fetchGmailDrafts(true);
    } catch (err) {
      showNotification('error', 'Failed to send email: ' + (err?.response?.data?.detail || err?.message || 'Unknown error'));
    } finally {
      setIsProcessing(false);
    }
  };

  const filteredDrafts = drafts.filter(d =>
    d.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.to.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.snippet.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="animate-in fade-in duration-700">
      <div className="flex justify-between items-end mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-[28px] font-bold text-white tracking-tight">Gmail Sync</h1>
            <div className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-[9px] font-black text-blue-500 uppercase tracking-widest">Live Drafts</div>
          </div>
          <p className="text-[#64748b] text-[12px] font-medium">
            Direct real-time synchronization with your linked Gmail account drafts.
          </p>
        </div>
        <button
          onClick={() => fetchGmailDrafts(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[11px] font-bold text-white uppercase tracking-widest transition-all disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
          {isRefreshing ? 'Syncing...' : 'Force Refresh'}
        </button>
      </div>

      {/* Control Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="md:col-span-3 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search within Gmail drafts..."
            className="w-full bg-[#131722] border border-white/5 rounded-2xl py-3 pl-12 pr-4 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/30 transition-all"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center justify-center bg-[#131722] border border-white/5 rounded-2xl px-4 py-3">
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Total: {drafts.length}</span>
        </div>
      </div>

      <div className="bg-[#131722] border border-[#ffffff08] rounded-[24px] overflow-hidden shadow-2xl relative">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0f121b]/80 border-b border-[#ffffff08]">
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Recipient / Thread</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Subject & Context</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Draft Snippet</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Last Modified</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] text-right">Access</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ffffff08]">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="px-6 py-32 text-center">
                    <div className="flex flex-col items-center gap-4">
                      <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
                      <p className="text-[10px] font-black text-slate-500 uppercase tracking-[3px]">Polling Gmail Servers...</p>
                    </div>
                  </td>
                </tr>
              ) : filteredDrafts.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-32 text-center text-[#64748b] font-bold uppercase tracking-[2px] text-[10px]">
                    No drafts found in your Gmail account matching current filters.
                  </td>
                </tr>
              ) : filteredDrafts.map(draft => (
                <tr key={draft.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 font-black text-[10px]">G</div>
                      <div>
                        <div className="text-[12px] font-bold text-white truncate max-w-[200px]">{draft.to || '—'}</div>
                        <div className="text-[9px] text-slate-500 font-medium tracking-tight mt-0.5">Draft ID: {draft.id.substring(0,8)}...</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <div className="text-[12px] text-blue-400 font-bold tracking-tight mb-1">{draft.subject || '(No Subject)'}</div>
                    <div className="flex items-center gap-2">
                      <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[8px] font-black text-slate-400 uppercase tracking-tighter border border-white/5">Synced</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <p className="text-[11px] text-[#94a3b8] font-medium line-clamp-2 max-w-[400px]">
                      {draft.snippet || 'No content snippet available.'}
                    </p>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex flex-col">
                      <span className="text-[11px] text-white font-bold">{draft.date ? new Date(draft.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Recently'}</span>
                      <span className="text-[9px] text-slate-500 font-medium uppercase tracking-tighter mt-1">{draft.date ? new Date(draft.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        onClick={() => handleEditClick(draft)}
                        className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all border border-white/5 cursor-pointer"
                        title="Edit Draft"
                      >
                        <Edit3 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleSendDraft(draft.id)}
                        className="p-2 bg-blue-600/10 hover:bg-blue-600 rounded-lg text-blue-400 hover:text-white transition-all border border-blue-600/20 cursor-pointer"
                        title="Send Draft Now"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                      <a
                        href="https://mail.google.com/mail/u/0/#drafts"
                        target="_blank"
                        rel="noreferrer"
                        className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all border border-white/5 cursor-pointer"
                        title="View in Gmail"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-8 p-6 rounded-[24px] bg-gradient-to-br from-indigo-500/5 to-purple-500/5 border border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-blue-500">
            <Mail className="w-6 h-6" />
          </div>
          <div>
            <h4 className="text-[14px] font-bold text-white">Gmail Integration Active</h4>
            <p className="text-[11px] text-slate-500 font-medium">Any changes made in your Gmail account will reflect here after a refresh.</p>
          </div>
        </div>
        <div className="flex gap-4">
          <div className="text-center px-6 border-r border-white/10">
            <div className="text-[18px] font-black text-white">{drafts.length}</div>
            <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mt-1">Stored Drafts</div>
          </div>
          <div className="text-center px-6">
            <div className="text-[18px] font-black text-emerald-500 tracking-tighter flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
              OK
            </div>
            <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mt-1">API Status</div>
          </div>
        </div>
      </div>

      {/* Notification Toast */}
      {notification && (
        <div className="fixed bottom-8 right-8 z-[6000] animate-in slide-in-from-bottom-4 duration-300">
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${
            notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
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

export default GmailDrafts;
