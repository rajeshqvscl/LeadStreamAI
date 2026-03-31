import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  ArrowLeft, MapPin, Building2, BarChart, RefreshCw, Zap, 
  ExternalLink, Loader2, Users, Search, Filter, Mail, Phone,
  ChevronRight, Globe, Info, Plus
} from 'lucide-react';
import api from '../services/api';

const FamilyOfficeDetail = () => {
  const { officeId } = useParams();
  const navigate = useNavigate();
  const [office, setOffice] = useState(null);
  const [leads, setLeads] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isExtracting, setIsExtracting] = useState(false);
  
  // Discovery Engine Form State
  const [jobTitle, setJobTitle] = useState('');
  const [location, setLocation] = useState('');
  const [keywords, setKeywords] = useState('');
  const [limit, setLimit] = useState(5);
  const [isSaving, setIsSaving] = useState(false);

  const fetchOfficeData = async () => {
    setIsLoading(true);
    try {
      const officeRes = await api.get(`/api/family-offices/${officeId}`);
      const officeData = officeRes.data;
      setOffice(officeData);
      
      // Initialize location if not already set by user
      if (officeData.location && !location) {
        setLocation(officeData.location);
      }
      
      const leadsRes = await api.get(`/api/family-offices/${officeId}/leads`);
      setLeads(leadsRes.data || []);
    } catch (err) {
      console.error('Failed to fetch office details', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Reset form state when changing offices
    setJobTitle('');
    setLocation('');
    setKeywords('');
    setLimit(5);
    fetchOfficeData();
  }, [officeId]);

  const handleUpdateProfile = async () => {
    setIsSaving(true);
    try {
      await api.patch(`/api/family-offices/${officeId}`, {
        location: location
      });
      // Refresh to get updated data
      fetchOfficeData();
    } catch (err) {
      console.error('Failed to update office profile', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleExtractLeads = async () => {
    setIsExtracting(true);
    try {
      await api.post(`/api/family-offices/${officeId}/rocketreach`, {
        job_title: jobTitle,
        location: location,
        keywords: keywords,
        limit: parseInt(limit)
      });
      fetchOfficeData();
    } catch (err) {
      console.error('Failed to extract leads', err);
    } finally {
      setIsExtracting(false);
    }
  };

  const getFitClass = (fit) => {
    // If it's N/A, make it green as per screenshot, or based on score
    const score = parseInt(fit) || 0;
    if (score >= 80 || fit?.toLowerCase().includes('high') || fit === 'N/A') return 'text-green-500 border-green-500/20 bg-green-500/10';
    if (score >= 50 || fit?.toLowerCase().includes('med')) return 'text-amber-500 border-amber-500/20 bg-amber-500/10';
    return 'text-slate-500 border-slate-500/20 bg-slate-500/10';
  };

  if (isLoading && !office) {
    return (
      <div className="py-32 flex flex-col items-center justify-center">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-medium">Loading office profile...</p>
      </div>
    );
  }

  if (!office) {
    return (
      <div className="py-32 text-center">
        <h2 className="text-white text-xl font-bold mb-4">Office Not Found</h2>
        <button className="btn btn-primary" onClick={() => navigate('/dashboard/family-offices')}>
          Back to Offices
        </button>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-700">
      {/* Breadcrumb */}
      <div className="mb-8">
        <button 
          onClick={() => navigate('/dashboard/family-offices')}
          className="flex items-center text-blue-400 hover:text-blue-300 text-sm font-bold transition-colors group"
        >
          <ArrowLeft className="w-4 h-4 mr-2 group-hover:-translate-x-1 transition-transform" />
          Back to Offices
        </button>
      </div>

      {/* Header Profile Section */}
      <div className="bg-slate-900/40 border border-white/5 rounded-[32px] p-8 mb-8 relative overflow-hidden backdrop-blur-sm">
        <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/5 blur-[100px] rounded-full pointer-events-none"></div>
        
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 mb-12">
          <div className="flex items-center gap-6">
            <div className="w-20 h-20 rounded-3xl bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center text-white font-black text-3xl shadow-2xl shadow-blue-500/30">
              {(office.name?.substring(0, 2) || 'FO').toUpperCase()}
            </div>
            <div>
              <h1 className="text-4xl font-black text-white tracking-tight mb-2">{office.name}</h1>
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5 text-green-500 text-xs font-bold">
                  Office Profile
                </span>
                <span className="w-1 h-1 rounded-full bg-slate-700"></span>
                <span className="flex items-center gap-1.5 text-slate-500 text-sm">
                  {office.location || 'Global'}
                </span>
              </div>
            </div>
          </div>
          
          <div className="text-right">
            <div className="text-[10px] font-black text-slate-500 uppercase tracking-[3px] mb-2 mr-1">STRATEGIC FIT</div>
            <div className={`px-6 py-2 rounded-2xl border text-3xl font-black text-center ${getFitClass(office.strategic_fit)}`}>
              {office.strategic_fit || 'N/A'}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 pt-8 border-t border-white/5">
          <div className="space-y-1">
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest leading-none">CATEGORY / SECTOR</div>
            <div className="text-white font-bold text-sm truncate">{office.category || 'Uncategorized'}</div>
          </div>
          <div className="space-y-1">
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest leading-none">PORTFOLIO LEADS</div>
            <div className="text-white font-bold text-sm">{office.count || 0} Contacts</div>
          </div>
          <div className="space-y-1">
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest leading-none">HQ LOCATION</div>
            <div className="text-white font-bold text-sm">{office.location || 'Mumbai'}</div>
          </div>
          <div className="space-y-1">
            <div className="text-[10px] font-black text-slate-600 uppercase tracking-widest leading-none">LAST DATABASE SYNC</div>
            <div className="text-white font-bold text-sm">
              {office.last_synced ? new Date(office.last_synced).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : 'March 15, 2026'}
            </div>
          </div>
        </div>
      </div>

      {/* Discovery Engine Section */}
      <div className="bg-slate-900/40 border border-white/5 rounded-[32px] p-8 mb-12 overflow-hidden relative">
        <div className="flex justify-between items-center mb-8">
          <h3 className="text-white font-bold text-lg flex items-center gap-3">
            <Zap className="w-5 h-5 text-amber-500 fill-amber-500" />
            Discovery Engine: <span className="text-blue-500">{office.name}</span>
          </h3>
          <span className="text-[10px] font-black text-slate-600 uppercase tracking-[2px]">TARGET OFFICE EXTRACTION</span>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-blue-500 uppercase tracking-widest ml-1">JOB TITLE PATTERNS</label>
            <input 
              type="text" 
              placeholder="e.g. Portfolio Manager, CIO, Principal, Director" 
              className="w-full bg-slate-950/40 border border-white/10 rounded-xl py-2.5 px-4 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-indigo-500 uppercase tracking-widest ml-1">LOOKUP ENTITY</label>
            <input 
              type="text" 
              readOnly
              value={office.name}
              className="w-full bg-slate-950/40 border border-white/10 rounded-xl py-2.5 px-4 text-xs text-white focus:outline-none" 
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">SEARCH KEYWORDS</label>
            <input 
              type="text" 
              placeholder={`e.g. ${office.name}, Investment`} 
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              className="w-full bg-slate-950/40 border border-white/10 rounded-xl py-2.5 px-4 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50" 
            />
          </div>
          <div className="space-y-1.5 relative">
            <div className="flex justify-between items-center mb-0.5">
              <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest ml-1">FOCUS LOCATION</label>
              <button 
                onClick={handleUpdateProfile}
                disabled={isSaving || location === office.location}
                className="text-[9px] font-black text-blue-400 hover:text-blue-300 uppercase tracking-tighter disabled:opacity-0 transition-opacity"
              >
                {isSaving ? 'Saving...' : 'Save to Profile'}
              </button>
            </div>
            <input 
              type="text" 
              placeholder="City, Country"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full bg-slate-950/40 border border-white/10 rounded-xl py-2.5 px-4 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-blue-500/50" 
            />
          </div>
        </div>
        
        <div className="mt-8 pt-6 border-t border-white/5 flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            <div>
              <span className="text-[11px] font-bold text-white uppercase tracking-tight block">Engine Optimized</span>
              <span className="text-[10px] text-slate-600">Tip: If 0 results, try moving the name to Search Keywords or removing Lookup Entity.</span>
            </div>
          </div>
          <button 
            onClick={handleExtractLeads}
            disabled={isExtracting}
            className="btn btn-primary px-10 py-2.5 rounded-xl shadow-blue-500/20 disabled:opacity-50"
          >
            {isExtracting ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Finding...
              </>
            ) : (
              'Find Office Leads'
            )}
          </button>
        </div>
      </div>

      {/* Associated Leads Section */}
      <h2 className="text-xl font-black text-white mb-1">Associated Portfolio Contacts</h2>
      <p className="text-slate-500 text-sm mb-8">Verified leads linked to this institution.</p>

      {leads.length === 0 ? (
        <div className="bg-slate-900/40 border border-dashed border-white/10 rounded-[32px] py-24 flex flex-col items-center justify-center">
          <p className="text-slate-500 font-medium mb-6 text-center">No contacts linked to this office yet.</p>
          <button className="btn btn-ghost border-white/5 text-slate-400 flex items-center gap-2">
            <Plus className="w-4 h-4" /> Link Lead
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {leads.map((lead) => (
            <div 
              key={lead.id} 
              onClick={() => navigate(`/dashboard/leads/${lead.id}`)}
              className="bg-slate-800/20 border border-white/5 hover:border-blue-500/30 rounded-[24px] p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 transition-all group cursor-pointer"
            >
              <div className="flex items-center gap-5">
                <div className="w-14 h-14 rounded-2xl bg-slate-800 border border-white/5 flex items-center justify-center text-blue-400 font-bold text-xl group-hover:bg-blue-500/10 transition-colors">
                  {lead.first_name?.[0]}{lead.last_name?.[0]}
                </div>
                <div>
                  <h4 className="text-white font-bold text-lg group-hover:text-blue-400 transition-colors">
                    {lead.first_name} {lead.last_name}
                  </h4>
                  <div className="flex items-center gap-3 text-slate-500 text-sm">
                    <span className="text-indigo-400 font-medium">{lead.designation || 'Executive'}</span>
                    <span className="w-1 h-1 rounded-full bg-slate-700"></span>
                    <span className="flex items-center gap-1.5"><MapPin className="w-3 h-3" /> {lead.city || 'Location N/A'}</span>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-3">
                  <button className="p-3 rounded-xl bg-slate-800 border border-white/5 text-slate-400 hover:text-white hover:border-blue-500/30 transition-all">
                    <Mail className="w-4 h-4" />
                  </button>
                  <button className="p-3 rounded-xl bg-slate-800 border border-white/5 text-slate-400 hover:text-white hover:border-blue-500/30 transition-all">
                    <ExternalLink className="w-4 h-4" />
                  </button>
                </div>
                <div className="flex flex-col items-end min-w-[100px]">
                  <span className="text-[10px] font-black text-slate-600 uppercase tracking-widest mb-1">Fit Score</span>
                  <div className="text-blue-500 font-black text-xl italic">{lead.fit_score || '0'}</div>
                </div>
                <ChevronRight className="w-6 h-6 text-slate-700 group-hover:text-blue-500 transition-all group-hover:translate-x-1" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default FamilyOfficeDetail;
