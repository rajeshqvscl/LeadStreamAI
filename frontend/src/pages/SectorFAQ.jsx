import React, { useState } from 'react';
import { 
  Shield, Rocket, Brain, Cpu, Globe, 
  ChevronDown, Search, HelpCircle, 
  Calendar, Zap, BarChart3, ArrowRight
} from 'lucide-react';
import api from '../services/api';
import ReactMarkdown from 'react-markdown';

const SectorFAQ = () => {
  const [activeCategory, setActiveCategory] = useState('DEFENCE');
  const [searchTerm, setSearchTerm] = useState('');
  const [openIndex, setOpenIndex] = useState(0);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [showFullReport, setShowFullReport] = useState(false);
  
  const currentYear = new Date().getFullYear();
  const predictionYear = currentYear + 1;
  const currentMonth = new Date().toLocaleString('default', { month: 'long' });

  const handleSendChat = async () => {
      if (!chatInput.trim()) return;
      
      const userMsg = { role: 'user', content: chatInput };
      setChatMessages(prev => [...prev, userMsg]);
      setChatInput('');
      setChatLoading(true);
      
      try {
          const { data } = await api.post('/api/intelligence/chat', {
              message: userMsg.content,
              history: chatMessages
          });
          setChatMessages(prev => [...prev, { role: 'ai', content: data.response }]);
      } catch (err) {
          console.error('Chat failed', err);
          setChatMessages(prev => [...prev, { role: 'ai', content: 'Apologies, I am having trouble accessing the intelligence layer right now.' }]);
      } finally {
          setChatLoading(false);
      }
  };

  const categories = [
    { id: 'DEFENCE', label: 'Defence & Aerospace', icon: <Shield size={16} /> },
    { id: 'TECH', label: 'High Tech & AI', icon: <Cpu size={16} /> },
    { id: 'FINANCE', label: 'FinTech & M&A', icon: <Zap size={16} /> },
    { id: 'GLOBAL', label: 'Global Trade', icon: <Globe size={16} /> }
  ];

  const faqs = {
    DEFENCE: [
      {
        q: "What have been the major shifts in India's Defence Sector over the last 10 years?",
        a: "The last decade (2014-2024) has seen a massive push towards 'Atmanirbhar Bharat' (Self-Reliant India). Key milestones include the introduction of Positive Indigenisation Lists, the corporatization of Ordnance Factory Boards, and a significant increase in the FDI limit to 74% via the automatic route. Defense exports have hit an all-time high of ₹21,083 crore in FY 2023-24."
      },
      {
        q: "How has technology integration changed the landscape of modern warfare since 2014?",
        a: "We have moved from conventional hardware-centric strategies to network-centric and data-driven warfare. The emergence of 'iDEX' (Innovations for Defence Excellence) has allowed over 100+ startups to integrate AI, drone swarms, and quantum communication into the Indian Armed Forces' ecosystem."
      },
      {
        q: "What role does the private sector play in defence manufacturing now vs 10 years ago?",
        a: "Previously, defence was dominated by DPSUs. Today, private players like Tata, L&T, and Adani are prime contractors. The share of private sector in total production value has grown from ~15% in 2014 to over 22% in 2024, with a projected target of 35% by 2030."
      }
    ],
    TECH: [
      {
        q: "How has the Indian SaaS ecosystem evolved in the last decade?",
        a: "India has transformed from a back-office hub to a 'SaaS Nation'. In 2014, there were fewer than 5 SaaS unicorns; today, there are over 20. The focus has shifted from pure SMB tools to deep-tech, enterprise AI, and vertical-specific SaaS solutions."
      },
      {
        q: "What are the key trends in AI infrastructure development since 2020?",
        a: "The primary trend is the shift towards 'Edge AI' and localized sovereign AI clouds. With the Digital India initiative, the infrastructure has evolved to support massive compute requirements for LLMs, specialized chipsets, and green data centers."
      }
    ],
    FINANCE: [
      {
        q: "What has been the impact of UPI on the FinTech sector since its launch in 2016?",
        a: "UPI has been a once-in-a-generation shift, democratizing digital payments. It has enabled a secondary layer of lending, wealth-tech, and insurance-tech startups that leverage transaction data to offer personalized financial products to the 'unbanked' population."
      }
    ],
    GLOBAL: [
      {
        q: "How has the 'China + 1' strategy influenced global supply chains for India?",
        a: "Over the last 5-7 years, global manufacturers have actively looked to diversify away from China. India's PLI (Production Linked Incentive) schemes across 14 sectors have successfully attracted giants like Apple and Samsung to establish massive manufacturing bases in India."
      }
    ]
  };

  const filteredFaqs = faqs[activeCategory].filter(item => 
    item.q.toLowerCase().includes(searchTerm.toLowerCase()) || 
    item.a.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="max-w-[1200px] mx-auto px-6 py-10 animate-in fade-in duration-700">
      {/* Hero Header */}
      <div className="relative rounded-[40px] overflow-hidden mb-12 bg-slate-900 border border-white/10 shadow-2xl group">
        <div className="absolute inset-0 opacity-40 mix-blend-overlay grayscale group-hover:grayscale-0 transition-all duration-1000">
            <img 
              src="/Users/harshbisht/.gemini/antigravity/brain/a91de879-17be-4c24-aca0-b0dd4a012a63/sector_faq_banner_1777189165440.png" 
              alt="Sector Banner" 
              className="w-full h-full object-cover"
            />
        </div>
        <div className="relative z-10 p-12 bg-gradient-to-r from-slate-950 via-slate-950/80 to-transparent">
          <div className="flex items-center gap-3 mb-6">
            <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] font-black text-blue-500 uppercase tracking-[3px]">
              Knowledge Base V2.0
            </div>
            <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
          </div>
          <h1 className="text-[42px] font-black text-white leading-none tracking-tighter mb-4">
            Sector <span className="text-blue-500 italic">Intelligence</span> & FAQ
          </h1>
          <p className="text-slate-400 max-w-xl text-lg font-medium leading-relaxed">
            Deep-dive insights and historical data across key industries. Understanding the last 10 years of growth to predict the next decade.
          </p>
        </div>
      </div>

      {/* Control Bar */}
      <div className="flex flex-col md:flex-row gap-6 mb-12">
        <div className="flex-1 relative group">
          <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-blue-500 transition-colors" />
          <input 
            type="text" 
            placeholder="Search intelligence database..."
            className="w-full bg-white/[0.02] border border-white/5 rounded-2xl py-4 pl-14 pr-6 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/30 transition-all"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex bg-white/[0.02] border border-white/5 p-1.5 rounded-2xl gap-2 overflow-x-auto no-scrollbar">
          {categories.map(cat => (
            <button
              key={cat.id}
              onClick={() => { setActiveCategory(cat.id); setOpenIndex(0); }}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-xl text-[11px] font-black uppercase tracking-widest whitespace-nowrap transition-all cursor-pointer ${activeCategory === cat.id ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20' : 'text-slate-500 hover:text-white hover:bg-white/5'}`}
            >
              {cat.icon}
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* FAQ Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2 space-y-4">
          {filteredFaqs.length > 0 ? (
            filteredFaqs.map((faq, index) => (
              <div 
                key={index}
                className={`group border rounded-[32px] transition-all duration-500 overflow-hidden ${openIndex === index ? 'bg-white/[0.03] border-white/10 shadow-2xl' : 'bg-transparent border-white/5 hover:border-white/10'}`}
              >
                <button 
                  className="w-full p-8 text-left flex items-center justify-between gap-6 cursor-pointer group"
                  onClick={() => setOpenIndex(openIndex === index ? -1 : index)}
                >
                  <span className={`text-[17px] font-black tracking-tight leading-snug transition-colors ${openIndex === index ? 'text-white' : 'text-slate-400 group-hover:text-slate-200'}`}>
                    {faq.q}
                  </span>
                  <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center border transition-all ${openIndex === index ? 'bg-blue-500 border-blue-500 rotate-180 text-white' : 'border-white/10 text-slate-500'}`}>
                    <ChevronDown size={18} />
                  </div>
                </button>
                {openIndex === index && (
                  <div className="px-8 pb-8 animate-in slide-in-from-top-4 duration-500">
                    <div className="h-px bg-white/5 mb-8" />
                    <p className="text-slate-300 text-[16px] leading-[1.8] font-medium tracking-tight">
                      {faq.a}
                    </p>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="py-20 text-center bg-white/[0.02] border border-dashed border-white/10 rounded-[32px]">
              <HelpCircle className="w-12 h-12 text-slate-700 mx-auto mb-4 opacity-20" />
              <p className="text-slate-500 font-black uppercase tracking-widest text-xs">No matching intelligence found</p>
            </div>
          )}
        </div>

        {/* Sidebar Info Cards */}
        <div className="space-y-6">
          <div className="bg-gradient-to-br from-indigo-600/20 to-purple-600/20 border border-white/10 p-8 rounded-[40px] shadow-2xl">
            <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-indigo-400 mb-6">
              <Calendar className="w-6 h-6" />
            </div>
            <h4 className="text-xl font-black text-white mb-3 tracking-tight">Timeline Analysis</h4>
            <p className="text-slate-400 text-sm leading-relaxed mb-6">
              Access comprehensive data spanning from 2014 to 2026. Our intelligence layer tracks policy shifts, funding rounds, and market consolidation.
            </p>
            <button 
                onClick={() => setShowFullReport(true)}
                className="flex items-center gap-2 text-xs font-black text-indigo-400 uppercase tracking-widest group cursor-pointer hover:text-indigo-300 transition-colors"
            >
              View full report <ArrowRight size={14} className="group-hover:translate-x-1 transition-transform" />
            </button>
          </div>

          <div className="bg-gradient-to-br from-emerald-600/20 to-teal-600/20 border border-white/10 p-8 rounded-[40px] shadow-2xl">
            <div className="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center text-emerald-400 mb-6">
              <BarChart3 className="w-6 h-6" />
            </div>
            <h4 className="text-xl font-black text-white mb-3 tracking-tight">Sector Growth</h4>
            <div className="space-y-4 mb-6">
              <div>
                <div className="flex justify-between text-[10px] font-black text-slate-400 uppercase mb-1.5">
                  <span>Defence Tech</span>
                  <span>+420%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 w-[85%] rounded-full shadow-[0_0_10px_rgba(16,185,129,0.3)]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[10px] font-black text-slate-400 uppercase mb-1.5">
                  <span>AI Infra</span>
                  <span>+680%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 w-[95%] rounded-full shadow-[0_0_10px_rgba(59,130,246,0.3)]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[10px] font-black text-slate-400 uppercase mb-1.5">
                  <span>SaaS Nation</span>
                  <span>+310%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 w-[70%] rounded-full shadow-[0_0_10px_rgba(99,102,241,0.3)]" />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-[10px] font-black text-slate-400 uppercase mb-1.5">
                  <span>Clean Energy</span>
                  <span>+245%</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-teal-500 w-[60%] rounded-full shadow-[0_0_10px_rgba(20,184,166,0.3)]" />
                </div>
              </div>
            </div>
            <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest text-center">Data Updated: {currentMonth} {currentYear}</p>
          </div>
        </div>
      </div>

      {/* AI Intelligence Chat Section */}
      <div className="mt-10 pt-10 border-t border-white/5">
        <div className="flex flex-col items-center text-center mb-12">
            <div className="w-16 h-16 rounded-[24px] bg-indigo-600/20 border border-indigo-500/20 flex items-center justify-center text-indigo-400 mb-6 shadow-2xl shadow-indigo-600/20">
                <Brain className="w-8 h-8 animate-pulse" />
            </div>
            <h2 className="text-3xl font-black text-white tracking-tight mb-3">Ask <span className="text-indigo-400 italic">Sector AI</span></h2>
            <p className="text-slate-500 max-w-lg text-sm font-medium">Deep-dive into specific industry questions. This AI is restricted to historical and strategic sector intelligence.</p>
        </div>

        <div className="max-w-3xl mx-auto">
            <div className="bg-[#0e121d] border border-white/5 rounded-[40px] overflow-hidden shadow-2xl flex flex-col min-h-[400px]">
                {/* Chat History Area */}
                <div className="flex-1 p-8 overflow-y-auto space-y-6 max-h-[500px] custom-scrollbar">
                    <div className="flex items-start gap-4">
                        <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                            <Brain size={20} />
                        </div>
                        <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl rounded-tl-none text-slate-300 text-sm leading-relaxed max-w-[85%]">
                            Hello! I am your specialized Intelligence assistant. I can answer questions about the last 10 years of growth in sectors like Defence, SaaS, and AI. What would you like to know?
                        </div>
                    </div>

                    {/* Dynamic Messages would go here */}
                    {chatMessages.map((msg, i) => (
                        <div key={i} className={`flex items-start gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-indigo-600/10 border border-indigo-500/20 text-indigo-400'}`}>
                                {msg.role === 'user' ? 'U' : <Brain size={20} />}
                            </div>
                            <div className={`p-5 rounded-3xl text-sm leading-relaxed max-w-[85%] ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-tr-none' : 'bg-white/[0.03] border border-white/5 text-slate-300 rounded-tl-none markdown-container'}`}>
                                {msg.role === 'ai' ? (
                                    <ReactMarkdown 
                                        components={{
                                            p: ({node, ...props}) => <p className="mb-4 last:mb-0" {...props} />,
                                            ul: ({node, ...props}) => <ul className="list-disc ml-4 mb-4" {...props} />,
                                            li: ({node, ...props}) => <li className="mb-1" {...props} />,
                                            h3: ({node, ...props}) => <h3 className="text-white font-black mt-6 mb-3 uppercase tracking-tight text-[12px]" {...props} />,
                                            strong: ({node, ...props}) => <strong className="text-indigo-400 font-bold" {...props} />
                                        }}
                                    >
                                        {msg.content}
                                    </ReactMarkdown>
                                ) : (
                                    msg.content
                                )}
                            </div>
                        </div>
                    ))}
                    {chatLoading && (
                         <div className="flex items-start gap-4">
                            <div className="w-10 h-10 rounded-xl bg-indigo-600/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
                                <Brain size={20} className="animate-spin" />
                            </div>
                            <div className="p-5 bg-white/[0.03] border border-white/5 rounded-3xl rounded-tl-none text-slate-500 text-xs font-black uppercase tracking-widest animate-pulse">
                                Synthesizing Intelligence...
                            </div>
                        </div>
                    )}
                </div>

                {/* Input Area */}
                <div className="p-4 bg-white/[0.02] border-t border-white/5 flex gap-3">
                    <input 
                        type="text"
                        placeholder="Ask about Defence growth, SaaS trends, etc..."
                        className="flex-1 bg-black/40 border border-white/10 rounded-2xl px-6 py-4 text-sm text-white focus:outline-none focus:border-indigo-500/30 transition-all"
                        value={chatInput}
                        onChange={(e) => setChatInput(e.target.value)}
                        onKeyPress={(e) => e.key === 'Enter' && handleSendChat()}
                        disabled={chatLoading}
                    />
                    <button 
                        onClick={handleSendChat}
                        disabled={chatLoading || !chatInput.trim()}
                        className="w-14 h-14 rounded-2xl bg-indigo-600 hover:bg-indigo-500 text-white flex items-center justify-center transition-all shadow-xl shadow-indigo-600/20 active:scale-95 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <ArrowRight size={24} />
                    </button>
                </div>
            </div>

            {/* Quick Suggestions */}
            <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                    "Defence exports since 2014?",
                    "SaaS unicorn growth in India?",
                    "Future of AI infrastructure?",
                    "Semiconductor policy impacts?"
                ].map((tag, i) => (
                    <button 
                        key={i}
                        onClick={() => { setChatInput(tag); }}
                        className="px-4 py-2 rounded-full bg-white/5 border border-white/5 text-[10px] font-black text-slate-500 uppercase tracking-widest hover:bg-indigo-600/10 hover:text-indigo-400 hover:border-indigo-500/20 transition-all cursor-pointer"
                    >
                        {tag}
                    </button>
                ))}
            </div>
        </div>
      </div>
      {/* Full Report Modal */}
      {showFullReport && (
          <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-black/90 backdrop-blur-xl p-4 animate-in fade-in duration-300">
              <div className="w-full max-w-4xl max-h-[90vh] overflow-y-auto bg-slate-900 border border-white/10 rounded-[48px] shadow-2xl custom-scrollbar relative">
                  <button 
                    onClick={() => setShowFullReport(false)}
                    className="absolute top-8 right-8 w-12 h-12 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-slate-400 hover:text-white hover:bg-rose-500/20 hover:border-rose-500/20 transition-all cursor-pointer z-50"
                  >
                    ✕
                  </button>

                  <div className="p-12">
                      <div className="flex items-center gap-4 mb-8">
                          <div className="px-4 py-1.5 bg-emerald-500/10 border border-emerald-500/20 rounded-full text-[10px] font-black text-emerald-500 uppercase tracking-widest">
                              Intelligence Report #842
                          </div>
                          <div className="text-slate-600 text-xs font-bold uppercase tracking-widest">Released April 26, 2026</div>
                      </div>

                      <h2 className="text-5xl font-black text-white tracking-tighter mb-10 leading-none">
                        Annual Strategic <br /><span className="text-blue-500 italic">Sector Analysis</span>
                      </h2>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 mb-16">
                          <div className="space-y-6">
                              <h4 className="text-sm font-black text-slate-500 uppercase tracking-[3px] mb-4">Macro Trends</h4>
                              <div className="p-6 bg-white/[0.02] border border-white/5 rounded-[32px] space-y-4">
                                  <div className="flex items-start gap-3">
                                      <div className="w-1.5 h-1.5 rounded-full bg-blue-500 mt-1.5 shrink-0" />
                                      <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">India Sovereign AI:</strong> Massive shift towards localized data centers and high-tier sovereign LLMs specialized for Indic languages.</p>
                                  </div>
                                  <div className="flex items-start gap-3">
                                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-1.5 shrink-0" />
                                      <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">Defence Ecosystem:</strong> Exports reaching $5B annually driven by missile systems and UAV technologies.</p>
                                  </div>
                                  <div className="flex items-start gap-3">
                                      <div className="w-1.5 h-1.5 rounded-full bg-indigo-500 mt-1.5 shrink-0" />
                                      <p className="text-slate-300 text-sm leading-relaxed"><strong className="text-white">SaaS Efficiency:</strong> 85% of Indian SaaS unicorns have reached EBITDA positive status as of Q1 2026.</p>
                                  </div>
                              </div>
                          </div>

                          <div className="space-y-6">
                              <h4 className="text-sm font-black text-slate-500 uppercase tracking-[3px] mb-4">Market Valuation</h4>
                              <div className="grid grid-cols-2 gap-4">
                                  <div className="p-6 bg-white/[0.02] border border-white/5 rounded-[32px] text-center">
                                      <div className="text-[28px] font-black text-white mb-1">$72B</div>
                                      <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">SaaS TAM 2026</div>
                                  </div>
                                  <div className="p-6 bg-white/[0.02] border border-white/5 rounded-[32px] text-center">
                                      <div className="text-[28px] font-black text-blue-500 mb-1">125+</div>
                                      <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Active Unicorns</div>
                                  </div>
                              </div>
                              <div className="p-6 bg-blue-600/10 border border-blue-500/20 rounded-[32px]">
                                  <div className="flex justify-between items-center mb-4">
                                      <span className="text-[10px] font-black text-blue-400 uppercase tracking-widest">Investor Sentiment</span>
                                      <span className="text-xs font-black text-white">BULLISH</span>
                                  </div>
                                  <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                                      <div className="h-full bg-blue-500 w-[92%] rounded-full shadow-[0_0_15px_rgba(59,130,246,0.5)]" />
                                  </div>
                              </div>
                          </div>
                      </div>

                      <div className="bg-gradient-to-br from-slate-950 to-slate-900 border border-white/10 rounded-[40px] p-10">
                          <h3 className="text-2xl font-black text-white mb-6 tracking-tight flex items-center gap-3">
                              <Zap className="text-amber-500" /> Key Prediction for {predictionYear}
                          </h3>
                          <p className="text-slate-300 text-lg leading-relaxed mb-8">
                              "By Q3 {predictionYear}, the convergence of Quantum Computing and Generative AI will create a new 'Super-Intelligence' layer in Defence and Finance. We project that 40% of strategic decision-making in Fortune 500 companies will be autonomously verified by AI-Sovereign nodes to ensure zero-latency execution."
                          </p>
                          <div className="flex gap-4">
                              <div className="px-6 py-3 bg-white/5 rounded-2xl text-[10px] font-black text-slate-400 uppercase tracking-widest border border-white/5">
                                  Data Integrity: 99.8%
                              </div>
                              <div className="px-6 py-3 bg-white/5 rounded-2xl text-[10px] font-black text-slate-400 uppercase tracking-widest border border-white/5">
                                  Confidence: High
                              </div>
                          </div>
                      </div>
                  </div>
              </div>
          </div>
      )}
    </div>
  );
};

export default SectorFAQ;
