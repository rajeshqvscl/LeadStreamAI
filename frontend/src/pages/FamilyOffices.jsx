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
        <div className="flex gap-4">
          <button 
            className="btn btn-ghost border-white/5 text-slate-400 hover:text-white disabled:opacity-50" 
            title="Sync from Google Sheets"
            onClick={handleSyncList}
            disabled={isSyncing}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isSyncing ? 'animate-spin' : ''}`} /> Sync List
          </button>
          <button 
            className="btn btn-ghost border-blue-500/30 text-blue-400 hover:bg-blue-500/10 disabled:opacity-50"
            onClick={handleBulkSyncLeads}
            disabled={isSyncing}
          >
            <Zap className="w-4 h-4 mr-2" /> Bulk Sync Leads
          </button>
          <button className="btn btn-primary px-6 shadow-blue-500/20" onClick={() => setShowAddModal(true)}>
            <Plus className="w-5 h-5 mr-2" /> Add Office
          </button>
        </div>
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
                {offices.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
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

      <div className="bg-slate-800/20 border border-white/10 rounded-2xl p-4 mb-8 flex items-center gap-4">
        <Search className="w-5 h-5 text-slate-500 ml-2" />
        <input 
          type="text" 
          placeholder="Search by office name or location..." 
          className="flex-1 bg-transparent border-none outline-none text-white text-sm"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <button className="btn btn-primary px-6 py-2 text-xs">Search</button>
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
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {offices.map((office) => (
            <div 
              key={office.id} 
              onClick={() => navigate(`/dashboard/family-offices/${office.id}`)}
              className="card bg-slate-800/40 border-white/5 hover:border-blue-500/30 transition-all p-6 group cursor-pointer relative overflow-hidden backdrop-blur-sm"
            >
              <div className="flex justify-between items-start mb-6">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-xl shadow-lg shadow-blue-500/20 group-hover:scale-110 transition-transform">
                  {office.name?.substring(0, 2).toUpperCase()}
                </div>
                <span className={`px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${getFitClass(office.strategic_fit)}`}>
                  {office.strategic_fit || 'N/A Fit'}
                </span>
              </div>
              
              <div className="mb-6">
                <h3 className="text-white font-black text-lg leading-tight mb-2 group-hover:text-blue-400 transition-colors">{office.name}</h3>
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
                  <MapPin className="w-3.5 h-3.5 text-blue-500" /> {office.location || 'Global Operations'}
                </div>
                <div className="flex items-center gap-2 text-slate-400 text-xs font-medium mt-1">
                  <Building2 className="w-3.5 h-3.5 text-indigo-500" /> {office.category || 'Uncategorized'}
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 mt-auto pt-6 border-t border-white/5">
                <div className="flex flex-col">
                  <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-1 leading-none">Total Leads</span>
                  <div className="text-lg font-black text-white">{office.count || 0}</div>
                </div>
                <div className="flex flex-col text-right">
                  <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-1 leading-none">Last Synced</span>
                  <div className="text-xs font-bold text-slate-400 mt-1 uppercase">
                    {office.last_synced ? new Date(office.last_synced).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : 'Never'}
                  </div>
                </div>
              </div>
              
              <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <ExternalLink className="w-4 h-4 text-slate-500" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FamilyOffices;
