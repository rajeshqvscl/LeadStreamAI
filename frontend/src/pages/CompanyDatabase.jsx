import React, { useState, useEffect, useCallback } from 'react';
import { 
  Search, Upload, Download, Trash2, Loader2, Sparkles, 
  Table, FileSpreadsheet, Plus, CheckCircle2, AlertCircle, X
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

  const filteredCompanies = companies.filter(c =>
    Object.values(c).some(val => 
      String(val).toLowerCase().includes(search.toLowerCase())
    )
  );

  const headers = companies.length > 0 
    ? Object.keys(companies[0]).filter(h => h !== 'id') 
    : ["Name", "Company", "Status", "Sector", "Email", "Note"];

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
            onClick={() => document.getElementById('file-upload').click()}
            disabled={isImporting}
            className="btn btn-primary px-6 h-12 rounded-2xl flex items-center gap-3 text-[11px] font-black uppercase tracking-widest shadow-xl shadow-blue-500/20 disabled:opacity-50"
          >
            {isImporting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            Import Sheet
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
                {headers.map((header) => (
                  <th key={header} className="px-6 py-6 text-[10px] font-black text-slate-500 uppercase tracking-[3px] border-r border-white/5 last:border-0 min-w-[200px]">
                    <div className="flex items-center gap-3">
                      <Table className="w-3 h-3 opacity-30" />
                      {header.replace(/_/g, ' ')}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {filteredCompanies.map((company, i) => (
                <tr key={company.id} className="hover:bg-blue-500/[0.04] transition-all group">
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
    </div>
  );
};

export default CompanyDatabase;
