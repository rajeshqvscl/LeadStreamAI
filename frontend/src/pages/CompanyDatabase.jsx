import React, { useState, useEffect } from 'react';
import { Search, Building2, Globe, Users, Target, Lock, Loader2, Sparkles, AlertCircle, CheckCircle2 } from 'lucide-react';
import api from '../services/api';

const CompanyDatabase = () => {
  const [companies, setCompanies] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [accessDenied, setAccessDenied] = useState(false);
  const [requestSent, setRequestSent] = useState(false);
  const [search, setSearch] = useState('');

  const fetchCompanies = async () => {
    setIsLoading(true);
    try {
      const response = await api.get('/api/companies');
      if (response.data.access_denied) {
        setAccessDenied(true);
      } else {
        setCompanies(response.data.companies || []);
        setAccessDenied(false);
      }
    } catch (err) {
      console.error('Failed to fetch companies', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  const handleRequestAccess = async () => {
    try {
      await api.post('/api/companies/request-access');
      setRequestSent(true);
    } catch (err) {
      alert('Failed to send request');
    }
  };

  const filteredCompanies = companies.filter(c => 
    Object.values(c).some(val => 
      String(val).toLowerCase().includes(search.toLowerCase())
    )
  );

  const headers = companies.length > 0 ? Object.keys(companies[0]) : [];

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh]">
        <Loader2 className="w-12 h-12 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-400 font-black tracking-[4px] uppercase text-[10px]">Syncing Drive Intelligence...</p>
      </div>
    );
  }

  if (accessDenied) {
    return (
      <div className="flex items-center justify-center min-h-[70vh] px-4">
        <div className="card max-w-lg w-full bg-[#131722]/80 border-white/5 backdrop-blur-2xl p-10 text-center shadow-2xl relative overflow-hidden group">
          <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 via-transparent to-purple-500/10 pointer-events-none"></div>
          <div className="w-20 h-20 bg-blue-500/10 rounded-3xl flex items-center justify-center mx-auto mb-8 group-hover:scale-110 transition-transform">
             <Lock className="w-10 h-10 text-blue-500" />
          </div>
          <h2 className="text-[28px] font-black text-white mb-4 tracking-tight">Access Restricted</h2>
          <p className="text-slate-400 text-sm leading-relaxed mb-10 uppercase font-bold tracking-tighter">
            The Company Intelligence Database contains privileged global data. Access requires administrative clearance or enterprise approval.
          </p>
          
          {requestSent ? (
            <div className="flex items-center justify-center gap-3 py-4 px-6 bg-emerald-500/10 border border-emerald-500/20 rounded-2xl text-emerald-500">
               <CheckCircle2 className="w-5 h-5" />
               <span className="font-black text-xs uppercase tracking-widest">Request Transmitted</span>
            </div>
          ) : (
            <button 
              onClick={handleRequestAccess}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-4 rounded-2xl text-[11px] uppercase tracking-[3px] transition-all shadow-xl shadow-blue-500/20 active:scale-95"
            >
              Request System Access
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-700">
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 mb-10">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[9px] font-black text-blue-500 uppercase tracking-widest">External Drive Sync</div>
            <Sparkles className="w-4 h-4 text-amber-500" />
          </div>
          <h1 className="text-3xl font-black text-white tracking-tight">Company <span className="bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent italic">Intel</span></h1>
          <p className="text-slate-500 text-xs font-bold uppercase tracking-[2px] mt-2">Static Archive • Sourced from Google Drive</p>
        </div>

        <div className="relative w-full lg:w-96">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text"
            placeholder="Search Global Sheet..."
            className="w-full bg-[#131722] border border-white/10 rounded-2xl py-3.5 pl-12 pr-4 text-white text-sm focus:outline-none focus:border-blue-500/50 transition-all font-medium placeholder:text-slate-700 shadow-xl"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl">
        <div className="overflow-x-auto custom-scrollbar">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-white/[0.02] border-b border-white/5">
                {headers.map((header) => (
                  <th key={header} className="px-6 py-5 text-[10px] font-black text-slate-500 uppercase tracking-[2px] whitespace-nowrap">
                    {header.replace(/_/g, ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.03]">
              {filteredCompanies.map((company, i) => (
                <tr key={i} className="hover:bg-blue-500/[0.02] transition-colors group">
                  {headers.map((header) => (
                    <td key={header} className="px-6 py-4 text-sm font-medium text-slate-300 group-hover:text-white transition-colors">
                      {company[header] || '-'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {filteredCompanies.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
           <AlertCircle className="w-12 h-12 text-slate-800 mb-4" />
           <p className="text-slate-600 font-black uppercase tracking-[4px] text-xs">No records found in drive archive</p>
        </div>
      )}
    </div>
  );
};

export default CompanyDatabase;
