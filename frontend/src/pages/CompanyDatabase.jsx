import React, { useState, useEffect, useCallback } from 'react';
import {
  Search, Upload, Download, Trash2, Loader2, Sparkles,
  Table, FileSpreadsheet, Plus, CheckCircle2, AlertCircle, X, Send, Mail, Pencil, PanelRightClose, Save, Layout, Tag, Building2, Filter, ChevronDown, User, Globe, Calendar
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import * as XLSX from 'xlsx';
import api from '../services/api';
import DraftTemplatePicker from '../components/DraftTemplatePicker';

const CompanyDatabase = () => {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [search, setSearch] = useState('');
  const [notification, setNotification] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [gsheetUrl, setGsheetUrl] = useState(localStorage.getItem('gsheet_sync_url') || '');
  const [sheetTabs, setSheetTabs] = useState([]);
  const [selectedTab, setSelectedTab] = useState(null);
  const [isLoadingTabs, setIsLoadingTabs] = useState(false);
  const [processingId, setProcessingId] = useState(null);

  const [isSaving, setIsSaving] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [selectedIds, setSelectedIds] = useState([]);
  const [columnFilters, setColumnFilters] = useState({});
  const [showFilters, setShowFilters] = useState(false);
  // Browsing Tabs State
  const [browsingTabs, setBrowsingTabs] = useState(['ALL DATA']);
  const [activeBrowsingTab, setActiveBrowsingTab] = useState(localStorage.getItem('active_browsing_tab') || 'ALL DATA');

  // Pagination State
  const [currentPage, setCurrentPage] = useState(parseInt(localStorage.getItem('current_company_page')) || 1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchCompanies = async (page = 1) => {
    setIsLoading(true);
    try {
      const filtersCopy = { ...columnFilters };
      if (activeBrowsingTab !== 'ALL DATA') {
        filtersCopy['_source_tab'] = activeBrowsingTab;
      }

      const filtersJson = JSON.stringify(filtersCopy);
      const queryParams = new URLSearchParams({
        page: String(page),
        limit: '100'
      });
      queryParams.append('_t', String(Date.now()));
      if (search) queryParams.append('search', search);
      if (filtersJson !== '{}') queryParams.append('filters', filtersJson);

      const response = await api.get(`/api/companies?${queryParams.toString()}`);
      setCompanies(response.data.companies || []);
      setTotalCount(response.data.total || 0);
      const limit = response.data.limit || 500;
      const pages = response.data.pages || Math.ceil((response.data.total || 0) / limit);
      setTotalPages(pages);
      setCurrentPage(response.data.page || page);
      
      // Extract unique tabs from the data if any (or we could fetch from a dedicated endpoint)
      // For now, let's fetch unique tabs periodically or once
    } catch (err) {
      console.error('Failed to fetch companies', err);
      showNotification('error', 'Sync Failure: Unable to establish link with the main database.');
    } finally {
      setIsLoading(false);
    }
  };

  // Debounced Search & Filter Effect
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchCompanies(currentPage);
      localStorage.setItem('current_company_page', String(currentPage));
      localStorage.setItem('active_browsing_tab', activeBrowsingTab);
    }, 400); // 400ms debounce

    return () => clearTimeout(handler);
  }, [search, columnFilters, activeBrowsingTab, currentPage]);

  const fetchTabs = async () => {
    try {
      const response = await api.get('/api/companies/unique-tabs');
      if (response.data.tabs) {
        setBrowsingTabs(['ALL DATA', ...response.data.tabs]);
      }
    } catch (err) {
      console.error('Failed to fetch tabs', err);
    }
  };

  useEffect(() => {
    fetchTabs();
  }, []);

  // Auto-load sheet tabs from localStorage URL on mount
  useEffect(() => {
    const saved = localStorage.getItem('gsheet_sync_url');
    if (saved && gsheetUrl && sheetTabs.length === 0) {
      const timer = setTimeout(() => handleLoadTabs(), 300);
      return () => clearTimeout(timer);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Handle manual page changes
  const handlePageChange = (newPage) => {
    if (newPage < 1 || newPage > totalPages) return;
    fetchCompanies(newPage);
  };

  // Initial fetch is handled by the useEffect above (since search/filters are stable)
  // However, we can keep a separate mount effect if needed, but it might double-fetch.
  // The debounced effect will handle the first load.

  // Cell Update Logic
  const handleCellUpdate = async (rowId, field, newValue) => {
    const updatedRow = companies.find(c => c.id === rowId);
    if (!updatedRow || updatedRow[field] === newValue) return;

    const newRowData = { ...updatedRow };
    delete newRowData.id; // Strip ID for the JSON model
    newRowData[field] = newValue;

    try {
      await api.patch(`/api/companies/${rowId}`, newRowData);
      setCompanies(prev => prev.map(c => c.id === rowId ? { ...c, [field]: newValue } : c));
    } catch (err) {
      showNotification('error', 'Storage Fault: Cell modification failed to persist.');
    }
  };

  // Import Spreadsheet Logic
  const onDrop = useCallback(acceptedFiles => {
    const file = acceptedFiles[0];
    const reader = new FileReader();

    reader.onload = async (e) => {
      setIsImporting(true);
      try {
        const data = new Uint8Array(e.target.result);
        const workbook = XLSX.read(data, { type: 'array' });
        const firstSheetName = workbook.SheetNames[0];
        const worksheet = workbook.Sheets[firstSheetName];
        const jsonData = XLSX.utils.sheet_to_json(worksheet);

        if (jsonData.length === 0) {
          showNotification('error', 'Import Aborted: The spreadsheet is empty.');
          return;
        }

        await api.post('/api/companies/import', jsonData);
        showNotification('success', `Dataset Synced: ${jsonData.length} records integrated.`);
        fetchCompanies();
        fetchTabs();
      } catch (err) {
        showNotification('error', 'Import Failure: Encryption mismatch or malformed file.');
        console.error(err);
      } finally {
        setIsImporting(false);
      }
    };
    reader.readAsArrayBuffer(file);
  }, [companies]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'], 'text/csv': ['.csv'] },
    noClick: true
  });

  // Export Logic
  const handleExport = () => {
    if (companies.length === 0) return;
    const exportData = companies.map(({ id, ...rest }) => rest);
    const ws = XLSX.utils.json_to_sheet(exportData);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "CompanyDatabase");
    XLSX.writeFile(wb, `Company_Intel_Export_${new Date().toISOString().split('T')[0]}.xlsx`);
  };

  // Clear Logic
  const handleClear = async () => {
    if (!window.confirm("Purge Registry? This will permanently erase all company metadata in the database.")) return;
    try {
      await api.delete('/api/companies/clear');
      setCompanies([]);
      showNotification('success', 'Registry Cleansed: All company profiles purged.');
      fetchTabs();
      setActiveBrowsingTab('ALL DATA');
    } catch (err) {
      showNotification('error', 'Purge Failure: Unable to wipe database shards.');
    }
  };

  const handleLoadTabs = async () => {
    if (!gsheetUrl) return;
    setIsLoadingTabs(true);
    setSheetTabs([]);
    setSelectedTab(null);
    try {
      const res = await api.post('/api/companies/gsheet-tabs', { url: gsheetUrl });
      const tabs = res.data.tabs || [];
      setSheetTabs(tabs);
      if (tabs.length > 0) setSelectedTab(tabs[0].name);
    } catch (err) {
      showNotification('error', 'Failed to load sheet tabs.');
    } finally {
      setIsLoadingTabs(false);
    }
  };

  const handleSyncGSheet = async () => {
    if (!gsheetUrl) {
      showNotification('error', 'Invalid Link: Please provide a valid Cloud URL.');
      return;
    }
    setIsSyncing(true);
    showNotification('success', 'Satellite Link Initiated: Fetching remote dataset...');
    try {
      await api.post('/api/companies/import-gsheet', { 
        url: gsheetUrl, 
        sheet_name: selectedTab,

      });
      showNotification('success', 'Satellite Link Established: Cloud dataset integrated.');
      // Keep URL as requested by user
      localStorage.setItem('gsheet_sync_url', gsheetUrl);
      
      // Auto-switch to the tab we just imported for immediate visibility
      if (selectedTab && selectedTab !== 'ALL_TABS') {
        setActiveBrowsingTab(selectedTab);
      } else {
        setActiveBrowsingTab('ALL_TABS');
      }

      fetchCompanies(1);
      fetchTabs();
    } catch (err) {
      showNotification('error', 'Cloud sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsSyncing(false);
    }
  };

  const handleFetchDetails = async (id) => {
    setProcessingId(id);
    showNotification('success', 'Intelligence Search Initiated: Querying global metadata...');
    try {
      await api.post(`/api/companies/${id}/enrich`);
      showNotification('success', 'Registry Updated: Metadata shards integrated into profile.');
      fetchCompanies();
    } catch (err) {
      showNotification('error', 'Fetch Fault: ' + (err.response?.data?.detail || err.message));
    } finally {
      setProcessingId(null);
    }
  };

  const handleGenerateDraft = async (id) => {
    setProcessingId(id);
    try {
      await api.post(`/api/companies/${id}/generate-draft`);
      showNotification('success', '✓ Lead moved to pipeline. Draft added to Email Queue.');
      fetchCompanies(); // Refresh — company is removed from registry
    } catch (err) {
      showNotification('error', 'Draft Generation Fault: ' + (err.response?.data?.detail || err.message));
    } finally {
      setProcessingId(null);
    }
  };

  const [isBulkDrafting, setIsBulkDrafting] = useState(false);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [templateTarget, setTemplateTarget] = useState(null); // null = bulk, or company id for single

  const handleBulkGenerateDrafts = async () => {
    if (selectedIds.length === 0) return;
    const taskId = `bulk-gen-${Date.now()}`;
    
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'AI Bulk Generation', subtitle: `Processing ${selectedIds.length} profiles...`, progress: 10, status: 'RUNNING' } 
    }));

    const ids = [...selectedIds];
    setSelectedIds([]);
    
    try {
      const res = await api.post('/api/companies/bulk-generate-drafts', {
        row_ids: ids,
        template_name: null,
      });
      const batchId = res.data.batch_id;
      if (!batchId) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Generation Failed', subtitle: 'No batch ID', progress: 0, status: 'FAILED' } 
        }));
      } else {
        const pollInterval = setInterval(async () => {
          try {
            const prog = await api.get(`/api/companies/bulk-progress/${batchId}`);
            const p = prog.data;
            window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
              detail: { id: taskId, title: 'Bulk Intelligence Matrix', subtitle: `${p.processed}/${p.total} profiles...`, progress: Math.round((p.processed / p.total) * 100), status: p.status === 'running' ? 'RUNNING' : 'COMPLETED' } 
            }));
            if (p.status === 'done') {
              clearInterval(pollInterval);
              fetchCompanies();
              showNotification('success', `✓ ${p.success} lead${p.success > 1 ? 's' : ''} moved to pipeline. Drafts added to Email Queue.`);
            } else if (p.status === 'error') {
              clearInterval(pollInterval);
              fetchCompanies();
              showNotification('error', 'Bulk generation failed');
            }
          } catch { clearInterval(pollInterval); }
        }, 1500);
      }
    } catch (err) {
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Bulk Generation Failed', subtitle: err.response?.data?.detail || err.message, progress: 0, status: 'FAILED' } 
      }));
      showNotification('error', 'Bulk generation failed');
    }
  };

  const openTemplatePicker = (companyId = null) => {
    setTemplateTarget(companyId); // null = bulk mode
    setShowTemplatePicker(true);
  };

  const handleTemplateGenerate = async (templateName) => {
    const ids = templateTarget !== null ? [templateTarget] : selectedIds;
    if (ids.length === 0) return;
    
    const taskId = `template-gen-${Date.now()}`;
    setShowTemplatePicker(false);
    
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: `Applying ${templateName}`, subtitle: `Processing ${ids.length} leads...`, progress: 10, status: 'RUNNING' } 
    }));

    if (templateTarget === null) setSelectedIds([]);
    
    try {
      const res = await api.post('/api/companies/bulk-generate-drafts', {
        row_ids: ids,
        template_name: templateName === 'ai' ? null : templateName,
      });
      const batchId = res.data.batch_id;
      if (!batchId) {
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Generation Failed', subtitle: 'No batch ID', progress: 0, status: 'FAILED' } 
        }));
      } else {
        const pollInterval = setInterval(async () => {
          try {
            const prog = await api.get(`/api/companies/bulk-progress/${batchId}`);
            const p = prog.data;
            window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
              detail: { id: taskId, title: `Template Matrix: ${templateName}`, subtitle: `${p.processed}/${p.total} profiles...`, progress: Math.round((p.processed / p.total) * 100), status: p.status === 'running' ? 'RUNNING' : 'COMPLETED' } 
            }));
            if (p.status === 'done') {
              clearInterval(pollInterval);
              fetchCompanies();
              showNotification('success', `Template "${templateName}" applied to ${p.success} lead${p.success > 1 ? 's' : ''}.`);
            } else if (p.status === 'error') {
              clearInterval(pollInterval);
              fetchCompanies();
              showNotification('error', 'Template generation failed');
            }
          } catch { clearInterval(pollInterval); }
        }, 1500);
      }
    } catch (err) {
      console.error("Bulk template failure:", err);
      window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
        detail: { id: taskId, title: 'Template Failed', subtitle: err.response?.data?.detail || err.message, progress: 0, status: 'FAILED' } 
      }));
      showNotification('error', 'Template generation failed');
    }
  };

  const handleSendEmail = async (id) => {
    if (!window.confirm("Confirm Direct Dispatch? This will generate a lead and mark email as sent.")) return;
    setProcessingId(id);
    try {
      await api.post(`/api/companies/${id}/send`);
      showNotification('success', 'Direct Dispatch: Logged in lead pipeline.');
    } catch (err) {
      showNotification('error', 'Dispatch Failure: ' + (err.response?.data?.detail || err.message));
    } finally {
      setProcessingId(null);
    }
  };

  const handleEditClick = (company) => {
    setSelectedCompany(company);
    setEditForm({ ...company });
    setIsDrawerOpen(true);
  };

  const handleDrawerSave = async () => {
    if (!selectedCompany) return;
    setIsSaving(true);
    try {
      const dataToSave = { ...editForm };
      delete dataToSave.id;
      await api.patch(`/api/companies/${selectedCompany.id}`, dataToSave);
      showNotification('success', 'Profile updated correctly.');
      fetchCompanies();
      setIsDrawerOpen(false);
    } catch (err) {
      showNotification('error', 'Update Error: Unable to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleStatusChange = async (id, newStatus) => {
    setProcessingId(id);
    try {
      const company = companies.find(c => c.id === id);
      const updatedData = { ...company, status: newStatus };
      delete updatedData.id;
      await api.patch(`/api/companies/${id}`, updatedData);
      showNotification('success', `Status updated to ${newStatus}.`);
      fetchCompanies();
    } catch (err) {
      showNotification('error', 'Status Update Fault.');
    } finally {
      setProcessingId(null);
    }
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === filteredCompanies.length && filteredCompanies.length > 0) {
      setSelectedIds([]);
    } else {
      setSelectedIds(filteredCompanies.map(c => c.id));
    }
  };

  const toggleSelectRow = (id) => {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    );
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Explunge ${selectedIds.length} shards? This action is non-reversible.`)) return;
    try {
      // Assuming backend supports bulk delete or we loop
      await Promise.all(selectedIds.map(id => api.delete(`/api/companies/${id}`)));
      showNotification('success', `${selectedIds.length} records purged.`);
      setSelectedIds([]);
      fetchCompanies();
    } catch (err) {
      showNotification('error', 'Bulk Purge Fault.');
    }
  };

  const handleBulkExport = () => {
    const dataToExport = companies.filter(c => selectedIds.includes(c.id)).map(({ id, ...rest }) => rest);
    const ws = XLSX.utils.json_to_sheet(dataToExport);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Selected_Companies");
    XLSX.writeFile(wb, `Bulk_Export_${new Date().getTime()}.xlsx`);
  };

  const handleBulkEnrich = async () => {
    if (selectedIds.length === 0) return;
    const taskId = `bulk-enrich-${Date.now()}`;
    
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'AI Global Enrichment', subtitle: `Fetching metadata for ${selectedIds.length} profiles...`, progress: 10, status: 'RUNNING' } 
    }));

    const ids = [...selectedIds];
    setSelectedIds([]);
    
    let success = 0;
    let failed = 0;
    for (const id of ids) {
      try {
        await api.post(`/api/companies/${id}/enrich`);
        success++;
        const prog = Math.round((success / ids.length) * 100);
        window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
          detail: { id: taskId, title: 'Global Metadata Sync', subtitle: `Enriched ${success}/${ids.length} profiles...`, progress: prog, status: 'RUNNING' } 
        }));
      } catch {
        failed++;
      }
    }
    
    window.dispatchEvent(new CustomEvent('TASK_UPDATE', { 
      detail: { id: taskId, title: 'Enrichment Matrix Complete', subtitle: `Success: ${success} | Failed: ${failed}`, progress: 100, status: 'COMPLETED' } 
    }));
    
    fetchCompanies();
  };

  const filteredCompanies = companies;

  const getUniqueValues = (column) => {
    const values = companies.map(c => c[column]).filter(v => v !== undefined && v !== null && v !== '');
    return Array.from(new Set(values)).sort();
  };

  const headers = React.useMemo(() => {
    if (companies.length === 0) return ["Name", "Company", "Email", "LinkedIn Profile", "Designation", "Mobile", "Sector"];
    
    // Only keep columns that have at least one non-empty value
    const colHasData = {};
    companies.forEach(c => {
      Object.keys(c).forEach(key => {
        if (key === 'id' || key === '_is_generated' || key.startsWith('_')) return;
        const val = c[key];
        if (val !== null && val !== undefined && String(val).trim()) {
          colHasData[key] = true;
        }
      });
    });
    
    const priority = ["Company Name", "Name", "Person Name", "Email", "Mobile", "LinkedIn Profile", "LinkedIn URL", "Designation", "Domain", "Website"];
    const keys = Object.keys(colHasData);
    
    return keys.sort((a, b) => {
      const aIdx = priority.findIndex(p => a.toLowerCase().includes(p.toLowerCase()));
      const bIdx = priority.findIndex(p => b.toLowerCase().includes(p.toLowerCase()));
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;
      return a.localeCompare(b);
    });
  }, [companies]);

  const renderEditDrawer = () => {
    if (!isDrawerOpen || !selectedCompany) return null;

    return (
      <div className="fixed inset-0 z-[100] flex justify-end animate-in fade-in duration-300">
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setIsDrawerOpen(false)} />
        <div className="relative w-full max-w-xl bg-[#0d1117] border-l border-white/10 shadow-2xl flex flex-col animate-in slide-in-from-right-full duration-500">
          <div className="p-6 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500">
                <Building2 className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-lg font-black text-white tracking-tight">Edit Profile</h3>
                <p className="text-[9px] font-black text-slate-500 uppercase tracking-widest mt-0.5">Registry ID: {selectedCompany.id}</p>
              </div>
            </div>
            <button onClick={() => setIsDrawerOpen(false)} className="p-2 hover:bg-white/5 rounded-lg transition-colors text-slate-500 hover:text-white">
              <PanelRightClose className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-8 space-y-8 custom-scrollbar">
            <div className="flex flex-wrap gap-3 p-4 bg-blue-500/5 rounded-2xl border border-blue-500/10">
              <button onClick={() => openTemplatePicker(selectedCompany.id)} className="flex-1 btn bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 py-3 rounded-xl flex items-center justify-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all">
                <Sparkles className="w-3.5 h-3.5" /> Draft AI
              </button>
              <button onClick={() => handleSendEmail(selectedCompany.id)} className="flex-1 btn bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 py-3 rounded-xl flex items-center justify-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all">
                <Send className="w-3.5 h-3.5" /> Dispatch
              </button>
              <button onClick={() => handleStatusChange(selectedCompany.id, 'APPROVED')} className="flex-1 btn bg-amber-500/10 hover:bg-amber-500/20 text-amber-500 py-3 rounded-xl flex items-center justify-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all">
                <CheckCircle2 className="w-3.5 h-3.5" /> Approve
              </button>
            </div>

            <div className="grid grid-cols-1 gap-6">
              {Object.keys(editForm).filter(key => key !== 'id').map((key) => (
                <div key={key} className="space-y-2">
                  <label className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">
                    <Tag className="w-3 h-3 opacity-30" />
                    {key.replace(/_/g, ' ')}
                  </label>
                  <input
                    type="text"
                    value={editForm[key] || ''}
                    onChange={(e) => setEditForm(prev => ({ ...prev, [key]: e.target.value }))}
                    className="w-full bg-[#131722] border border-white/5 rounded-xl px-4 py-3.5 text-sm text-white focus:outline-none focus:border-blue-500/30 transition-all font-medium"
                  />
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 border-t border-white/5 bg-white/[0.02] flex gap-3">
            <button onClick={() => setIsDrawerOpen(false)} className="flex-1 px-6 py-4 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 text-[11px] font-black uppercase tracking-widest transition-all">Cancel</button>
            <button onClick={handleDrawerSave} disabled={isSaving} className="flex-[2] px-6 py-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-black uppercase tracking-widest transition-all flex items-center justify-center gap-2">
              {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save Changes
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div {...getRootProps()} className={`min-h-screen animate-in fade-in duration-700 ${isDragActive ? 'bg-blue-600/5 cursor-copy' : ''}`}>
      <input {...getInputProps()} id="file-upload" />

      {/* Header Controls */}
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 mb-10">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[9px] font-black text-blue-500 uppercase tracking-[2px]">Interactive Data Studio</div>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight flex items-center gap-4">
            Intelligence <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent italic">Grid</span>
          </h1>
          <p className="text-slate-500 text-[10px] font-black uppercase tracking-[4px] mt-2 opacity-60">Manage & Edit System-Wide Company Profiles</p>
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full lg:w-auto">
          <div className="relative flex-1 lg:w-72">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search dataset..."
              className="w-full bg-[#131722]/60 border border-white/5 rounded-2xl py-3 pl-12 pr-4 text-white text-sm focus:outline-none focus:border-blue-500/30 transition-all font-medium placeholder:text-slate-700"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setCurrentPage(1);
              }}
            />
          </div>

          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`btn px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest transition-all cursor-pointer ${showFilters ? 'bg-blue-500 text-white shadow-blue-500/20' : 'bg-white/5 text-slate-400 border border-white/5'}`}
          >
            <Filter className="w-4 h-4" />
            {showFilters ? 'Hide Filters' : 'Filter'}
          </button>

          <button
            onClick={() => {
              setSearch('');
              setColumnFilters({});
              setCurrentPage(1);
            }}
            className="bg-white/5 hover:bg-white/10 border border-white/5 p-3 rounded-2xl text-slate-500 transition-all hover:text-white cursor-pointer"
            title="Reset All Matrix Filters"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="relative flex-1 lg:max-w-md space-y-2">
            <div className="relative">
              <FileSpreadsheet className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-500/50" />
              <input
                type="text"
                placeholder="Paste Google Sheet URL..."
                className="w-full bg-[#131722]/60 border border-emerald-500/10 rounded-2xl py-3 pl-12 pr-32 text-white text-[11px] focus:outline-none focus:border-emerald-500/30 transition-all font-medium placeholder:text-slate-700"
                value={gsheetUrl}
                onChange={(e) => { 
                  setGsheetUrl(e.target.value); 
                  setSheetTabs([]); 
                  setSelectedTab(null);
                  localStorage.setItem('gsheet_sync_url', e.target.value);
                }}
              />
              <button
                onClick={handleLoadTabs}
                disabled={isLoadingTabs || !gsheetUrl}
                className="absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-xl text-[9px] font-black uppercase tracking-widest transition-all disabled:opacity-40 cursor-pointer"
              >
                {isLoadingTabs ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Load Tabs'}
              </button>
            </div>
            {sheetTabs.length > 0 && (
              <div className="flex items-center gap-2">


                <div className="relative group/select flex-1">
                  <select
                    value={selectedTab === 'ALL_TABS' ? '' : (selectedTab || '')}
                    onChange={(e) => setSelectedTab(e.target.value)}
                    className="w-full h-10 appearance-none bg-white/5 border border-white/10 rounded-xl px-4 pr-10 text-[10px] font-black text-slate-300 uppercase tracking-widest focus:outline-none focus:border-emerald-500/30 transition-all cursor-pointer"
                  >
                    <option value="" disabled className="bg-[#0d1117]">Select Individual Tab</option>
                    {sheetTabs.map(tab => (
                      <option key={tab.gid} value={tab.name} className="bg-[#0d1117] text-white py-2">
                        {tab.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500 pointer-events-none group-hover/select:text-slate-300 transition-colors" />
                </div>
              </div>
            )}
            <div className="flex items-center gap-4 self-end">
              <button
                onClick={handleSyncGSheet}
                disabled={isSyncing || !gsheetUrl}
                className="h-10 px-6 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 rounded-xl flex items-center justify-center gap-2 text-[9px] font-black uppercase tracking-widest text-emerald-500 disabled:opacity-50 cursor-pointer transition-all"
              >
                {isSyncing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileSpreadsheet className="w-3.5 h-3.5" />}
                Sync
              </button>

              <button
                onClick={() => document.getElementById('file-upload').click()}
                disabled={isImporting}
                className="h-10 px-6 bg-blue-600 hover:bg-blue-500 text-white rounded-xl flex items-center gap-2 text-[9px] font-black uppercase tracking-widest shadow-lg shadow-blue-600/20 disabled:opacity-50 cursor-pointer transition-all"
              >
                {isImporting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                Import
              </button>

              <button
                onClick={handleExport}
                className="h-10 px-6 bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 rounded-xl flex items-center gap-2 text-[9px] font-black uppercase tracking-widest cursor-pointer transition-all"
              >
                <Download className="w-3.5 h-3.5 text-slate-500" />
                Export
              </button>

              <button
                onClick={handleClear}
                className="h-10 px-6 bg-red-500/10 hover:bg-red-500/20 border border-red-500/30 text-red-500 rounded-xl flex items-center gap-2 text-[9px] font-black uppercase tracking-widest cursor-pointer transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Purge
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic Filter Bar */}
      {showFilters && companies.length > 0 && (
        <div className="mb-8 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 p-6 bg-[#131722]/40 border border-white/5 rounded-3xl animate-in slide-in-from-top-4 duration-300">
          {/* Status Filter */}
          <div className="space-y-2">
            <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest ml-1">Status</label>
            <div className="relative group/select">
              <select
                className="w-full appearance-none bg-[#0d1117] border border-white/5 rounded-xl px-4 py-2.5 text-[11px] text-white focus:outline-none focus:border-blue-500/30 transition-all cursor-pointer"
                value={columnFilters['generated'] || ''}
                onChange={(e) => {
                  setColumnFilters(prev => ({ ...prev, generated: e.target.value }));
                  setCurrentPage(1);
                }}
              >
                <option value="">All Status</option>
                <option value="false">New</option>
                <option value="true">Generated</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-600 pointer-events-none group-hover/select:text-slate-400 transition-colors" />
            </div>
          </div>

          {headers.map(header => {
            const uniqueValues = getUniqueValues(header);
            return (
              <div key={header} className="space-y-2">
                <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest ml-1">{header.replace(/_/g, ' ')}</label>
                <div className="relative group/select">
                  <select
                    className="w-full appearance-none bg-[#0d1117] border border-white/5 rounded-xl px-4 py-2.5 text-[11px] text-white focus:outline-none focus:border-blue-500/30 transition-all cursor-pointer"
                    value={columnFilters[header] || ''}
                    onChange={(e) => {
                      setColumnFilters(prev => ({ ...prev, [header]: e.target.value }));
                      setCurrentPage(1);
                    }}
                  >
                    <option value="">All {header.replace(/_/g, ' ')}</option>
                    {uniqueValues.map(val => (
                      <option key={val} value={val}>{val}</option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-600 pointer-events-none group-hover/select:text-slate-400 transition-colors" />
                </div>
              </div>
            );
          })}
          
          <div className="flex items-end pb-0.5">
            <button
              onClick={() => {
                setSearch('');
                setColumnFilters({});
                setCurrentPage(1);
              }}
              className="w-full px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl text-[10px] font-black text-red-500 uppercase tracking-widest transition-all flex items-center justify-center gap-2 group cursor-pointer"
            >
              <Trash2 className="w-3 h-3 group-hover:scale-110 transition-transform" />
              Reset Filters
            </button>
          </div>
        </div>
      )}

      {notification && (
        <div className={`mb-6 p-4 rounded-2xl border flex items-center gap-4 animate-in slide-in-from-top-4 ${notification.type === 'error' ? 'bg-red-500/10 border-red-500/20 text-red-500' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500'}`}>
          {notification.type === 'error' ? <AlertCircle className="w-5 h-5 shrink-0" /> : <CheckCircle2 className="w-5 h-5 shrink-0" />}
          <span className="text-[11px] font-black uppercase tracking-widest leading-relaxed">{notification.message}</span>
          <button onClick={() => setNotification(null)} className="ml-auto opacity-40 hover:opacity-100 transition-opacity"><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Grid Matrix */}
      <div className="bg-[#131722]/80 border border-white/5 rounded-[32px] overflow-hidden shadow-2xl backdrop-blur-3xl relative">
        {isLoading && (
          <div className="absolute inset-0 bg-[#0d1117]/60 backdrop-blur-sm z-50 flex flex-col items-center justify-center gap-4">
            <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-[5px] animate-pulse">Syncing Registry Matrix...</p>
          </div>
        )}

        {isDragActive && (
          <div className="absolute inset-0 bg-blue-600/20 backdrop-blur-md z-50 flex flex-col items-center justify-center gap-4 border-4 border-dashed border-blue-500/50 m-4 rounded-[24px]">
            <FileSpreadsheet className="w-20 h-20 text-blue-400 animate-bounce" />
            <h2 className="text-2xl font-black text-white uppercase tracking-widest">Release to Integrate Dataset</h2>
          </div>
        )}

        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.03] border-b border-white/5">
                <th className="w-16 px-6 py-4 text-center">
                  <input
                    type="checkbox"
                    className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                    checked={selectedIds.length === filteredCompanies.length && filteredCompanies.length > 0}
                    onChange={toggleSelectAll}
                  />
                </th>
                {headers.map((header) => (
                  <th key={header} className="px-5 py-4 text-[9px] font-black text-slate-500 uppercase tracking-wider border-r border-white/5 last:border-0 min-w-[160px]">
                    <div className="flex items-center gap-2">
                      <Table className="w-3 h-3 opacity-40 text-blue-500" />
                      <span className="whitespace-nowrap">{header.replace(/_/g, ' ')}</span>
                    </div>
                  </th>
                ))}
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-[3px] min-w-[120px] text-center">
                  Status
                </th>
                <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-[3px] min-w-[180px] text-center">
                  Outreach Control
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {filteredCompanies.map((company, i) => (
                <tr key={company.id} className={`hover:bg-blue-500/[0.04] transition-all group ${selectedIds.includes(company.id) ? 'bg-blue-500/[0.06]' : ''}`}>
                  <td className="px-6 py-3 text-center">
                    <input
                      type="checkbox"
                      className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                      checked={selectedIds.includes(company.id)}
                      onChange={() => toggleSelectRow(company.id)}
                    />
                  </td>
                  {headers.map((header) => {
                    const raw = company[header];
                    const val = raw !== null && raw !== undefined ? String(raw) : '';
                    const displayVal = val.trim() ? val : '-';
                    const isLink = (/linkedin|url|website|link/i.test(header) || (val && (val.includes('linkedin.com') || val.includes('http://') || val.includes('https://')))) && val;
                    return (
                      <td key={header} className="p-0 border-r border-white/5 last:border-0">
                        {isLink ? (
                          <div className="px-5 py-3.5">
                            <a
                              href={val.startsWith('http') ? val : `https://${val}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="flex items-center gap-2 text-blue-400 hover:text-blue-300 text-xs font-medium transition-colors group/link"
                              title={val}
                            >
                              <Globe className="w-3.5 h-3.5 shrink-0 group-hover/link:scale-110 transition-transform" />
                              <span className="truncate max-w-[140px] underline underline-offset-4">{val}</span>
                            </a>
                          </div>
                        ) : (
                          <input
                            type="text"
                            defaultValue={displayVal}
                            onBlur={(e) => { const v = e.target.value.trim(); handleCellUpdate(company.id, header, v === '-' ? '' : v); }}
                            className="w-full h-full bg-transparent border-none px-5 py-3.5 text-slate-300 focus:outline-none focus:bg-white/[0.02] focus:text-white text-xs font-medium transition-all"
                          />
                        )}
                      </td>
                    );
                  })}
                  <td className="px-6 py-4 text-center">
                    {company._is_generated ? (
                      <span className="px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[9px] font-black text-emerald-500 uppercase tracking-wider">
                        Generated
                      </span>
                    ) : (
                      <span className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[9px] font-black text-blue-500 uppercase tracking-wider">
                        New
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <div className="flex items-center justify-center gap-2">
                      <button
                        onClick={() => handleEditClick(company)}
                        className="p-2.5 rounded-xl bg-slate-500/10 hover:bg-white/10 text-slate-400 transition-all group/btn"
                        title="Edit Detailed Metadata"
                      >
                        <Pencil className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />
                      </button>
                      <button
                        onClick={() => openTemplatePicker(company.id)}
                        disabled={processingId === company.id}
                        className="p-2.5 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 transition-all group/btn"
                        title="Generate Draft in Pipeline"
                      >
                        {processingId === company.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />}
                      </button>
                      <button
                        onClick={() => handleSendEmail(company.id)}
                        disabled={processingId === company.id}
                        className="p-2.5 rounded-xl bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 transition-all group/btn"
                        title="Mark as Sent in Pipeline"
                      >
                        {processingId === company.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4 group-hover/btn:scale-110 transition-transform" />}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {filteredCompanies.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center py-32 text-center">
              <div className="w-20 h-20 bg-slate-500/5 rounded-[30px] flex items-center justify-center mb-8 border border-white/5">
                <Plus className="w-10 h-10 text-slate-700" />
              </div>
              <h3 className="text-white text-lg font-bold mb-2">No Profiles Detected</h3>
              <p className="text-slate-600 font-extrabold uppercase tracking-[4px] text-[10px] max-w-sm mx-auto">
                Drag and drop a spreadsheet or click <span className="text-blue-500 underline cursor-pointer" onClick={() => document.getElementById('file-upload').click()}>Import</span> to populate the intelligence matrix.
              </p>
            </div>
          )}
        </div>

        {/* Spreadsheet-style Bottom Tabs */}
        {browsingTabs.length > 1 && (
          <div className="bg-[#0d1117]/90 border-t border-white/10 flex items-center px-4 overflow-x-auto no-scrollbar">
            <div className="flex items-center h-14">
              {browsingTabs.map((tab) => (
                <button
                  key={tab}
                  onClick={() => { setActiveBrowsingTab(tab); setCurrentPage(1); }}
                  className={`px-8 h-full flex items-center gap-3 text-[10px] font-black uppercase tracking-[2px] transition-all cursor-pointer border-r border-white/5 last:border-r-0 relative group min-w-[140px] justify-center ${
                    activeBrowsingTab === tab
                      ? 'bg-[#131722] text-blue-400'
                      : 'text-slate-600 hover:bg-white/[0.02] hover:text-slate-400'
                  }`}
                >
                  {tab === 'ALL DATA' ? <Layout className="w-4 h-4" /> : <Tag className="w-3.5 h-3.5 opacity-50" />}
                  {tab}
                  {activeBrowsingTab === tab && (
                    <div className="absolute bottom-0 left-0 right-0 h-[3px] bg-blue-500 shadow-[0_-2px_15px_rgba(59,130,246,0.6)]" />
                  )}
                  {activeBrowsingTab === tab && (
                    <ChevronDown className="w-3.5 h-3.5 text-blue-400/50" />
                  )}
                </button>
              ))}
              
              <button className="px-5 h-full flex items-center justify-center text-slate-700 hover:text-white transition-colors cursor-not-allowed border-l border-white/5" title="Add Tab (Read Only)">
                <Plus className="w-4.5 h-4.5" />
              </button>
            </div>
            
            <div className="ml-auto flex items-center gap-6 pr-6">
               <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest hidden md:block">
                 Matrix Mode: <span className="text-blue-500/50">Active Sync</span>
               </div>
               <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest">
                 Tab View: <span className="text-white">{activeBrowsingTab}</span>
               </div>
            </div>
          </div>
        )}
      </div>

      <div className="mt-8 flex flex-col md:flex-row justify-between items-center gap-6">
        <div className="flex items-center gap-4 text-[10px] font-black text-slate-600 uppercase tracking-[4px]">
          <span>Encrypted System Registry • Total Records: {totalCount}</span>
          <span className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_#10b981]"></div>
            Live Data Studio Linked
          </span>
        </div>

        {/* Pagination UI */}
        {totalPages > 1 && (
          <div className="flex items-center gap-2 bg-[#131722]/80 border border-white/5 rounded-2xl p-1.5 backdrop-blur-xl">
            <button
              disabled={currentPage === 1 || isLoading}
              onClick={() => handlePageChange(currentPage - 1)}
              className="p-2.5 rounded-xl hover:bg-white/5 text-slate-400 disabled:opacity-30 disabled:hover:bg-transparent transition-all cursor-pointer"
            >
              <ChevronDown className="w-5 h-5 rotate-90" />
            </button>
            <div className="flex items-center gap-1 px-4">
              <span className="text-[11px] font-black text-white">PAGE</span>
              <span className="text-[11px] font-black text-blue-500">{currentPage}</span>
              <span className="text-[11px] font-black text-slate-600">OF</span>
              <span className="text-[11px] font-black text-slate-600">{totalPages}</span>
            </div>
            <button
              disabled={currentPage === totalPages || isLoading}
              onClick={() => handlePageChange(currentPage + 1)}
              className="p-2.5 rounded-xl hover:bg-white/5 text-slate-400 disabled:opacity-30 disabled:hover:bg-transparent transition-all cursor-pointer"
            >
              <ChevronDown className="w-5 h-5 -rotate-90" />
            </button>
          </div>
        )}
      </div>
      {renderEditDrawer()}

      <DraftTemplatePicker
        isOpen={showTemplatePicker}
        onClose={() => setShowTemplatePicker(false)}
        selectedCount={templateTarget !== null ? 1 : selectedIds.length}
        onGenerate={handleTemplateGenerate}
      />

      {/* Bulk Action Bar */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-[90] animate-in slide-in-from-bottom-8 duration-500">
          <div className="bg-[#1e293b] border border-blue-500/30 rounded-2xl px-8 py-5 shadow-2xl flex items-center gap-10">
            <div className="flex items-center gap-3 pr-10 border-r border-white/10">
              <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center text-white font-black text-xs">
                {selectedIds.length}
              </div>
              <span className="text-[10px] font-black text-white uppercase tracking-widest">Companies Selected</span>
            </div>

            <div className="flex items-center gap-4">
              <button
                onClick={() => openTemplatePicker(null)}
                disabled={isBulkDrafting}
                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-[11px] font-black uppercase tracking-widest transition-all disabled:opacity-50 cursor-pointer"
              >
                {isBulkDrafting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {isBulkDrafting ? 'Drafting...' : 'Generate Drafts'}
              </button>
              <button
                onClick={handleBulkExport}
                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white text-[11px] font-black uppercase tracking-widest transition-all cursor-pointer"
              >
                <Download className="w-4 h-4" /> Export Selected
              </button>
              <button
                onClick={handleBulkDelete}
                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-500 text-[11px] font-black uppercase tracking-widest transition-all cursor-pointer"
              >
                <Trash2 className="w-4 h-4" /> Delete Selected
              </button>
              <button
                onClick={() => setSelectedIds([])}
                className="p-2 text-slate-500 hover:text-white transition-colors cursor-pointer"
                title="Deselect All"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        {/* Toast Notification */}
        </div>
      )}
    </div>
  );
};

export default CompanyDatabase;
