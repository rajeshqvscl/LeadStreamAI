import React, { useState, useEffect } from 'react';
import { Search, Rocket, Loader2, CheckCircle, AlertCircle, Database, Filter, MapPin, Building2, Tag, ChevronLeft, ChevronRight, User, FileText, Trash2, Check, Sparkles, FileSpreadsheet, Download, Pencil } from 'lucide-react';
import * as XLSX from 'xlsx';
import Papa from 'papaparse';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const BulkSearch = () => {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState(null);
  const [limit, setLimit] = useState(20);

  // Results Table State
  const [bulkLeads, setBulkLeads] = useState([]);
  const [isTableLoading, setIsTableLoading] = useState(false);
  const [pagination, setPagination] = useState({ page: 1, total_pages: 1, total: 0 });
  const [selectedLeads, setSelectedLeads] = useState(new Set());
  const [isBulkActionLoading, setIsBulkActionLoading] = useState(false);
  const [processingId, setProcessingId] = useState(null);

  const [syncMode, setSyncMode] = useState('rocketreach'); // 'rocketreach' or 'spreadsheet'
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastFetched, setLastFetched] = useState(null);

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
  const fileInputRef = React.useRef(null);

  // New Filter State
  const [filters, setFilters] = useState({
    search: '',
    persona: '',
    company: '',
    status: ''
  });
  const [sourceFilter, setSourceFilter] = useState('all'); // 'all' | 'bulk' | 'csv_import'

  // Selection States for Form
  const [selectedPersonas, setSelectedPersonas] = useState([]);
  const [selectedIndustry, setSelectedIndustry] = useState('');
  const [showPersonaDropdown, setShowPersonaDropdown] = useState(false);
  const [showIndustryDropdown, setShowIndustryDropdown] = useState(false);
  const [industrySearch, setIndustrySearch] = useState('');

  const personaOptions = ["CEO", "Founder", "Managing Director", "CFO", "Partner", "Investor"];
  const sectorOptions = [
    { id: 'DEEP_TECH', label: 'Deep Tech' },
    { id: 'HIGH_TECH', label: 'High Tech' },
    { id: 'SAAS', label: 'SAAS' },
    { id: 'DEFENCE_TECH', label: 'Defence Tech' },
    { id: 'TRAVEL', label: 'Travel' },
    { id: 'AUTOMOTIVE', label: 'Automotive' },
    { id: 'AI_INFRA', label: 'AI Infra' },
    { id: 'AI_INTEL', label: 'AI Intelligence' },
    { id: 'GEN_AI', label: 'Generative AI' },
    { id: 'ESPORTS', label: 'Esports' },
    { id: 'ENT_APP', label: 'Enterprise Applications' },
    { id: 'ENT_SW', label: 'Enterprise Software' },
    { id: 'EDTECH', label: 'EdTech' },
    { id: 'PHARMA', label: 'Pharmaceutical' },
    { id: 'NUTRA', label: 'Nutraceutical' },
    { id: 'CHEMICAL', label: 'Chemical' },
    { id: 'FOOD_EXT', label: 'Food Extracts' },
    { id: 'EV', label: 'EV (Electric Vehicles)' },
    { id: 'DRONES', label: 'Drones' },
    { id: 'FINTECH', label: 'Fintech' },
    { id: 'BEAUTY', label: 'Skincare/Beauty Care' },
    { id: 'REAL_ESTATE', label: 'Real Estate' },
    { id: 'FMCG', label: 'FMCG' },
    { id: 'CONSUMER', label: 'Consumes' },
    { id: 'TEXTILE', label: 'Textile (Clothing/Brands)' }
  ];

  const filteredIndustries = sectorOptions.filter(s =>
    s.label.toLowerCase().includes(industrySearch.toLowerCase())
  );

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchBulkLeads = async (pageToFetch = pagination.page) => {
    setIsTableLoading(true);
    try {
      const params = {
        page: 1,
        per_page: 1000,
        search: filters.search,
        persona: filters.persona,
        company: filters.company,
        validation_status: filters.status,
        exclude_drafted: true
      };
      // Filter by import source
      if (sourceFilter === 'bulk') {
        params.source = 'bulk';
      } else if (sourceFilter === 'csv_import') {
        params.source = 'csv_import';
      } else {
        // All: exclude sources that aren't bulk-related (e.g. direct pipeline)
        params.exclude_source = 'direct';
      }
      const response = await api.get('/api/leads', { params });
      setBulkLeads(response.data.leads || []);
      setPagination({
        page: pageToFetch,
        total_pages: Math.ceil((response.data.total || 0) / 10),
        total: response.data.total || 0
      });
      setSelectedLeads(new Set());
      setLastFetched(new Date());
    } catch (err) {
      console.error('Failed to fetch bulk leads', err);
    } finally {
      setIsTableLoading(false);
    }
  };

  useEffect(() => {
    fetchBulkLeads(1);
  }, [filters, sourceFilter]);

  const handleFilterChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const toggleSelect = (id) => {
    const newSelected = new Set(selectedLeads);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedLeads(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedLeads.size === bulkLeads.length && bulkLeads.length > 0) {
      setSelectedLeads(new Set());
    } else {
      setSelectedLeads(new Set(bulkLeads.map(l => l.id)));
    }
  };

  const handleBulkGenerateDrafts = async () => {
    if (selectedLeads.size === 0) return;
    setIsBulkActionLoading(true);
    try {
      const response = await api.post('/api/generate-bulk-domain-drafts', {
        lead_ids: Array.from(selectedLeads)
      });
      showNotification('success', `Drafts generated and moved to Email Drafts.`);
      setSelectedLeads(new Set());
      fetchBulkLeads(pagination.page);
    } catch (err) {
      showNotification('error', 'Bulk draft generation failed');
    } finally {
      setIsBulkActionLoading(false);
    }
  };

  const handleBulkApproveDrafts = async () => {
    if (selectedLeads.size === 0) return;
    setIsBulkActionLoading(true);
    try {
      const response = await api.post('/api/approve-bulk-domain-drafts', {
        lead_ids: Array.from(selectedLeads)
      });
      showNotification('success', `Approved leads moved to Email Drafts.`);
      setSelectedLeads(new Set());
      fetchBulkLeads(pagination.page);
    } catch (err) {
      showNotification('error', 'Bulk approval failed');
    } finally {
      setIsBulkActionLoading(false);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedLeads.size === 0) return;

    triggerConfirm(
      "Confirm Bulk Rejection",
      `Are you sure you want to reject and delete ${selectedLeads.size} selected leads? This action cannot be undone.`,
      async () => {
        setIsBulkActionLoading(true);
        try {
          await api.post('/api/leads/bulk-delete', Array.from(selectedLeads));
          showNotification('success', `${selectedLeads.size} leads deleted.`);
          fetchBulkLeads(pagination.page);
          setSelectedLeads(new Set());
        } catch (err) {
          showNotification('error', 'Bulk deletion failed');
        } finally {
          setIsBulkActionLoading(false);
        }
      },
      true
    );
  };

  const handleGenerateDraftSingle = async (id) => {
    setProcessingId(id);
    try {
      await api.post('/api/generate-draft', { lead_id: id });
      showNotification('success', 'Lead moved to Email Drafts.');
      fetchBulkLeads(pagination.page);
    } catch (err) {
      showNotification('error', 'Failed to generate draft');
    } finally {
      setProcessingId(null);
    }
  };

  const handleApproveDraftSingle = async (id) => {
    setProcessingId(id);
    try {
      await api.post(`/api/approve-draft/${id}`);
      showNotification('success', 'Lead approved and moved to Email Drafts!');
      fetchBulkLeads(pagination.page);
    } catch (err) {
      showNotification('error', 'Failed to approve lead');
    } finally {
      setProcessingId(null);
    }
  };

  const handleDeleteSingle = async (id) => {
    triggerConfirm(
      "Delete Discovered Lead",
      "Are you sure you want to delete this discovered lead? This action cannot be undone.",
      async () => {
        try {
          await api.post('/api/leads/bulk-delete', [id]);
          showNotification('success', 'Lead deleted');
          fetchBulkLeads(pagination.page);
        } catch (err) {
          showNotification('error', 'Failed to delete lead');
        }
      },
      true
    );
  };

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setIsSyncing(true);
    const reader = new FileReader();

    const processData = async (data) => {
      try {
        // Be extremely generous with column headers
        const cleanData = data.filter(row =>
          Object.keys(row).some(k => {
            const kLower = k.toLowerCase().replace(/[- ]/g, '');
            return (kLower.includes('email') || kLower.includes('name')) && row[k];
          })
        );
        const response = await api.post('/api/leads/bulk-import', cleanData);
        showNotification('success', response.data.message || 'Import successful');
        fetchBulkLeads();
      } catch (err) {
        showNotification('error', 'Import failed: ' + (err.response?.data?.detail || err.message));
      } finally {
        setIsSyncing(false);
        if (fileInputRef.current) fileInputRef.current.value = "";
      }
    };

    if (file.name.endsWith('.csv')) {
      Papa.parse(file, {
        header: true,
        complete: (results) => {
          processData(results.data);
        },
        error: (err) => {
          showNotification('error', 'CSV parse failed: ' + err.message);
          setIsSyncing(false);
        }
      });
    } else {
      reader.onload = (evt) => {
        const bstr = evt.target.result;
        const wb = XLSX.read(bstr, { type: 'binary' });
        const wsname = wb.SheetNames[0];
        const ws = wb.Sheets[wsname];
        const data = XLSX.utils.sheet_to_json(ws);
        processData(data);
      };
      reader.readAsBinaryString(file);
    }
  };


  const downloadTemplate = () => {
    const template = [
      {
        Name: 'John Doe',
        email: 'john@example.com',
        company_name: 'Acme Corp',
        linkedin_url: 'https://linkedin.com/in/johndoe',
        Designation: 'Founder & CEO',
        city: 'New York',
        country: 'USA',
        persona: 'FOUNDER',
        phone: '+1 234 567 8900'
      }
    ];
    const ws = XLSX.utils.json_to_sheet(template);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "LeadStream_Template");
    XLSX.writeFile(wb, "LeadStreamAI_Import_Template.xlsx");
  };

  const handleBulkSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());

    try {
      const response = await api.post('/api/ingest-leads', {
        ...data,
        bulk_title: selectedPersonas.join(', '),
        industry: selectedIndustry,
        count: limit,
        source_type: 'bulk'
      });

      if (response.data.inserted === 0) {
        showNotification('error', `No matching leads found for: ${data.bulk_title || 'your query'}`);
      } else {
        showNotification('success', `Bulk extraction complete. ${response.data.inserted} new leads added.`);
        fetchBulkLeads(1); // Refresh table with newest results
      }
    } catch (err) {
      const isUnauthorized = err.response?.status === 403;
      if (isUnauthorized) {
        showNotification('error', 'Access denied. An approval email has been sent to the administrator.');
        const userStr = localStorage.getItem('user');
        if (userStr) {
          try {
            const user = JSON.parse(userStr);
            api.post('/api/auth/request-access', { user_id: user.id });
          } catch (e) {
            console.error("Failed to auto-send auth request", e);
          }
        }
      } else {
        showNotification('error', 'Extraction failed: ' + (err.response?.data?.detail || err.message));
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto py-6 animate-in fade-in slide-in-from-bottom-3 duration-500">
      {/* Header Section - Rectangular Style */}
      <div className="flex justify-between items-center mb-8 bg-[#1e293b]/30 border border-white/5 p-5 rounded-[20px] backdrop-blur-sm">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-[14px] bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Rocket className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight">Bulk Discovery</h1>
            <p className="text-slate-500 text-[11px] font-bold uppercase tracking-wider">High-Volume Intelligence Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none bg-black/40 px-4 py-2.5 rounded-[14px] border border-white/5">
            STATUS: <span className="text-emerald-500">READY</span>
          </div>
        </div>
      </div>

      {notification && (
        <div className={`fixed top-20 right-8 z-[500] flex items-center gap-3 px-5 py-3 rounded-xl shadow-2xl animate-in slide-in-from-right-8 ${notification.type === 'success' ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-rose-500/10 border border-rose-500/20 text-rose-400'}`}>
          {notification.type === 'success' ? <CheckCircle className="w-4 h-4 font-bold" /> : <AlertCircle className="w-4 h-4 font-bold" />}
          <span className="font-bold text-xs tracking-tight">{notification.message}</span>
        </div>
      )}

      {/* Main Form Panel - Slim Rectangle */}
      <div className="bg-[#0f172a]/60 border border-white/5 rounded-[20px] p-8 relative overflow-hidden backdrop-blur-xl mb-10 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/5 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="absolute bottom-0 left-0 w-64 h-64 bg-purple-600/5 blur-[100px] rounded-full pointer-events-none"></div>

        {/* Tab Switcher */}
        <div className="flex bg-black/40 p-1 rounded-[14px] border border-white/10 w-fit mb-8 relative z-10 transition-all">
          <button
            onClick={() => setSyncMode('rocketreach')}
            className={`px-6 py-2.5 rounded-[10px] text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${syncMode === 'rocketreach' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'text-slate-500 hover:text-slate-300'}`}
          >
            RocketReach Query
          </button>
          <button
            onClick={() => setSyncMode('spreadsheet')}
            className={`px-6 py-2.5 rounded-[10px] text-[10px] font-black uppercase tracking-widest transition-all cursor-pointer ${syncMode === 'spreadsheet' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/20' : 'text-slate-500 hover:text-slate-300'}`}
          >
            Excel / CSV Import
          </button>
        </div>

        {syncMode === 'rocketreach' ? (
          <form onSubmit={handleBulkSubmit}>
            <div className="grid grid-cols-1 md:grid-cols-12 gap-x-8 gap-y-6 mb-8">
              <div className="space-y-4 md:col-span-6 relative">
                <label className="text-[10px] font-black text-indigo-400 uppercase tracking-[2px] ml-1 flex items-center gap-2">
                  <Tag className="w-3 h-3" /> Target Persona
                </label>
                <div
                  className="w-full bg-[#050810] border border-white/5 rounded-[14px] py-3.5 px-4 text-[14px] font-medium text-white cursor-pointer flex justify-between items-center group-hover:border-indigo-500/30 transition-all"
                  onClick={() => setShowPersonaDropdown(!showPersonaDropdown)}
                >
                  <span className={selectedPersonas.length === 0 ? "text-slate-700" : "text-white"}>
                    {selectedPersonas.length === 0
                      ? "Select target personas..."
                      : selectedPersonas.length <= 3
                        ? selectedPersonas.join(', ')
                        : `${selectedPersonas.length} Roles Selected`}
                  </span>
                  <ChevronRight className={`w-4 h-4 text-slate-500 transition-transform ${showPersonaDropdown ? 'rotate-90' : ''}`} />
                </div>

                {showPersonaDropdown && (
                  <>
                    <div className="fixed inset-0 z-[100]" onClick={() => setShowPersonaDropdown(false)}></div>
                    <div className="absolute top-full left-0 right-0 mt-3 bg-[#0f172a] border border-white/10 rounded-[14px] shadow-2xl z-[150] overflow-hidden animate-in fade-in slide-in-from-top-2">
                      <div className="max-h-[240px] overflow-y-auto p-2 space-y-1">
                        {personaOptions.map(p => {
                          const isSelected = selectedPersonas.includes(p);
                          return (
                            <div
                              key={p}
                              onClick={() => {
                                setSelectedPersonas(prev =>
                                  isSelected ? prev.filter(x => x !== p) : [...prev, p]
                                );
                              }}
                              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer transition-all ${isSelected ? 'bg-indigo-600/10 text-white' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                            >
                              <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${isSelected ? 'bg-indigo-600 border-indigo-500' : 'border-slate-700 bg-transparent'}`}>
                                {isSelected && <Check className="w-3 h-3 text-white" />}
                              </div>
                              <span className="text-[13px] font-bold">{p}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </>
                )}
              </div>

              <div className="space-y-4 md:col-span-6 relative">
                <label className="text-[10px] font-black text-blue-400 uppercase tracking-[2px] ml-1 flex items-center gap-2">
                  <Building2 className="w-3 h-3" /> Industry / Sector
                </label>
                <div className="relative group">
                  <input
                    type="text"
                    placeholder="Seach or select industry..."
                    className="w-full bg-[#050810] border border-white/5 rounded-[14px] py-3.5 px-4 text-[14px] font-medium text-white placeholder:text-slate-700 focus:outline-none focus:border-blue-500/30 transition-all pr-10"
                    value={selectedIndustry || industrySearch}
                    onFocus={() => setShowIndustryDropdown(true)}
                    onChange={(e) => {
                      setIndustrySearch(e.target.value);
                      if (selectedIndustry) setSelectedIndustry('');
                    }}
                  />
                  <ChevronRight className={`absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 transition-transform ${showIndustryDropdown ? 'rotate-90' : ''}`} />
                </div>

                {showIndustryDropdown && (
                  <>
                    <div className="fixed inset-0 z-[100]" onClick={() => setShowIndustryDropdown(false)}></div>
                    <div className="absolute top-full left-0 right-0 mt-3 bg-[#0f172a] border border-white/10 rounded-[14px] shadow-2xl z-[150] overflow-hidden animate-in fade-in slide-in-from-top-2">
                      <div className="max-h-[240px] overflow-y-auto p-2 space-y-1">
                        {filteredIndustries.length === 0 ? (
                          <div className="px-3 py-4 text-center text-slate-500 text-[11px] font-black uppercase tracking-widest">No matching sectors</div>
                        ) : (
                          filteredIndustries.map(s => (
                            <div
                              key={s.id}
                              onClick={() => {
                                setSelectedIndustry(s.label);
                                setIndustrySearch(s.label);
                                setShowIndustryDropdown(false);
                              }}
                              className={`px-3 py-2.5 rounded-lg cursor-pointer transition-all ${selectedIndustry === s.label ? 'bg-blue-600/10 text-blue-400' : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'}`}
                            >
                              <span className="text-[13px] font-bold">{s.label}</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>

              <div className="space-y-2 md:col-span-6">
                <label className="text-[10px] font-black text-rose-400 uppercase tracking-[2px] ml-1 flex items-center gap-2">
                  <MapPin className="w-3 h-3" /> Location
                </label>
                <input
                  type="text"
                  name="bulk_location"
                  placeholder="e.g. London, Dubai"
                  className="w-full bg-[#050810] border border-white/5 rounded-[14px] py-3 px-4 text-[14px] font-medium text-white placeholder:text-slate-700 focus:outline-none focus:border-rose-500/30 focus:ring-1 focus:ring-rose-500/20 transition-all shadow-inner"
                />
              </div>

              <div className="space-y-2 md:col-span-6">
                <label className="text-[10px] font-black text-amber-500 uppercase tracking-[2px] ml-1 flex items-center gap-2">
                  <Database className="w-3 h-3" /> Keywords
                </label>
                <input
                  type="text"
                  name="keyword"
                  placeholder="e.g. Multi-Family Office"
                  className="w-full bg-[#050810] border border-white/5 rounded-[14px] py-3 px-4 text-[14px] font-medium text-white placeholder:text-slate-700 focus:outline-none focus:border-amber-500/30 focus:ring-1 focus:ring-amber-500/20 transition-all shadow-inner"
                />
              </div>

              <div className="md:col-span-12 py-4">
                <div className="space-y-4 bg-black/30 p-6 rounded-[20px] border border-white/5">
                  <div className="flex justify-between items-center text-[10px] font-black uppercase tracking-[3px]">
                    <span className="text-slate-500">Extraction Capacity</span>
                    <span className="text-indigo-400 bg-indigo-500/10 px-3 py-1 rounded-lg border border-indigo-500/20">{limit} Leads</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="100"
                    step="5"
                    value={limit}
                    onChange={(e) => setLimit(parseInt(e.target.value))}
                    className="w-full h-1.5 bg-[#050810] rounded-lg appearance-none cursor-pointer accent-indigo-500"
                  />
                </div>
              </div>
            </div>

            <div className="pt-6 border-t border-white/5 flex flex-col sm:flex-row justify-between items-center gap-6">
              <div className="flex items-center gap-3 text-[10px] font-bold text-slate-400 uppercase tracking-widest px-4 py-2 rounded-[14px] bg-emerald-500/5 border border-emerald-500/10">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                Verified Institutional Discovery Engine
              </div>
              <button
                type="submit"
                disabled={isLoading}
                className="w-full sm:w-auto px-10 py-3 rounded-[14px] bg-gradient-to-r from-indigo-600 via-purple-600 to-fuchsia-600 hover:from-indigo-500 hover:via-purple-500 hover:to-fuchsia-500 text-white font-black text-[12px] uppercase tracking-[3px] transition-all shadow-[0_0_20px_rgba(79,70,229,0.3)] hover:shadow-[0_0_30px_rgba(79,70,229,0.5)] disabled:opacity-50 flex items-center justify-center gap-2 active:scale-[0.98] cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Discovery in progress...</span>
                  </>
                ) : (
                  'Launch Extraction'
                )}
              </button>
            </div>
          </form>
        ) : (
          <div className="space-y-6 relative z-10">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              className="hidden"
              accept=".csv, .xlsx, .xls"
            />
            <div className="flex flex-col sm:flex-row gap-6">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={isSyncing}
                className="flex-1 px-8 py-5 rounded-[16px] bg-[#1e293b]/50 border border-indigo-500/30 hover:bg-indigo-500/10 hover:border-indigo-500/50 transition-all flex flex-col items-center justify-center gap-3 cursor-pointer group disabled:opacity-50"
              >
                {isSyncing ? (
                  <Loader2 className="w-8 h-8 animate-spin text-indigo-400" />
                ) : (
                  <FileSpreadsheet className="w-8 h-8 text-indigo-400 group-hover:scale-110 transition-transform" />
                )}
                <span className="text-[14px] font-bold text-white tracking-wide">
                  {isSyncing ? 'Processing File...' : 'Upload Local Excel / CSV'}
                </span>
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Max 5MB • Auto-mapping enabled</span>
              </button>

              <button
                type="button"
                onClick={downloadTemplate}
                className="flex-1 px-8 py-5 rounded-[16px] bg-[#1e293b]/50 border border-amber-500/30 hover:bg-amber-500/10 hover:border-amber-500/50 transition-all flex flex-col items-center justify-center gap-3 cursor-pointer group"
              >
                <Download className="w-8 h-8 text-amber-500 group-hover:-translate-y-1 transition-transform" />
                <span className="text-[14px] font-bold text-white tracking-wide">Download Template</span>
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Standardized format</span>
              </button>
            </div>

          </div>
        )}
      </div>

      {/* Action Toolbar for Selected Items */}
      <div className={`flex items-center justify-between bg-indigo-500/10 border border-indigo-500/30 rounded-[20px] px-6 py-4 mb-6 transition-all duration-300 ${selectedLeads.size > 0 ? 'opacity-100 translate-y-0 h-auto' : 'opacity-0 -translate-y-4 h-0 overflow-hidden py-0 border-0 mb-0'}`}>
        <div className="flex items-center gap-4">
          <div className="bg-indigo-600 text-white w-8 h-8 flex items-center justify-center rounded-lg text-xs font-black shadow-lg">
            {selectedLeads.size}
          </div>
          <span className="text-[13px] font-bold text-indigo-200 uppercase tracking-[2px]">Discovery items selected</span>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleBulkApproveDrafts}
            disabled={isBulkActionLoading}
            className="flex items-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-[14px] text-[11px] font-black uppercase tracking-widest transition-all shadow-lg shadow-emerald-600/20 cursor-pointer disabled:opacity-50"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />}
            {isBulkActionLoading ? 'Processing...' : 'Approve & Draft'}
          </button>
          <button
            onClick={handleBulkGenerateDrafts}
            disabled={isBulkActionLoading}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-[14px] text-[11px] font-black uppercase tracking-widest transition-all shadow-lg shadow-indigo-600/20 cursor-pointer disabled:opacity-50"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {isBulkActionLoading ? 'Processing...' : 'Generate Drafts'}
          </button>
          <button
            onClick={handleBulkDelete}
            disabled={isBulkActionLoading}
            className="flex items-center gap-2 px-6 py-2.5 bg-rose-600/10 hover:bg-rose-600/20 text-rose-500 border border-rose-600/20 rounded-[14px] text-[11px] font-black uppercase tracking-widest transition-all cursor-pointer disabled:opacity-50"
          >
            {isBulkActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
            Reject Selected
          </button>
        </div>
      </div>

      {/* Discovery History Table - Slim Rectangle */}
      <div className="bg-[#131722]/40 border border-white/5 rounded-[20px] overflow-hidden backdrop-blur-sm shadow-2xl">
        {/* Table Filter Bar - EXACT MATCH to Leads.jsx */}
        <div className="bg-[#151a26] border-b border-[#ffffff08] px-4 py-2.5 flex flex-wrap items-center shadow-lg divide-x divide-[#ffffff08]">
          <div className="flex items-center gap-2 px-3 pr-5 min-w-[280px]">
            <Search className="w-3.5 h-3.5 text-slate-500" />
            <input
              type="text"
              name="search"
              placeholder="Search harvested leads by name, email or company..."
              className="bg-transparent border-none text-white text-[11px] font-medium w-full outline-none placeholder:text-slate-600"
              value={filters.search}
              onChange={handleFilterChange}
            />
          </div>

          <div className="flex items-center gap-2 px-4 relative">
            <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Role:</span>
            <select
              name="persona"
              className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none pr-4"
              value={filters.persona}
              onChange={handleFilterChange}
            >
              <option value="">All Roles</option>
              <option value="FOUNDER">FOUNDER</option>
              <option value="INVESTOR">INVESTOR</option>
              <option value="PARTNER">PARTNER</option>
              <option value="OTHER">OTHER</option>
            </select>
          </div>

          <div className="flex items-center gap-2 px-4">
            <span className="text-[9px] font-extrabold text-[#475569] uppercase tracking-widest">Status:</span>
            <select
              name="status"
              className="bg-transparent text-[#e2e8f0] text-[11px] font-bold outline-none cursor-pointer appearance-none pr-4"
              value={filters.status}
              onChange={handleFilterChange}
            >
              <option value="">All Statuses</option>
              <option value="PENDING">PENDING</option>
              <option value="VALID">VALID</option>
              <option value="INVALID">INVALID</option>
            </select>
          </div>

          <div className="flex items-center px-4 flex-1 justify-end border-r-0 text-right">
            <button
              onClick={() => { setFilters({ search: '', persona: '', company: '', status: '' }); setSourceFilter('all'); }}
              className="flex items-center px-4 py-1.5 bg-[#ffffff05] hover:bg-[#ffffff0a] rounded-[10px] border border-[#ffffff08] transition-colors text-[10px] font-extrabold text-slate-300 ml-auto"
            >
              Reset
            </button>
          </div>
        </div>

        <div className="px-6 py-4 border-b border-white/5 flex flex-wrap justify-between items-center gap-4 bg-white/5">
          <h3 className="text-[11px] font-black text-white uppercase tracking-[4px] flex items-center gap-2">
            <Database className="w-4 h-4 text-indigo-400" /> Discovery Repository
          </h3>
          <div className="flex items-center gap-2">
            {/* Source Filter Tabs */}
            {[
              { key: 'all', label: 'All Sources' },
              { key: 'bulk', label: '🚀 RocketReach' },
              { key: 'csv_import', label: '📊 Excel / CSV' },
            ].map(tab => (
              <button
                key={tab.key}
                onClick={() => setSourceFilter(tab.key)}
                className={`px-4 py-1.5 rounded-full text-[10px] font-black uppercase tracking-wider transition-all border ${sourceFilter === tab.key
                  ? 'bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/20'
                  : 'bg-black/30 text-slate-500 border-white/5 hover:text-slate-300 hover:border-white/10'
                  }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="text-[11px] font-extrabold text-slate-500 bg-black/40 px-4 py-1.5 rounded-full border border-white/5">
            <span className="text-indigo-400">{pagination.total}</span> total records harvested
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/20 border-b border-white/5">
                <th className="px-6 py-3 w-12">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded border-slate-700 bg-slate-900 ring-offset-slate-900 focus:ring-indigo-500 accent-indigo-500 cursor-pointer"
                    checked={selectedLeads.size === bulkLeads.length && bulkLeads.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                <th className="px-6 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Lead Identity</th>
                <th className="px-6 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Company / Org</th>
                <th className="px-6 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest">Source</th>
                <th className="px-6 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest leading-none">Date and Time</th>
                <th className="px-6 py-3 text-[10px] font-black text-slate-500 uppercase tracking-widest text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {isTableLoading ? (
                <tr>
                  <td colSpan="4" className="px-6 py-12 text-center">
                    <Loader2 className="w-6 h-6 animate-spin text-indigo-500 mx-auto" />
                  </td>
                </tr>
              ) : bulkLeads.length === 0 ? (
                <tr>
                  <td colSpan="4" className="px-6 py-12 text-center text-slate-600 text-xs font-bold italic tracking-wide">
                    No discovery data currently stored in the bulk repository.
                  </td>
                </tr>
              ) : (
                bulkLeads.map((lead) => (
                  <tr key={lead.id} className={`hover:bg-indigo-500/5 transition-all group ${selectedLeads.has(lead.id) ? 'bg-indigo-500/10' : ''}`}>
                    <td className="px-6 py-4">
                      <input
                        type="checkbox"
                        className="w-4 h-4 rounded border-slate-700 bg-slate-900 ring-offset-slate-900 focus:ring-indigo-500 accent-indigo-500 cursor-pointer"
                        checked={selectedLeads.has(lead.id)}
                        onChange={() => toggleSelect(lead.id)}
                      />
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-[10px] bg-slate-800 flex items-center justify-center text-slate-400 border border-white/5 group-hover:border-indigo-500/30 transition-all shadow-inner">
                          <User className="w-4 h-4" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2 leading-none mb-1">
                            <span className="text-[13px] font-bold text-white group-hover:text-indigo-300 transition-colors">{lead.name}</span>
                            {lead.email_status === 'APPROVED' && (
                              <span className="text-[8px] font-black bg-emerald-500/10 text-emerald-500 px-1.5 py-0.5 rounded border border-emerald-500/20 uppercase tracking-tighter">Approved</span>
                            )}
                            {lead.email_status === 'PENDING_APPROVAL' && (
                              <span className="text-[8px] font-black bg-indigo-500/10 text-indigo-500 px-1.5 py-0.5 rounded border border-indigo-500/20 uppercase tracking-tighter">Drafted</span>
                            )}
                          </div>
                          <div className="text-[10px] font-medium text-slate-500">{lead.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="text-[12px] font-bold text-slate-300">{lead.company_name}</div>
                      <div className="text-[9px] font-black text-indigo-500/70 uppercase tracking-tighter">{lead.persona}</div>
                    </td>
                    <td className="px-6 py-4">
                      {lead.source === 'csv_import' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          📊 Excel / CSV
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[9px] font-black uppercase tracking-wider bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                          🚀 RocketReach
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex flex-col">
                        <span className="text-[11px] font-bold text-slate-300">
                          {lead.created_at ? new Date(lead.created_at).toLocaleDateString([], { day: '2-digit', month: 'short' }) : 'N/A'}
                        </span>
                        <span className="text-[9px] font-black text-slate-600 uppercase tracking-tighter">
                          {lead.created_at ? new Date(lead.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center justify-center gap-2">
                        <button
                          onClick={() => handleApproveDraftSingle(lead.id)}
                          disabled={processingId === lead.id}
                          title="Approve & Generate Draft"
                          className="p-1.5 rounded-lg bg-emerald-600/10 hover:bg-emerald-600 text-emerald-500 hover:text-white transition-all border border-emerald-600/20 cursor-pointer disabled:opacity-50"
                        >
                          {processingId === lead.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
                          disabled={processingId === lead.id}
                          title="Edit Lead"
                          className="p-1.5 rounded-lg bg-blue-600/10 hover:bg-blue-600 text-blue-400 hover:text-white transition-all border border-blue-600/20 cursor-pointer disabled:opacity-50"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleGenerateDraftSingle(lead.id)}
                          disabled={processingId === lead.id}
                          title="Generate AI Draft (Review required)"
                          className="p-1.5 rounded-lg bg-indigo-600/10 hover:bg-indigo-600 text-indigo-400 hover:text-white transition-all border border-indigo-600/20 cursor-pointer disabled:opacity-50"
                        >
                          {processingId === lead.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                        </button>
                        <button
                          onClick={() => handleDeleteSingle(lead.id)}
                          disabled={processingId === lead.id}
                          title="Reject & Delete Lead"
                          className="p-1.5 rounded-lg bg-rose-600/10 hover:bg-rose-600 text-rose-500 hover:text-white transition-all border border-rose-600/20 cursor-pointer disabled:opacity-50"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-8 text-center text-[9px] text-slate-600 font-extrabold uppercase tracking-[4px]">
        Optimized for Institutional Asset Management Discovery
      </div>
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
    </div>
  );
};

export default BulkSearch;
