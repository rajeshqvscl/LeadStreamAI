import React, { useState, useEffect } from 'react';
import api from '../services/api';

const RocketReach = () => {
  const [query, setQuery] = useState({ name: '', title: '', company: '', location: '', industry: '' });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [creditStats, setCreditStats] = useState({ used: 0, remaining: 2400 });
  const [selectedLeads, setSelectedLeads] = useState([]);
  const [addingLeads, setAddingLeads] = useState({});
  const [successMessage, setSuccessMessage] = useState('');
  const [page, setPage] = useState(1);
  const [totalResults, setTotalResults] = useState(0);
  const user = JSON.parse(localStorage.getItem('user') || '{}');

  useEffect(() => {
    fetchCreditStats();
  }, []);

  const fetchCreditStats = async () => {
    try {
      const { data } = await api.get('/api/rocketreach/credits');
      if (data) setCreditStats(data);
    } catch (e) {
      // Credits not critical
    }
  };

  const handleSearch = async (e, newPage = 1) => {
    if (e) e.preventDefault();
    if (!query.name && !query.title && !query.company && !query.industry && !query.location) {
      setError('Please fill at least one search field.');
      return;
    }
    setLoading(true);
    setError('');
    setSelectedLeads([]);
    setPage(newPage);
    try {
      const params = { page: newPage, ...query };
      const { data } = await api.get('/api/rocketreach/search', { params });
      setResults(data.profiles || []);
      setTotalResults(data.total || data.profiles?.length || 0);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Search failed. Check your API key.');
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(totalResults / 50);
  const hasNext = page < totalPages;
  const hasPrev = page > 1;

  const handleAddToLeads = async (profile) => {
    setAddingLeads(prev => ({ ...prev, [profile.id]: true }));
    try {
      await api.post('/api/rocketreach/add-lead', {
        rr_id: profile.id,
        first_name: profile.first_name || (profile.name || '').split(' ')[0],
        last_name: profile.last_name || (profile.name || '').split(' ').slice(1).join(' '),
        email: profile.email || profile.current_work_email || '',
        company_name: profile.current_employer || '',
        persona: profile.current_title || 'UNKNOWN',
        validation_status: 'VALID',
      });
      setSuccessMessage(`✅ ${profile.name} added to Lead Pipeline!`);
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to add lead.');
    } finally {
      setAddingLeads(prev => ({ ...prev, [profile.id]: false }));
    }
  };

  const handleAddSelected = async () => {
    for (const profile of selectedLeads) {
      await handleAddToLeads(profile);
    }
    setSelectedLeads([]);
  };

  const toggleSelect = (profile) => {
    setSelectedLeads(prev =>
      prev.find(p => p.id === profile.id)
        ? prev.filter(p => p.id !== profile.id)
        : [...prev, profile]
    );
  };

  const creditPct = Math.round((creditStats.used / 2400) * 100);

  return (
    <div className="min-h-screen text-slate-100">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-rose-600 flex items-center justify-center text-2xl shadow-lg shadow-orange-500/20">🚀</div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight">RocketReach Discovery</h1>
            <p className="text-slate-500 text-sm">Free unlimited lookups — Export credits used only when fetching emails</p>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-[#0e121d] border border-white/5 rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Free Lookups</div>
          <div className="text-2xl font-black text-white">∞</div>
          <div className="text-xs text-emerald-400 font-semibold mt-1">Unlimited</div>
        </div>
        <div className="bg-[#0e121d] border border-white/5 rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Export Credits</div>
          <div className="text-2xl font-black text-white">{(2400 - creditStats.used).toLocaleString()}</div>
          <div className="text-xs text-slate-400 font-semibold mt-1">of 2,400 remaining</div>
          <div className="mt-2 h-1 bg-slate-800 rounded-full overflow-hidden">
            <div className="h-full bg-gradient-to-r from-orange-500 to-rose-500 rounded-full transition-all" style={{ width: `${creditPct}%` }}></div>
          </div>
        </div>
        <div className="bg-[#0e121d] border border-white/5 rounded-xl p-4">
          <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-1">Results Found</div>
          <div className="text-2xl font-black text-white">{totalResults.toLocaleString()}</div>
          <div className="text-xs text-slate-400 font-semibold mt-1">from current search</div>
        </div>
      </div>

      {/* Search Panel */}
      <div className="bg-[#0e121d] border border-white/5 rounded-2xl p-6 mb-6">
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500 mb-4">🔍 Search Parameters (All Free, No Credits)</div>
        <form onSubmit={handleSearch} className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {[
            { key: 'name', label: 'Full Name', placeholder: 'e.g. John Smith', icon: '👤' },
            { key: 'title', label: 'Job Title', placeholder: 'e.g. CEO, CTO, Procurement', icon: '💼' },
            { key: 'company', label: 'Company', placeholder: 'e.g. Tata, Infosys', icon: '🏢' },
            { key: 'industry', label: 'Industry', placeholder: 'e.g. Financial Services', icon: '📊' },
            { key: 'location', label: 'Location', placeholder: 'e.g. Mumbai, Delhi', icon: '📍' },
          ].map(({ key, label, placeholder, icon }) => (
            <div key={key}>
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">{label}</label>
              <div className="flex items-center gap-2 bg-[#111521] border border-white/5 rounded-lg px-3 py-2 focus-within:border-orange-500/50 transition-all">
                <span className="text-sm">{icon}</span>
                <input
                  type="text"
                  placeholder={placeholder}
                  value={query[key]}
                  onChange={e => setQuery(prev => ({ ...prev, [key]: e.target.value }))}
                  className="bg-transparent text-[13px] text-slate-200 w-full outline-none placeholder:text-slate-600"
                />
              </div>
            </div>
          ))}
          <div className="flex items-end">
            <button
              type="submit"
              disabled={loading}
              className="w-full h-[42px] bg-gradient-to-r from-orange-500 to-rose-600 hover:from-orange-400 hover:to-rose-500 text-white font-bold text-sm rounded-lg transition-all shadow-lg shadow-orange-500/20 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer flex items-center justify-center gap-2"
            >
              {loading ? (
                <><div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div> Searching...</>
              ) : (
                <><span>🔎</span> Search Free</>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Messages */}
      {error && (
        <div className="mb-4 bg-rose-500/10 border border-rose-500/20 rounded-xl px-4 py-3 text-rose-400 text-sm font-medium">{error}</div>
      )}
      {successMessage && (
        <div className="mb-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl px-4 py-3 text-emerald-400 text-sm font-bold">{successMessage}</div>
      )}

      {/* Bulk Action Bar */}
      {selectedLeads.length > 0 && (
        <div className="mb-4 bg-orange-500/10 border border-orange-500/30 rounded-xl px-4 py-3 flex items-center justify-between">
          <span className="text-orange-300 font-bold text-sm">{selectedLeads.length} leads selected</span>
          <button
            onClick={handleAddSelected}
            className="bg-gradient-to-r from-orange-500 to-rose-600 text-white text-sm font-bold px-5 py-2 rounded-lg hover:opacity-90 transition-all cursor-pointer"
          >
            ➕ Add All to Pipeline
          </button>
        </div>
      )}

      {/* Results Table */}
      {results.length > 0 && (
        <div className="bg-[#0e121d] border border-white/5 rounded-2xl overflow-hidden">
          <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
            <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
              Showing {results.length} of {totalResults.toLocaleString()} results — Page {page} of {Math.max(1, Math.ceil(totalResults / 50))}
            </div>
            <button
              onClick={() => {
                if (selectedLeads.length === results.length) setSelectedLeads([]);
                else setSelectedLeads(results);
              }}
              className="text-xs text-orange-400 font-bold hover:text-orange-300 transition-colors cursor-pointer"
            >
              {selectedLeads.length === results.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-[#111521] text-[10px] font-bold uppercase tracking-widest text-slate-500">
                  <th className="px-4 py-3 text-left w-8"></th>
                  <th className="px-4 py-3 text-left">Name</th>
                  <th className="px-4 py-3 text-left">Title</th>
                  <th className="px-4 py-3 text-left">Company</th>
                  <th className="px-4 py-3 text-left">Location</th>
                  <th className="px-4 py-3 text-left">LinkedIn</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {results.map((profile, idx) => {
                  const isSelected = selectedLeads.find(p => p.id === profile.id);
                  return (
                    <tr
                      key={profile.id || idx}
                      className={`border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors ${isSelected ? 'bg-orange-500/5' : ''}`}
                    >
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={!!isSelected}
                          onChange={() => toggleSelect(profile)}
                          className="w-4 h-4 rounded accent-orange-500 cursor-pointer"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          {profile.profile_pic ? (
                            <img src={profile.profile_pic} alt={profile.name} className="w-8 h-8 rounded-full object-cover" onError={e => e.target.style.display='none'} />
                          ) : (
                            <div className="w-8 h-8 rounded-full bg-gradient-to-br from-orange-500 to-rose-600 flex items-center justify-center text-xs font-bold text-white">
                              {(profile.name || 'NA')[0]}
                            </div>
                          )}
                          <div>
                            <div className="text-sm font-semibold text-white">{profile.name || '—'}</div>
                            <div className="text-xs text-slate-500">{profile.email || profile.current_work_email || 'Email via export'}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-300">{profile.current_title || '—'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-300">{profile.current_employer || '—'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-slate-500">{profile.city || profile.location || '—'}</span>
                      </td>
                      <td className="px-4 py-3">
                        {profile.linkedin_url ? (
                          <a href={profile.linkedin_url} target="_blank" rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300 font-medium transition-colors">
                            View →
                          </a>
                        ) : <span className="text-xs text-slate-600">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleAddToLeads(profile)}
                          disabled={addingLeads[profile.id]}
                          className="text-xs font-bold px-3 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                        >
                          {addingLeads[profile.id] ? '...' : '➕ Add to Pipeline'}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between px-6 py-4 border-t border-white/5">
            <div className="text-xs text-slate-500">
              Page <span className="text-white font-bold">{page}</span> of <span className="text-white font-bold">{Math.max(1, Math.ceil(totalResults / 50))}</span>
              <span className="mx-2 text-slate-700">·</span>
              <span className="text-slate-400">{totalResults.toLocaleString()} total results</span>
            </div>
            <div className="flex gap-2">
              <button
                onClick={(e) => handleSearch(e, page - 1)}
                disabled={page <= 1 || loading}
                className="text-xs px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-slate-400 hover:bg-white/10 hover:text-white disabled:opacity-30 font-bold transition-all flex items-center gap-1.5"
              >
                ← Prev
              </button>
              <span className="text-xs px-4 py-2 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400 font-black">
                {page}
              </span>
              <button
                onClick={(e) => handleSearch(e, page + 1)}
                disabled={!hasNext || loading}
                className="text-xs px-4 py-2 rounded-lg bg-white/5 border border-white/5 text-slate-400 hover:bg-white/10 hover:text-white disabled:opacity-30 font-bold transition-all flex items-center gap-1.5"
              >
                Next →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && results.length === 0 && (
        <div className="text-center py-20">
          <div className="text-6xl mb-4">🚀</div>
          <div className="text-white font-bold text-xl mb-2">Find Your Next Lead</div>
          <div className="text-slate-500 text-sm max-w-md mx-auto">
            Enter any combination of name, title, company, industry, or location above. All searches are free with your unlimited lookup plan. Export credits are only used when you fetch verified email addresses.
          </div>
        </div>
      )}
    </div>
  );
};

export default RocketReach;
