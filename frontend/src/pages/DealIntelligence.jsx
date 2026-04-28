import React, { useState, useEffect } from 'react';
import axios from '../services/api';
import ReactMarkdown from 'react-markdown';
import { Brain, FileText, Sparkles, Clock, ExternalLink, RefreshCw, ChevronRight, Inbox as InboxIcon, Calendar } from 'lucide-react';

const formatIST = (dateStr) => {
  if (!dateStr) return { date: '—', time: '—' };
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return { date: '—', time: '—' };
  
  const formattedDate = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(d);
  
  const formattedTime = new Intl.DateTimeFormat('en-IN', {
    timeZone: 'Asia/Kolkata',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true
  }).format(d);
  
  return { date: formattedDate, time: formattedTime };
};

const DealIntelligence = () => {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedDealId, setSelectedDealId] = useState(null);
  const [activeTab, setActiveTab] = useState('analysis');

  const fetchDeals = async () => {
    try {
      const { data } = await axios.get('/api/gmail/inbound-deals');
      // Only keep deals that have a pitch deck or RAG advice
      const ragDeals = data.filter(d => d.pitch_deck_url || d.rag_advice);
      setDeals(ragDeals);
      
      // Auto-select the first deal if none is selected
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
  }, []);

  const selectedDeal = deals.find(d => d.id === selectedDealId);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10 animate-in fade-in duration-700 h-[calc(100vh-80px)] flex flex-col">
      <div className="mb-8 flex flex-col md:flex-row justify-between items-start md:items-end gap-6 shrink-0">
        <div>
          <div className="flex items-center gap-3 mb-4">
            <div className="px-3 py-1 bg-violet-500/10 border border-violet-500/20 rounded-full text-[10px] font-black text-violet-400 uppercase tracking-[3px] flex items-center gap-2">
              <Brain className="w-3 h-3" /> AI Deal Intelligence
            </div>
            <div className="w-2 h-2 rounded-full bg-violet-500 animate-pulse"></div>
          </div>
          <h1 className="text-[38px] font-black text-white tracking-tight leading-none mb-4">
            Pitch Deck <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent italic">Analysis</span>
          </h1>
          <p className="text-slate-400 text-lg font-medium">
            AI-powered insights and RAG analysis for inbound pitch decks.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={async () => {
              setLoading(true);
              try {
                await axios.post('/api/gmail/retro-sync-pdfs');
              } catch(e) {}
              fetchDeals();
            }}
            className="flex items-center gap-2 px-4 py-2 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg cursor-pointer hover:scale-105 active:scale-95 border border-blue-500/20"
          >
            <InboxIcon className="w-4 h-4" /> Sync Old PDFs
          </button>
          <button 
            onClick={() => { setLoading(true); fetchDeals(); }}
            className="flex items-center gap-2 px-4 py-2 bg-[#131722] hover:bg-white/10 hover:text-white border border-white/5 text-slate-300 text-xs font-black uppercase tracking-widest rounded-xl transition-all shadow-lg cursor-pointer hover:scale-105 active:scale-95"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh Data
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center py-20 opacity-50">
          <Brain className="w-12 h-12 text-violet-500 mb-4 animate-pulse" />
          <div className="text-[12px] font-black text-slate-400 uppercase tracking-[4px]">Synthesizing Intelligence...</div>
        </div>
      ) : deals.length === 0 ? (
        <div className="flex-1 bg-[#131722] border border-white/5 rounded-[32px] p-20 flex flex-col items-center justify-center text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center mb-6">
            <FileText className="w-8 h-8 text-slate-600" />
          </div>
          <h3 className="text-xl font-black text-white mb-2">No Pitch Decks Found</h3>
          <p className="text-slate-500 max-w-md">
            When a lead replies with a pitch deck attachment or link, it will appear here alongside a deep AI deal analysis.
          </p>
        </div>
      ) : (
        <div className="flex-1 flex flex-col md:flex-row gap-6 min-h-0">
          
          {/* Master List (Left) */}
          <div className="w-full md:w-1/3 flex flex-col bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl shrink-0">
            <div className="p-6 border-b border-white/5 bg-white/[0.01]">
              <div className="text-[10px] font-black text-slate-500 uppercase tracking-[3px]">Inbound Decks</div>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
              {deals.map(deal => {
                const ist = formatIST(deal.updated_at);
                return (
                  <button
                    key={deal.id}
                    onClick={() => setSelectedDealId(deal.id)}
                    className={`w-full text-left p-4 rounded-2xl transition-all cursor-pointer group ${selectedDealId === deal.id ? 'bg-violet-500/10 border-violet-500/30 border shadow-lg shadow-violet-500/5 translate-x-1' : 'bg-transparent border border-transparent hover:bg-white/5 hover:translate-x-1'}`}
                  >
                    <div className="flex items-center gap-3 mb-2">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center font-black flex-shrink-0 transition-colors ${selectedDealId === deal.id ? 'bg-violet-500/20 text-violet-400' : 'bg-white/5 text-slate-400 group-hover:text-slate-300'}`}>
                        {deal.first_name?.[0] || '?'}{deal.last_name?.[0] || ''}
                      </div>
                      <div className="flex-1 min-w-0">
                        <h4 className={`text-sm font-black truncate uppercase transition-colors ${selectedDealId === deal.id ? 'text-white' : 'text-slate-300 group-hover:text-white'}`}>
                          {deal.company_name || `${deal.first_name} ${deal.last_name}`}
                        </h4>
                        <p className="text-[10px] font-bold text-slate-500 truncate lowercase">{deal.email}</p>
                      </div>
                      {deal.rag_advice ? (
                        <Sparkles className={`w-4 h-4 transition-colors ${selectedDealId === deal.id ? 'text-violet-400' : 'text-slate-600 group-hover:text-violet-400/50'}`} />
                      ) : (
                        <Clock className={`w-4 h-4 transition-colors ${selectedDealId === deal.id ? 'text-blue-400' : 'text-slate-600'}`} />
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 text-[8px] font-black uppercase tracking-widest text-slate-600 pl-[52px]">
                      <Calendar className="w-2.5 h-2.5" />
                      {ist.date} — {ist.time}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Detail View (Right) */}
          <div className="w-full md:w-2/3 flex flex-col bg-[#131722] border border-white/5 rounded-[32px] overflow-hidden shadow-2xl">
            {selectedDeal ? (
              <div className="flex flex-col h-full">
                
                {/* Header */}
                <div className="p-8 border-b border-white/5 bg-gradient-to-br from-white/[0.02] to-transparent shrink-0">
                  <div className="flex justify-between items-start mb-6">
                    <div>
                      <h2 className="text-2xl font-black text-white uppercase mb-2">
                        {selectedDeal.company_name || 'Individual Prospect'}
                      </h2>
                      <div className="flex items-center gap-3">
                        <span className="text-[11px] font-black text-slate-400 uppercase tracking-widest">{selectedDeal.first_name} {selectedDeal.last_name}</span>
                        <span className="w-1 h-1 rounded-full bg-slate-700"></span>
                        <span className="text-[11px] font-bold text-slate-500 lowercase">{selectedDeal.email}</span>
                      </div>
                    </div>
                    
                    {selectedDeal.pitch_deck_url && (
                      <a
                        href={selectedDeal.pitch_deck_url}
                        target="_blank"
                        rel="noreferrer"
                        className="flex items-center gap-2 px-4 py-2.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 text-blue-400 hover:text-blue-300 text-[10px] font-black uppercase tracking-widest rounded-xl transition-all shadow-lg cursor-pointer hover:-translate-y-0.5 active:translate-y-0"
                      >
                        <FileText className="w-3.5 h-3.5" /> Open Pitch Deck
                      </a>
                    )}
                  </div>
                  
                  {selectedDeal.pitch_deck_url && selectedDeal.pitch_deck_url.includes('Attached PDF:') && (
                     <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-white/5 border border-white/10 rounded-lg text-[9px] font-black text-slate-300 uppercase tracking-widest">
                       <InboxIcon className="w-3 h-3 text-slate-400" />
                       Directly Attached to Email
                     </div>
                  )}
                </div>

                {/* Content Body (Tabbed View) */}
                <div className="flex-1 flex flex-col overflow-hidden">
                  
                  {/* Tabs Header */}
                  <div className="flex items-center gap-6 px-8 border-b border-white/5 bg-white/[0.01] shrink-0">
                    <button 
                      onClick={() => setActiveTab('analysis')}
                      className={`cursor-pointer py-4 text-[11px] font-black uppercase tracking-widest border-b-2 transition-all ${activeTab === 'analysis' ? 'border-violet-500 text-violet-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                    >
                      AI Deal Analysis
                    </button>
                    <button 
                      onClick={() => setActiveTab('pdf')}
                      className={`cursor-pointer py-4 text-[11px] font-black uppercase tracking-widest border-b-2 transition-all ${activeTab === 'pdf' ? 'border-blue-500 text-blue-400' : 'border-transparent text-slate-500 hover:text-slate-300'}`}
                    >
                      Original Pitch Deck
                    </button>
                  </div>

                  {/* Tab Content */}
                  <div className="flex-1 overflow-hidden relative">
                    
                    {/* Analysis Tab */}
                    {activeTab === 'analysis' && (
                      <div className="absolute inset-0 overflow-y-auto p-8 custom-scrollbar">
                        {selectedDeal.rag_advice ? (
                          <div className="relative max-w-3xl">
                            <div className="absolute -top-3 -left-3 w-16 h-16 bg-violet-500/10 rounded-full blur-2xl"></div>
                            <div className="flex items-center gap-3 mb-6 relative z-10">
                              <div className="w-8 h-8 rounded-xl bg-violet-500/10 flex items-center justify-center border border-violet-500/20">
                                <Sparkles className="w-4 h-4 text-violet-400" />
                              </div>
                              <h4 className="text-[13px] font-black text-violet-400 uppercase tracking-widest">Deep RAG Insights</h4>
                            </div>
                            
                            {/* Ensure all single newlines become double newlines for perfect Markdown spacing */}
                            <div className="prose prose-invert max-w-none text-[14px] font-medium text-slate-300 leading-[1.8] prose-p:mb-5 prose-headings:font-black prose-headings:text-white prose-headings:mt-8 prose-headings:mb-4 prose-strong:text-white prose-strong:font-black prose-li:marker:text-violet-500 prose-ul:my-4 prose-li:my-1">
                              <ReactMarkdown>
                                {selectedDeal.rag_advice
                                  ?.replace(/([^\n])\n([^\n])/g, '$1\n\n$2') 
                                  ?.replace(/(\n)?(\*\*\d+\.|\d+\.)/g, '\n\n$2')}
                              </ReactMarkdown>
                            </div>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-full py-20 text-center opacity-70">
                            <Clock className="w-12 h-12 text-slate-600 mb-4" />
                            <div className="text-[14px] font-black text-slate-400 uppercase tracking-widest mb-2">Analysis Pending</div>
                            <p className="text-slate-500 text-[12px] font-medium max-w-sm">
                              The pitch deck has been received but not yet processed by the RAG system. Run "Sync Inbound" to trigger the pipeline.
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* PDF Tab */}
                    {activeTab === 'pdf' && (
                      <div className="absolute inset-0 bg-[#0b0f1a]/30 flex flex-col">
                        {!selectedDeal.pitch_deck_url ? (
                          <div className="flex flex-col items-center justify-center h-full py-20 text-center opacity-70">
                            <FileText className="w-12 h-12 text-slate-600 mb-4" />
                            <div className="text-[14px] font-black text-slate-400 uppercase tracking-widest mb-2">No Pitch Deck Available</div>
                            <p className="text-slate-500 text-[12px] font-medium max-w-md">
                              There is no Pitch Deck URL associated with this deal in the database.
                            </p>
                          </div>
                        ) : selectedDeal.pitch_deck_url.startsWith('Attached PDF:') ? (
                          <div className="flex flex-col items-center justify-center h-full py-20 text-center opacity-70">
                            <InboxIcon className="w-12 h-12 text-slate-600 mb-4" />
                            <div className="text-[14px] font-black text-slate-400 uppercase tracking-widest mb-2">Local File Unavailable</div>
                            <p className="text-slate-500 text-[12px] font-medium max-w-md">
                              This PDF ({selectedDeal.pitch_deck_url.replace('Attached PDF: ', '')}) was received as a direct email attachment before the live-viewer feature was enabled. Please check your Gmail Inbox to view it.
                            </p>
                          </div>
                        ) : (
                          <>
                            <div className="px-6 py-3 border-b border-white/5 flex items-center justify-between bg-white/[0.02]">
                              <div className="flex items-center gap-2">
                                <FileText className="w-4 h-4 text-blue-400" />
                                <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Document Viewer</span>
                              </div>
                              <a 
                                href={selectedDeal.pitch_deck_url} 
                                target="_blank" 
                                rel="noreferrer"
                                download
                                className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 text-blue-400 text-[9px] font-black uppercase tracking-widest rounded-lg transition-all cursor-pointer"
                              >
                                Download PDF
                              </a>
                            </div>
                            <iframe 
                              src={
                                selectedDeal.pitch_deck_url.includes('drive.google.com') 
                                  ? selectedDeal.pitch_deck_url.replace(/\/view.*$/, '/preview')
                                  : selectedDeal.pitch_deck_url
                              } 
                              title="Pitch Deck Viewer" 
                              className="flex-1 w-full h-full border-none bg-white" 
                            />
                          </>
                        )}
                      </div>
                    )}

                  </div>
                </div>

              </div>
            ) : (
              <div className="flex items-center justify-center h-full text-slate-600 font-black uppercase tracking-widest text-[11px]">
                Select a deal from the list to view intelligence
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  );
};

export default DealIntelligence;
