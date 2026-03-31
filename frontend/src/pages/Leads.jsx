import React, { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Rocket, X, Loader2, CheckCircle, AlertTriangle, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, Tag, MoreHorizontal, Sparkles, Upload, FileText, Trash2, RefreshCw } from 'lucide-react';
import api from '../services/api';

const Leads = () => {
  const navigate = useNavigate();
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pagination, setPagination] = useState({ page: 1, total_pages: 1, total: 0 });
  const [filters, setFilters] = useState({
    search: '',
    title: '',
    persona: '',
    status: '',
    country: '',
    city: '',
    company: '',
    show_unsubscribed: false,
  });

  // Hardcoded for now based on templates, ideally fetched from API
  const personas = ['FOUNDER', 'INVESTOR', 'PARTNER', 'OTHER'];
  const statuses = ['PENDING', 'VALIDATING', 'VALID', 'INVALID'];

  const [discoveryTab, setDiscoveryTab] = useState('company'); // 'company' or 'bulk'
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [notification, setNotification] = useState(null); 
  
  // Table specific state
  const [selectedLeads, setSelectedLeads] = useState(new Set());
  const [sortConfig, setSortConfig] = useState({ key: 'created_at', direction: 'desc' });
  
  const [showLabelModal, setShowLabelModal] = useState(false);
  const [labelInput, setLabelInput] = useState('');
  const [targetLeadIds, setTargetLeadIds] = useState([]); // IDs of leads to receive new label

  // Custom Multi-Select State
  const availableTitles = ['CEO', 'Founder', 'Co Founder', 'CFO', 'MD', 'Director'];
  const [selectedTitles, setSelectedTitles] = useState([]);
  const [showTitleDropdown, setShowTitleDropdown] = useState(false);
  
  const toggleTitle = (title) => {
    setSelectedTitles(prev => 
      prev.includes(title) ? prev.filter(t => t !== title) : [...prev, title]
    );
  };

  const [showFilterTitleDropdown, setShowFilterTitleDropdown] = useState(false);
  const toggleFilterTitle = (title) => {
    setFilters(prev => {
      let current = prev.title ? prev.title.split(',') : [];
      if (current.includes(title)) {
        current = current.filter(t => t !== title);
      } else {
        current.push(title);
      }
      return { ...prev, title: current.join(',') };
    });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

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
        title: filters.title,
        persona: filters.persona,
        validation_status: filters.status,
        city: filters.city,
        company: filters.company,
        country: filters.country,
      };
      const response = await api.get('/api/leads', { params });
      
      // Map leads to ensure 'labels' array exists locally even if backend doesn't return it yet
      const fetchedLeads = response.data.leads.map(lead => ({
        ...lead,
        labels: lead.labels || []
      }));
      
      setLeads(fetchedLeads);
      setPagination(prev => ({
        ...prev,
        total_pages: Math.ceil(response.data.total / 25),
        total: response.data.total
      }));
      setSelectedLeads(new Set()); // Context reset
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
    
    // Inject multi-select titles into payload
    if (discoveryTab === 'company' && selectedTitles.length > 0) {
      data.title = selectedTitles.join(',');
    }

    try {
      const response = await api.post('/api/ingest-leads', data);
      fetchLeads();
      
      if (response.data.inserted === 0) {
        showNotification('error', `No data found for this specific search (${data.company || data.bulk_title || 'query'}).`);
      } else {
        showNotification('success', `Extraction complete. ${response.data.inserted} new leads added.`);
      }
    } catch (err) {
      showNotification('error', 'Extraction failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setDiscoveryLoading(false);
    }
  };

  // Setup Sorting
  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortedLeads = useMemo(() => {
    let sortableItems = [...leads];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let valA = a[sortConfig.key] || '';
        let valB = b[sortConfig.key] || '';
        if (typeof valA === 'string') valA = valA.toLowerCase();
        if (typeof valB === 'string') valB = valB.toLowerCase();
        
        if (valA < valB) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (valA > valB) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [leads, sortConfig]);

  // Selection Management
  const handleSelectAll = (e) => {
    if (e.target.checked) {
      setSelectedLeads(new Set(leads.map(lead => lead.id)));
    } else {
      setSelectedLeads(new Set());
    }
  };

  const handleSelectOne = (e, id) => {
    const newSelected = new Set(selectedLeads);
    if (e.target.checked) {
      newSelected.add(id);
    } else {
      newSelected.delete(id);
    }
    setSelectedLeads(newSelected);
  };

  // Bulk Email Actions
  const handleGenerateDomainDrafts = async () => {
    if (selectedLeads.size === 0) return;
    setIsLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      const res = await api.post('/api/generate-bulk-domain-drafts', { lead_ids: leadIds });
      showNotification('success', res.data.message);
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to generate drafts: ' + (err.response?.data?.error || err.message));
      setIsLoading(false);
    }
  };

  const handleSendDomainEmails = async () => {
    if (selectedLeads.size === 0) return;
    setIsLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      const res = await api.post('/api/send-bulk-domain-emails', { lead_ids: leadIds });
      showNotification('success', res.data.message);
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to send emails: ' + (err.response?.data?.error || err.message));
      setIsLoading(false);
    }
  };
  
  const handleApproveDomainDrafts = async () => {
    if (selectedLeads.size === 0) return;
    setIsLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      const res = await api.post('/api/approve-bulk-domain-drafts', { lead_ids: leadIds });
      showNotification('success', res.data.message);
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to approve drafts: ' + (err.response?.data?.error || err.message));
      setIsLoading(false);
    }
  };

  // Labels Management
  const handleAddLabelToSelected = () => {
    if (selectedLeads.size === 0) return;
    setTargetLeadIds(Array.from(selectedLeads));
    setShowLabelModal(true);
  };

  const handleAddLabelToSingle = (id) => {
    setTargetLeadIds([id]);
    setShowLabelModal(true);
  };
  const submitLabels = () => {
    if (!labelInput.trim()) return;
    const newLabels = labelInput.split(',').map(l => l.trim()).filter(l => l);

    // Apply labels through API
    api.post('/api/leads/bulk-labels', { lead_ids: targetLeadIds, labels: newLabels })
      .then(() => {
        setLeads(prev => prev.map(lead => {
          if (targetLeadIds.includes(lead.id)) {
            const uniqueLabels = Array.from(new Set([...(lead.labels || []), ...newLabels]));
            return { ...lead, labels: uniqueLabels };
          }
          return lead;
        }));
        showNotification('success', `Added ${newLabels.length} label(s) to ${targetLeadIds.length} lead(s).`);
      })
      .catch(err => {
        showNotification('error', 'Failed to save labels to server.');
        console.error(err);
      });
    
    setShowLabelModal(false);
    setLabelInput('');
    setTargetLeadIds([]);
  };

  const removeLabel = (leadId, labelToRemove) => {
    api.post(`/api/leads/${leadId}/remove-label`, { label: labelToRemove })
      .then(() => {
        setLeads(prev => prev.map(lead => {
          if (lead.id === leadId) {
            return { ...lead, labels: (lead.labels || []).filter(l => l !== labelToRemove) };
          }
          return lead;
        }));
      })
      .catch(err => {
        console.error('Failed to remove label:', err);
      });
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Lead Pipeline</h1>
          <p className="text-slate-400 text-sm mt-1">Manage and organize your AI-triaged investment leads via list view.</p>
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

      {/* Discovery Engine Panel - Same as Original */}
      <div className="bg-gradient-to-br from-[#1e293b]/70 to-[#0f172a]/90 border border-blue-500/20 rounded-[20px] p-6 mb-8 relative group shadow-heavy">
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
              <div className="space-y-1.5 relative">
                <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Job Title</label>
                <div 
                  className="form-control cursor-pointer flex items-center justify-between"
                  onClick={() => setShowTitleDropdown(!showTitleDropdown)}
                >
                  <span className={`text-sm ${selectedTitles.length === 0 ? 'text-slate-500' : 'text-white'}`}>
                    {selectedTitles.length === 0 ? 'Any Title / Auto' : selectedTitles.length <= 2 ? selectedTitles.join(', ') : `${selectedTitles.length} selected`}
                  </span>
                  <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${showTitleDropdown ? 'rotate-180' : ''}`} />
                </div>
                
                {/* Custom Multi-Select Dropdown Menu */}
                {showTitleDropdown && (
                  <>
                    <div className="fixed inset-0 z-[100]" onClick={() => setShowTitleDropdown(false)}></div>
                    <div className="absolute top-full left-0 right-0 mt-2 bg-[#151a26] border border-[#ffffff10] rounded-xl shadow-2xl z-[150] overflow-hidden animate-in fade-in slide-in-from-top-2">
                      <div className="max-h-[200px] overflow-y-auto custom-scrollbar p-2">
                        {availableTitles.map(title => (
                          <div 
                            key={title}
                            onClick={() => toggleTitle(title)}
                            className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                          >
                            <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${selectedTitles.includes(title) ? 'bg-blue-500 border-blue-500' : 'border-slate-600 bg-transparent'}`}>
                              {selectedTitles.includes(title) && <CheckCircle className="w-3 h-3 text-white" />}
                            </div>
                            <span className={`text-sm font-semibold tracking-wide ${selectedTitles.includes(title) ? 'text-white' : 'text-slate-400'}`}>
                              {title}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
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

      {/* Filter System - Same as Original */}
      <div className="bg-[#151a26] border border-[#ffffff08] rounded-[14px] px-4 py-3 mb-6 flex flex-wrap items-center shadow-lg divide-x divide-[#ffffff08]">
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

        <div className="flex items-center gap-2 px-4 relative">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Title:</span>
          
          <div 
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer flex items-center gap-1"
            onClick={() => setShowFilterTitleDropdown(!showFilterTitleDropdown)}
          >
            <span>{filters.title ? (filters.title.split(',').length <= 2 ? filters.title : `${filters.title.split(',').length} Selected`) : 'All Titles'}</span>
            <ChevronDown className="w-3 h-3 text-slate-500" />
          </div>

          {showFilterTitleDropdown && (
            <>
              <div className="fixed inset-0 z-[100]" onClick={() => setShowFilterTitleDropdown(false)}></div>
              <div className="absolute top-full left-0 mt-2 w-48 bg-[#151a26] border border-[#ffffff10] rounded-xl shadow-2xl z-[150] overflow-hidden animate-in fade-in slide-in-from-top-2">
                <div className="max-h-[200px] overflow-y-auto custom-scrollbar p-2">
                  {availableTitles.map(title => {
                    const isSelected = filters.title && filters.title.split(',').includes(title);
                    return (
                      <div 
                        key={title}
                        onClick={() => toggleFilterTitle(title)}
                        className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                      >
                        <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center transition-colors ${isSelected ? 'bg-blue-500 border-blue-500' : 'border-slate-600 bg-transparent'}`}>
                          {isSelected && <CheckCircle className="w-2.5 h-2.5 text-white" />}
                        </div>
                        <span className={`text-[11px] font-bold ${isSelected ? 'text-white' : 'text-slate-400'}`}>
                          {title}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
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
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Company:</span>
          <input
            type="text"
            name="company"
            placeholder="Search strict..."
            className="bg-transparent border-none text-[#e2e8f0] text-[11px] font-bold outline-none w-[90px] placeholder-slate-600"
            value={filters.company}
            onChange={handleFilterChange}
          />
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

        <div className="flex items-center gap-2 px-4 flex-1 justify-end border-r-0">
          <button
            onClick={() => setFilters({ search: '', title: '', company: '', persona: '', status: '', country: '', city: '', show_unsubscribed: false })}
            className="flex items-center px-4 py-1.5 bg-[#ffffff05] hover:bg-[#ffffff0a] rounded-lg border border-[#ffffff08] transition-colors text-[10px] font-extrabold text-slate-300"
          >
            Reset
          </button>
        </div>
      </div>

      {/* Action Toolbar for Selected Items */}
      <div className={`flex items-center justify-between bg-accent-blue/10 border border-accent-blue/30 rounded-xl px-4 py-3 mb-4 transition-all duration-300 ${selectedLeads.size > 0 ? 'opacity-100 translate-y-0 h-auto' : 'opacity-0 -translate-y-4 h-0 overflow-hidden py-0 border-0 mb-0'}`}>
        <div className="flex items-center gap-3">
          <span className="bg-accent-blue text-white w-6 h-6 flex items-center justify-center rounded-full text-xs font-bold">
            {selectedLeads.size}
          </span>
          <span className="text-sm font-semibold text-blue-200">leads selected</span>
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={handleGenerateDomainDrafts}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200"
          >
            <Sparkles className="w-4 h-4 mr-2 text-blue-400" /> Generate Drafts
          </button>
          <button 
            onClick={handleApproveDomainDrafts}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200"
          >
            <CheckCircle className="w-4 h-4 mr-2 text-blue-400" /> Approve Selected
          </button>
          <button 
            onClick={handleSendDomainEmails}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200"
          >
            <Rocket className="w-4 h-4 mr-2 text-emerald-400" /> Send Selected
          </button>
          <button 
            onClick={handleAddLabelToSelected}
            className="btn btn-primary py-2 px-4 shadow-none"
          >
            <Tag className="w-4 h-4 mr-2" /> Assign Labels
          </button>
        </div>
      </div>

      {/* Results Sheet-Style Table */}
      {isLoading ? (
        <div className="leads-table-container">
          <table className="leads-table">
            <thead>
              <tr>
                <th className="w-10">
                  <input type="checkbox" className="custom-checkbox" disabled />
                </th>
                <th>Name</th>
                <th>Company</th>
                <th>Title / Role</th>
                <th>Location</th>
                <th>Domain / Website</th>
                <th>Labels</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {[...Array(5)].map((_, idx) => (
                <tr key={idx}>
                  <td><div className="w-4 h-4 bg-slate-800 rounded animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-32 animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-24 animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-28 animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-20 animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-32 animate-shimmer"></div></td>
                  <td><div className="h-4 bg-slate-800 rounded w-16 animate-shimmer"></div></td>
                  <td className="text-right"><div className="h-6 w-6 bg-slate-800 rounded-full inline-block animate-shimmer"></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : sortedLeads.length === 0 ? (
        <div className="bg-slate-800/20 border border-dashed border-white/10 rounded-3xl p-24 text-center">
          <div className="text-5xl mb-6 opacity-20">🔭</div>
          <h3 className="text-white text-lg font-bold mb-2">No Leads Found</h3>
          <p className="text-slate-500 text-sm max-w-sm mx-auto">Try adjusting your filters or use the Discovery Engine above to find new targets.</p>
        </div>
      ) : (
        <div className="leads-table-container">
          <table className="leads-table">
            <thead>
              <tr>
                <th className="w-10">
                  <input 
                    type="checkbox" 
                    className="custom-checkbox"
                    checked={selectedLeads.size === sortedLeads.length && sortedLeads.length > 0}
                    onChange={handleSelectAll}
                  />
                </th>
                <th className="sortable" onClick={() => requestSort('name')}>
                  <div className="flex items-center gap-1">
                    Name
                    {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('company_name')}>
                  <div className="flex items-center gap-1">
                    Company
                    {sortConfig.key === 'company_name' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('persona')}>
                  <div className="flex items-center gap-1">
                    Title / Role
                    {sortConfig.key === 'persona' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('city')}>
                  <div className="flex items-center gap-1">
                    Location
                    {sortConfig.key === 'city' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('domain')}>
                  <div className="flex items-center gap-1">
                    Domain / Website
                    {sortConfig.key === 'domain' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3"/> : <ChevronDown className="w-3 h-3"/>)}
                  </div>
                </th>
                <th>Labels</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedLeads.map((lead) => {
                const isSelected = selectedLeads.has(lead.id);
                return (
                  <tr key={lead.id} className={isSelected ? 'selected' : ''}>
                    <td>
                      <input 
                        type="checkbox" 
                        className="custom-checkbox"
                        checked={isSelected}
                        onChange={(e) => handleSelectOne(e, lead.id)}
                      />
                    </td>
                    <td>
                      <button 
                        onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                        className="font-bold text-white hover:text-blue-400 transition-colors cursor-pointer text-left"
                      >
                        {lead.name}
                      </button>
                    </td>
                    <td className="font-medium text-slate-300">
                      {lead.company_name || lead.family_office_name || 'N/A'}
                    </td>
                    <td>
                      <span className={`px-2 py-1 rounded-[4px] text-[10px] font-bold tracking-wider ${
                        ['FOUNDER', 'C-SUITE', 'EXECUTIVE'].includes(lead.persona) ? 'bg-blue-500/10 text-blue-400' :
                        ['PARTNER', 'INVESTOR'].includes(lead.persona) ? 'bg-purple-500/10 text-purple-400' :
                        'bg-amber-500/10 text-amber-400'
                      }`}>
                        {lead.persona || 'UNKNOWN'}
                      </span>
                    </td>
                    <td className="text-slate-400">
                      {[lead.city, lead.country].filter(Boolean).join(', ') || 'Global'}
                    </td>
                    <td className="text-slate-400">
                      {lead.domain ? (
                        <a href={`https://${lead.domain}`} target="_blank" rel="noreferrer" className="hover:text-blue-400 hover:underline">
                          {lead.domain}
                        </a>
                      ) : '-'}
                    </td>
                    <td className="max-w-[150px]">
                      <div className="flex flex-wrap items-center">
                        {(lead.labels || []).map((label, idx) => (
                          <span key={idx} className="label-tag">
                            {label}
                            <button className="remove-label" onClick={(e) => { e.stopPropagation(); removeLabel(lead.id, label); }}>×</button>
                          </span>
                        ))}
                        <button 
                          onClick={() => handleAddLabelToSingle(lead.id)}
                          className="w-5 h-5 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition-colors ml-1 border border-white/10"
                          title="Add Label"
                        >
                          <Plus className="w-3 h-3" />
                        </button>
                      </div>
                    </td>
                    <td className="text-right">
                      <button 
                        onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                        className="p-2 bg-slate-800/50 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg transition-colors inline-block"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Container - Same as Original */}
      {sortedLeads.length > 0 && pagination.total_pages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-8 pb-10">
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
                className={`w-10 h-10 rounded-xl font-bold text-sm transition-all ${pagination.page === i + 1
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

      {/* Add Lead Mock Drawer - Same as Original */}
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

      {/* Label Assignment Modal */}
      {showLabelModal && (
        <>
          <div className="drawer-backdrop show" onClick={() => setShowLabelModal(false)}></div>
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-[#151a26] border border-white/10 p-6 rounded-2xl shadow-2xl z-[2000] w-[400px] animate-in zoom-in-95">
            <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
              <Tag className="w-5 h-5 text-blue-400" />
              Assign Labels
            </h3>
            <p className="text-sm text-slate-400 mb-5">
              Add labels to {targetLeadIds.length} selected lead(s). Separated by commas.
            </p>
            
            <input 
              type="text" 
              className="form-control mb-5" 
              placeholder="e.g. VIP, High Priority, Follow-up" 
              value={labelInput}
              onChange={e => setLabelInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  submitLabels();
                }
              }}
              autoFocus
            />
            
            <div className="flex justify-end gap-3">
              <button 
                className="btn btn-ghost px-5" 
                onClick={() => {
                  setShowLabelModal(false);
                  setLabelInput('');
                }}
              >
                Cancel
              </button>
              <button className="btn btn-primary px-6" onClick={submitLabels}>
                Save Labels
              </button>
            </div>
          </div>
        </>
      )}

      {/* Toast Notification */}
      {notification && (
        <div className={`fixed bottom-8 right-8 z-[3000] animate-in slide-in-from-bottom-4 duration-300`}>
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${notification.type === 'success'
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
