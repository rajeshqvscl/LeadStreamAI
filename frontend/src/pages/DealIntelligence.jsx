import { useState, useEffect, useRef } from 'react';
import { 
  Brain, FileText, Sparkles, Clock, RefreshCw, 
  ChevronRight, Search, Copy, CheckCircle2, 
  Layout, ShieldAlert, ShieldCheck, Target, Info, Zap,
  BarChart3, Activity, Layers, MessageSquare,
  GitCompare, ArrowUpRight, Terminal, SearchCode,
  Network, History as HistoryIcon, TrendingUp, Building2
} from 'lucide-react';
import api from '../services/api';
import ReactMarkdown from 'react-markdown';
import {
  ResponsiveContainer, AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie,
  XAxis, YAxis, CartesianGrid, Tooltip, Cell, Legend
} from 'recharts';

const Citation = ({ text }) => (
  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-[9px] font-black text-indigo-400 uppercase tracking-tighter mx-0.5 cursor-help hover:bg-indigo-500/20 transition-colors">
    <Info className="w-2.5 h-2.5" /> {text.replace('[Source: ', '').replace(']', '')}
  </span>
);

const DealIntelligence = () => {
    const [compareMode, setCompareMode] = useState(false);
    const [selectedForCompare, setSelectedForCompare] = useState([]);
    const [comparisonReport, setComparisonReport] = useState(null);
    const [chatMessages, setChatMessages] = useState([]);
    const [currentMessage, setCurrentMessage] = useState('');
    const [isStreaming, setIsStreaming] = useState(false);
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDealId, setSelectedDealId] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncLog, setSyncLog] = useState([]);
  const [syncProgress, setSyncProgress] = useState(0);
  const [showSyncPanel, setShowSyncPanel] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);
  const [showSuccessPulse, setShowSuccessPulse] = useState(false);
  const [page, setPage] = useState(1);
  const [totalDeals, setTotalDeals] = useState(0);
  const perPage = 10;
  const [activeTab, setActiveTab] = useState('REVERT'); // REVERT, CLOUD
  const [cloudFeature, setCloudFeature] = useState(null);
  const [cloudOutput, setCloudOutput] = useState(null);
  const [showDebug, setShowDebug] = useState(false);
  const [pdfFilter, setPdfFilter] = useState('with_pdf'); // 'with_pdf' or 'all'
  const [pitchMode, setPitchMode] = useState('general');
  const [demoDataLoaded, setDemoDataLoaded] = useState(false);
  const [chartType, setChartType] = useState('bar');
  const [chartMetric, setChartMetric] = useState('revenue');
  const [darkMode, setDarkMode] = useState(true);

  const pitchBranding = {
    general: { title: 'INBOUND REVERT PROCESSOR', button: 'Analyze Pitch Deck', agentTitle: 'AGENT INTELLIGENCE' },
    investor: { title: 'DUE DILIGENCE ANALYZER', button: 'Launch Investment Analyst', agentTitle: 'INVESTMENT SIGNALS' },
    enterprise: { title: 'DECISION INTELLIGENCE ENGINE', button: 'Launch Due Diligence', agentTitle: 'ENTERPRISE INSIGHTS' },
    technical: { title: 'RESEARCH INTELLIGENCE PIPELINE', button: 'Run Multi-Agent', agentTitle: 'AGENT ORCHESTRATION' }
  };

  const demoFinancialData = {
    years: ['FY21', 'FY22', 'FY23', 'FY24', 'FY25', 'FY26'],
    revenue: [2.5, 4.2, 7.8, 12.5, 18.2, 25.0],
    growth: [45, 68, 86, 60, 46, 37],
    orders: [12000, 18500, 32000, 58000, 85000, 120000]
  };

  // Filter deals based on PDF presence
  const filteredDeals = deals.filter(deal => {
    if (pdfFilter !== 'with_pdf') return true;
    const ragIntel = deal.rag_intelligence || {};
    const hasPdf = deal.pitch_deck_url || ragIntel.filename;
    return hasPdf;
  });

  // Handle cloud feature clicks
  useEffect(() => {
    const fetchCloudFeature = async () => {
      if (!cloudFeature) return;
      setCloudOutput('Loading...');
      
      // Direct fetch to bypass CORS issues
      const baseUrl = 'https://rag-sys-gz59.onrender.com';
      
      try {
        let data;
        switch(cloudFeature) {
          case 'workflows':
            data = await fetch(`${baseUrl}/workflows`).then(r => r.json());
            setCloudOutput(data.workflows || []);
            break;
          case 'graph':
            data = await fetch(`${baseUrl}/documents/graph`).then(r => r.json());
            setCloudOutput(data.nodes || []);
            break;
          case 'clusters':
            data = await fetch(`${baseUrl}/documents/clusters`).then(r => r.json());
            setCloudOutput(data.clusters || []);
            break;
          case 'intent':
            data = await fetch(`${baseUrl}/classify-intent`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({query: 'show me healthtech investors'})
            }).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'web':
            data = await fetch(`${baseUrl}/search/web`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({query: 'AI investment trends 2025'})
            }).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'memory':
            // Create a session and get it
            const session = await fetch(`${baseUrl}/session/create`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({name: 'Test Session'})
            }).then(r => r.json());
            data = await fetch(`${baseUrl}/session/${session.session_id}`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'compare':
            data = await fetch(`${baseUrl}/documents/clusters`).then(r => r.json());
            setCloudOutput(data.clusters || []);
            break;
          case 'report':
            data = await fetch(`${baseUrl}/insights`).then(r => r.json());
            setCloudOutput(data.slice ? data.slice(0, 5) : []);
            break;
          case 'contradictions':
            data = await fetch(`${baseUrl}/contradictions`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({documents: []})
            }).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'hybrid':
            data = await fetch(`${baseUrl}/search/hybrid`, {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({query: 'investment trends 2025'})
            }).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'pitch':
            data = await fetch(`${baseUrl}/pitch/config?mode=general`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'deck_types':
            data = await fetch(`${baseUrl}/analysis/deck-types`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'tables':
            data = await fetch(`${baseUrl}/documents/tables`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'quick_compare':
            data = await fetch(`${baseUrl}/documents/available`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'investors':
            data = await fetch(`${baseUrl}/investors`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'clients':
            data = await fetch(`${baseUrl}/clients`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'library':
            data = await fetch(`${baseUrl}/library`).then(r => r.json());
            setCloudOutput(data);
            break;
          case 'automation':
            data = await fetch(`${baseUrl}/automation/daily`, { method: 'POST' }).then(r => r.json());
            setCloudOutput({status: 'Automation triggered', result: data});
            break;
          default:
            setCloudOutput({message: `Feature: ${cloudFeature} - API connected`});
        }
      } catch (err) {
        console.error(err);
        setCloudOutput({error: 'Failed to connect to RAG service'});
      }
    };
    
    fetchCloudFeature();
  }, [cloudFeature]);

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
  const hasPdf = selectedDeal?.pitch_deck_url;
  
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
    setShowSyncPanel(true);
    setSyncLog([]);
    setSyncProgress(0);
    addLog('Initializing sync engine...');
    
    try {
        addLog('Querying Gmail API...');
        setSyncProgress(20);
        
        const res = await api.post('/api/gmail/sync-inbound');
        setSyncProgress(70);
        
        const detected = res.data?.detected || 0;
        addLog(`Processing ${detected} leads...`);
        setSyncProgress(85);
        
        if (detected > 0) {
            for (let i = 0; i < Math.min(detected, 5); i++) {
                addLog(`Syncing Unit-${760 + i}...`);
                await new Promise(r => setTimeout(r, 300));
                setSyncProgress(85 + (i * 3));
            }
        }
        
        addLog(`Sync complete! ${detected} leads enriched.`);
        setSyncProgress(100);
        setShowSyncPanel(false);
        setTimeout(() => setIsSyncing(false), 2000);
        
        await fetchDeals();
        setShowSuccessPulse(true);
        setTimeout(() => setShowSuccessPulse(false), 2000);
    } catch (err) {
        console.error('Sync failed', err);
        addLog('Sync failed: ' + err.message);
        setShowSyncPanel(false);
    } finally {
        setTimeout(() => setIsSyncing(false), 2000);
    }
  };
  
  const addLog = (msg) => {
    const time = new Date().toLocaleTimeString('en-US', { hour12: false });
    setSyncLog(prev => [...prev.slice(-8), `[${time}] ${msg}`]);
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

  const handleCompare = async () => {
    if (selectedForCompare.length < 2) return;
    setIsAnalyzing(true);
    try {
      const { data } = await api.post('/api/intelligence/compare-leads', { lead_ids: selectedForCompare });
      setComparisonReport(data.report);
    } catch (err) {
      console.error('Comparison failed', err);
    } finally {
      setIsAnalyzing(false);
    }
  };

const handleSendMessage = async () => {
    if (!currentMessage.trim()) return;
    const msg = currentMessage;
    setCurrentMessage('');
    setChatMessages(prev => [...prev, { role: 'user', content: msg }]);
    setIsStreaming(true);
    
    try {
        // Include selected deal context
        const dealContext = selectedDeal ? {
            company: selectedDeal.company_name,
            sector: selectedDeal.sector,
            rag_intel: selectedDeal.rag_intelligence,
            rag_advice: selectedDeal.rag_advice
        } : null;
        
        const { data } = await api.post('/api/intelligence/chat', { 
            message: msg, 
            history: chatMessages,
            deal_context: dealContext
        });
        setChatMessages(prev => [...prev, { 
            role: 'assistant', 
            content: data.response, 
            intent: data.intent 
        }]);
    } catch (err) {
        console.error('Chat failed', err);
    } finally {
        setIsStreaming(false);
    }
};

  const parseCitations = (content) => {
    if (!content) return null;
    const parts = content.split(/(\[Source: [^\]]+\])/);
    return parts.map((part, i) => {
        if (part.startsWith('[Source: ')) {
            return <Citation key={i} text={part} />;
        }
        return part;
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
      {/* Full-screen overlay removed - using right-side panel instead */}
      
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
          
          <div className="space-y-1">
            <button 
                onClick={() => setActiveTab('REVERT')}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'REVERT' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'bg-white/5 text-slate-500 hover:bg-white/10'}`}
            >
                <Activity className="w-3.5 h-3.5" /> Revert Analysis
            </button>
            <button 
                onClick={() => setActiveTab('CLOUD')}
                className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${activeTab === 'CLOUD' ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'bg-white/5 text-slate-500 hover:bg-white/10'}`}
            >
                <SearchCode className="w-3.5 h-3.5" /> Intelligence Cloud
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-6 custom-scrollbar">
          <div className="flex items-center justify-between mb-4 px-1">
            <div className="text-[8px] font-black text-slate-700 uppercase tracking-widest">Inbound Stream</div>
            <div className="flex items-center gap-2 bg-[#0d1117] rounded-lg p-1 border border-white/5">
              <button
                onClick={() => setPdfFilter('with_pdf')}
                className={`px-3 py-1.5 rounded-md text-[9px] font-black uppercase tracking-widest transition-all ${pdfFilter === 'with_pdf' ? 'bg-emerald-600 text-white' : 'text-slate-500 hover:text-white'}`}
              >
                With PDF
              </button>
              <button
                onClick={() => setPdfFilter('all')}
                className={`px-3 py-1.5 rounded-md text-[9px] font-black uppercase tracking-widest transition-all ${pdfFilter === 'all' ? 'bg-indigo-600 text-white' : 'text-slate-500 hover:text-white'}`}
              >
                All
              </button>
            </div>
          </div>
          <div className="space-y-2">
            {filteredDeals.map(deal => (
                <div 
                  key={deal.id}
                  onClick={() => {
                    if (compareMode) {
                        setSelectedForCompare(prev => 
                            prev.includes(deal.id) ? prev.filter(id => id !== deal.id) : [...prev, deal.id]
                        );
                    } else {
                        setSelectedDealId(deal.id);
                    }
                  }}
                  className={`
                    p-5 rounded-[24px] cursor-pointer transition-all duration-300 border mb-4 relative
                    ${selectedDealId === deal.id && !compareMode
                      ? 'bg-indigo-600/20 border-indigo-500/50 shadow-[0_0_20px_rgba(79,70,229,0.15)] scale-[1.02]' 
                      : 'bg-white/[0.02] border-white/5 hover:bg-white/[0.05] hover:border-white/10 hover:scale-[1.01]'
                    }
                    ${compareMode && selectedForCompare.includes(deal.id) ? 'border-amber-500/50 bg-amber-500/5' : ''}
                  `}
                >
                  {compareMode && (
                    <div className={`absolute top-4 right-4 w-4 h-4 rounded-full border-2 ${selectedForCompare.includes(deal.id) ? 'bg-amber-500 border-amber-500' : 'border-white/10'}`}>
                        {selectedForCompare.includes(deal.id) && <CheckCircle2 className="w-3 h-3 text-white" />}
                    </div>
                  )}
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="text-[12px] font-black text-white truncate max-w-[120px]">
                      {deal.company_name || `${deal.first_name}`}
                    </h3>
                    <span className="text-[9px] font-black text-slate-500 uppercase">{deal.updated_at ? new Date(deal.updated_at).toLocaleDateString() : ''}</span>
                  </div>
<p className="text-[10px] text-slate-500 truncate mb-2">{deal.email}</p>
                  {(deal.pitch_deck_url || deal.rag_intelligence?.filename) && (
                    <div className="flex items-center gap-2 mb-3 max-w-full">
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 border border-emerald-500/20 text-[8px] font-black text-emerald-400 uppercase truncate max-w-full overflow-hidden">
                        <FileText className="w-2.5 h-2.5 shrink-0" />
                        <span className="truncate">
                          {deal.rag_intelligence?.filename || deal.pitch_deck_url?.split('/').pop()?.split('?')[0] || 'PDF'}
                        </span>
                      </span>
                    </div>
                  )}
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

          {/* No Results Message */}
          {filteredDeals.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FileText className="w-12 h-12 text-slate-700 mb-4" />
              <p className="text-[10px] font-black text-slate-500 uppercase tracking-widest">
                {pdfFilter === 'with_pdf' ? 'No deals with PDF attachments' : 'No deals found'}
              </p>
            </div>
          )}

          {/* Pagination Controls */}
          {filteredDeals.length > 0 && totalDeals > perPage && (
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

        <div className="p-5 border-t border-white/5 space-y-4">
            <div className="flex flex-col gap-1">
                <div className="flex justify-between items-center text-[8px] font-black uppercase tracking-widest">
                    <span className="text-slate-600">Engine</span>
                    <span className="text-indigo-500">Groq Llama 3.1</span>
                </div>
                <div className="flex justify-between items-center text-[8px] font-black uppercase tracking-widest">
                    <span className="text-slate-600">Latency</span>
                    <span className="text-slate-400">~1.2s</span>
                </div>
                <div className="flex justify-between items-center text-[8px] font-black uppercase tracking-widest">
                    <span className="text-slate-600">Status</span>
                    <span className="text-emerald-500">STABLE</span>
                </div>
            </div>
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
                {isSyncing ? `${syncProgress}%` : 'Sync Inbox'}
              </span>
            </button>
            <div className="flex items-center gap-2 px-3 py-1 bg-emerald-500/10 border border-emerald-500/20 rounded-full">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse"></div>
              <span className="text-[9px] font-black text-emerald-400 uppercase tracking-widest">Stable</span>
            </div>
            <div className="flex items-center gap-2 px-3 py-1 bg-white/5 border border-white/10 rounded-xl">
              <select 
                value={pitchMode}
                onChange={(e) => setPitchMode(e.target.value)}
                className="bg-transparent text-white text-[10px] font-bold focus:outline-none cursor-pointer"
              >
                <option value="general" className="bg-[#0b0f1a]">📊 General</option>
                <option value="investor" className="bg-[#0b0f1a]">💰 Investor</option>
                <option value="enterprise" className="bg-[#0b0f1a]">🏢 Enterprise</option>
                <option value="technical" className="bg-[#0b0f1a]">⚙️ Technical</option>
              </select>
            </div>
            <button 
              onClick={() => setDarkMode(!darkMode)}
              className="p-2 rounded-lg hover:bg-white/5 transition-colors"
              title="Toggle Dark Mode"
            >
              {darkMode ? <span className="text-slate-400">☀️</span> : <span className="text-slate-400">🌙</span>}
            </button>
            <div className="w-8 h-8 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-[10px] font-black text-indigo-400">AA</div>
          </div>
        </header>

        {/* MAIN CONTENT AREA WITH SYNC PANEL */}
        <main className="flex-1 p-6 overflow-y-auto custom-scrollbar">
          {/* Right-side Sync Panel */}
          {showSyncPanel && (
            <div className="fixed right-6 top-20 w-80 bg-[#0b0f1a]/98 border border-indigo-500/40 rounded-2xl p-4 shadow-2xl z-[100] animate-in slide-in-from-right-2 cursor-default">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 text-indigo-400 animate-spin" />
                  <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Background Operations</span>
                </div>
                <button 
                  onClick={() => setShowSyncPanel(false)} 
                  className="text-slate-500 hover:text-white cursor-pointer p-1"
                >×</button>
              </div>
              
              <div className="mb-3">
                <div className="flex justify-between text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">
                  <span>Processing...</span>
                  <span>{syncProgress}%</span>
                </div>
                <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 transition-all duration-300" style={{ width: `${syncProgress}%` }} />
                </div>
              </div>
              
              <div className="space-y-1 max-h-32 overflow-y-auto">
                {syncLog.map((log, i) => (
                  <div key={i} className="text-[10px] font-mono text-slate-400">{log}</div>
                ))}
              </div>
              
              <div className="mt-3 pt-3 border-t border-white/5 text-[9px] text-slate-600">
                Multi-threaded processing active. You can safely navigate while tasks complete.
              </div>
            </div>
          )}
          
          {activeTab === 'CLOUD' ? (
            <div className="space-y-6 animate-in slide-in-from-right-4 duration-500">
                <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-12 min-h-[600px] flex flex-col">
                    <div className="mb-12">
                        <h2 className="text-3xl font-black text-white uppercase tracking-tight mb-2">Intelligence <span className="text-indigo-500">Cloud</span></h2>
                        <p className="text-slate-500 text-sm font-medium">Access advanced RAG modules and agentic orchestration tools.</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                        {[
                            { id: 'workflows', label: 'Workflows', icon: Layers, color: 'indigo', desc: 'Agentic Pipeline' },
                            { id: 'graph', label: 'Document Graph', icon: Network, color: 'blue', desc: 'Entity Mapping' },
                            { id: 'clusters', label: 'Clusters', icon: Target, color: 'purple', desc: 'Lead Segments' },
                            { id: 'intent', label: 'Intent', icon: Brain, color: 'rose', desc: 'Query Routing' },
                            { id: 'web', label: 'Web Search', icon: SearchCode, color: 'cyan', desc: 'Web RAG' },
                            { id: 'memory', label: 'Memory', icon: HistoryIcon, color: 'amber', desc: 'Chat Context' },
                            { id: 'compare', label: 'Compare', icon: GitCompare, color: 'emerald', desc: 'Multi-Lead' },
                            { id: 'report', label: 'Reports', icon: FileText, color: 'violet', desc: 'Investment Docs' },
                            { id: 'contradictions', label: 'Contra', icon: ShieldAlert, color: 'red', desc: 'Conflict Check' },
                            { id: 'hybrid', label: 'Hybrid', icon: Search, color: 'orange', desc: 'Local + Web' },
                            { id: 'pitch', label: 'Pitch', icon: TrendingUp, color: 'lime', desc: 'Positioning' },
                            { id: 'tables', label: 'Tables', icon: Layout, color: 'rose', desc: 'PDF Extract' },
                            { id: 'investors', label: 'Investors', icon: Network, color: 'violet', desc: 'Investor DB' },
                            { id: 'clients', label: 'Clients', icon: Building2, color: 'fuchsia', desc: 'Client DB' },
                            { id: 'library', label: 'Library', icon: FileText, color: 'cyan', desc: 'Doc Library' },
                            { id: 'automation', label: 'Automation', icon: Zap, color: 'amber', desc: 'Daily Pipeline' }
                        ].map((feature) => (
                            <button 
                                key={feature.id}
                                onClick={() => setCloudFeature(feature.id)}
                                className="group p-6 bg-white/[0.02] border border-white/5 rounded-3xl text-left hover:bg-indigo-600/10 hover:border-indigo-500/30 transition-all"
                            >
                                <div className={`w-10 h-10 rounded-xl bg-${feature.color}-500/10 border border-${feature.color}-500/20 flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                                    <feature.icon className={`w-5 h-5 text-${feature.color}-400`} />
                                </div>
                                <div className="text-[12px] font-black text-white uppercase tracking-widest mb-1">{feature.label}</div>
                                <div className="text-[10px] text-slate-500 font-medium">{feature.desc}</div>
                            </button>
                        ))}
                    </div>

                    <div className="flex-1 bg-black/40 border border-white/5 rounded-[32px] p-8">
                        <div className="text-[9px] font-black text-slate-700 uppercase tracking-widest mb-6 flex items-center gap-2">
                            <Terminal className="w-3 h-3" /> System Output: {cloudFeature || 'Ready'}
                        </div>
                        <div className="text-[13px] text-slate-400 font-medium leading-relaxed italic">
                            {!cloudFeature && "Select a module above to initiate advanced intelligence processing."}
                            
                            {cloudFeature === 'workflows' && Array.isArray(cloudOutput) && (
                                <div className="not-italic space-y-3">
                                    {cloudOutput.map((w, i) => (
                                        <div key={i} className="p-4 bg-indigo-500/10 border border-indigo-500/20 rounded-xl">
                                            <div className="text-indigo-400 font-black uppercase text-xs">{w.name}</div>
                                            <div className="text-slate-400 text-sm mt-1">{w.description}</div>
                                            <div className="text-slate-600 text-xs mt-2">Steps: {w.step_count} | Trigger: {w.trigger}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            
                            {cloudFeature === 'graph' && Array.isArray(cloudOutput) && (
                                <div className="not-italic">
                                    <div className="text-emerald-400 font-black uppercase text-xs mb-3">Graph Nodes ({cloudOutput.length})</div>
                                    <div className="space-y-2 max-h-64 overflow-y-auto">
                                        {cloudOutput.slice(0, 10).map((n, i) => (
                                            <div key={i} className="p-3 bg-white/5 rounded-lg flex justify-between">
                                                <span className="text-white font-medium">{n.company}</span>
                                                <span className="text-slate-500 text-xs">{n.type}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {cloudFeature === 'clusters' && cloudOutput && (
                                <div className="not-italic">
                                    <div className="text-purple-400 font-black uppercase text-xs mb-3">Semantic Clusters</div>
                                    {cloudOutput.clusters?.map((cluster, i) => (
                                        <div key={i} className="mb-4">
                                            <div className="text-slate-400 text-xs mb-2">Cluster {i + 1}: {cluster.length} docs</div>
                                            <div className="space-y-1">
                                                {cluster.slice(0, 3).map((d, j) => (
                                                    <div key={j} className="text-slate-500 text-xs pl-2">{d.company || 'Unknown'}</div>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                            
                            {cloudFeature === 'intent' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                                        <div className="text-rose-400 font-black uppercase text-xs">Query</div>
                                        <div className="text-white">{cloudOutput.query}</div>
                                    </div>
                                    <div className="p-4 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                                        <div className="text-rose-400 font-black uppercase text-xs">Detected Intent</div>
                                        <div className="text-white text-lg">{cloudOutput.intent}</div>
                                    </div>
                                </div>
                            )}
                            
                            {cloudFeature === 'web' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-cyan-400 font-black uppercase text-xs mb-3">Web Search Results</div>
                                    <pre className="text-xs text-slate-500 overflow-x-auto">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'memory' && cloudOutput && (
                                <div className="not-italic">
                                    <div className="text-amber-400 font-black uppercase text-xs mb-3">Session Memory</div>
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'compare' && cloudOutput && (
                                <div className="not-italic">
                                    <div className="text-emerald-400 font-black uppercase text-xs mb-3">Document Clusters</div>
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'report' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-violet-400 font-black uppercase text-xs mb-3">Generated Reports</div>
                                    {Array.isArray(cloudOutput) && cloudOutput.slice(0, 5).map((r, i) => {
                                        const summary = (r.summary || r.insights?.summary || '').replace(/\*\*/g, '');
                                        return (
                                            <div key={i} className="p-4 bg-violet-500/10 border border-violet-500/20 rounded-xl">
                                                <div className="text-white font-bold">{r.company}</div>
                                                <div className="text-violet-400 text-xs mt-1">
                                                    {r.score ? `Score: ${r.score} | ` : ''}
                                                    {r.verdict || 'Analyzed'}
                                                </div>
                                                <div className="text-slate-500 text-xs mt-2 line-clamp-2">
                                                    {summary.substring(0, 80) || 'No summary'}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                            
                            {cloudFeature === 'contradictions' && cloudOutput && (
                                <div className="not-italic">
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'hybrid' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-orange-400 font-black uppercase text-xs mb-3">Hybrid Search Results</div>
                                    <pre className="text-xs text-slate-500 overflow-x-auto">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'pitch' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-lime-400 font-black uppercase text-xs mb-3">Pitch Configuration</div>
                                    <div className="grid grid-cols-2 gap-3">
                                        {cloudOutput.positioning && (
                                            <div className="p-3 bg-lime-500/10 border border-lime-500/20 rounded-xl">
                                                <div className="text-lime-400 text-xs font-black uppercase">Positioning</div>
                                                <div className="text-white text-sm mt-1">{JSON.stringify(cloudOutput.positioning).substring(0, 50)}</div>
                                            </div>
                                        )}
                                        {cloudOutput.trust && (
                                            <div className="p-3 bg-lime-500/10 border border-lime-500/20 rounded-xl">
                                                <div className="text-lime-400 text-xs font-black uppercase">Trust Layer</div>
                                                <div className="text-white text-sm mt-1">Trust metrics configured</div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                            
                            {cloudFeature === 'deck_types' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-sky-400 font-black uppercase text-xs mb-3">Pitch Deck Types</div>
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'tables' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-rose-400 font-black uppercase text-xs mb-3">Extracted Tables</div>
                                    {cloudOutput.tables?.length > 0 ? (
                                        cloudOutput.tables.slice(0, 5).map((t, i) => (
                                            <div key={i} className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl">
                                                <div className="text-white font-medium">Table {i + 1}</div>
                                                <div className="text-rose-400 text-xs mt-1">{t.rows?.length || 0} rows</div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-slate-500 text-sm">No tables found</div>
                                    )}
                                </div>
                            )}
                            
                            {cloudFeature === 'quick_compare' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-teal-400 font-black uppercase text-xs mb-3">Available Documents</div>
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'investors' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-violet-400 font-black uppercase text-xs mb-3">Investor Database</div>
                                    {Array.isArray(cloudOutput) ? cloudOutput.slice(0, 10).map((inv, i) => (
                                        <div key={i} className="p-3 bg-violet-500/10 border border-violet-500/20 rounded-xl">
                                            <div className="text-white font-medium">{inv.name || inv.company_name}</div>
                                            <div className="text-violet-400 text-xs mt-1">{inv.type || inv.category}</div>
                                        </div>
                                    )) : (
                                        <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                    )}
                                </div>
                            )}
                            
                            {cloudFeature === 'clients' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-fuchsia-400 font-black uppercase text-xs mb-3">Client Database</div>
                                    {Array.isArray(cloudOutput) ? cloudOutput.slice(0, 10).map((c, i) => (
                                        <div key={i} className="p-3 bg-fuchsia-500/10 border border-fuchsia-500/20 rounded-xl">
                                            <div className="text-white font-medium">{c.name || c.company_name}</div>
                                            <div className="text-fuchsia-400 text-xs mt-1">{c.sector}</div>
                                        </div>
                                    )) : (
                                        <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                    )}
                                </div>
                            )}
                            
                            {cloudFeature === 'library' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-cyan-400 font-black uppercase text-xs mb-3">Document Library</div>
                                    <pre className="text-xs text-slate-500">{JSON.stringify(cloudOutput, null, 2)}</pre>
                                </div>
                            )}
                            
                            {cloudFeature === 'automation' && cloudOutput && (
                                <div className="not-italic space-y-3">
                                    <div className="text-amber-400 font-black uppercase text-xs mb-3">Daily Automation</div>
                                    <div className="p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
                                        <div className="text-white font-medium">{cloudOutput.status || 'Completed'}</div>
                                        <div className="text-amber-400 text-xs mt-1">{JSON.stringify(cloudOutput.result || cloudOutput).substring(0, 100)}</div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </section>
            </div>
          ) : (
            <div className="grid grid-cols-12 gap-6 h-full">
          
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6">
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl relative group">
              <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em] mb-6">Processor</h2>
              <div className="flex flex-col items-center justify-center py-12 border-2 border-dashed border-white/5 rounded-3xl bg-white/[0.01]">
                <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
                  <FileText className="w-6 h-6 text-indigo-500" />
                </div>
                <div className="text-[11px] font-bold text-white mb-6 text-center truncate max-w-full px-4">
                  {selectedDeal?.pitch_deck_url ? (
                    <span className="flex items-center justify-center gap-2 truncate">
                      <ShieldCheck className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                      <span className="truncate">{selectedDeal.pitch_deck_url?.split('/').pop()?.split('?')[0] || 'PDF Attached'}</span>
                    </span>
                  ) : (
                    'Awaiting Document...'
                  )}
                </div>
                <button 
                  onClick={handleAnalyze}
                  disabled={isAnalyzing || !selectedDeal}
                  className="px-8 py-3 bg-indigo-600 hover:bg-indigo-500 text-white text-[10px] font-black uppercase tracking-widest rounded-xl transition-all disabled:opacity-50"
                >
                  {isAnalyzing ? 'Processing...' : pitchBranding[pitchMode]?.button || 'Analyze Pitch Deck'}
                </button>
                <button 
                  onClick={() => { setDemoDataLoaded(true); }}
                  className="mt-4 px-4 py-2 text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-white transition-colors border border-dashed border-slate-700 rounded-lg hover:border-slate-500"
                >
                  📊 Load Demo Data
                </button>
              </div>
            </section>

            {/* FINANCIAL VISUALIZATIONS */}
            {(demoDataLoaded || (hasPdf && selectedDeal?.rag_advice)) && (
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-6 shadow-2xl">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">📈 FINANCIAL VISUALIZATIONS</h2>
                <TrendingUp className="w-4 h-4 text-slate-600" />
              </div>
              
              {/* Chart Type Selector */}
              <div className="flex flex-wrap gap-2 mb-4">
                {['bar', 'line', 'pie', 'area'].map(type => (
                  <button
                    key={type}
                    onClick={() => setChartType(type)}
                    className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${chartType === type ? 'bg-violet-600 text-white' : 'bg-white/5 text-slate-500 hover:text-white'}`}
                  >
                    {type === 'bar' ? '📊 Bar' : type === 'line' ? '📈 Line' : type === 'pie' ? '🥧 Pie' : '📉 Area'}
                  </button>
                ))}
              </div>
              
              {/* Metric Toggle */}
              <div className="flex gap-2 mb-4">
                {[
                  { id: 'revenue', label: 'Revenue', color: '#3b82f6' },
                  { id: 'growth', label: 'Growth %', color: '#10b981' },
                  { id: 'orders', label: 'Orders', color: '#f59e0b' }
                ].map(m => (
                  <button
                    key={m.id}
                    onClick={() => setChartMetric(m.id)}
                    className="px-4 py-2 rounded-lg text-[10px] font-black uppercase"
                    style={{ background: chartMetric === m.id ? m.color : '#1e293b', color: chartMetric === m.id ? 'white' : '#94a3b8', border: chartMetric === m.id ? 'none' : '1px solid #334155' }}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
              
              {/* Chart Display - Recharts Integration */}
              <div className="h-72 bg-white/[0.02] border border-white/5 rounded-2xl p-6 relative overflow-hidden">
                <ResponsiveContainer width="100%" height="100%">
                  {chartType === 'bar' ? (
                    <BarChart data={demoDataLoaded ? demoFinancialData.years.map((y, i) => ({
                      name: y,
                      value: demoFinancialData[chartMetric][i]
                    })) : [10, 25, 45, 70].map((v, i) => ({ name: `FY${21+i}`, value: v }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" vertical={false} />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <Tooltip 
                        contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px'}}
                        itemStyle={{color: '#fff', fontSize: '12px'}}
                      />
                      <Bar 
                        dataKey="value" 
                        fill={chartMetric === 'revenue' ? '#3b82f6' : chartMetric === 'growth' ? '#10b981' : '#f59e0b'} 
                        radius={[6, 6, 0, 0]}
                        barSize={32}
                      />
                    </BarChart>
                  ) : chartType === 'line' ? (
                    <LineChart data={demoDataLoaded ? demoFinancialData.years.map((y, i) => ({
                      name: y,
                      value: demoFinancialData[chartMetric][i]
                    })) : [10, 25, 45, 70].map((v, i) => ({ name: `FY${21+i}`, value: v }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" vertical={false} />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <Tooltip 
                        contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px'}}
                      />
                      <Line 
                        type="monotone" 
                        dataKey="value" 
                        stroke={chartMetric === 'revenue' ? '#3b82f6' : chartMetric === 'growth' ? '#10b981' : '#f59e0b'} 
                        strokeWidth={3}
                        dot={{ r: 4, fill: '#fff' }}
                      />
                    </LineChart>
                  ) : chartType === 'area' ? (
                    <AreaChart data={demoDataLoaded ? demoFinancialData.years.map((y, i) => ({
                      name: y,
                      value: demoFinancialData[chartMetric][i]
                    })) : [10, 25, 45, 70].map((v, i) => ({ name: `FY${21+i}`, value: v }))}>
                      <defs>
                        <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={chartMetric === 'revenue' ? '#3b82f6' : chartMetric === 'growth' ? '#10b981' : '#f59e0b'} stopOpacity={0.3}/>
                          <stop offset="95%" stopColor={chartMetric === 'revenue' ? '#3b82f6' : chartMetric === 'growth' ? '#10b981' : '#f59e0b'} stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#ffffff0a" vertical={false} />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <YAxis axisLine={false} tickLine={false} tick={{fill: '#64748b', fontSize: 10}} />
                      <Tooltip contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px'}} />
                      <Area 
                        type="monotone" 
                        dataKey="value" 
                        stroke={chartMetric === 'revenue' ? '#3b82f6' : chartMetric === 'growth' ? '#10b981' : '#f59e0b'} 
                        fillOpacity={1} 
                        fill="url(#colorValue)" 
                        strokeWidth={2}
                      />
                    </AreaChart>
                  ) : (
                    <PieChart>
                      <Pie
                        data={demoDataLoaded ? demoFinancialData.years.map((y, i) => ({
                          name: y,
                          value: demoFinancialData[chartMetric][i]
                        })) : [10, 25, 45, 70].map((v, i) => ({ name: `FY${21+i}`, value: v }))}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {(demoDataLoaded ? demoFinancialData.years : [0,1,2,3]).map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#06b6d4'][index % 6]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '12px'}} />
                      <Legend verticalAlign="bottom" height={36}/>
                    </PieChart>
                  )}
                </ResponsiveContainer>
              </div>
              
              {demoDataLoaded && (
                <div className="mt-4 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                  <div className="text-[10px] font-black text-emerald-400 uppercase mb-2">✓ Demo Financial Analysis</div>
                  <div className="text-[11px] text-slate-400">
                    FY21: ₹2.5Cr → FY26: ₹25Cr (10x growth) | 6-Year CAGR: 58% | Current Growth: 37%
                  </div>
                </div>
              )}
            </section>
            )}

            {hasPdf ? (
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex-1 min-h-[400px]">
              <div className="flex justify-between items-center mb-8">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">Deep-Dive Analysis</h2>
                {selectedDeal?.rag_advice && <ShieldAlert className="w-4 h-4 text-amber-500/50" />}
              </div>

              <div className="memorandum-container bg-white/[0.01] border border-white/5 rounded-3xl p-8 min-h-[500px]">
                {comparisonReport ? (
                    <div className="animate-in slide-in-from-bottom-4 duration-500">
                        <div className="flex justify-between items-center mb-8">
                            <h3 className="text-xl font-black text-white uppercase tracking-widest flex items-center gap-3">
                                <GitCompare className="w-6 h-6 text-amber-500" /> Multi-Lead Comparison
                            </h3>
                            <button onClick={() => setComparisonReport(null)} className="text-[10px] font-black text-slate-500 uppercase tracking-widest hover:text-white transition-colors">Close Report</button>
                        </div>
                        <div className="prose prose-invert max-w-none prose-sm">
                            <ReactMarkdown>{comparisonReport}</ReactMarkdown>
                        </div>
                    </div>
                ) : selectedDeal?.rag_advice ? (
                    <>
                        {/* Clean Card-Based Display */}
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                            {/* Verdict Card */}
                            {(ragIntel.verdict || selectedDeal.rag_advice?.includes('VERDICT')) && (
                                <div className="bg-gradient-to-br from-indigo-500/10 to-purple-500/5 border border-indigo-500/20 rounded-2xl p-6 flex flex-col min-h-[160px]">
                                    <div className="flex items-center gap-2 mb-4">
                                        <ShieldCheck className="w-4 h-4 text-indigo-400" />
                                        <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">Verdict</span>
                                    </div>
                                    <div className="text-xl font-black text-white leading-tight break-words flex-1 flex items-center">
                                        {ragIntel.verdict || 'NEUTRAL'}
                                    </div>
                                </div>
                            )}
                            
                            {/* Confidence Card */}
                            <div className="bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/20 rounded-2xl p-6 flex flex-col min-h-[160px]">
                                <div className="flex items-center gap-2 mb-4">
                                    <Target className="w-4 h-4 text-emerald-400" />
                                    <span className="text-[10px] font-black text-emerald-400 uppercase tracking-widest">Confidence</span>
                                </div>
                                <div className="text-3xl font-black text-white flex-1 flex items-center">{displayScore}%</div>
                            </div>
                            
                            {/* Priority Card */}
                            {ragIntel.strategy && (
                                <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/20 rounded-2xl p-6 flex flex-col min-h-[160px]">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Zap className="w-4 h-4 text-amber-400" />
                                        <span className="text-[10px] font-black text-amber-400 uppercase tracking-widest">Priority</span>
                                    </div>
                                    <div className="text-3xl font-black text-white flex-1 flex items-center">{ragIntel.strategy.priority || 'MEDIUM'}</div>
                                </div>
                            )}
                        </div>
                        
                        {/* Actuals Section */}
                        {ragIntel.actuals && Object.keys(ragIntel.actuals).length > 0 && (
                            <div className="mb-10 animate-in fade-in slide-in-from-top-2 duration-700">
                                <h3 className="text-indigo-400 text-[11px] font-black uppercase tracking-[0.2em] mb-4">Key Metrics</h3>
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                    {Object.entries(ragIntel.actuals).map(([key, value]) => (
                                        <div key={key} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
                                            <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">{key.replace(/_/g, ' ')}</div>
                                            <div className="text-[16px] font-black text-indigo-400">{String(value).replace(/\*\*/g, '') || '—'}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                        
                        {/* Key Signals */}
                        {ragIntel.key_signals && (
                            <div className="mb-8 p-8 bg-gradient-to-r from-blue-600/10 to-transparent border border-blue-500/20 rounded-3xl">
                                <h3 className="text-blue-400 text-[11px] font-black uppercase tracking-[0.3em] mb-4">Key Strategic Signal</h3>
                                <p className="text-[14px] font-medium text-slate-200 leading-relaxed drop-shadow-sm">{String(ragIntel.key_signals).replace(/\*\*/g, '')}</p>
                            </div>
                        )}
                        
                        {/* Full Report */}
                        {selectedDeal.rag_advice && (
                            <div className="p-6 bg-white/[0.02] border border-white/5 rounded-2xl">
                                <h3 className="text-slate-400 text-[11px] font-black uppercase tracking-[0.2em] mb-4">Full Analysis</h3>
                                <div className="text-[13px] text-slate-300 leading-relaxed space-y-4">
                                    {selectedDeal.rag_advice.split('###').filter(s => s.trim()).map((section, idx) => {
                                        const lines = section.trim().split('\n');
                                        const title = lines[0]?.trim().replace(/\*\*/g, '');
                                        const content = lines.slice(1).join('\n').trim().replace(/\*\*/g, '');
                                        if (!title) return null;
                                        return (
                                            <div key={idx}>
                                                <h4 className="text-indigo-400 text-[11px] font-black uppercase tracking-widest mb-2">{title}</h4>
                                                <p className="text-slate-300 whitespace-pre-wrap">{content}</p>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        )}
                    </>
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
          ) : (
            <div className="flex-1 flex items-center justify-center min-h-[400px]">
              <div className="text-center">
                <FileText className="w-16 h-16 text-slate-700 mx-auto mb-4" />
                <p className="text-[11px] font-black text-slate-500 uppercase tracking-widest">No PDF Attached</p>
                <p className="text-[9px] text-slate-600 mt-2">This deal has no incoming PDF document</p>
              </div>
            </div>
          )}
          </div>

          <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex flex-col gap-8">
              <div className="flex justify-between items-center">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-[0.2em]">{pitchBranding[pitchMode]?.agentTitle || 'AGENT INTELLIGENCE'}</h2>
                <Brain className="w-4 h-4 text-indigo-500" />
              </div>

              <div className="space-y-6">
                {/* Intent */}
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-black text-slate-500 uppercase">INTENT</span>
                  <span className={`px-2 py-1 rounded-md text-[9px] font-black uppercase ${selectedDeal?.reply_intent === 'INTERESTED' ? 'bg-emerald-500/20 text-emerald-400' : selectedDeal?.reply_intent === 'MEETING_REQUESTED' ? 'bg-amber-500/20 text-amber-400' : 'bg-indigo-500/20 text-indigo-400'}`}>
                    {ragIntel.category || selectedDeal?.reply_intent || 'NEUTRAL'}
                  </span>
                </div>

                {/* Strategy */}
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-black text-slate-500 uppercase">STRATEGY</span>
                  <span className="text-[11px] font-bold text-cyan-400">{ragIntel.strategy?.next_step || 'N/A'}</span>
                </div>

                {/* Score */}
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-black text-slate-500 uppercase">SCORE</span>
                  <span className="text-[18px] font-black text-white">{displayScore || 'N/A'}</span>
                </div>

                {/* Deal Status */}
                <div className="flex justify-between items-center pt-4 border-t border-white/5">
                  <span className="text-[10px] font-black text-slate-500 uppercase">DEAL STATUS</span>
                  <span className="text-[10px] font-black text-amber-400 uppercase">{selectedDeal?.email_status || 'IN REVIEW'}</span>
                </div>

                {/* Key Signal */}
                {ragIntel.key_signals && (
                  <div className="p-3 bg-cyan-500/10 border border-cyan-500/20 rounded-xl">
                    <span className="text-[9px] font-black text-cyan-400 uppercase tracking-widest">KEY INVESTMENT SIGNAL</span>
                    <p className="text-[11px] text-slate-300 mt-2 leading-relaxed">{String(ragIntel.key_signals).substring(0, 100)}</p>
                  </div>
                )}

                {/* Confidence */}
                <div className="flex justify-between items-center">
                  <span className="text-[10px] font-black text-slate-500 uppercase">SYSTEM CONFIDENCE</span>
                  <span className="text-[10px] font-black text-emerald-400">{Math.floor(Number(displayScore) || 75)}%</span>
                </div>

                {/* Visual Dashboard - RAG Features */}
                {(hasPdf || !selectedDeal?.pitch_deck_url) && (
                <div className="mt-6 pt-6 border-t border-white/5">
                  <h3 className="text-[9px] font-black text-slate-600 uppercase tracking-widest mb-4 flex items-center gap-2">
                    <BarChart3 className="w-3 h-3" /> Visual Intelligence
                  </h3>
                  
                  {/* RAG System Stats */}
                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <button 
                      onClick={async () => { setCloudFeature('insights'); }}
                      className="p-3 bg-gradient-to-br from-indigo-500/10 to-purple-500/5 border border-indigo-500/20 rounded-xl hover:border-indigo-500/40 transition-all text-left group"
                    >
                      <div className="text-[8px] font-black text-indigo-400 uppercase tracking-[0.2em] mb-1">Insights</div>
                      <div className="text-[11px] font-black text-white group-hover:text-indigo-300 transition-colors">View All</div>
                    </button>
                    <button 
                      onClick={async () => { setCloudFeature('clusters'); }}
                      className="p-3 bg-gradient-to-br from-emerald-500/10 to-teal-500/5 border border-emerald-500/20 rounded-xl hover:border-emerald-500/40 transition-all text-left group"
                    >
                      <div className="text-[8px] font-black text-emerald-400 uppercase tracking-[0.2em] mb-1">Clusters</div>
                      <div className="text-[11px] font-black text-white group-hover:text-emerald-300 transition-colors">View Map</div>
                    </button>
                    <button 
                      onClick={async () => { setCloudFeature('graph'); }}
                      className="p-3 bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/20 rounded-xl hover:border-amber-500/40 transition-all text-left group"
                    >
                      <div className="text-[8px] font-black text-amber-400 uppercase tracking-[0.2em] mb-1">Graph</div>
                      <div className="text-[11px] font-black text-white group-hover:text-amber-300 transition-colors">Network</div>
                    </button>
                    <button 
                      onClick={async () => { setCloudFeature('compare'); }}
                      className="p-3 bg-gradient-to-br from-rose-500/10 to-pink-500/5 border border-rose-500/20 rounded-xl hover:border-rose-500/40 transition-all text-left group"
                    >
                      <div className="text-[8px] font-black text-rose-400 uppercase tracking-[0.2em] mb-1">Compare</div>
                      <div className="text-[11px] font-black text-white group-hover:text-rose-300 transition-colors">Analysis</div>
                    </button>
                  </div>

                  {/* Quick Actions */}
                  <div className="space-y-2">
                    <button 
                      onClick={async () => {
                        try {
                          const res = await fetch('https://rag-sys-gz59.onrender.com/documents/tables').then(r => r.json());
                          setCloudFeature('tables');
                          setCloudOutput(res);
                          setActiveTab('CLOUD');
                        } catch(e) { console.error('Failed to fetch tables'); }
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-[9px] font-black text-slate-400 uppercase tracking-widest transition-all"
                    >
                      <Layers className="w-3 h-3" /> Extract Tables
                    </button>
                    <button 
                      onClick={async () => {
                        try {
                          const res = await fetch('https://rag-sys-gz59.onrender.com/ask', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({question: 'Summarize this deal briefly'})
                          }).then(r => r.json());
                          setCloudFeature('summary');
                          setCloudOutput(res);
                          setActiveTab('CLOUD');
                        } catch(e) { console.error('Failed'); }
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-[9px] font-black text-slate-400 uppercase tracking-widest transition-all"
                    >
                      <Sparkles className="w-3 h-3" /> Quick Summary
                    </button>
                  </div>
                </div>
                )}

                <div className="border-t border-white/5 pt-6">
                  <label className="text-[9px] font-black text-slate-700 uppercase tracking-widest mb-2 block">Score</label>
                  <div className="text-6xl font-black text-white tabular-nums tracking-tighter drop-shadow-[0_0_30px_rgba(255,255,255,0.05)] flex items-baseline">
                    <span>{Math.floor(Number(displayScore) || 0)}</span>
                    <span className="text-2xl text-indigo-500/50 font-bold ml-1">.{((Number(displayScore) || 0) % 1 * 100).toFixed(0).padStart(2, '0')}</span>
                  </div>
                </div>
              </div>

              <div className="p-6 bg-gradient-to-br from-white/[0.03] to-transparent border border-white/5 rounded-[24px]">
                <div className="flex flex-col gap-1 mb-6">
                  <span className="text-[10px] font-black text-indigo-500 uppercase tracking-[0.2em]">RAG Analysis Verdict</span>
                  <span className="text-[16px] font-black text-white uppercase tracking-tight">{ragIntel.verdict || 'WARM LEAD'}</span>
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

            <section className="bg-[#0b0f1a] border border-white/5 rounded-[32px] p-8 shadow-2xl flex-1 flex flex-col overflow-hidden relative">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-widest flex items-center gap-2">
                    <MessageSquare className="w-3 h-3" /> Sector Intelligence Chat
                </h2>
                <div className="flex gap-2">
                    <button 
                        onClick={() => { setCompareMode(!compareMode); setSelectedForCompare([]); }}
                        className={`px-3 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest transition-all ${compareMode ? 'bg-amber-500 text-white' : 'bg-white/5 text-slate-500'}`}
                    >
                        {compareMode ? 'Cancel Compare' : 'Compare Mode'}
                    </button>
                    {compareMode && selectedForCompare.length >= 2 && (
                        <button onClick={handleCompare} className="px-3 py-1.5 bg-indigo-600 text-white rounded-lg text-[9px] font-black uppercase tracking-widest animate-pulse">Run Compare</button>
                    )}
                </div>
              </div>

              <div className="flex-1 bg-black/40 border border-white/5 rounded-2xl p-4 overflow-y-auto custom-scrollbar shadow-inner flex flex-col gap-4">
                {chatMessages.length === 0 && (
                    <div className="flex flex-col items-center justify-center h-full text-slate-600 italic text-[10px]">
                        Ask about market trends, competitors, or specific lead details...
                    </div>
                )}
                {chatMessages.map((m, i) => (
                    <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                        {m.intent && (
                            <span className="text-[8px] font-black text-indigo-500 uppercase tracking-widest mb-1 ml-1">{m.intent}</span>
                        )}
                        <div className={`max-w-[85%] p-3 rounded-2xl text-[12px] leading-relaxed ${
                            m.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-white/5 text-slate-300 border border-white/5'
                        }`}>
                            {m.content}
                        </div>
                    </div>
                ))}
                {isStreaming && (
                    <div className="flex items-center gap-2 text-indigo-500 animate-pulse text-[10px] font-black uppercase tracking-widest">
                        <Zap className="w-3 h-3" /> AI Thinking...
                    </div>
                )}
              </div>

              <div className="mt-4 flex gap-2">
                <input 
                    type="text"
                    value={currentMessage}
                    onChange={(e) => setCurrentMessage(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                    placeholder="Type a query..."
                    className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-[12px] focus:outline-none focus:border-indigo-500/50"
                />
                <button 
                    onClick={handleSendMessage}
                    disabled={isStreaming}
                    className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center text-white hover:bg-indigo-500 transition-colors shadow-lg shadow-indigo-500/20"
                >
                    <ArrowUpRight className="w-5 h-5" />
                </button>
              </div>
            </section>
          </div>
        </div>
      )}
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
