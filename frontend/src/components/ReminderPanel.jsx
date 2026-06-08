import React, { useState, useEffect, useCallback } from 'react';
import { Bell, Plus, X, Check, Clock, AlertTriangle, Loader2, Trash2, Mail, Send, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const PRIORITIES = [
  { value: 'HIGH', label: 'High', color: 'bg-rose-500/10 text-rose-400 border-rose-500/20' },
  { value: 'MEDIUM', label: 'Medium', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20' },
  { value: 'LOW', label: 'Low', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' },
];

const ReminderPanel = () => {
  const navigate = useNavigate();
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ title: '', description: '', due_at: '', priority: 'MEDIUM' });
  const [saving, setSaving] = useState(false);
  const [dueAlerts, setDueAlerts] = useState([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [urgent, setUrgent] = useState({ pending_followups: [], pending_followups_count: 0, pending_drafts: [], pending_drafts_count: 0, total_pending_leads: 0 });

  const userId = JSON.parse(localStorage.getItem('user') || '{}').id || 'admin';
  const headers = { 'X-User-Id': userId };

  const fetchReminders = useCallback(async () => {
    try {
      const { data } = await api.get('/api/reminders?status=PENDING', { headers });
      setReminders(data || []);
    } catch (e) {
      console.error('Failed to load reminders', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchUrgent = useCallback(async () => {
    try {
      const { data } = await api.get('/api/reminders/urgent-actions', { headers });
      setUrgent(data || { pending_followups: [], pending_followups_count: 0, pending_drafts: [], pending_drafts_count: 0, total_pending_leads: 0 });
    } catch (e) {
      console.error('Failed to load urgent actions', e);
    }
  }, []);

  const checkDue = useCallback(async () => {
    try {
      const { data } = await api.get('/api/reminders/due', { headers });
      if (data && data.length > 0) {
        setDueAlerts(data);
        setShowAlerts(true);
        // Play sound
        try {
          const ctx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = ctx.createOscillator();
          osc.type = 'sine';
          osc.frequency.value = 800;
          osc.connect(ctx.destination);
          osc.start();
          setTimeout(() => { osc.stop(); ctx.close(); }, 300);
        } catch {}
      }
    } catch (e) {
      console.error('Failed to check due reminders', e);
    }
  }, []);

  useEffect(() => { fetchReminders(); fetchUrgent(); }, []);
  useEffect(() => {
    checkDue();
    const interval = setInterval(() => { checkDue(); fetchUrgent(); }, 30000);
    return () => clearInterval(interval);
  }, [checkDue, fetchUrgent]);

  const handleCreate = async () => {
    if (!form.title.trim() || !form.due_at) return;
    setSaving(true);
    try {
      await api.post('/api/reminders', {
        title: form.title,
        description: form.description,
        due_at: new Date(form.due_at).toISOString(),
        priority: form.priority
      }, { headers });
      setForm({ title: '', description: '', due_at: '', priority: 'MEDIUM' });
      setShowAdd(false);
      fetchReminders();
    } catch (e) {
      alert('Failed: ' + (e.response?.data?.detail || e.message));
    } finally { setSaving(false); }
  };

  const handleComplete = async (id) => {
    try {
      await api.patch(`/api/reminders/${id}`, { status: 'COMPLETED' }, { headers });
      setReminders(prev => prev.filter(r => r.id !== id));
      setDueAlerts(prev => prev.filter(r => r.id !== id));
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`/api/reminders/${id}`);
      setReminders(prev => prev.filter(r => r.id !== id));
      setDueAlerts(prev => prev.filter(r => r.id !== id));
    } catch (e) { console.error(e); }
  };

  const formatDue = (dateStr) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = d - now;
    if (diff <= 0) return 'Overdue';
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m left`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h left`;
    const days = Math.floor(hours / 24);
    return `${days}d left`;
  };

  return (
    <>
      {/* Floating Bell */}
      <button onClick={() => setShowAlerts(true)}
        className="fixed bottom-6 right-6 z-[300] w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 border border-white/10 shadow-2xl flex items-center justify-center hover:scale-105 transition-all cursor-pointer group"
        title="Reminders">
        <Bell className="w-6 h-6 text-white" />
        {(reminders.length > 0 || urgent.pending_followups_count > 0 || urgent.pending_drafts_count > 0) && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-rose-500 text-[9px] font-black text-white flex items-center justify-center shadow-lg">
            {reminders.length + (urgent.pending_followups_count > 0 ? urgent.pending_followups_count : 0) + (urgent.pending_drafts_count > 0 ? urgent.pending_drafts_count : 0)}
          </span>
        )}
      </button>

      {/* Alerts Overlay */}
      {showAlerts && (
        <div className="fixed inset-0 z-[500] flex justify-end bg-black/40 backdrop-blur-sm animate-in fade-in duration-300">
          <div className="absolute inset-0" onClick={() => setShowAlerts(false)} />
          <div className="relative w-full max-w-md bg-[#0b0f1a] border-l border-white/10 h-full overflow-y-auto shadow-2xl animate-in slide-in-from-right duration-500 p-6">
            <div className="flex items-center justify-between mb-8">
              <div className="flex items-center gap-3">
                <Bell className="w-5 h-5 text-blue-400" />
                <h2 className="text-lg font-black text-white uppercase tracking-widest">Reminders</h2>
              </div>
              <div className="flex items-center gap-2">
                <button onClick={() => setShowAdd(true)}
                  className="p-2.5 bg-blue-500/10 hover:bg-blue-500/20 rounded-xl text-blue-400 transition-all cursor-pointer border border-blue-500/20">
                  <Plus className="w-4 h-4" />
                </button>
                <button onClick={() => setShowAlerts(false)}
                  className="p-2.5 bg-white/5 hover:bg-white/10 rounded-xl text-slate-400 transition-all cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Due Alerts */}
            {dueAlerts.length > 0 && (
              <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl">
                <div className="flex items-center gap-2 mb-3">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span className="text-[10px] font-black text-rose-400 uppercase tracking-widest">Overdue</span>
                </div>
                {dueAlerts.map(r => (
                  <div key={r.id} className="flex items-center justify-between py-2 border-b border-rose-500/10 last:border-0">
                    <span className="text-xs font-bold text-white truncate">{r.title}</span>
                    <button onClick={() => handleComplete(r.id)}
                      className="p-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-lg text-emerald-400 transition-all cursor-pointer">
                      <Check className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Urgent Actions */}
            <div className="mb-6 space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span className="text-[10px] font-black text-amber-400 uppercase tracking-widest">Urgent Actions</span>
              </div>

              <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Send className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-[11px] font-bold text-amber-300">Follow-ups Due</span>
                  </div>
                  <span className="text-[18px] font-black text-amber-400">{urgent.pending_followups_count}</span>
                </div>
                {urgent.pending_followups_count > 0 ? (
                  <div className="space-y-1.5">
                    {urgent.pending_followups.slice(0, 5).map(f => (
                      <div key={f.id} className="flex items-center justify-between text-[10px] text-slate-400">
                        <span className="truncate">{f.name} — {f.company_name || f.sector}</span>
                        <span className="text-amber-500 font-bold shrink-0 ml-2">Stage {f.followup_stage || 0}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-slate-500">No follow-ups due</p>
                )}
                <button onClick={() => { setShowAlerts(false); navigate('/dashboard/followups'); }}
                  className="mt-2 w-full py-2 bg-amber-600/20 hover:bg-amber-600/30 rounded-lg text-[9px] font-black text-amber-400 uppercase tracking-widest transition-all cursor-pointer flex items-center justify-center gap-1">
                  View All <ArrowRight className="w-3 h-3" />
                </button>
              </div>

              <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-2xl">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Mail className="w-3.5 h-3.5 text-rose-400" />
                    <span className="text-[11px] font-bold text-rose-300">Drafts Pending</span>
                  </div>
                  <span className="text-[18px] font-black text-rose-400">{urgent.pending_drafts_count}</span>
                </div>
                {urgent.pending_drafts_count > 0 ? (
                  <div className="space-y-1.5">
                    {urgent.pending_drafts.slice(0, 5).map(d => (
                      <div key={d.id} className="flex items-center justify-between text-[10px] text-slate-400">
                        <span className="truncate">{d.name} — {d.company_name || d.sector}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-slate-500">No drafts pending</p>
                )}
                <button onClick={() => { setShowAlerts(false); navigate('/dashboard/followups'); }}
                  className="mt-2 w-full py-2 bg-rose-600/20 hover:bg-rose-600/30 rounded-lg text-[9px] font-black text-rose-400 uppercase tracking-widest transition-all cursor-pointer flex items-center justify-center gap-1">
                  Review Drafts <ArrowRight className="w-3 h-3" />
                </button>
              </div>
            </div>

            {/* Reminder List */}
            {loading ? (
              <div className="flex justify-center py-10"><Loader2 className="w-6 h-6 text-blue-500 animate-spin" /></div>
            ) : reminders.length === 0 ? (
              <div className="py-20 text-center">
                <Clock className="w-10 h-10 text-slate-700 mx-auto mb-4" />
                <p className="text-[10px] font-black text-slate-600 uppercase tracking-widest">No pending reminders</p>
                <button onClick={() => setShowAdd(true)}
                  className="mt-4 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer">
                  + Add Reminder
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                {reminders.map(r => (
                  <div key={r.id} className="p-4 bg-white/[0.02] border border-white/5 rounded-xl hover:bg-white/[0.04] transition-all group">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-[9px] font-black px-2 py-0.5 rounded-full border ${(PRIORITIES.find(p => p.value === r.priority) || PRIORITIES[1]).color}`}>
                            {r.priority}
                          </span>
                          <span className={`text-[9px] font-bold ${new Date(r.due_at) <= new Date() ? 'text-rose-400' : 'text-slate-500'}`}>
                            {formatDue(r.due_at)}
                          </span>
                        </div>
                        <h4 className="text-sm font-bold text-white truncate">{r.title}</h4>
                        {r.description && <p className="text-[10px] text-slate-500 mt-1 line-clamp-2">{r.description}</p>}
                      </div>
                      <div className="flex items-center gap-1 shrink-0 ml-2">
                        <button onClick={() => handleComplete(r.id)}
                          className="p-1.5 bg-emerald-500/10 hover:bg-emerald-500/20 rounded-lg text-emerald-400 opacity-0 group-hover:opacity-100 transition-all cursor-pointer">
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleDelete(r.id)}
                          className="p-1.5 bg-rose-500/10 hover:bg-rose-500/20 rounded-lg text-rose-400 opacity-0 group-hover:opacity-100 transition-all cursor-pointer">
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5 text-[9px] text-slate-600">
                      <Clock className="w-3 h-3" />
                      {new Date(r.due_at).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Add Form */}
            {showAdd && (
              <div className="fixed inset-0 z-[600] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
                onClick={(e) => e.target === e.currentTarget && setShowAdd(false)}>
                <div className="bg-[#131722] border border-white/10 rounded-[32px] w-full max-w-md shadow-2xl overflow-hidden animate-in fade-in zoom-in duration-300">
                  <div className="p-8 border-b border-white/5 flex items-center justify-between">
                    <h3 className="text-base font-black text-white uppercase tracking-widest">New Reminder</h3>
                    <button onClick={() => setShowAdd(false)} className="p-2 bg-white/5 hover:bg-white/10 rounded-xl text-slate-400 transition-all cursor-pointer">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-8 space-y-5">
                    <div>
                      <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Title *</label>
                      <input value={form.title} onChange={(e) => setForm(f => ({ ...f, title: e.target.value }))}
                        placeholder="What needs to be done?"
                        className="w-full bg-[#0b0f19] border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 placeholder:text-slate-600" />
                    </div>
                    <div>
                      <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Description</label>
                      <textarea value={form.description} onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))}
                        rows={3} placeholder="Optional details..."
                        className="w-full bg-[#0b0f19] border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50 placeholder:text-slate-600 resize-none" />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Due Date *</label>
                        <input type="datetime-local" value={form.due_at}
                          onChange={(e) => setForm(f => ({ ...f, due_at: e.target.value }))}
                          className="w-full bg-[#0b0f19] border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                          style={{ colorScheme: 'dark' }} />
                      </div>
                      <div>
                        <label className="block text-[9px] font-black text-slate-500 uppercase tracking-widest mb-2">Priority</label>
                        <select value={form.priority} onChange={(e) => setForm(f => ({ ...f, priority: e.target.value }))}
                          className="w-full bg-[#0b0f19] border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500/50">
                          {PRIORITIES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                        </select>
                      </div>
                    </div>
                    <button onClick={handleCreate} disabled={saving || !form.title.trim() || !form.due_at}
                      className="w-full py-3.5 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 text-white font-black uppercase tracking-widest text-[10px] rounded-xl transition-all cursor-pointer disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-xl shadow-blue-600/20">
                      {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                      {saving ? 'Creating...' : 'Create Reminder'}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default ReminderPanel;
