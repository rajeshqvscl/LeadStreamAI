import React, { useState, useEffect } from 'react';
import { Link, useLocation, Outlet } from 'react-router-dom';

const Layout = () => {
  const location = useLocation();
  const pathParts = location.pathname.split('/');
  // If path is /dashboard, pathParts is ["", "dashboard"], so 2nd index is undefined.
  // If path is /dashboard/leads, pathParts is ["", "dashboard", "leads"]
  const activePage = pathParts[2] || 'dashboard';
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [time, setTime] = useState('');
  const [totalLeads, setTotalLeads] = useState(0);
  const [totalCompanies, setTotalCompanies] = useState(0);

  useEffect(() => {
    const updateTime = () => setTime(new Date().toLocaleTimeString('en-US', { hour12: false }));
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const { data } = await import('../services/api').then(m => m.default.get('/api/dashboard/stats'));
        if (data) {
          if (data.total_leads !== undefined) setTotalLeads(data.total_leads);
          if (data.total_companies !== undefined) setTotalCompanies(data.total_companies);
        }
      } catch (err) {
        console.error('Failed to fetch topbar stats', err);
      }
    };

    const fetchStatus = async () => {
      try {
        const { data } = await import('../services/api').then(m => m.default.get('/api/auth/me'));
        if (data) {
          // Update localStorage to keep status in sync across the app
          const localUser = JSON.parse(localStorage.getItem('user') || '{}');
          const updatedUser = { ...localUser, ...data };
          localStorage.setItem('user', JSON.stringify(updatedUser));
          
          // Trigger a re-render if needed by force-updating the user variable logic
          // (Since 'user' is re-read on every render from localStorage, we just need to trigger a state update)
          setTotalLeads(prev => prev); // Small hack to trigger render cycle
        }
      } catch (err) {
        console.error('Failed to poll user status', err);
      }
    };

    fetchStats();
    fetchStatus();
    
    const statsInterval = setInterval(fetchStats, 15000);
    const statusInterval = setInterval(fetchStatus, 12000); // Poll status every 12s
    
    return () => {
      clearInterval(statsInterval);
      clearInterval(statusInterval);
    };
  }, []);

  const user = JSON.parse(localStorage.getItem('user') || '{}');
  const getInitials = (name) => {
    if (!name) return 'AD';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <div className="flex min-h-screen bg-[#0b0f19] text-[#e2e8f0] font-sans">
      <aside className="w-[240px] bg-[#0e121d] border-r border-[#ffffff15] fixed top-0 left-0 bottom-0 z-[200] flex flex-col overflow-y-auto overflow-x-hidden transition-all pb-14">
        <div className="flex items-center gap-2.5 p-4 border-b border-[#ffffff15] shrink-0">
          <div className="w-[34px] h-[34px] rounded-lg bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center text-[18px] shrink-0 shadow-[0_2px_8px_rgba(59,130,246,0.3)] relative overflow-hidden">
            <span className="text-white relative z-10">⚡</span>
            <div className="absolute top-[-50%] left-[-50%] w-[200%] h-[200%] bg-[radial-gradient(circle,rgba(255,255,255,0.2)_0%,transparent_70%)]"></div>
          </div>
          <div>
            <h2 className="text-[15px] font-bold text-white tracking-[-0.3px] leading-[1.2]">LeadStream AI</h2>
            <small className="text-[10px] text-[#64748b] font-medium uppercase tracking-[0.5px]">Inbound System</small>
          </div>
        </div>

        <div className="p-3 pb-0">
          <Link to="/dashboard" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'dashboard' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'dashboard' ? 'text-white' : 'text-[#94a3b8]'}`}>📊</span> Dashboard
          </Link>
          <Link to="/dashboard/leads" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'leads' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'leads' ? 'text-white' : 'text-[#94a3b8]'}`}>👥</span> Lead Pipeline
          </Link>
          <Link to="/dashboard/bulk-search" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'bulk-search' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'bulk-search' ? 'text-white' : 'text-[#94a3b8]'}`}>🚀</span> Bulk Search
          </Link>
          <Link to="/dashboard/rocketreach" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'rocketreach' ? 'bg-orange-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0`}>🔍</span> RocketReach
          </Link>
          <Link to="/dashboard/companies" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'companies' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'companies' ? 'text-white' : 'text-[#94a3b8]'}`}>📊</span> Company Database
          </Link>
          <Link to="/dashboard/family-offices" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'family-offices' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'family-offices' ? 'text-white' : 'text-[#94a3b8]'}`}>🏢</span> Family Offices
          </Link>
          <Link to="/dashboard/emails" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'emails' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'emails' ? 'text-white' : 'text-[#94a3b8]'}`}>✉️</span> Email Drafts
          </Link>
          {/* 
          <Link to="/dashboard/generate" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'generate' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'generate' ? 'text-white' : 'text-[#94a3b8]'}`}>✨</span> AI Generation
          </Link> 
          */}
          <Link to="/dashboard/campaigns" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'campaigns' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'campaigns' ? 'text-white' : 'text-[#94a3b8]'}`}>🎯</span> Campaigns
          </Link>
          <Link to="/dashboard/followups" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'followups' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'followups' ? 'text-white' : 'text-[#94a3b8]'}`}>🔄</span> Follow-ups
          </Link>
        </div>

        <div className="p-3 pb-0">
          <div className="text-[10px] font-semibold uppercase tracking-[1px] text-[#475569] px-2 pt-2.5 pb-1.5">Analytics</div>
          <Link to="/dashboard/metrics" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'metrics' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'metrics' ? 'text-white' : 'text-[#94a3b8]'}`}>📈</span> Reports
          </Link>
          {user.role === 'ADMIN' && (
            <Link to="/dashboard/history" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'history' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
              <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'history' ? 'text-white' : 'text-[#94a3b8]'}`}>🕒</span> History
            </Link>
          )}
        </div>

        <div className="p-3 pb-0">
          <div className="text-[10px] font-semibold uppercase tracking-[1px] text-[#475569] px-2 pt-2.5 pb-1.5">Settings</div>
          <Link to="/dashboard/prompts" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'prompts' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
            <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'prompts' ? 'text-white' : 'text-[#94a3b8]'}`}>🧠</span> AI Prompts
          </Link>
          {user.role === 'ADMIN' && (
            <Link to="/dashboard/users" className={`flex items-center gap-2.5 px-2.5 py-[9px] rounded-lg text-[13px] font-medium transition-all mb-px ${activePage === 'users' ? 'bg-blue-600 text-white font-semibold' : 'text-[#94a3b8] hover:bg-white/5 hover:text-white'}`}>
              <span className={`text-[16px] w-[22px] text-center shrink-0 ${activePage === 'users' ? 'text-white' : 'text-[#94a3b8]'}`}>👥</span> Team Management
            </Link>
          )}
        </div>

        <div className="mt-auto p-3.5 border-t border-[#ffffff15] shrink-0 absolute bottom-0 left-0 w-[240px] bg-[#0e121d]">
          <div className="bg-[#151a26] rounded-xl p-3 border border-white/5">
            <div className="flex items-center justify-between mb-2">
              <div className="text-[9px] font-bold uppercase tracking-[0.8px] text-[#64748b]">Account Status</div>
              {user.is_approved ? (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20">
                  <div className="w-1 h-1 rounded-full bg-emerald-500 animate-pulse"></div>
                  <span className="text-[8px] font-black text-emerald-500 uppercase tracking-tighter">Active</span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/20">
                  <div className="w-1 h-1 rounded-full bg-amber-500"></div>
                  <span className="text-[8px] font-black text-amber-500 uppercase tracking-tighter">Locked</span>
                </div>
              )}
            </div>
            
            <div className="text-[12px] font-bold text-white mb-3 truncate">
              {user.full_name || user.username || 'Administrator'}
            </div>
            
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center px-2 py-0.5 rounded-[4px] text-[8px] font-black uppercase tracking-[1px] bg-indigo-500/15 text-indigo-400 border border-indigo-500/20">
                {user.role || 'ADMIN'}
              </span>
              <button 
                onClick={async () => { 
                  try { await import('../services/api').then(m => m.default.post('/api/auth/logout')); } catch (e) { console.error(e); } 
                  localStorage.removeItem('token'); 
                  localStorage.removeItem('user'); 
                  localStorage.removeItem('token_admin'); 
                  localStorage.removeItem('user_admin'); 
                  window.location.href = '/login?logout=success';
                }} 
                className="text-[10px] text-[#f43f5e] font-bold transition-all hover:text-rose-400 cursor-pointer hover:translate-x-0.5"
              >
                Logout →
              </button>
            </div>
          </div>
        </div>
      </aside>

      <header className="fixed top-0 left-[240px] right-0 h-[64px] bg-[#0e121d] border-b border-[#ffffff15] flex items-center justify-between z-[150] px-6">
        <div className="flex items-center gap-6">
          <div className="flex flex-col">
            <span className="text-[9px] font-semibold uppercase tracking-[0.8px] text-[#64748b] leading-none">Total Leads</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-[18px] font-bold text-white">{totalLeads}</span>
            </div>
          </div>
          <div className="w-px h-8 bg-white/10 mx-1" />
          <div className="flex flex-col">
            <span className="text-[9px] font-semibold uppercase tracking-[0.8px] text-[#64748b] leading-none">Total Registry</span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-[18px] font-bold text-white">{totalCompanies}</span>
            </div>
          </div>
          <div className="bg-black/20 border border-white/5 px-4 py-2 rounded-[10px] flex items-center gap-3">
            <div className="text-[10px] font-extrabold text-[#475569] uppercase tracking-[1px]">System Matrix</div>
            <div className="text-[14px] font-black text-white font-mono min-w-[80px]">{time}</div>
            <div className="inline-flex items-center px-1.5 py-0.5 border border-green-500/20 rounded-[4px] text-[8px] font-bold text-green-500 bg-green-500/10 tracking-[0.5px]">SYNCED</div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-[#111521] border border-[#ffffff15] rounded-lg px-3 py-[7px] w-[220px] focus-within:border-blue-500 focus-within:shadow-[0_0_0_2px_rgba(37,99,235,0.15)] transition-all">
            <span className="text-[#64748b] text-[14px]">🔍</span>
            <input type="text" placeholder="Search leads..." className="bg-transparent border-none text-[13px] text-[#e2e8f0] w-full outline-none placeholder:text-[#64748b]" />
          </div>
          <div className="relative">
            <div
              className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-[12px] font-bold text-white cursor-pointer border-2 border-transparent transition-all hover:border-blue-500"
              onClick={() => setDropdownOpen(!dropdownOpen)}
            >
              {getInitials(user.full_name)}
            </div>
            {dropdownOpen && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setDropdownOpen(false)}></div>
                <div className="absolute right-0 top-10 w-[200px] bg-[#151a26] border border-[#ffffff15] rounded-xl shadow-[0_10px_40px_rgba(0,0,0,0.6)] z-50 overflow-hidden">
                  <div className="flex items-center gap-3 p-3.5 border-b border-white/5">
                    <div className="w-9 h-9 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-[12px] font-bold text-white">
                      {getInitials(user.full_name)}
                    </div>
                    <div>
                      <div className="text-[13px] font-semibold text-white">
                        {user.full_name || 'Admin'}
                      </div>
                      <div className="text-[11px] font-medium text-[#64748b]">
                        {user.role || 'ADMIN'}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={async () => {
                      try {
                        await api.post('/api/auth/logout');
                      } catch (e) {
                        console.error('Logout API failed:', e);
                      }
                      localStorage.removeItem('token');
                      localStorage.removeItem('user');
                      localStorage.removeItem('token_admin');
                      localStorage.removeItem('user_admin');
                      window.location.href = '/login?logout=success';
                    }}
                    className="block w-full text-left px-3.5 py-2.5 text-[13px] text-[#f43f5e] font-medium hover:bg-white/5 transition-colors"
                  >
                    🚪 Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </header>


      <main className="ml-[240px] mt-[64px] flex-1 p-6 z-[100] relative">
        <Outlet />
      </main>
    </div>
  );
};

export default Layout;
