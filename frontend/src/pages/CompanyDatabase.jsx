import React, { useState, useEffect, useCallback } from 'react';
import { 
  Search, Upload, Download, Trash2, Loader2, Sparkles, 
  Table, FileSpreadsheet, Plus, CheckCircle2, AlertCircle, X, Send, Mail, Pencil, PanelRightClose, Save, Layout, Tag, Building2, Filter, ChevronDown
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import * as XLSX from 'xlsx';
import api from '../services/api';

const CompanyDatabase = () => {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isImporting, setIsImporting] = useState(false);
  const [search, setSearch] = useState('');
  const [notification, setNotification] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [gsheetUrl, setGsheetUrl] = useState('');
  const [processingId, setProcessingId] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [editForm, setEditForm] = useState({});
  const [selectedIds, setSelectedIds] = useState([]);
  const [columnFilters, setColumnFilters] = useState({});
  const [showFilters, setShowFilters] = useState(false);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchCompanies = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/companies');
      setCompanies(response.data.companies || []);
    } catch (err) {
      console.error('Failed to fetch companies', err);
      showNotification('error', 'Sync Failure: Unable to establish link with the main database.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

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
    } catch (err) {
      showNotification('error', 'Purge Failure: Unable to wipe database shards.');
    }
  };

  const handleSyncGSheet = async () => {
    if (!gsheetUrl) {
      showNotification('error', 'Invalid Link: Please provide a valid Google Sheet URL.');
      return;
    }
    setIsSyncing(true);
    try {
      await api.post('/api/companies/import-gsheet', { url: gsheetUrl });
      showNotification('success', 'Satellite Link Established: Cloud dataset integrated.');
      fetchCompanies();
    } catch (err) {
      showNotification('error', 'Cloud sync failed: ' + (err.response?.data?.detail || err.message));
    } finally {
      setIsSyncing(false);
    }
  };

  const handleGenerateDraft = async (id) => {
    setProcessingId(id);
    try {
      await api.post(`/api/companies/${id}/generate-draft`);
      showNotification('success', 'Draft Synchronized: Moved to lead pipeline.');
    } catch (err) {
      showNotification('error', 'Draft Generation Fault: ' + (err.response?.data?.detail || err.message));
    } finally {
      setProcessingId(null);
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
    const dataToExport = companies.filter(c => selectedIds.includes(c.id)).map(({id, ...rest}) => rest);
    const ws = XLSX.utils.json_to_sheet(dataToExport);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Selected_Companies");
    XLSX.writeFile(wb, `Bulk_Export_${new Date().getTime()}.xlsx`);
  };

  const filteredCompanies = companies.filter(c => {
    const matchesSearch = Object.values(c).some(val => 
      String(val).toLowerCase().includes(search.toLowerCase())
    );
    const matchesColumnFilters = Object.entries(columnFilters).every(([key, value]) => {
      if (!value) return true;
      return String(c[key] || '').toLowerCase().includes(value.toLowerCase());
    });
    return matchesSearch && matchesColumnFilters;
  });

  const getUniqueValues = (column) => {
    const values = companies.map(c => c[column]).filter(v => v !== undefined && v !== null && v !== '');
    return Array.from(new Set(values)).sort();
  };

  const headers = companies.length > 0 
    ? Object.keys(companies[0]).filter(h => h !== 'id') 
    : ["Name", "Company", "Status", "Sector", "Email", "Note"];

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
               <button onClick={() => handleGenerateDraft(selectedCompany.id)} className="flex-1 btn bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 py-3 rounded-xl flex items-center justify-center gap-2 text-[10px] font-black uppercase tracking-widest transition-all">
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
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <button 
            onClick={() => setShowFilters(!showFilters)}
            className={`btn px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest transition-all ${showFilters ? 'bg-blue-500 text-white shadow-blue-500/20' : 'bg-white/5 text-slate-400 border border-white/5'}`}
          >
            <Filter className="w-4 h-4" />
            {showFilters ? 'Hide Filters' : 'Filter'}
          </button>
          
          <div className="relative flex-1 lg:max-w-md">
            <FileSpreadsheet className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-emerald-500/50" />
            <input
              type="text"
              placeholder="Paste Google Sheet URL..."
              className="w-full bg-[#131722]/60 border border-emerald-500/10 rounded-2xl py-3 pl-12 pr-4 text-white text-[11px] focus:outline-none focus:border-emerald-500/30 transition-all font-medium placeholder:text-slate-700"
              value={gsheetUrl}
              onChange={(e) => setGsheetUrl(e.target.value)}
            />
          </div>

          <button 
            onClick={handleSyncGSheet}
            disabled={isSyncing}
            className="btn bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest text-emerald-500 shadow-xl shadow-emerald-500/10 disabled:opacity-50"
          >
            {isSyncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileSpreadsheet className="w-4 h-4" />}
            Sync Cloud
          </button>

          <button 
            onClick={() => document.getElementById('file-upload').click()}
            disabled={isImporting}
            className="btn btn-primary px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 disabled:opacity-50"
          >
            {isImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Import
          </button>

          <button 
            onClick={handleExport}
            className="bg-white/5 hover:bg-white/10 border border-white/10 px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest text-slate-300 transition-all"
          >
            <Download className="w-4 h-4" />
            Export
          </button>

          <button 
            onClick={handleClear}
            className="bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest text-red-500 transition-all"
          >
            <Trash2 className="w-4 h-4" />
            Purge
          </button>
        </div>
      </div>

      {/* Dynamic Filter Bar */}
      {showFilters && companies.length > 0 && (
        <div className="mb-8 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 p-6 bg-[#131722]/40 border border-white/5 rounded-3xl animate-in slide-in-from-top-4 duration-300">
          {headers.map(header => {
            const uniqueValues = getUniqueValues(header);
            return (
              <div key={header} className="space-y-2">
                <label className="text-[9px] font-black text-slate-500 uppercase tracking-widest ml-1">{header.replace(/_/g, ' ')}</label>
                <div className="relative group/select">
                  <select
                    className="w-full appearance-none bg-[#0d1117] border border-white/5 rounded-xl px-4 py-2.5 text-[11px] text-white focus:outline-none focus:border-blue-500/30 transition-all cursor-pointer"
                    value={columnFilters[header] || ''}
                    onChange={(e) => setColumnFilters(prev => ({ ...prev, [header]: e.target.value }))}
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
          <table className="w-full text-left border-collapse table-fixed">
            <thead>
              <tr className="bg-white/[0.03] border-b border-white/5">
                  <th className="w-16 px-6 py-6 text-center">
                    <input 
                      type="checkbox" 
                      className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                      checked={selectedIds.length === filteredCompanies.length && filteredCompanies.length > 0}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  {headers.map((header) => (
                    <th key={header} className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-[3px] border-r border-white/5 last:border-0 min-w-[200px]">
                      <div className="flex items-center gap-3">
                        <Table className="w-3 h-3 opacity-30" />
                        {header.replace(/_/g, ' ')}
                      </div>
                    </th>
                  ))}
                  <th className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-[3px] min-w-[180px] text-center">
                    Outreach Control
                  </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {filteredCompanies.map((company, i) => (
                <tr key={company.id} className={`hover:bg-blue-500/[0.04] transition-all group ${selectedIds.includes(company.id) ? 'bg-blue-500/[0.06]' : ''}`}>
                  <td className="px-6 py-4 text-center">
                    <input 
                      type="checkbox" 
                      className="w-4 h-4 rounded border-white/10 bg-transparent text-blue-500 focus:ring-offset-0 focus:ring-0 cursor-pointer"
                      checked={selectedIds.includes(company.id)}
                      onChange={() => toggleSelectRow(company.id)}
                    />
                  </td>
                  {headers.map((header) => (
                    <td key={header} className="p-0 border-r border-white/5 last:border-0">
                      <input 
                        type="text"
                        defaultValue={company[header] || ''}
                        onBlur={(e) => handleCellUpdate(company.id, header, e.target.value)}
                        className="w-full h-full bg-transparent border-none px-6 py-4 text-slate-300 focus:outline-none focus:bg-white/5 focus:text-white text-sm font-medium transition-all"
                      />
                    </td>
                  ))}
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
                        onClick={() => handleGenerateDraft(company.id)}
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
      </div>
      
      <div className="mt-8 flex justify-between items-center text-[10px] font-black text-slate-600 uppercase tracking-[4px]">
        <span>Encrypted System Registry • Total Records: {companies.length}</span>
        <span className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse shadow-[0_0_8px_#10b981]"></div>
          Live Data Studio Linked
        </span>
      </div>
      {renderEditDrawer()}

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
                onClick={handleBulkExport}
                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-white text-[11px] font-black uppercase tracking-widest transition-all"
              >
                <Download className="w-4 h-4" /> Export Selected
              </button>
              <button 
                onClick={handleBulkDelete}
                className="flex items-center gap-2 px-6 py-2 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-500 text-[11px] font-black uppercase tracking-widest transition-all"
              >
                <Trash2 className="w-4 h-4" /> Delete Selected
              </button>
              <button 
                onClick={() => setSelectedIds([])}
                className="p-2 text-slate-500 hover:text-white transition-colors"
                title="Deselect All"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CompanyDatabase;
