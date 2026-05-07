import React, { useState, useEffect, useMemo } from 'react';
import api from '../services/api';
import {
  Search, Filter, Download, ChevronLeft, ChevronRight,
  ShieldCheck, Clock, User, Target, Mail, AlertCircle,
  X, RefreshCcw
} from 'lucide-react';

const AdminAuditLogs = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, limit: 50, total: 0, pages: 0 });
  const [filters, setFilters] = useState({ user_id: '', action: '' });
  const [searchTerm, setSearchTerm] = useState('');
  const [allUsers, setAllUsers] = useState([]);

  const fetchLogs = async (page = 1) => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append('page', page);
      params.append('limit', 50);
      if (filters.user_id) params.append('target_user_id', filters.user_id);
      if (filters.action) params.append('action_type', filters.action);

      const res = await api.get(`/api/admin/audit-logs?${params.toString()}`);
      setLogs(res.data.logs || []);
      setPagination({
        page: res.data.page || 1,
        limit: res.data.limit || 50,
        total: res.data.total || 0,
        pages: res.data.pages || 0
      });
    } catch (err) {
      console.error('Failed to fetch audit logs', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(pagination.page);
  }, [filters]);

  useEffect(() => {
    const fetchAllUsers = async () => {
      try {
        const res = await api.get('/api/admin/users-stats');
        setAllUsers(res.data || []);
      } catch (err) {
        console.error('Failed to fetch users', err);
      }
    };
    fetchAllUsers();
  }, []);

  const actionOptions = useMemo(() => {
    const actions = new Set(logs.map(l => l.action).filter(Boolean));
    return Array.from(actions);
  }, [logs]);

  const userOptions = useMemo(() => {
    const users = new Set();
    logs.forEach(l => {
      if (l.actor_username) users.add(l.actor_username);
      if (l.user_id) users.add(l.user_id);
    });
    return Array.from(users);
  }, [logs]);

  const filteredLogs = useMemo(() => {
    if (!searchTerm) return logs;
    const term = searchTerm.toLowerCase();
    return logs.filter(l =>
      l.actor_name?.toLowerCase().includes(term) ||
      l.actor_username?.toLowerCase().includes(term) ||
      l.action?.toLowerCase().includes(term) ||
      l.details?.toLowerCase().includes(term) ||
      l.lead_name?.toLowerCase().includes(term) ||
      l.lead_email?.toLowerCase().includes(term)
    );
  }, [logs, searchTerm]);

  const getActionColor = (action) => {
    const colors = {
      'CREATE': 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
      'UPDATE': 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      'DELETE': 'bg-rose-500/20 text-rose-400 border-rose-500/30',
      'SENT': 'bg-violet-500/20 text-violet-400 border-violet-500/30',
      'EMAIL_SENT': 'bg-violet-500/20 text-violet-400 border-violet-500/30',
      'BULK_DRAFT_GENERATE': 'bg-amber-500/20 text-amber-400 border-amber-500/30',
      'LOGIN': 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
      'LOGOUT': 'bg-slate-500/20 text-slate-400 border-slate-500/30',
    };
    return colors[action] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  };

  const exportLogs = () => {
    const headers = ['Timestamp', 'Actor', 'Action', 'Details', 'Lead', 'Email'].join(',');
    const rows = filteredLogs.map(l => {
      const clean = (val) => `"${(val || '').toString().replace(/"/g, '""')}"`;
      return [
        clean(l.created_at ? new Date(l.created_at).toLocaleString() : ''),
        clean(l.actor_name || l.actor_username || 'System'),
        clean(l.action),
        clean(l.details),
        clean(l.lead_name),
        clean(l.lead_email)
      ].join(',');
    });
    const csv = [headers, ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.setAttribute('hidden', ''); a.setAttribute('href', url);
    a.setAttribute('download', `AUDIT_LOGS_${new Date().toISOString().split('T')[0]}.csv`);
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  };

  if (loading && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-[80vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin"></div>
          <p className="text-slate-400 font-medium animate-pulse">Loading Audit Trail...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-[#0a0c10] p-2 lg:p-4 overflow-x-hidden">
      <div className="flex justify-between items-end mb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-6 h-6 rounded-lg bg-rose-500/10 flex items-center justify-center border border-rose-500/20">
              <ShieldCheck className="w-3.5 h-3.5 text-rose-400" />
            </div>
            <span className="text-[9px] font-black text-rose-400 uppercase tracking-[0.2em]">Security Control</span>
          </div>
          <h1 className="text-2xl font-black text-white uppercase tracking-tight">Audit <span className="text-rose-500">Logs</span></h1>
        </div>

        <div className="flex items-center gap-4">
          <button
            onClick={() => fetchLogs(pagination.page)}
            className="flex items-center gap-2 px-4 py-2.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all cursor-pointer"
          >
            <RefreshCcw className="w-3.5 h-3.5" /> Refresh
          </button>
          <button
            onClick={exportLogs}
            className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all cursor-pointer"
          >
            <Download className="w-3.5 h-3.5" /> Export CSV
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-4 mb-6">
        <div className="relative flex-1 min-w-[300px]">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search logs by actor, action, details..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-white/[0.03] border border-white/5 rounded-xl py-3 pl-12 pr-4 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-indigo-500/50 transition-all"
          />
        </div>

        <div className="flex items-center gap-3">
          <select
            value={filters.user_id}
            onChange={(e) => { setFilters({ ...filters, user_id: e.target.value }); setPagination(p => ({ ...p, page: 1 })); }}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50 cursor-pointer"
          >
            <option value="">All Users</option>
            {allUsers.map(u => (
              <option key={u.id} value={u.username}>{u.username}</option>
            ))}
          </select>

          <select
            value={filters.action}
            onChange={(e) => { setFilters({ ...filters, action: e.target.value }); setPagination(p => ({ ...p, page: 1 })); }}
            className="bg-white/[0.03] border border-white/5 rounded-xl py-3 px-4 text-[10px] font-black text-slate-400 uppercase tracking-widest focus:outline-none focus:border-indigo-500/50 cursor-pointer"
          >
            <option value="">All Actions</option>
            {actionOptions.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-[#0f111a] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/5 sticky top-0 z-10">
                <th className="px-3 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Timestamp</th>
                <th className="px-3 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Action</th>
                <th className="px-3 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Details</th>
                <th className="px-3 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Target Lead</th>
                <th className="px-3 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Lead Email</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredLogs.map((log, idx) => (
                <tr key={idx} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-3 py-3">
                    <div className="flex items-center gap-2">
                      <Clock className="w-3.5 h-3.5 text-slate-500" />
                      <span className="text-[12px] font-medium text-slate-400">
                        {log.created_at ? new Date(log.created_at).toLocaleString() : '—'}
                      </span>
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${getActionColor(log.action)}`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-[12px] font-medium text-slate-400 max-w-[250px] line-clamp-2 block">
                      {log.details || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-[12px] font-medium text-white">{log.lead_name || '—'}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className="text-[11px] font-medium text-slate-400">{log.lead_email || '—'}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filteredLogs.length === 0 && (
            <div className="p-20 text-center">
              <AlertCircle className="w-12 h-12 text-slate-700 mx-auto mb-4" />
              <div className="text-slate-500 font-bold uppercase tracking-widest">No audit logs found</div>
            </div>
          )}
        </div>
      </div>

      {pagination.pages > 1 && (
        <div className="flex items-center justify-between mt-4 px-2">
          <div className="text-[11px] font-medium text-slate-500">
            Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total} entries
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => fetchLogs(pagination.page - 1)}
              disabled={pagination.page === 1}
              className="flex items-center gap-1 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Prev
            </button>
            <span className="text-[11px] font-bold text-slate-400 px-4">
              Page {pagination.page} of {pagination.pages}
            </span>
            <button
              onClick={() => fetchLogs(pagination.page + 1)}
              disabled={pagination.page >= pagination.pages}
              className="flex items-center gap-1 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[10px] font-black uppercase tracking-widest rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              Next <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminAuditLogs;