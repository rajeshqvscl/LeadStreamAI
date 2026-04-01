import React, { useState, useEffect } from 'react';
import { Search, Plus, MapPin, Building2, BarChart, RefreshCw, Zap, ExternalLink, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const FamilyOffices = () => {
  const [offices, setOffices] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showAddModal, setShowAddModal] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);

  // Custom Multi-Select State
  const availableTitles = ['Partner', 'Associate', 'Manager', 'Founder', 'Analyst'];
  const [selectedTitles, setSelectedTitles] = useState([]);
  const [showTitleDropdown, setShowTitleDropdown] = useState(false);

  const toggleTitle = (title) => {
    setSelectedTitles(prev =>
      prev.includes(title) ? prev.filter(t => t !== title) : [...prev, title]
    );
  };

  const navigate = useNavigate();

  const fetchOffices = async () => {
    setIsLoading(true);
    try {
      // Assuming we'll add this endpoint or it returns JSON when requested with Accept: application/json
      const response = await api.get('/api/family-offices', { params: { search } });
      setOffices(response.data || []);
    } catch (err) {
      console.error('Failed to fetch family offices', err);
      // Fallback for demonstration if API isn't ready
      setOffices([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOffices();
  }, [search]);

  const handleSyncList = async () => {
    if (window.confirm("Are you sure you want to sync the office list with Google Sheets? This will update existing office profiles.")) {
      setIsSyncing(true);
      try {
        await api.post('/api/family-offices/sync');
        fetchOffices();
      } catch (err) {
        console.error('Failed to sync offices', err);
      } finally {
        setIsSyncing(false);
      }
    }
  };

  const handleBulkSyncLeads = async () => {
    if (window.confirm("Are you sure you want to bulk sync leads? This will delete all existing office leads and fetch 5 fresh leads per office.")) {
      setIsSyncing(true);
      try {
        await api.post('/api/family-offices/bulk-sync');
        fetchOffices();
      } catch (err) {
        console.error('Failed to bulk sync leads', err);
      } finally {
        setIsSyncing(false);
      }
    }
  };

  const handleDiscoverySubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const officeId = formData.get('office_id');
    if (!officeId) {
      alert("Please select a target office.");
      return;
    }

    setIsExtracting(true);
    try {
      await api.post(`/api/family-offices/${officeId}/rocketreach`, {
        job_title: selectedTitles.length > 0 ? selectedTitles.join(',') : '',
        location: formData.get('location'),
        limit: parseInt(formData.get('limit')) || 10
      });
      alert('Extraction completed successfully.');
      fetchOffices();
    } catch (err) {
      console.error('Failed to extract leads', err);
      alert('Extraction failed.');
    } finally {
      setIsExtracting(false);
    }
  };

  const getFitClass = (fit) => {
    const score = parseInt(fit) || 0;
    if (score >= 80 || fit?.toLowerCase().includes('high')) return 'badge-green bg-green-500/10 border-green-500/20 text-green-500';
    if (score >= 50 || fit?.toLowerCase().includes('med')) return 'badge-amber bg-amber-500/10 border-amber-500/20 text-amber-500';
    return 'badge-gray bg-slate-500/10 border-slate-500/20 text-slate-500';
  };

  return (
    <div className="animate-in fade-in duration-500">
      <div className="flex justify-between items-end mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white uppercase tracking-tight">Family Offices</h1>
          <p className="text-slate-400 text-sm mt-1">Office investment profiles and portfolio relationship management.</p>
        </div>
          <button
            className="group px-4 py-2 bg-slate-800/40 border border-white/5 rounded-xl text-[11px] font-bold text-slate-400 hover:text-white hover:bg-slate-800/60 transition-all flex items-center gap-2"
            title="Sync from Google Sheets"
            onClick={handleSyncList}
            disabled={isSyncing}
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isSyncing ? 'animate-spin text-blue-400' : 'text-blue-500'}`} />
            Sync List
          </button>
          <button
            className="group px-4 py-2 bg-slate-800/40 border border-blue-500/20 rounded-xl text-[11px] font-bold text-blue-400 hover:bg-blue-500/10 transition-all flex items-center gap-2"
            onClick={handleBulkSyncLeads}
            disabled={isSyncing}
          >
            <Zap className="w-3.5 h-3.5 fill-blue-500/20" />
            Bulk Sync Leads
          </button>
          <button
            className="px-6 py-2 bg-blue-600 hover:bg-blue-500 text-white font-black text-[11px] rounded-xl transition-all shadow-lg shadow-blue-500/20 flex items-center gap-2"
            onClick={() => setShowAddModal(true)}
          >
            <Plus className="w-4 h-4" />
            Add Office
          </button>
      </div>

      {/* Discovery Engine */}
      <div className="bg-gradient-to-br from-slate-900/80 to-slate-900/40 border border-blue-500/20 rounded-3xl p-8 mb-10 relative group z-20">
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-blue-500/5 blur-[120px] rounded-full pointer-events-none"></div>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-white font-bold text-lg flex items-center gap-3 italic">
            <span className="text-2xl text-blue-500 not-italic">⚡</span>
            RocketReach <span className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">Discovery Engine</span>
          </h3>
          <span className="text-[10px] font-black text-slate-600 uppercase tracking-[2px]">Office Lead Extraction</span>
        </div>

        <form onSubmit={handleDiscoverySubmit}>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-blue-500 uppercase tracking-widest ml-1">Target Office</label>
              <select name="office_id" className="w-full bg-black/40 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 appearance-none cursor-pointer">
                <option value="">— Select Profile —</option>
                {offices.map((o, idx) => <option key={o.id || `opt-${idx}`} value={o.id}>{o.name}</option>)}
              </select>
            </div>
            <div className="space-y-1.5 relative">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Job Title</label>
              <div
                className="w-full bg-black/40 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50 cursor-pointer flex items-center justify-between"
                onClick={() => setShowTitleDropdown(!showTitleDropdown)}
              >
                <span className={selectedTitles.length === 0 ? 'text-slate-500' : 'text-white'}>
                  {selectedTitles.length === 0 ? 'All Titles' : selectedTitles.length <= 2 ? selectedTitles.join(', ') : `${selectedTitles.length} selected`}
                </span>
              </div>

              {showTitleDropdown && (
                <>
                  <div className="fixed inset-0 z-[100]" onClick={() => setShowTitleDropdown(false)}></div>
                  <div className="absolute top-full left-0 mt-2 w-full bg-[#151a26] border border-[#ffffff10] rounded-xl shadow-2xl z-[150] overflow-hidden animate-in fade-in slide-in-from-top-2">
                    <div className="max-h-[200px] overflow-y-auto custom-scrollbar p-2">
                      {availableTitles.map(title => (
                        <div
                          key={title}
                          onClick={() => toggleTitle(title)}
                          className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 cursor-pointer transition-colors"
                        >
                          <div className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${selectedTitles.includes(title) ? 'bg-blue-500 border-blue-500' : 'border-slate-600 bg-transparent'}`}>
                            {selectedTitles.includes(title) && <svg className="w-3 h-3 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>}
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
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Location</label>
              <input type="text" name="location" placeholder="e.g. Dubai, London" className="w-full bg-black/40 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50" />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">Limit</label>
              <input type="number" name="limit" defaultValue={10} className="w-full bg-black/40 border border-white/10 rounded-xl py-2.5 px-4 text-sm text-white focus:outline-none focus:border-blue-500/50" />
            </div>
          </div>

          <div className="mt-8 pt-6 border-t border-white/5 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 rounded-full bg-green-500 shadow-[0_0_8px_#10b981] animate-pulse"></div>
              <span className="text-[11px] font-bold text-slate-500 uppercase tracking-tight">RocketReach API ready</span>
            </div>
            <button type="submit" disabled={isExtracting} className="btn btn-primary px-10 rounded-xl disabled:opacity-50">
              {isExtracting ? 'Extracting...' : 'Extract Portfolio Leads'}
            </button>
          </div>
        </form>
      </div>

      {/* Search Bar */}
      <div className="relative mb-10 group">
        <div className="absolute inset-y-0 left-0 pl-6 flex items-center pointer-events-none">
          <Search className="h-5 w-5 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
        </div>
        <input
          type="text"
          placeholder="Search by office name or location..."
          className="w-full bg-[#0f121b]/80 border border-white/5 rounded-2xl py-4 pl-14 pr-32 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50 focus:ring-1 focus:ring-blue-500/20 transition-all backdrop-blur-md"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="absolute inset-y-0 right-2 flex items-center pr-2">
          <button className="bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs py-2.5 px-8 rounded-xl transition-all shadow-lg shadow-blue-500/20">
            Search
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center opacity-50">
          <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
          <p className="text-slate-400 font-medium tracking-tight">Retrieving office profiles...</p>
        </div>
      ) : offices.length === 0 ? (
        <div className="py-32 flex flex-col items-center justify-center border border-dashed border-white/10 rounded-[40px] opacity-40">
          <Building2 className="w-16 h-16 text-slate-600 mb-6" />
          <h3 className="text-white font-bold text-xl mb-1">No Offices Found</h3>
          <p className="text-slate-500 text-sm">Synchronize with Excel or add manually to start tracking.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {offices.map((office, idx) => (
            <div
              key={office.id || `fo-${idx}`}
              onClick={() => navigate(`/dashboard/family-offices/${office.id}`)}
              className="group relative bg-[#131722]/60 border border-white/5 rounded-[24px] p-8 hover:border-blue-500/40 transition-all duration-500 cursor-pointer overflow-hidden"
            >
              <div className="absolute top-0 right-0 w-32 h-32 bg-blue-600/5 blur-[60px] rounded-full pointer-events-none group-hover:bg-blue-600/10 transition-all duration-500"></div>

              <div className="flex justify-between items-start mb-8">
                <div className="w-14 h-14 rounded-[18px] bg-blue-600 flex items-center justify-center text-white font-black text-xl shadow-lg shadow-blue-600/20 group-hover:scale-105 transition-transform duration-500">
                  {office.name?.substring(0, 2).toUpperCase() || 'FO'}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`px-3 py-1 rounded-full text-[9px] font-black uppercase tracking-[1.5px] bg-amber-500/10 text-amber-500 border border-amber-500/20`}>
                      {office.strategic_fit || 'MEDIUM'}
                    </span>
                    <ExternalLink className="w-4 h-4 text-slate-600 group-hover:text-blue-500 transition-colors" />
                  </div>
                </div>
              </div>

              <div className="mb-10">
                <h3 className="text-2xl font-black text-white mb-3 group-hover:text-blue-400 transition-colors tracking-tight">
                  {office.name}
                </h3>
                <div className="flex flex-col gap-2">
                  <div className="flex items-center gap-2.5 text-slate-500 text-[11px] font-bold">
                    <MapPin className="w-3.5 h-3.5 text-blue-500" />
                    {office.location || 'Location Unknown'}
                  </div>
                  <div className="flex items-center gap-2.5 text-slate-500 text-[11px] font-bold">
                    <Building2 className="w-3.5 h-3.5 text-indigo-500" />
                    {office.category || 'Portfolio Strategy'}
                  </div>
                </div>
              </div>

              <div className="flex justify-between items-end pt-6 border-t border-white/5">
                <div>
                  <div className="text-[10px] font-black text-slate-600 uppercase tracking-[2px] mb-2">Total Leads</div>
                  <div className="text-2xl font-black text-white leading-none">
                    {office.count || 0}
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-[10px] font-black text-slate-600 uppercase tracking-[2px] mb-2">Last Synced</div>
                  <div className="text-sm font-black text-slate-400 uppercase tracking-tight">
                    {office.last_synced ? new Date(office.last_synced).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : '23 MAR'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FamilyOffices;
