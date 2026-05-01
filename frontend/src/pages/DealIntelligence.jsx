import React, { useState, useEffect } from 'react';
import api from '../services/api';
import ReactMarkdown from 'react-markdown';
import { 
  Brain, FileText, Sparkles, Clock, RefreshCw, 
  ChevronRight, Inbox as InboxIcon, Calendar, 
  Search, Bell, User, Copy, CheckCircle2, 
  Layout, Cloud, Library, Settings as SettingsIcon,
  TrendingUp, ShieldAlert, Target, DollarSign,
  ArrowUpRight, Info, MoreHorizontal, Zap,
  BarChart3, Activity, Layers, MessageSquare
} from 'lucide-react';

const DealIntelligence = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDealId, setSelectedDealId] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [showSuccessPulse, setShowSuccessPulse] = useState(false);
  const [page, setPage] = useState(1);
  const [totalDeals, setTotalDeals] = useState(0);
  const perPage = 10;

  const fetchDeals = async () => {
    try {
      const { data } = await api.get(`/api/gmail/inbound-deals?page=${page}&per_page=${perPage}`);
      const ragDeals = data.leads || [];
      setDeals(ragDeals);
      setTotalDeals(data.total || 0);
      
      if (ragDeals.length > 0 && !selectedDealId) {
        setSelectedDealId(ragDeals[0].id);
      }
      setLoading(false);
    } catch (err) {
      console.error('Error fetching RAG deals:', err);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDeals();
  }, [page]);

  const selectedDeal = deals.find(d => d.id === selectedDealId);
  const ragIntel = selectedDeal?.rag_intelligence || {};
  
  // LOGIC FIX: Ensure we find the score anywhere it might be hiding
  const displayScore = ragIntel.sentiment_score || ragIntel.score || selectedDeal?.sentiment_score || 0;
  const formattedScore = typeof displayScore === 'number' ? displayScore.toFixed(2) : displayScore;

  const handleAnalyze = async () => {
    if (!selectedDealId) return;
    setIsAnalyzing(true);
    try {
      await api.post(`/api/intelligence/analyze-lead/${selectedDealId}`);
      await fetchDeals();
    } catch (err) {
      console.error('Analysis failed', err);
    } finally {
      // Keep overlay visible for a brief moment for effect
      setTimeout(() => setIsAnalyzing(false), 800);
    }
  };

  const ProcessingOverlay = ({ title, subtext }) => (
    <div className="fixed inset-0 z-[9999] bg-[#05070a]/80 backdrop-blur-md flex items-center justify-center animate-in fade-in duration-300">
      <div className="bg-[#0f172a] border border-indigo-500/30 p-10 rounded-[32px] flex flex-col items-center shadow-2xl">
        <RefreshCw className="w-12 h-12 text-indigo-500 animate-spin mb-6" />
        <h2 className="text-white text-xl font-black uppercase tracking-widest mb-2">{title || "Refreshing"}</h2>
        <p className="text-slate-500 text-[10px] font-black uppercase tracking-[0.3em]">{subtext || "Syncing with RAG Engine..."}</p>
      </div>
    </div>
  );

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await api.post('/api/gmail/sync-inbound');
      await fetchDeals();
      setShowSuccessPulse(true);
      setTimeout(() => setShowSuccessPulse(false), 2000);
    } catch (err) {
      console.error('Sync failed', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleCopy = () => {
    const text = ragIntel.answer || selectedDeal?.rag_advice || '';
    navigator.clipboard.writeText(text);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const getSections = (text) => {
    if (!text) return [];
    const sections = text.split(/(?=### )/);
    return sections.map(s => {
        const lines = s.trim().split('\n');
        const title = lines[0].replace('### ', '').trim();
        const content = lines.slice(1).join('\n').trim();
        return { title, content };
    });
  };

  const sections = getSections(selectedDeal?.rag_advice);

  if (loading) return (
    <div className="h-screen bg-[#05070a] flex flex-col items-center justify-center">
      <Brain className="w-10 h-10 text-indigo-500 mb-4 animate-pulse" />
      <div className="text-[9px] font-black text-slate-500 uppercase tracking-[0.4em]">Calibrating...</div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[#05070a] text-slate-200 font-inter overflow-hidden">
      {isSyncing && (
        <ProcessingOverlay 
          title="Refreshing Intelligence"
          subtext="Syncing Inbound Stream with RAG"
        />
      )}

      {isAnalyzing && (
        <ProcessingOverlay 
          title="Analyzing forensic Data"
          subtext={`Deep-Dive into ${selectedDeal?.first_name || 'Lead'} Intelligence`}
        />
      )}
      <div className="h-[calc(100vh-20px)] bg-[#05070a] text-slate-400 font-sans flex overflow-hidden rounded-[32px] border border-white/5 m-2 shadow-2xl">
      
      {/* SLIM LEFT RAIL (Optimized for 100% zoom) */}
      <div className="w-56 border-r border-white/5 flex flex-col bg-[#080b14] shrink-0">
        <div className="p-5 border-b border-white/5">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-7 h-7 bg-indigo-600 rounded-lg flex items-center justify-center font-black text-white italic shadow-lg shadow-indigo-500/20 text-xs">F</div>
            <h1 className="text-sm font-black text-white tracking-tighter uppercase">FinRAG <span className="text-indigo-500 text-[9px] ml-0.5">4.6</span></h1>
          </div>
          
          <button className="w-full flex items-center gap-3 px-4 py-3 bg-indigo-600/10 text-indigo-400 rounded-xl border border-indigo-500/20 text-[10px] font-black uppercase tracking-widest">
            <Layout className="w-3.5 h-3.5" /> Revert
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 custom-scrollbar">
          <div className="text-[8px] font-black text-slate-700 uppercase tracking-widest mb-4 px-1">Inbound Stream</div>
          <div className="space-y-2">
            {deals.map(deal => (
                <div 
                  key={deal.id}
                  onClick={() => setSelectedDealId(deal.id)}
                  className={`
                    p-5 rounded-[24px] cursor-pointer transition-all duration-300 border mb-4
                    ${selectedDealId === deal.id 
                      ? 'bg-indigo-600/20 border-indigo-500/50 shadow-[0_0_20px_rgba(79,70,229,0.15)] scale-[1.02]' 
                      : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.05] hover:border-white/10 hover:scale-[1.01]'
                    }
                  `}
                >
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-[12px] font-black text-white truncate max-w-[120px]">
                      {deal.company_name || `${deal.first_name}`}
                    </h3>
                    <span className="text-[9px] font-black text-slate-500 uppercase">{deal.updated_at ? new Date(deal.updated_at).toLocaleDateString() : ''}</span>
                  </div>
                  <p className="text-[10px] text-slate-500 truncate mb-3">{deal.email}</p>
                  
                  <div className="flex items-center gap-2">
                    <span className={`px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${
                      deal.reply_intent === 'MEETING_REQUESTED' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                      deal.reply_intent === 'INTERESTED' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
                      'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    }`}>
                      {deal.reply_intent || 'New Revert'}
                    </span>
                  </div>
                </div>
            ))}
          </div>

          {/* Pagination Controls */}
          {totalDeals > perPage && (
            <div className="mt-6 flex items-center justify-between px-2 py-4 border-t border-white/5">
              <button 
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
                className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors disabled:opacity-30 disabled:hover:text-slate-500"
              >
                <ChevronRight className="w-3 h-3 rotate-180" /> Prev
              </button>
              <div className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em]">
                Page {page} of {Math.ceil(totalDeals / perPage)}
              </div>
              <button 
                onClick={() => setPage(p => p + 1)}
                disabled={page >= Math.ceil(totalDeals / perPage)}
                className="flex items-center gap-2 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors disabled:opacity-30 disabled:hover:text-slate-500"
              >
                Next <ChevronRight className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 bg-[#05070a]">
        
        {/* TOP BAR (Compact) */}
        <header className="flex items-center justify-between px-8 py-5 border-b border-white/5 bg-[#0b0f1a]/80 backdrop-blur-xl sticky top-0 z-50">
          {showSuccessPulse && (
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
               <div className="absolute inset-0 bg-indigo-500/5 animate-pulse-slow"></div>
               <div className="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-indigo-500 to-transparent animate-scan-line"></div>
            </div>
          )}
          <div className="relative w-72 group">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-600" />
            <input 
              type="text" 
              placeholder="Search Intelligence..." 
              className="w-full bg-white/5 border border-white/10 rounded-full py-2 pl-10 pr-4 text-[11px] focus:outline-none placeholder:text-slate-700"
            />
          </div>
          <div className="flex items-center gap-6">
            <button 
              onClick={handleSync}
              disabled={isSyncing}
              className={`
                flex items-center gap-2.5 px-5 py-2.5 rounded-full transition-all duration-500 group relative overflow-hidden
                ${isSyncing 
                  ? 'bg-indigo-500/20 border-indigo-500/40 cursor-wait' 
                  : 'bg-indigo-500/10 border border-indigo-500/20 hover:bg-indigo-500/20 hover:border-indigo-500/40 cursor-pointer active:scale-95 shadow-[0_0_15px_rgba(99,102,241,0.1)] hover:shadow-[0_0_25px_rgba(99,102,241,0.2)]'
                }
              `}
            >
              {isSyncing && <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent animate-shimmer"></div>}
              <RefreshCw className={`w-3.5 h-3.5 text-indigo-400 group-hover:text-indigo-300 ${isSyncing ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-700'}`} />
              <span className="text-[11px] font-black text-indigo-400/90 uppercase tracking-widest leading-none">
                {isSyncing ? 'Scanning Inbox...' : 'Sync Inbox'}
              </span>
            </button>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse"></div>
              <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Stable</span>
            </div>
            <div className="w-8 h-8 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-[10px] font-black text-indigo-400">AA</div>
          </div>
        </header>

        {/* PANELS GRID (Optimized for space) */}
        <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-y-auto custom-scrollbar">
          
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl relative group">
              <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em] mb-6">Processor</h2>
              <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-white/5 rounded-3xl bg-white/[0.01]">
                <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <FileText className="w-6 h-6 text-indigo-500" />
                </div>
                <div className="text-[11px] font-bold text-white mb-6 text-center truncate max-w-xs">
                  {selectedDeal?.pitch_deck_url?.split('/').pop() || 'Awaiting Document...'}
                </div>
                <button 
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || !selectedDeal}
                  className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all disabled:opacity-50"
                >
                  {isAnalyzing ? 'Processing...' : 'Analyze Pitch Deck'}
                </button>
              </div>
            </section>

            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex-1 min-h-[400px]">
              <div className="flex justify-between items-center mb-8">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">Deep-Dive Analysis</h2>
                {selectedDeal?.rag_advice && <ShieldAlert className="w-4 h-4 text-amber-500/50" />}
              </div>

              <div className="memorandum-container bg-white/[0.01] border border-white/5 rounded-3xl p-8 min-h-[500px]">
                {selectedDeal?.rag_advice ? (
                  <div className="prose prose-invert max-w-none 
                    prose-h1:text-[18px] prose-h1:font-black prose-h1:uppercase prose-h1:tracking-[0.2em] prose-h1:text-white prose-h1:mb-8 prose-h1:border-b prose-h1:border-white/10 prose-h1:pb-4
                    prose-h2:text-[14px] prose-h2:font-black prose-h2:uppercase prose-h2:tracking-widest prose-h2:text-indigo-400 prose-h2:mt-10 prose-h2:mb-6
                    prose-p:text-[14px] prose-p:text-slate-300 prose-p:leading-relaxed prose-p:mb-6
                    prose-strong:text-white prose-strong:font-black
                    prose-ul:list-disc prose-ul:pl-6 prose-li:text-slate-400 prose-li:mb-2
                    ">
                    <ReactMarkdown>{selectedDeal.rag_advice}</ReactMarkdown>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 bg-white/[0.01] border border-dashed border-white/5 rounded-[32px]">
                    <div className="w-16 h-16 bg-white/5 rounded-2xl flex items-center justify-center mb-6 animate-pulse">
                        <Brain className="w-8 h-8 text-slate-700" />
                    </div>
                    <p className="text-[10px] font-black uppercase tracking-[0.3em] text-slate-500 mb-6">Awaiting RAG Core Intelligence</p>
                    <button 
                      onClick={handleAnalyze}
                      disabled={isAnalyzing}
                      className={`
                        px-10 py-4 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-black uppercase tracking-[0.2em] rounded-2xl transition-all duration-300 
                        shadow-[0_10px_25px_rgba(79,70,229,0.3)] hover:shadow-[0_15px_35px_rgba(79,70,229,0.4)] hover:-translate-y-1 active:translate-y-0.5
                        cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed group relative overflow-hidden
                      `}
                    >
                      {isAnalyzing && <div className="absolute inset-0 bg-white/10 animate-pulse"></div>}
                      <span className="flex items-center gap-3 relative z-10">
                        {isAnalyzing ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin text-white/80" />
                            <span>Processing Core...</span>
                          </>
                        ) : (
                          <>
                            <Zap className="w-4 h-4 text-amber-400 group-hover:scale-125 transition-transform" />
                            <span>Run Intelligence Scan</span>
                          </>
                        )}
                      </span>
                    </button>
                  </div>
                )}
              </div>
            </section>
          </div>

          <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex flex-col gap-8">
              <div className="flex justify-between items-center">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">Agent Intelligence</h2>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="text-[9px] font-black text-slate-700 uppercase tracking-widest mb-3 block">Intent</label>
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] font-black text-white uppercase">{ragIntel.category || selectedDeal?.reply_intent || 'PENDING'}</span>
                    <span className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[9px] font-black uppercase tracking-widest rounded-md">INTERESTED</span>
                  </div>
                </div>

                <div>
                  <label className="text-[9px] font-black text-slate-700 uppercase tracking-widest mb-3 block">Strategy</label>
                  <div className="text-[13px] font-black text-indigo-400 mb-1 leading-tight uppercase">{ragIntel.strategy?.next_step || 'Awaiting Deployment...'}</div>
                  <div className="text-[10px] font-medium text-slate-500 leading-relaxed italic border-l border-white/10 pl-3">
                    {ragIntel.strategy?.reason || 'Analysis required to generate strategy.'}
                  </div>
                </div>

                <div className="border-t border-white/5 pt-6">
                  <label className="text-[9px] font-black text-slate-700 uppercase tracking-widest mb-2 block">Score</label>
                  <div className="text-6xl font-black text-white tabular-nums tracking-tighter drop-shadow-[0_0_30px_rgba(255,255,255,0.05)] flex items-baseline">
                    <span>{Math.floor(Number(displayScore) || 0)}</span>
                    <span className="text-2xl text-indigo-500/50 font-bold ml-1">.{((Number(displayScore) || 0) % 1 * 100).toFixed(0).padStart(2, '0')}</span>
                  </div>
                </div>
              </div>

              <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl">
                <div className="flex justify-between items-center mb-4">
                  <span className="text-[9px] font-black text-amber-500/80 uppercase tracking-widest">Status</span>
                  <span className="text-[9px] font-black text-slate-700 uppercase">{ragIntel.verdict || 'WARM LEAD'}</span>
                </div>
                <div className="p-4 bg-indigo-600/5 border border-indigo-500/10 rounded-xl">
                   <div className="text-[9px] font-black text-indigo-400 uppercase tracking-widest mb-2 flex items-center gap-2">
                     <Target className="w-3 h-3" /> Key Signal
                   </div>
                   <p className="text-[10px] font-medium text-slate-400 leading-relaxed">
                     {ragIntel.key_signals || 'Signals extracted from RAG metrics.'}
                   </p>
                </div>
              </div>
            </section>

            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex-1 flex flex-col overflow-hidden">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-widest">RAG Strategy Portfolio</h2>
                <button onClick={handleCopy} className={`p-2 rounded-lg transition-all ${copySuccess ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/5 text-slate-500'}`}>
                  {copySuccess ? <CheckCircle2 className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>

              <div className="flex-1 bg-black/40 border border-white/5 rounded-2xl p-6 overflow-y-auto custom-scrollbar shadow-inner">
                <div className="prose prose-invert prose-sm max-w-none 
                  prose-h3:text-[11px] prose-h3:font-black prose-h3:uppercase prose-h3:tracking-[0.2em] prose-h3:text-indigo-400 prose-h3:mt-6 prose-h3:mb-3 prose-h3:border-b prose-h3:border-white/5 prose-h3:pb-2
                  prose-p:text-[12px] prose-p:text-slate-300 prose-p:leading-relaxed prose-p:mb-4
                  prose-li:text-[11px] prose-li:text-slate-400
                  ">
                  <ReactMarkdown>{selectedDeal?.rag_advice || '### Awaiting Deep Analysis\n\nRun the scan to extract forensic RAG intelligence from the deck.'}</ReactMarkdown>
                </div>
              </div>

              <button className="w-full mt-6 py-4 bg-indigo-600 hover:bg-indigo-500 text-white text-[11px] font-black uppercase tracking-[0.2em] rounded-2xl shadow-xl shadow-indigo-500/20">
                Send Dispatch
              </button>
            </section>
          </div>
        </main>
      </div>

      <style dangerouslySetInnerHTML={{ __html: `
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.05); border-radius: 10px; }
      `}} />
      </div>
    </div>
  );
};

export default DealIntelligence;
