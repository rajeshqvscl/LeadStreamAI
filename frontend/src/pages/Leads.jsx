import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Search, Plus, Rocket, Filter, MapPin, Phone, Linkedin, ChevronLeft, ChevronRight, X, Loader2, CheckCircle, AlertTriangle, Sparkles } from 'lucide-react';
import api from '../services/api';

const Leads = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total_pages: 1, total: 0 });
  const [filters, setFilters] = useState({
    search: '',
    persona: '',
    status: '',
    country: '',
    city: '',
    show_unsubscribed: false,
  });
  
  // Hardcoded for now based on templates, ideally fetched from API
  const personas = ['FOUNDER', 'INVESTOR', 'PARTNER', 'OTHER'];
  const statuses = ['PENDING', 'VALIDATING', 'VALID', 'INVALID'];
  
  const [discoveryTab, setDiscoveryTab] = useState('company'); // 'company' or 'bulk'
  const [discoveryLoading, setDiscoveryLoading] = useState(false);

  const [showAddModal, setShowAddModal] = useState(false);
  const [notification, setNotification] = useState(null); // { type: 'success' | 'error', message: string }

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };



  const fetchLeads = async () => {
    setIsLoading(true);
    try {
      const params = {
        page: pagination.page,
        search: filters.search,
        persona: filters.persona,
        validation_status: filters.status,
        city: filters.city,
        country: filters.country,
      };
      const response = await api.get('/api/leads', { params });
      setLeads(response.data.leads);
      setPagination(prev => ({ 
        ...prev, 
        total_pages: Math.ceil(response.data.total / 25),
        total: response.data.total 
      }));
    } catch (err) {
      console.error('Failed to fetch leads', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [pagination.page, filters]);

  const handleFilterChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const handleDiscoverySubmit = async (e) => {
    e.preventDefault();
    setDiscoveryLoading(true);
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    
    try {
      await api.post('/api/ingest-leads', data);
      fetchLeads();
      showNotification('success', 'Extraction started successfully. New leads will appear shortly.');
    } catch (err) {
      showNotification('error', 'Extraction failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDiscoveryLoading(false);
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Lead Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">Manage and approve AI-triaged investment leads with active filters.</p>
        </div>
      </div>

      <div className="flex gap-4 mb-6">
        <button 
          onClick={() => setShowAddModal(true)}
          className="flex-1 btn btn-ghost py-3.5 text-base border-dashed hover:border-blue-500/50"
        >
          <Plus className="w-5 h-5 mr-2" /> New Lead
        </button>
        <button className="flex-1 btn btn-primary py-3.5 text-base shadow-blue-500/20">
          <Rocket className="w-5 h-5 mr-2" /> Batch Import
        </button>
      </div>

      {/* Discovery Engine Panel */}
      <div className="bg-gradient-to-br from-[#1e293b]/70 to-[#0f172a]/90 border border-blue-500/20 rounded-[20px] p-6 mb-8 relative overflow-hidden group shadow-heavy">
        <div className="flex justify-between items-center mb-5">
          <h3 className="text-white font-bold flex items-center gap-2">
            <span className="text-xl text-[#3b82f6]">⚡</span>
            RocketReach <span className="bg-gradient-to-r from-[#3b82f6] to-[#8b5cf6] bg-clip-text text-transparent">Discovery Engine</span>
          </h3>
          <div className="flex gap-4">
            <button 
              onClick={() => setDiscoveryTab('company')}
              className={`pb-2 text-[12px] font-extrabold uppercase tracking-wider transition-all relative ${discoveryTab === 'company' ? 'text-[#3b82f6] after:absolute after:bottom-[-2px] after:left-0 after:right-0 after:h-0.5 after:bg-[#3b82f6] after:shadow-[0_0_10px_#3b82f6]' : 'text-[#475569] hover:text-white'}`}
            >
              1. Company Search
            </button>
            <button 
              onClick={() => setDiscoveryTab('bulk')}
              className={`pb-2 text-[12px] font-extrabold uppercase tracking-wider transition-all relative ${discoveryTab === 'bulk' ? 'text-[#8b5cf6] after:absolute after:bottom-[-2px] after:left-0 after:right-0 after:h-0.5 after:bg-[#8b5cf6] after:shadow-[0_0_10px_#8b5cf6]' : 'text-[#475569] hover:text-white'}`}
            >
              2. Bulk Search
            </button>
          </div>
        </div>

        <form onSubmit={handleDiscoverySubmit}>
          {discoveryTab === 'company' ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-1.5 md:col-span-1">
                <label className="text-[10px] font-extrabold text-[#3b82f6] uppercase tracking-widest pl-1">Target Company</label>
                <input type="text" name="company" className="form-control" placeholder="e.g. NVIDIA, Stripe" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Job Title</label>
                <input type="text" name="title" className="form-control" placeholder="e.g. CTO, Founder" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Location</label>
                <input type="text" name="location" className="form-control" placeholder="e.g. California" />
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#8b5cf6] uppercase tracking-widest pl-1">Broad Titles</label>
                <input type="text" name="bulk_title" className="form-control border-[#8b5cf6]/20" placeholder="Founders" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Location</label>
                <input type="text" name="bulk_location" className="form-control" placeholder="USA" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Industry</label>
                <input type="text" name="industry" className="form-control" placeholder="SaaS" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Keywords</label>
                <input type="text" name="keyword" className="form-control" placeholder="AI, Web3" />
              </div>
              <div className="space-y-1.5">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Exclude</label>
                <input type="text" name="exclude" className="form-control" placeholder="HR, Recruiting" />
              </div>
            </div>
          )}

          <div className="flex justify-between items-center mt-6 pt-5 border-t border-white/5">
            <div className="flex items-center gap-4">
              <div className="bg-black/30 px-4 py-2 rounded-xl border border-white/5 flex items-center gap-3">
                <label className="text-[10px] font-black text-[#475569] uppercase">Limit</label>
                <input type="number" name="count" defaultValue="10" min="1" max="100" className="bg-transparent border-none text-white font-black w-8 outline-none text-[15px]" />
              </div>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-[#10b981] rounded-full shadow-[0_0_8px_#10b981]"></div>
                <span className="text-[11px] text-[#475569] font-semibold">RocketReach API Connected</span>
              </div>
            </div>
            <button 
              type="submit" 
              disabled={discoveryLoading}
              className={`btn px-10 py-3.5 rounded-[12px] font-extrabold text-white shadow-lg transition-all duration-300 min-w-[200px] ${discoveryTab === 'company' ? 'bg-[#3b82f6] hover:bg-[#2563eb] shadow-[0_10px_20px_rgba(37,99,235,0.2)]' : 'bg-[#8b5cf6] hover:bg-[#7c3aed] shadow-[0_10px_20px_rgba(139,92,246,0.2)]'}`}
            >
              {discoveryLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Searching RocketReach...</span>
                </div>
              ) : (
                'Begin Extraction'
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Filter System */}
      <div className="bg-[#151a26] border border-[#ffffff08] rounded-[14px] px-4 py-3 mb-6 flex items-center shadow-lg divide-x divide-[#ffffff08] overflow-x-auto whitespace-nowrap hide-scrollbar">
        <div className="flex items-center gap-2 px-3 pr-5 min-w-[220px]">
          <Search className="w-3.5 h-3.5 text-slate-500" />
          <input 
            type="text" 
            name="search" 
            placeholder="Search by name, email or company..." 
            className="bg-transparent border-none text-white text-[11px] font-medium w-full outline-none"
            value={filters.search}
            onChange={handleFilterChange}
          />
        </div>

        <div className="flex items-center gap-2 px-4">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Role:</span>
          <select 
            name="persona" 
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none"
            value={filters.persona}
            onChange={handleFilterChange}
          >
            <option value="">All Personas ▼</option>
            {personas.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>

        <div className="flex items-center gap-2 px-4">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Status:</span>
          <select 
            name="status" 
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none"
            value={filters.status}
            onChange={handleFilterChange}
          >
            <option value="">All Statuses ▼</option>
            {statuses.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="flex items-center gap-2 px-4">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Location:</span>
          <select 
            name="country" 
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none min-w-[60px]"
            value={filters.country}
            onChange={handleFilterChange}
          >
            <option value="">Global ▼</option>
            <option value="United States">US</option>
            <option value="United Kingdom">UK</option>
          </select>
        </div>

        <div className="flex items-center gap-2 px-4">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">City:</span>
          <select 
            name="city" 
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none min-w-[70px]"
            value={filters.city}
            onChange={handleFilterChange}
          >
            <option value="">All Cities ▼</option>
          </select>
        </div>

        <div className="flex items-center gap-2 px-4">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Show Opt-Outs</span>
          <div className="relative inline-block w-8 h-4 cursor-pointer" onClick={() => setFilters(prev => ({...prev, show_unsubscribed: !prev.show_unsubscribed}))}>
            <div className={`absolute inset-0 rounded-full transition-colors ${filters.show_unsubscribed ? 'bg-[#3b82f6]' : 'bg-[#1e293b]'}`}></div>
            <div className={`absolute top-[2px] left-[2px] bg-white w-[12px] h-[12px] rounded-full transition-transform ${filters.show_unsubscribed ? 'translate-x-4' : 'translate-x-0'}`}></div>
          </div>
        </div>

        <div className="flex items-center gap-2 px-4 flex-1 justify-end border-r-0">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Group By:</span>
          <select className="bg-transparent text-white text-[11px] font-bold outline-none cursor-pointer appearance-none">
            <option>None ▼</option>
          </select>
        </div>

        <div className="pl-4 pr-1">
          <button 
            onClick={() => setFilters({ search: '', persona: '', status: '', country: '', city: '', show_unsubscribed: false })}
            className="flex items-center px-4 py-1.5 bg-[#ffffff05] hover:bg-[#ffffff0a] rounded-lg border border-[#ffffff08] transition-colors text-[10px] font-extrabold text-slate-300"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Results Grid */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center py-32 opacity-50">
          <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-400 font-medium">Synchronizing lead pipeline...</p>
        </div>
      ) : leads.length === 0 ? (
        <div className="bg-slate-800/20 border border-dashed border-white/10 rounded-3xl p-24 text-center">
          <div className="text-5xl mb-6 opacity-20">🔭</div>
          <h3 className="text-white text-lg font-bold mb-2">No Leads Found</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">Try adjusting your filters or use the Discovery Engine above to find new investment targets.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mb-10">
            {leads.map((lead) => {
              const personaVal = lead.persona || 'OTHER';
              const score = lead.fit_score || 0;
              const fitClass = score >= 80 ? 'text-[#10b981]' : (score >= 50 ? 'text-[#f59e0b]' : 'text-[#64748b]');
              const fitBg = score >= 80 ? 'bg-[#10b981]' : (score >= 50 ? 'bg-[#f59e0b]' : 'bg-[#64748b]');
              
              return (
                <div key={lead.id} 
                  className="bg-[#151a26] border border-[#ffffff08] rounded-[16px] p-5 hover:border-[#ffffff15] hover:bg-[#1a202c] transition-all cursor-pointer relative overflow-hidden group shadow-[0_4px_20px_rgba(0,0,0,0.2)] flex flex-col justify-between h-[230px]"
                  onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                >
                  <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-accent-indigo/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                  
                  <div>
                    {/* Top Row */}
                    <div className="flex justify-between items-start mb-5">
                      <div className="flex items-center gap-3">
                        <div className={`w-11 h-11 rounded-[10px] flex items-center justify-center text-[15px] font-black shadow-lg ${
                          ['FOUNDER','C-SUITE','EXECUTIVE'].includes(personaVal) ? 'bg-[#2563eb] text-white' :
                          ['PARTNER','INVESTOR'].includes(personaVal) ? 'bg-[#8b5cf6] text-white' :
                          'bg-[#f59e0b] text-white'
                        }`}>
                          {lead.name.substring(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <h4 className="text-white font-bold text-[15px] tracking-tight mb-0.5 group-hover:text-blue-400 transition-colors">{lead.name}</h4>
                          <p className="text-[#64748b] text-[12px] font-medium line-clamp-1">
                            {lead.company_name || lead.family_office_name || lead.industry || 'Unknown Sector'}
                          </p>
                        </div>
                      </div>
                      <div className={`px-2 py-1 rounded-[6px] text-[9px] font-black tracking-widest flex items-center gap-1.5 uppercase border border-transparent ${
                        ['FOUNDER','C-SUITE','EXECUTIVE'].includes(personaVal) ? 'bg-[#3b82f6]/10 text-[#60a5fa]' :
                        ['PARTNER','INVESTOR'].includes(personaVal) ? 'bg-[#8b5cf6]/10 text-[#a78bfa]' :
                        'bg-[#f59e0b]/10 text-[#fbbf24]'
                      }`}>
                        <span className="opacity-80 text-[10px]">
                           {['FOUNDER','C-SUITE','EXECUTIVE'].includes(personaVal) ? '📁' : ['PARTNER','INVESTOR'].includes(personaVal) ? '🤝' : '👤'}
                        </span>
                        {{ 'C-SUITE': 'FOUNDER', 'EXECUTIVE': 'FOUNDER', 'INVESTOR': 'PARTNER' }[personaVal] || personaVal}
                      </div>
                    </div>

                    {/* Location & Phone Row */}
                    <div className="flex items-center justify-between text-[#475569] font-medium text-[11px] mb-8">
                       <div className="flex items-center gap-1.5 line-clamp-1 flex-1">
                         <MapPin className="w-3 h-3 text-red-500/80" />
                         {[lead.city, lead.country].filter(Boolean).join(', ') || 'Remote'}
                       </div>
                       {lead.phone && (
                         <div className="flex items-center gap-1 text-slate-500 tabular-nums ml-2">
                           <Phone className="w-2.5 h-2.5" />
                           {lead.phone}
                         </div>
                       )}
                    </div>

                    {/* Strategic Fit */}
                    <div>
                      <div className="flex justify-between items-center mb-2.5">
                        <span className="text-[10px] font-bold text-[#475569] uppercase tracking-widest">Strategic Fit</span>
                        <span className={`text-[13px] font-black ${fitClass}`}>{score}%</span>
                      </div>
                      <div className="h-1.5 w-full bg-[#1e2433] rounded-full overflow-hidden">
                        <div className={`h-full ${fitBg} rounded-full transition-all duration-1000`} style={{ width: `${score}%` }}></div>
                      </div>
                    </div>
                  </div>

                  {/* Date Pill at Bottom */}
                  <div className="flex justify-end mt-4">
                     <span className="bg-white/5 border border-white/5 text-[#64748b] text-[9px] font-bold tabular-nums tracking-widest px-2 py-1 rounded">
                       {lead.created_at ? lead.created_at.split('T')[0] : '2026-03-09'}
                     </span>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          {pagination.total_pages > 1 && (
            <div className="flex justify-center items-center gap-2 pb-10">
              <button 
                disabled={pagination.page === 1}
                onClick={() => setPagination(v => ({ ...v, page: v.page - 1 }))}
                className="w-10 h-10 flex items-center justify-center rounded-xl bg-slate-800 border border-white/5 text-slate-400 disabled:opacity-20 translate-y-0 hover:-translate-y-0.5 transition-all"
              >
                <ChevronLeft className="w-5 h-5" />
              </button>
              
              <div className="flex gap-1">
                {[...Array(pagination.total_pages)].map((_, i) => (
                  <button 
                    key={i}
                    onClick={() => setPagination(v => ({ ...v, page: i + 1 }))}
                    className={`w-10 h-10 rounded-xl font-bold text-sm transition-all ${
                      pagination.page === i + 1 
                      ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/20' 
                      : 'bg-slate-800 border border-white/5 text-slate-400 hover:bg-slate-700'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>

              <button 
                disabled={pagination.page === pagination.total_pages}
                onClick={() => setPagination(v => ({ ...v, page: v.page + 1 }))}
                className="w-10 h-10 flex items-center justify-center rounded-xl bg-slate-800 border border-white/5 text-slate-400 disabled:opacity-20 translate-y-0 hover:-translate-y-0.5 transition-all"
              >
                <ChevronRight className="w-5 h-5" />
              </button>
            </div>
          )}
        </>
      )}

      {/* Add Lead Mock Drawer */}
      <div className={`drawer-backdrop ${showAddModal ? 'show' : ''}`} onClick={() => setShowAddModal(false)}></div>
      <div className={`drawer ${showAddModal ? 'show' : ''}`}>
        <div className="drawer-header">
          <h2 className="text-white font-bold text-lg flex items-center gap-2">
            <span className="text-xl">👥</span> Add New Target
          </h2>
          <button onClick={() => setShowAddModal(false)} className="text-slate-500 hover:text-white transition-colors">
            <X className="w-6 h-6" />
          </button>
        </div>
        <div className="drawer-body">
          <form className="space-y-4">
            <div className="form-group">
              <label>Full Name</label>
              <input type="text" className="form-control" placeholder="John Doe" />
            </div>
            <div className="form-group">
              <label>Email Address</label>
              <input type="email" className="form-control" placeholder="john@example.com" />
            </div>
            <div className="form-group">
              <label>Target Role (Persona)</label>
              <select className="form-control">
                {personas.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Company</label>
              <input type="text" className="form-control" placeholder="Acme Inc" />
            </div>
            <div className="form-group">
              <label>LinkedIn URL</label>
              <input type="url" className="form-control" placeholder="https://linkedin.com/in/..." />
            </div>
          </form>
        </div>
        <div className="drawer-footer">
          <button className="btn btn-ghost" onClick={() => setShowAddModal(false)}>Cancel</button>
          <button className="btn btn-primary px-8">Create Lead</button>
        </div>
      </div>

      {/* Toast Notification */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4 duration-300`}>
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${
            notification.type === 'success' 
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' 
            : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {notification.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
            <p className="text-sm font-bold tracking-tight">{notification.message}</p>
            <button 
              onClick={() => setNotification(null)}
              className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Leads;
