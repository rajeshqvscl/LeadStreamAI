import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import { 
  History as HistoryIcon, 
  Search, 
  User, 
  Clock, 
  Download, 
  ExternalLink, 
  Filter,
  Loader2,
  Mail,
  Zap,
  Tag,
  Rocket,
  Trash2,
  Calendar,
  AlertCircle
} from 'lucide-react';

const History = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total_pages: 1, total: 0 });
  const [users, setUsers] = useState([]);
  const [filters, setFilters] = useState({
    target_user_id: '',
    action_type: '',
  });
  const [exporting, setExporting] = useState(false);

  const currentUser = JSON.parse(localStorage.getItem('user') || '{}');
  const isAdmin = currentUser.role === 'ADMIN';

  const actionTypes = [
    { value: 'BULK_INGESTION', label: 'Bulk Ingestion', icon: <Download className="w-3.5 h-3.5 text-blue-400" /> },
    { value: 'LEAD_SEARCH', label: 'Lead Search', icon: <Search className="w-3.5 h-3.5 text-indigo-400" /> },
    { value: 'EMAIL_SENT', label: 'Email Sent', icon: <Mail className="w-3.5 h-3.5 text-emerald-400" /> },
    { value: 'DRAFT_GENERATED', label: 'Draft Generated', icon: <Zap className="w-3.5 h-3.5 text-amber-400" /> },
    { value: 'UPDATE_LEAD', label: 'Lead Updated', icon: <HistoryIcon className="w-3.5 h-3.5 text-purple-400" /> },
    { value: 'LABEL_ASSIGNED', label: 'Label Assigned', icon: <Tag className="w-3.5 h-3.5 text-pink-400" /> },
    { value: 'BULK_DRAFT_GENERATE', label: 'Bulk Drafts', icon: <Rocket className="w-3.5 h-3.5 text-orange-400" /> },
  ];

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const endpoint = isAdmin ? '/api/admin/audit-logs' : '/api/users/my-history';
      const params = isAdmin ? {
        page: pagination.page,
        target_user_id: filters.target_user_id || undefined,
        action_type: filters.action_type || undefined,
        limit: 50
      } : {};

      const response = await axios.get(endpoint, { params });
      
      if (isAdmin) {
        setLogs(response.data.logs);
        setPagination(prev => ({
          ...prev,
          total_pages: response.data.pages,
          total: response.data.total
        }));
      } else {
        setLogs(response.data);
      }
    } catch (err) {
      console.error('Failed to fetch activity logs', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsers = async () => {
    if (!isAdmin) return;
    try {
      const response = await axios.get('/api/admin/users-stats');
      setUsers(response.data);
    } catch (err) {
      console.error('Failed to fetch users', err);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [pagination.page, filters]);

  useEffect(() => {
    fetchUsers();
  }, []);

  const handleExport = async () => {
    setExporting(true);
    try {
      const response = await axios.get('/api/admin/audit-logs/export', {
        params: { target_user_id: filters.target_user_id || undefined },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit_log_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error('Export failed', err);
    } finally {
      setExporting(false);
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return 'N/A';
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const getActionBadge = (action) => {
    const type = actionTypes.find(t => action.includes(t.value)) || { label: action, icon: <AlertCircle className="w-3.5 h-3.5 text-slate-500" /> };
    return (
      <div className="flex items-center gap-2">
        {type.icon}
        <span className="text-[11px] font-black uppercase tracking-wider text-slate-300">
          {type.label}
        </span>
      </div>
    );
  };

  return (
    <div className="animate-in fade-in duration-500 pb-10">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 mb-8">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-blue-500/10 border border-blue-500/20 rounded-lg">
              <HistoryIcon className="w-5 h-5 text-blue-500" />
            </div>
            <h1 className="text-3xl font-black text-white tracking-tight">Audit <span className="text-blue-500 italic">History</span></h1>
          </div>
          <p className="text-slate-500 text-sm font-medium pl-11">
            {isAdmin 
              ? "Comprehensive timeline of all system actions and lead ingestions across all user accounts."
              : "Timeline of your recent activities, lead extractions, and outbound dispatches."}
          </p>
        </div>

        {isAdmin && (
          <button 
            onClick={handleExport}
            disabled={exporting}
            className="btn bg-white/5 border border-white/10 hover:bg-white/10 text-white px-6 py-2.5 rounded-xl flex items-center gap-2.5 font-black uppercase tracking-widest text-[10px] transition-all shadow-xl disabled:opacity-50"
          >
            {exporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Export DB Activity (CSV)
          </button>
        )}
      </div>

      {/* Filter Bar */}
      <div className="bg-[#111827] border border-white/5 rounded-[24px] p-2 mb-8 shadow-2xl flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-3 px-4 py-2 border-r border-white/5 bg-black/20 rounded-l-[18px]">
          <Filter className="w-4 h-4 text-slate-500" />
          <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Filters</span>
        </div>

        {isAdmin && (
          <div className="px-4 py-2 border-r border-white/5 flex items-center gap-3">
            <User className="w-3.5 h-3.5 text-blue-500/60" />
            <select 
              value={filters.target_user_id}
              onChange={(e) => {
                setFilters(f => ({ ...f, target_user_id: e.target.value }));
                setPagination(p => ({ ...p, page: 1 }));
              }}
              className="bg-transparent border-none text-white text-[11px] font-black uppercase tracking-widest outline-none cursor-pointer min-w-[140px]"
            >
              <option value="">All Users</option>
              {users.map(u => (
                <option key={u.id} value={u.id}>{u.full_name || u.username}</option>
              ))}
            </select>
          </div>
        )}

        <div className="px-4 py-2 border-r border-white/5 flex items-center gap-3">
          <Zap className="w-3.5 h-3.5 text-amber-500/60" />
          <select 
            value={filters.action_type}
            onChange={(e) => {
              setFilters(f => ({ ...f, action_type: e.target.value }));
              setPagination(p => ({ ...p, page: 1 }));
            }}
            className="bg-transparent border-none text-white text-[11px] font-black uppercase tracking-widest outline-none cursor-pointer min-w-[140px]"
          >
            <option value="">All Actions</option>
            {actionTypes.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
        </div>

        <div className="ml-auto px-4 py-2 text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
          <Clock className="w-3.5 h-3.5" />
          Live Update Active
        </div>
      </div>

      {/* Table Container */}
      <div className="bg-[#111827] border border-white/5 rounded-[32px] overflow-hidden shadow-heavy">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/40 border-b border-white/5">
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Timestamp</th>
                {isAdmin && <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Actor</th>}
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Action Category</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Target Lead</th>
                <th className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px]">Summary Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td colSpan={5} className="px-6 py-6">
                      <div className="h-4 bg-white/5 rounded-full w-full"></div>
                    </td>
                  </tr>
                ))
              ) : logs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-20 text-center">
                    <div className="flex flex-col items-center gap-3">
                      <div className="w-12 h-12 bg-white/5 rounded-full flex items-center justify-center">
                        <HistoryIcon className="w-6 h-6 text-slate-600" />
                      </div>
                      <div className="text-slate-500 font-black uppercase tracking-widest text-[11px]">No activity logs found</div>
                    </div>
                  </td>
                </tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-white/[0.02] transition-colors group">
                    <td className="px-6 py-5">
                      <div className="flex items-center gap-3">
                        <Calendar className="w-3.5 h-3.5 text-slate-600" />
                        <span className="text-[11px] font-bold text-slate-400 font-mono tracking-tight">{formatTime(log.created_at)}</span>
                      </div>
                    </td>
                    {isAdmin && (
                      <td className="px-6 py-5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-7 h-7 rounded-full bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-[10px] font-black text-blue-500">
                            {(log.actor_name || log.performed_by || '??').charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-[11px] font-black text-white">{log.actor_name || log.actor_username || log.performed_by}</div>
                            <div className="text-[9px] font-bold text-slate-500 uppercase tracking-tighter">User ID: {log.user_id || 'SYS'}</div>
                          </div>
                        </div>
                      </td>
                    )}
                    <td className="px-6 py-5">
                      {getActionBadge(log.action)}
                    </td>
                    <td className="px-6 py-5">
                      {log.lead_name ? (
                        <div className="flex flex-col">
                          <span className="text-[11px] font-black text-white">{log.lead_name}</span>
                          <span className="text-[9px] font-bold text-slate-500 truncate max-w-[150px]">{log.lead_email}</span>
                        </div>
                      ) : (
                        <span className="text-[10px] font-bold text-slate-600 italic">Global Task</span>
                      )}
                    </td>
                    <td className="px-6 py-5">
                      <div className="text-[11px] font-medium text-slate-400 line-clamp-2 max-w-[400px]">
                        {log.details || 'No extended metadata available.'}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {isAdmin && logs.length > 0 && (
          <div className="flex justify-between items-center px-8 py-6 bg-black/20 border-t border-white/5">
            <div className="text-[10px] font-black text-slate-500 uppercase tracking-[1px]">
              Showing <span className="text-white">{logs.length}</span> of {pagination.total} audit entries
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={() => setPagination(p => ({ ...p, page: Math.max(1, p.page - 1) }))}
                disabled={pagination.page === 1}
                className="btn bg-white/5 border border-white/10 p-2 rounded-lg disabled:opacity-30"
              >
                ← Prev
              </button>
              <div className="flex gap-1">
                {[...Array(Math.min(5, pagination.total_pages))].map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setPagination(p => ({ ...p, page: i + 1 }))}
                    className={`w-8 h-8 rounded-lg text-[10px] font-black transition-all ${pagination.page === i + 1 ? 'bg-blue-600 text-white' : 'hover:bg-white/5 text-slate-500'}`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
              <button 
                onClick={() => setPagination(p => ({ ...p, page: Math.min(pagination.total_pages, p.page + 1) }))}
                disabled={pagination.page === pagination.total_pages}
                className="btn bg-white/5 border border-white/10 p-2 rounded-lg disabled:opacity-30"
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default History;
