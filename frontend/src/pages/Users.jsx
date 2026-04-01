import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Search, Plus, UserCircle, Shield, ShieldCheck, ShieldAlert, Mail, MoreHorizontal, Edit2, Trash2, X, Loader2, Check, AlertCircle, Play, RotateCcw } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const Users = () => {
  const navigate = useNavigate();
  const storedUser = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => {
    if (storedUser.username !== 'admin') {
      navigate('/dashboard');
    }
  }, [storedUser, navigate]);

  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total: 0 });
  const [filterRole, setFilterRole] = useState('');
  const [showDrawer, setShowDrawer] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'USER'
  });

  const fetchUsers = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/users/', {
        params: { page: pagination.page, role: filterRole || undefined }
      });
      setUsers(response.data.users || []);
      setPagination(prev => ({ ...prev, total: response.data.total }));
    } catch (err) {
      console.error('Failed to fetch users', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [pagination.page, filterRole]);

  const handleOpenDrawer = (user = null) => {
    if (user) {
      setEditingUser(user);
      setFormData({
        username: user.username,
        email: user.email,
        full_name: user.full_name || '',
        password: '',
        role: user.role
      });
    } else {
      setEditingUser(null);
      setFormData({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'USER'
      });
    }
    setShowDrawer(true);
  };

  const handleSubmit = async (e) => {
    if (e) e.preventDefault();
    try {
      if (editingUser) {
        await api.put(`/api/users/${editingUser.id}`, formData);
      } else {
        await api.post('/api/users/', formData);
      }
      setShowDrawer(false);
      fetchUsers();
    } catch (err) {
      alert('Operation failed: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to suspend this user?')) return;
    try {
      await api.delete(`/api/users/${id}`);
      fetchUsers();
    } catch (err) {
      alert('Failed to suspend user: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  const handleResume = async (id) => {
    if (!window.confirm('Are you sure you want to resume access for this user?')) return;
    try {
      await api.post(`/api/users/${id}/resume`);
      fetchUsers();
    } catch (err) {
      alert('Failed to resume user: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  const handleHardDelete = async (id) => {
    if (!window.confirm('CRITICAL: Permanent deletion cannot be undone. Delete this user record forever?')) return;
    try {
      await api.delete(`/api/users/${id}/hard`);
      fetchUsers();
    } catch (err) {
      alert('Failed to delete record: ' + (err.response?.data?.detail || 'Unknown error'));
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">System Access Control</h1>
          <p className="text-slate-400 text-sm mt-1">Manage administrative permissions and monitor system-wide user activity.</p>
        </div>
        <button
          onClick={() => handleOpenDrawer()}
          className="btn btn-primary px-6 py-2.5 shadow-blue-500/20"
        >
          <Plus className="w-5 h-5 mr-2" /> Provision User
        </button>
      </div>

      <div className="card bg-slate-800/20 border-white/5 backdrop-blur-md overflow-hidden shadow-2xl">
        <div className="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-slate-800/40">
          <div className="flex items-center gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search administrators..."
                className="bg-slate-900/50 border border-white/10 rounded-xl py-2 pl-10 pr-4 text-sm text-white focus:outline-none focus:border-blue-500/50 w-64 transition-all"
              />
            </div>
            <div className="flex bg-slate-900/80 p-1 rounded-xl border border-white/10">
              {[
                { label: 'All', value: '' },
                { label: 'Admins', value: 'ADMIN' },
                { label: 'Users', value: 'USER' },
              ].map(tab => (
                <button
                  key={tab.value}
                  onClick={() => setFilterRole(tab.value)}
                  className={`px-4 py-1.5 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${filterRole === tab.value ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-white'}`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Identity</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Access Level</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Account Status</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider">Registration</th>
                <th className="px-6 py-4 text-[10px] font-black text-slate-500 uppercase tracking-wider text-right">Settings</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 text-[13px]">
              {isLoading ? (
                <tr><td colSpan="5" className="px-6 py-20 text-center"><Loader2 className="w-8 h-8 text-blue-500 animate-spin mx-auto" /></td></tr>
              ) : users.length === 0 ? (
                <tr><td colSpan="5" className="px-6 py-20 text-center text-slate-500">No users found match the current criteria.</td></tr>
              ) : users.map(user => (
                <tr key={user.id} className="hover:bg-white/5 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-9 h-9 rounded-xl flex items-center justify-center font-bold text-white shadow-lg ${user.role === 'ADMIN' ? 'bg-gradient-to-br from-red-600 to-orange-600 shadow-red-600/20' :
                          'bg-gradient-to-br from-blue-600 to-cyan-600 shadow-blue-600/20'
                        }`}>
                        {user.username.substring(0, 1).toUpperCase()}
                      </div>
                      <div>
                        <div className="font-bold text-white leading-tight">{user.full_name || user.username}</div>
                        <div className="text-[11px] text-slate-500 mt-0.5">{user.email}</div>
                      </div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      {user.role === 'ADMIN' ? <ShieldAlert className="w-4 h-4 text-red-500" /> :
                        <ShieldCheck className="w-4 h-4 text-blue-500" />}
                      <span className="font-black text-[11px] uppercase tracking-widest text-slate-300">{user.role}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className={`w-1.5 h-1.5 rounded-full ${user.is_active ? 'bg-green-500 shadow-[0_0_8px_#10b981]' : 'bg-red-500 shadow-[0_0_8px_#ef4444]'}`}></div>
                      <span className={`text-[11px] font-extrabold uppercase tracking-tighter ${user.is_active ? 'text-green-500' : 'text-red-500'}`}>
                        {user.is_active ? 'Authorized' : 'Suspended'}
                      </span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-[11px] text-slate-500 font-medium whitespace-nowrap">
                    {new Date(user.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 text-right">
                    <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handleOpenDrawer(user)}
                        className="p-2 rounded-lg bg-slate-900 border border-white/5 hover:bg-blue-500/20 hover:text-blue-400 transition-all text-slate-500"
                        title="Update Policy"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      
                      {user.is_active ? (
                        <button
                          onClick={() => handleDelete(user.id)}
                          className="p-2 rounded-lg bg-slate-900 border border-white/5 hover:bg-orange-500/20 hover:text-orange-400 transition-all text-slate-500"
                          title="Suspend Access"
                        >
                          <AlertCircle className="w-4 h-4" />
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => handleResume(user.id)}
                            className="p-2 rounded-lg bg-slate-900 border border-white/5 hover:bg-emerald-500/20 hover:text-emerald-400 transition-all text-slate-500"
                            title="Resume Access"
                          >
                            <Play className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleHardDelete(user.id)}
                            className="p-2 rounded-lg bg-slate-900 border border-white/5 hover:bg-red-500/20 hover:text-red-400 transition-all text-slate-500"
                            title="Delete Record Permanently"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* User Provisioning Drawer — rendered via Portal to escape main's stacking context */}
      {createPortal(
        <>
          <div className={`drawer-backdrop ${showDrawer ? 'show' : ''}`} onClick={() => setShowDrawer(false)}></div>
          <div className={`drawer ${showDrawer ? 'show' : ''}`}>
            <div className="drawer-header bg-slate-900/50">
              <div>
                <h2 className="text-white font-bold text-lg flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white"><UserCircle className="w-5 h-5" /></div>
                  {editingUser ? 'Policy Modification' : 'Access Provisioning'}
                </h2>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Identity & Access Management</p>
              </div>
              <button onClick={() => setShowDrawer(false)} className="text-slate-500 hover:text-white transition-colors">
                <X className="w-6 h-6" />
              </button>
            </div>
            <div className="drawer-body bg-[#0a0f1a]">
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="form-group">
                  <label>System Username</label>
                  <input
                    type="text"
                    required
                    className="form-control bg-slate-900/50"
                    placeholder="Unique Identifier"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Corporate Email</label>
                  <input
                    type="email"
                    required
                    className="form-control bg-slate-900/50"
                    placeholder="user@organization.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Full Identity Name</label>
                  <input
                    type="text"
                    className="form-control bg-slate-900/50"
                    placeholder="Legal Identity"
                    value={formData.full_name}
                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Access Credential (Password)</label>
                  <input
                    type="password"
                    required={!editingUser}
                    className="form-control bg-slate-900/50"
                    placeholder={editingUser ? "Leave blank to keep current" : "Minimum 8 characters"}
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  />
                </div>

                <div className="form-group">
                  <label>Global Permission Role</label>
                  <div className="space-y-3 mt-3">
                    {[
                      { id: 'ADMIN', label: 'Global Administrator', desc: 'Full system overrides and security control', icon: ShieldAlert, color: 'text-red-500' },
                      { id: 'USER', label: 'Standard User', desc: 'Access to core features and campaign management', icon: ShieldCheck, color: 'text-blue-500' },
                    ].map(role => (
                      <label
                        key={role.id}
                        className={`flex items-center gap-4 p-4 rounded-2xl border cursor-pointer transition-all ${formData.role === role.id ? 'bg-blue-600/10 border-blue-600/50' : 'bg-slate-900 border-white/5 hover:border-white/10'}`}
                      >
                        <input
                          type="radio"
                          name="role"
                          className="hidden"
                          checked={formData.role === role.id}
                          onChange={() => setFormData({ ...formData, role: role.id })}
                        />
                        <div className={`w-10 h-10 rounded-xl bg-slate-950 flex items-center justify-center ${role.color} ${formData.role === role.id ? 'shadow-lg' : ''}`}>
                          <role.icon className="w-5 h-5" />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center justify-between">
                            <span className={`text-sm font-bold ${formData.role === role.id ? 'text-white' : 'text-slate-300'}`}>{role.label}</span>
                            {formData.role === role.id && <Check className="w-4 h-4 text-blue-500" />}
                          </div>
                          <p className="text-[10px] text-slate-500 font-medium mt-0.5">{role.desc}</p>
                        </div>
                      </label>
                    ))}
                  </div>
                </div>
              </form>
            </div>
            <div className="drawer-footer bg-slate-900/20">
              <button className="btn btn-ghost px-6" onClick={() => setShowDrawer(false)}>Terminate</button>
              <button onClick={handleSubmit} className="btn btn-primary px-8 shadow-blue-600/20">
                {editingUser ? 'Update Policy' : 'Finalize Provisioning'}
              </button>
            </div>
          </div>
        </>,
        document.body
      )}
    </div>
  );
};

export default Users;
