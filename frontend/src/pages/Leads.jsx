import React, { useState, useEffect, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Rocket, Search, ChevronDown, CheckCircle, Mail, User, Linkedin,
  Loader2, Sparkles, Tag, Plus, ChevronRight, X, AlertTriangle, AlertCircle,
  ChevronLeft, ChevronUp, FileSpreadsheet, Download, Trash2, Pencil, ShieldAlert
} from 'lucide-react';
import axios from 'axios';
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
    source: '',
    show_drafted: false,
    show_unsubscribed: false,
  });

  const personas = ['FOUNDER', 'INVESTOR', 'PARTNER', 'OTHER'];
  const statuses = ['PENDING', 'VALIDATING', 'VALID', 'INVALID'];

  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [isRequestingAccess, setIsRequestingAccess] = useState(false);
  const [isBulkActionLoading, setIsBulkActionLoading] = useState(false);

  const [showAddModal, setShowAddModal] = useState(false);
  const [isCreatingLead, setIsCreatingLead] = useState(false);
  const [newLeadData, setNewLeadData] = useState({
    first_name: '', last_name: '', email: '', company_name: '',
    designation: '', phone: '', city: '', country: '',
    linkedin_url: '', persona: 'OTHER'
  });
  const [notification, setNotification] = useState(null);

  const [selectedLeads, setSelectedLeads] = useState(new Set());
  const [sortConfig, setSortConfig] = useState({ key: 'created_at', direction: 'desc' });
  const [lastFetched, setLastFetched] = useState(null);

  const [showLabelModal, setShowLabelModal] = useState(false);
  const [labelInput, setLabelInput] = useState('');
  const [targetLeadIds, setTargetLeadIds] = useState([]);

  // Confirm Dialog State
  const [confirmDialog, setConfirmDialog] = useState({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: null,
    isDanger: false
  });

  const triggerConfirm = (title, message, onConfirm, isDanger = false) => {
    setConfirmDialog({ isOpen: true, title, message, onConfirm, isDanger });
  };

  const uniqueCompanies = useMemo(() => {
    const comps = new Set();
    leads.forEach(l => {
      const c = l.company_name || l.company;
      if (c) comps.add(c);
    });
    return Array.from(comps).sort();
  }, [leads]);

  const availableTitles = ['CEO', 'Founder', 'Managing Director', 'CFO', 'Partner', 'Investor'];
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

  const [lookupMode, setLookupMode] = useState('search');

  const showNotification = (type, message, action = null) => {
    setNotification({ type, message, action });
    setTimeout(() => setNotification(null), 8000); // Longer timeout for action items
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
        exclude_drafted: !filters.show_drafted,
        source: filters.source,
      };
      const response = await api.get('/api/leads', { params });

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
      setSelectedLeads(new Set());
      setLastFetched(new Date());
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

    const formData = new FormData(e.currentTarget);
    const data = {
      mode: lookupMode,
      company: formData.get('company'),
      title: selectedTitles.join(','),
      location: formData.get('location'),
      count: formData.get('count'),
      email: formData.get('email'),
      linkedin_url: formData.get('linkedin_url')
    };

    try {
      const response = await api.post('/api/ingest-leads', {
        ...data,
        source_type: 'direct'
      });
      fetchLeads();

      if (response.data.inserted === 0) {
        let msg = "No data found for this specific search.";
        if (lookupMode === 'email') msg = `No verified profile found for the email: ${data.email}`;
        showNotification('error', msg);
      } else {
        showNotification('success', `Extraction complete. ${response.data.inserted} new lead(s) added.`);
      }
    } catch (err) {
      if (err.response?.status === 403) {
        // Show the high-impact approval modal instead of a simple notification
        setShowApprovalModal(true);
      } else {
        showNotification('error', 'Extraction failed: ' + (err.response?.data?.detail || err.message));
      }
    } finally {
      setDiscoveryLoading(false);
    }
  };

  const handleRequestAccess = async () => {
    setIsRequestingAccess(true);
    try {
      const userStr = localStorage.getItem('user');
      if (!userStr) throw new Error("User session not found");
      const user = JSON.parse(userStr);

      await api.post('/api/auth/request-access', { user_id: user.id });
      showNotification('success', 'Access request dispatched to administrator.');
      setShowApprovalModal(false);
    } catch (err) {
      showNotification('error', 'Failed to send request: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsRequestingAccess(false);
    }
  };

  const handleCreateManualLead = async (e) => {
    e.preventDefault();
    setIsCreatingLead(true);
    try {
      const response = await api.post('/api/leads', newLeadData);

      if (response.data.was_duplicate) {
        showNotification('success', response.data.message, {
          label: 'View Lead',
          onClick: () => navigate(`/dashboard/leads/${response.data.lead_id}`)
        });
      } else {
        showNotification('success', 'Lead created successfully and added to pipeline.');
      }

      setShowAddModal(false);
      setNewLeadData({
        first_name: '', last_name: '', email: '', company_name: '',
        designation: '', phone: '', city: '', country: '',
        linkedin_url: '', persona: 'OTHER'
      });
      fetchLeads();
    } catch (err) {
      if (err.response?.data?.error === 'DUPLICATE_LEAD') {
        const leadId = err.response.data.lead_id;
        showNotification('error', err.response.data.detail, {
          label: 'View Lead',
          onClick: () => navigate(`/dashboard/leads/${leadId}`)
        });
      } else {
        showNotification('error', 'Failed to create lead: ' + (err.response?.data?.detail || err.message));
      }
    } finally {
      setIsCreatingLead(false);
    }
  };

  const handleDeleteSingle = async (id) => {
    triggerConfirm(
      "Confirm Deletion",
      "Are you sure you want to delete this lead? This action cannot be undone.",
      async () => {
        try {
          await api.post('/api/leads/bulk-delete', [id]);
          showNotification('success', 'Lead successfully deleted.');
          fetchLeads();
        } catch (err) {
          showNotification('error', 'Failed to delete lead: ' + (err.response?.data?.detail || err.message));
        }
      },
      true
    );
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedLeads);
    if (ids.length === 0) return;

    triggerConfirm(
      ids.length === 1 ? "Confirm Deletion" : "Confirm Bulk Deletion",
      `Are you sure you want to delete ${ids.length} selected lead${ids.length > 1 ? 's' : ''}? This action cannot be undone.`,
      async () => {
        setIsBulkActionLoading(true);
        try {
          await api.post('/api/leads/bulk-delete', ids);
          showNotification('success', `${ids.length} leads deleted successfully.`);
          setSelectedLeads(new Set());
          fetchLeads();
        } catch (err) {
          showNotification('error', 'Failed to delete leads: ' + (err.response?.data?.detail || err.message));
        } finally {
          setIsBulkActionLoading(false);
        }
      },
      true
    );
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
    setIsBulkActionLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      await api.post('/api/generate-bulk-domain-drafts', { lead_ids: leadIds });
      showNotification('success', 'Drafts generated and moved to Email Drafts.');
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to generate drafts: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsBulkActionLoading(false);
    }
  };

  const handleSendDomainEmails = async () => {
    if (selectedLeads.size === 0) return;
    setIsBulkActionLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      await api.post('/api/send-bulk-domain-emails', { lead_ids: leadIds });
      showNotification('success', 'Emails sent successfully.');
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to send emails: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsBulkActionLoading(false);
    }
  };

  const handleApproveDomainDrafts = async () => {
    if (selectedLeads.size === 0) return;
    setIsBulkActionLoading(true);
    try {
      const leadIds = Array.from(selectedLeads);
      await api.post('/api/approve-bulk-domain-drafts', { lead_ids: leadIds });
      showNotification('success', 'Leads approved and moved to Email Drafts.');
      setSelectedLeads(new Set());
      fetchLeads();
    } catch (err) {
      showNotification('error', 'Failed to approve drafts: ' + (err.response?.data?.error || err.message));
    } finally {
      setIsBulkActionLoading(false);
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

  const removeLabel = async (leadId, label) => {
    try {
      await axios.post(`http://localhost:8000/api/leads/${leadId}/remove-label`, { label });
      setLeads(leads.map(l => l.id === leadId ? { ...l, labels: l.labels.filter(x => x !== label) } : l));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Lead Pipeline</h1>
          <div className="flex items-center gap-2 mt-1">
            <p className="text-slate-400 text-sm">Manage and organize your AI-triaged investment leads via list view.</p>
            {lastFetched && (
              <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full font-bold border border-blue-500/20 flex items-center gap-1.5 animate-in fade-in slide-in-from-left-2">
                <div className="w-1 h-1 bg-blue-400 rounded-full animate-pulse" />
                Updated at {lastFetched.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowAddModal(true)}
          className="btn btn-primary px-6 py-2.5 text-[11px] font-black uppercase tracking-widest rounded-xl flex items-center gap-2 shadow-blue-500/20 cursor-pointer"
        >
          <Plus className="w-4 h-4" /> New Lead
        </button>
      </div>

      <div className="bg-gradient-to-br from-[#1e293b]/70 to-[#0f172a]/90 border border-blue-500/20 rounded-[20px] p-6 mb-8 mt-6 relative group shadow-heavy">
        <div className="absolute top-0 right-0 w-64 h-64 bg-blue-500/5 blur-[80px] rounded-full pointer-events-none"></div>

        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-6 mb-8">
          <div>
            <h3 className="text-white font-bold flex items-center gap-2 mb-1">
              <span className="text-xl text-[#3b82f6]">⚡</span>
              RocketReach <span className="bg-gradient-to-r from-[#3b82f6] to-[#8b5cf6] bg-clip-text text-transparent">Discovery Engine</span>
            </h3>
            <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest pl-7">Institutional Data Extraction</p>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex bg-black/40 p-1 rounded-[14px] border border-white/10 self-stretch sm:self-auto">
            <button
              onClick={() => setLookupMode('search')}
              className={`flex-1 sm:flex-none px-4 py-2 rounded-[10px] text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${lookupMode === 'search' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
            >
              Direct Extract
            </button>
            <button
              onClick={() => setLookupMode('email')}
              className={`flex-1 sm:flex-none px-4 py-2 rounded-[10px] text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${lookupMode === 'email' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-300'}`}
            >
              By Mail
            </button>
            <button
              onClick={() => setLookupMode('url')}
              className={`flex-1 sm:flex-none px-4 py-2 rounded-[10px] text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${lookupMode === 'url' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-500 hover:text-slate-400'}`}
            >
              By LinkedIn URL
            </button>
          </div>
        </div>

        <form onSubmit={handleDiscoverySubmit}>
          <div className="grid grid-cols-1 md:grid-cols-12 gap-5">
            {lookupMode === 'search' ? (
              <>
                <div className="space-y-1.5 md:col-span-4">
                  <label className="text-[10px] font-extrabold text-[#3b82f6] uppercase tracking-widest pl-1">Target Company</label>
                  <input type="text" name="company" className="form-control h-12" placeholder="e.g. NVIDIA, Stripe" />
                </div>
                <div className="space-y-1.5 md:col-span-4 relative">
                  <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Job Title</label>
                  <div
                    className="form-control h-12 cursor-pointer flex items-center justify-between"
                    onClick={() => setShowTitleDropdown(!showTitleDropdown)}
                  >
                    <span className={`text-sm ${selectedTitles.length === 0 ? 'text-slate-500' : 'text-white'}`}>
                      {selectedTitles.length === 0 ? 'Any Title / Auto' : selectedTitles.length <= 2 ? selectedTitles.join(', ') : `${selectedTitles.length} selected`}
                    </span>
                    <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${showTitleDropdown ? 'rotate-180' : ''}`} />
                  </div>

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
                <div className="space-y-1.5 md:col-span-4">
                  <label className="text-[10px] font-extrabold text-[#475569] uppercase tracking-widest pl-1">Location</label>
                  <input type="text" name="location" className="form-control h-12" placeholder="e.g. California" />
                </div>
              </>
            ) : lookupMode === 'email' ? (
              <div className="space-y-1.5 md:col-span-12">
                <label className="text-[10px] font-extrabold text-[#3b82f6] uppercase tracking-widest pl-1 flex items-center gap-2">
                  <Mail className="w-3 h-3" /> Target Email Address
                </label>
                <input
                  key="email-input"
                  type="email"
                  name="email"
                  required
                  className="form-control h-12 w-full bg-black/40 border-blue-500/30 focus:border-blue-500 transition-all text-base px-6 italic"
                  placeholder="Paste direct email (e.g. j.doe@nvidia.com)"
                />
              </div>
            ) : (
              <div className="space-y-1.5 md:col-span-12">
                <label className="text-[10px] font-extrabold text-[#3b82f6] uppercase tracking-widest pl-1 flex items-center gap-2">
                  <Linkedin className="w-3 h-3" /> LinkedIn Profile URL
                </label>
                <input
                  key="linkedin-input"
                  type="url"
                  name="linkedin_url"
                  required
                  className="form-control h-12 w-full"
                  placeholder="https://www.linkedin.com/in/jensenhuang/"
                />
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row justify-between items-center mt-8 pt-6 border-t border-white/5 gap-4">
            <div className="flex items-center gap-4">
              {lookupMode === 'search' && (
                <div className="bg-black/30 px-4 py-2 rounded-xl border border-white/5 flex items-center gap-3">
                  <label className="text-[10px] font-black text-[#64748b] uppercase tracking-[1px]">Limit</label>
                  <input
                    type="number"
                    name="count"
                    defaultValue="5"
                    min="1"
                    max="100"
                    className="bg-white/5 border border-white/10 rounded-lg text-white font-black w-12 h-8 text-center outline-none focus:border-blue-500/50 focus:bg-white/10 transition-all text-[13px]"
                  />
                </div>
              )}
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-[#10b981] rounded-full shadow-[0_0_8px_#10b981]"></div>
                <span className="text-[11px] text-[#475569] font-semibold">RocketReach Multi-Node Extraction Active</span>
              </div>
            </div>
            <button
              type="submit"
              disabled={discoveryLoading}
              className="w-full sm:w-auto btn btn-primary px-12 py-3.5 rounded-[12px] font-extrabold text-white shadow-blue-500/20 transition-all duration-300 min-w-[200px]"
            >
              {discoveryLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="w-5 h-5 animate-spin" />
                  <span>Identifying High-Value Lead...</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  {lookupMode === 'search' ? <Rocket className="w-4 h-4" /> : lookupMode === 'email' ? <Mail className="w-4 h-4" /> : <Linkedin className="w-4 h-4" />}
                  <span>{lookupMode === 'search' ? 'Begin Extraction' : 'Identify & Import'}</span>
                </div>
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
          <select
            name="company"
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none max-w-[120px]"
            value={filters.company}
            onChange={handleFilterChange}
          >
            <option value="">All Companies ▼</option>
            {uniqueCompanies.map(c => <option key={c} value={c}>{c}</option>)}
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

        <div className="flex items-center gap-2 px-4 border-r border-[#ffffff08]">
          <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Source:</span>
          <select
            name="source"
            className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none min-w-[100px]"
            value={filters.source}
            onChange={handleFilterChange}
          >
            <option value="">All Sources ▼</option>
            <option value="direct">Direct Discovery</option>
            <option value="intelligence">Company Intel</option>
            <option value="bulk">Bulk Search</option>
          </select>
        </div>

        <div className="flex items-center gap-4 px-4 border-r border-[#ffffff08]">
          <label className="flex items-center gap-2 cursor-pointer group">
            <div className="relative">
              <input
                type="checkbox"
                name="show_drafted"
                checked={filters.show_drafted}
                onChange={handleFilterChange}
                className="sr-only"
              />
              <div className={`w-8 h-4 rounded-full transition-colors ${filters.show_drafted ? 'bg-blue-600' : 'bg-slate-700'}`}></div>
              <div className={`absolute left-0.5 top-0.5 w-3 h-3 bg-white rounded-full transition-transform ${filters.show_drafted ? 'translate-x-4' : 'translate-x-0'}`}></div>
            </div>
            <span className="text-[9px] font-black text-slate-400 group-hover:text-slate-200 uppercase tracking-widest transition-colors">Include Drafted</span>
          </label>
        </div>

        <div className="flex items-center gap-2 px-4 flex-1 justify-end border-r-0 text-right">
          <button
            onClick={() => setFilters({ search: '', title: '', company: '', persona: '', status: '', country: '', city: '', source: '', show_drafted: false, show_unsubscribed: false })}
            className="flex items-center px-4 py-1.5 bg-[#ffffff05] hover:bg-[#ffffff0a] rounded-lg border border-[#ffffff08] transition-colors text-[10px] font-extrabold text-slate-300 ml-auto"
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
            disabled={isBulkActionLoading}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200 disabled:opacity-50 cursor-pointer"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 mr-2 text-blue-400 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2 text-blue-400" />}
            Generate Drafts
          </button>
          <button
            onClick={handleApproveDomainDrafts}
            disabled={isBulkActionLoading}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200 disabled:opacity-50 cursor-pointer"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 mr-2 text-blue-400 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2 text-blue-400" />}
            Approve Selected
          </button>
          <button
            onClick={handleSendDomainEmails}
            disabled={isBulkActionLoading}
            className="btn btn-ghost py-2 px-4 shadow-none bg-white/5 border-white/10 hover:bg-white/10 text-slate-200 disabled:opacity-50 cursor-pointer"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 mr-2 text-emerald-400 animate-spin" /> : <Rocket className="w-4 h-4 mr-2 text-emerald-400" />}
            Send Selected
          </button>
          <button
            onClick={handleAddLabelToSelected}
            disabled={isBulkActionLoading}
            className="btn btn-primary py-2 px-4 shadow-none disabled:opacity-50 cursor-pointer"
          >
            <Tag className="w-4 h-4 mr-2" /> Assign Labels
          </button>
          <button
            onClick={handleBulkDelete}
            disabled={isBulkActionLoading}
            className="btn btn-ghost py-2 px-4 shadow-none bg-rose-500/5 border-rose-500/10 hover:bg-rose-500/10 text-rose-400 font-bold disabled:opacity-50 cursor-pointer"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trash2 className="w-4 h-4 mr-2" />}
            Delete Selected
          </button>
        </div>
      </div>

      {/* Results Data Table */}
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
                <th>Date and Time</th>
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
                  <td><div className="h-4 bg-slate-800 rounded w-28 animate-shimmer"></div></td>
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
                    {sortConfig.key === 'name' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('company_name')}>
                  <div className="flex items-center gap-1">
                    Company
                    {sortConfig.key === 'company_name' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('persona')}>
                  <div className="flex items-center gap-1">
                    Title / Role
                    {sortConfig.key === 'persona' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('city')}>
                  <div className="flex items-center gap-1">
                    Location
                    {sortConfig.key === 'city' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
                  </div>
                </th>
                <th className="sortable" onClick={() => requestSort('created_at')}>
                  <div className="flex items-center gap-1">
                    Date and Time
                    {sortConfig.key === 'created_at' && (sortConfig.direction === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
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
                      <span className={`px-2 py-1 rounded-[4px] text-[10px] font-bold tracking-wider ${['FOUNDER', 'C-SUITE', 'EXECUTIVE'].includes(lead.persona) ? 'bg-blue-500/10 text-blue-400' :
                        ['PARTNER', 'INVESTOR'].includes(lead.persona) ? 'bg-purple-500/10 text-purple-400' :
                          'bg-amber-500/10 text-amber-400'
                        }`}>
                        {lead.designation || lead.persona || 'UNKNOWN'}
                      </span>
                    </td>
                    <td className="text-slate-400">
                      {[lead.city, lead.country].filter(Boolean).join(', ') || 'Global'}
                    </td>
                    <td className="text-[11px] font-bold text-slate-400 whitespace-nowrap">
                      {lead.created_at ? (
                        <>
                          <span className="text-slate-300">{new Date(lead.created_at).toLocaleDateString([], { day: '2-digit', month: 'short' })}</span>
                          <span className="mx-1 opacity-30">·</span>
                          <span className="opacity-70">{new Date(lead.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </>
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
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                          title="Edit Lead"
                          className="p-2 hover:bg-blue-500/10 rounded-lg text-slate-500 hover:text-blue-400 transition-all shadow-sm cursor-pointer"
                        >
                          <Pencil className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                          className="p-2 hover:bg-white/5 rounded-lg text-slate-400 hover:text-white transition-all shadow-sm group cursor-pointer"
                        >
                          <ChevronRight className="w-5 h-5 group-hover:translate-x-0.5 transition-transform" />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteSingle(lead.id); }}
                          className="p-2 hover:bg-rose-500/10 rounded-lg text-slate-500 hover:text-rose-400 transition-all shadow-sm cursor-pointer"
                        >
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
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
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-slate-800 border border-white/5 text-slate-400 disabled:opacity-20 translate-y-0 hover:-translate-y-0.5 transition-all cursor-pointer"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          <div className="flex gap-1">
            {[...Array(pagination.total_pages)].map((_, i) => (
              <button
                key={i}
                onClick={() => setPagination(v => ({ ...v, page: i + 1 }))}
                className={`w-10 h-10 rounded-xl font-bold text-sm transition-all cursor-pointer ${pagination.page === i + 1
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
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-slate-800 border border-white/5 text-slate-400 disabled:opacity-20 translate-y-0 hover:-translate-y-0.5 transition-all cursor-pointer"
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
          <form className="space-y-4" onSubmit={handleCreateManualLead} id="manual-lead-form">
            <div className="grid grid-cols-2 gap-4">
              <div className="form-group">
                <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">First Name</label>
                <input
                  type="text" required className="form-control" placeholder="John"
                  value={newLeadData.first_name}
                  onChange={e => setNewLeadData({ ...newLeadData, first_name: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Last Name</label>
                <input
                  type="text" className="form-control" placeholder="Doe"
                  value={newLeadData.last_name}
                  onChange={e => setNewLeadData({ ...newLeadData, last_name: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Email Address</label>
              <input
                type="email" required className="form-control" placeholder="john@example.com"
                value={newLeadData.email}
                onChange={e => setNewLeadData({ ...newLeadData, email: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Designation / Job Title</label>
              <input
                type="text" className="form-control" placeholder="Managing Director"
                value={newLeadData.designation}
                onChange={e => setNewLeadData({ ...newLeadData, designation: e.target.value })}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="form-group">
                <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">City</label>
                <input
                  type="text" className="form-control" placeholder="New York"
                  value={newLeadData.city}
                  onChange={e => setNewLeadData({ ...newLeadData, city: e.target.value })}
                />
              </div>
              <div className="form-group">
                <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Country</label>
                <input
                  type="text" className="form-control" placeholder="USA"
                  value={newLeadData.country}
                  onChange={e => setNewLeadData({ ...newLeadData, country: e.target.value })}
                />
              </div>
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Phone (Optional)</label>
              <input
                type="text" className="form-control" placeholder="+1 234 567 890"
                value={newLeadData.phone}
                onChange={e => setNewLeadData({ ...newLeadData, phone: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Company</label>
              <input
                type="text" className="form-control" placeholder="Acme Inc"
                value={newLeadData.company_name}
                onChange={e => setNewLeadData({ ...newLeadData, company_name: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">Target Persona</label>
              <select
                className="form-control cursor-pointer"
                value={newLeadData.persona}
                onChange={e => setNewLeadData({ ...newLeadData, persona: e.target.value })}
              >
                {personas.map(p => <option key={p} value={p}>{p}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label className="text-[10px] font-black uppercase text-slate-500 tracking-wider">LinkedIn URL</label>
              <input
                type="url" className="form-control" placeholder="https://linkedin.com/in/..."
                value={newLeadData.linkedin_url}
                onChange={e => setNewLeadData({ ...newLeadData, linkedin_url: e.target.value })}
              />
            </div>
          </form>
        </div>
        <div className="drawer-footer">
          <button className="btn btn-ghost px-6" onClick={() => setShowAddModal(false)}>Cancel</button>
          <button
            type="submit"
            form="manual-lead-form"
            disabled={isCreatingLead}
            className="btn btn-primary px-8"
          >
            {isCreatingLead ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Create Lead'}
          </button>
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
            <div className="flex flex-col gap-1">
              <p className="text-sm font-bold tracking-tight">{notification.message}</p>
              {notification.action && (
                <button
                  onClick={() => {
                    notification.action.onClick();
                    setNotification(null);
                  }}
                  className="text-[11px] font-black uppercase tracking-widest text-white hover:text-white/80 transition-colors w-fit underline underline-offset-4"
                >
                  {notification.action.label} →
                </button>
              )}
            </div>
            <button
              onClick={() => setNotification(null)}
              className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Custom Confirmation Modal */}
      {confirmDialog.isOpen && (
        <>
          <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[4000] animate-in fade-in" onClick={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}></div>
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm bg-[#151a26] border border-white/10 rounded-2xl shadow-2xl z-[4001] animate-in zoom-in-95 duration-200 overflow-hidden">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center ${confirmDialog.isDanger ? 'bg-rose-500/10 text-rose-500' : 'bg-blue-500/10 text-blue-500'}`}>
                  <AlertCircle className="w-5 h-5" />
                </div>
                <h3 className="text-lg font-bold text-white">{confirmDialog.title}</h3>
              </div>
              <p className="text-slate-400 text-sm leading-relaxed mb-6">
                {confirmDialog.message}
              </p>
              <div className="flex gap-3">
                <button
                  onClick={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 font-bold text-xs uppercase tracking-widest transition-colors border border-white/5"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    confirmDialog.onConfirm();
                    setConfirmDialog(prev => ({ ...prev, isOpen: false }));
                  }}
                  className={`flex-1 px-4 py-2.5 rounded-xl text-white font-bold text-xs uppercase tracking-widest transition-all shadow-lg ${confirmDialog.isDanger ? 'bg-rose-600 hover:bg-rose-500 shadow-rose-500/20' : 'bg-blue-600 hover:bg-blue-500 shadow-blue-500/20'}`}
                >
                  Confirm
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Approval Required Modal */}
      {showApprovalModal && (
        <>
          <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-[5000] animate-in fade-in duration-300" onClick={() => setShowApprovalModal(false)}></div>
          <div className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[#0d1117] border border-white/10 rounded-3xl shadow-[0_0_50px_rgba(0,0,0,0.5)] z-[5001] animate-in zoom-in-95 duration-300 overflow-hidden">
            <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-600 via-indigo-600 to-purple-600"></div>
            <div className="p-8 text-center">
              <div className="w-20 h-20 bg-blue-600/10 rounded-2xl flex items-center justify-center mx-auto mb-6 shadow-inner border border-blue-500/20">
                <ShieldAlert className="w-10 h-10 text-blue-500" />
              </div>
              <h2 className="text-2xl font-black text-white mb-2 tracking-tight">Access Required</h2>
              <p className="text-slate-400 text-sm leading-relaxed mb-8">
                To maintain system security and optimize credit usage, the <span className="text-blue-400 font-bold">Lead Discovery & Extraction Engine</span> requires a fresh administrator approval for every session.
              </p>

              <div className="space-y-3">
                <button
                  onClick={handleRequestAccess}
                  disabled={isRequestingAccess}
                  className="w-full py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-black text-xs uppercase tracking-widest transition-all shadow-[0_0_20px_rgba(37,99,235,0.3)] flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isRequestingAccess ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Rocket className="w-4 h-4" />
                  )}
                  {isRequestingAccess ? 'Requesting Access...' : 'Request Discovery Access'}
                </button>
                <button
                  onClick={() => setShowApprovalModal(false)}
                  className="w-full py-4 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 font-bold text-xs uppercase tracking-widest transition-colors border border-white/5"
                >
                  Cancel
                </button>
              </div>

              <p className="text-[10px] text-slate-500 font-medium mt-8 uppercase tracking-widest">
                Admin will receive an instant priority notification
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Leads;
