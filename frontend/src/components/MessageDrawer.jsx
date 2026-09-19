import React from 'react';
import { Mail, Loader2, ShieldAlert, Sparkles, X, RefreshCw } from 'lucide-react';
import { sanitizeHtml } from '../utils/sanitizeHtml';

const renderEmailContent = (content) => {
  if (!content) return null;
  const isHtml = /<[a-z][\s\S]*>/i.test(content);
  if (isHtml) {
    return <div className="email-html-content" dangerouslySetInnerHTML={{ __html: sanitizeHtml(content) }} />;
  }
  const renderLine = (text) => {
    const parts = text.split(/(\*[^*]+\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('*') && part.endsWith('*')) {
        return <strong key={i} className="font-black text-blue-400">{part.slice(1, -1)}</strong>;
      }
      return part;
    });
  };
  const lines = content.trim().split('\n');
  return lines.map((line, idx) => {
    const trimmedLine = line.trim();
    const isQuote = trimmedLine.startsWith('>');
    let cleanLine = line;
    if (isQuote) {
      cleanLine = line.replace(/^\s*> ?/, '');
    }
    if (isQuote) {
      return (
        <div key={idx} className="pl-4 border-l-2 border-slate-700 text-slate-500 my-1 py-0.5">
          {renderLine(cleanLine)}
        </div>
      );
    }
    return <div key={idx} className="min-h-[1.5em]">{renderLine(cleanLine)}</div>;
  });
};

const formatIST = (dateStr, short) => {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (short) {
      return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' });
    }
    return d.toLocaleDateString('en-IN', { timeZone: 'Asia/Kolkata', day: '2-digit', month: 'short', year: 'numeric' })
      + ', ' + d.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: true })
      + ' IST';
  } catch { return dateStr; }
};

const MessageDrawer = React.memo(({ selectedMsg, msgDetail, loadingDetail, onRefresh, onClose, onGoogleLink }) => {
  if (!selectedMsg) return null;

  return (
    <div className="fixed inset-0 z-[500] flex justify-end animate-in fade-in duration-300" role="dialog" aria-label="Message detail">
      <div className="absolute inset-0 bg-slate-950/40 backdrop-blur-md" onClick={onClose}></div>
      <div className="relative w-full max-w-[600px] bg-[#0b0f1a] border-l border-white/5 shadow-[0_0_80px_rgba(0,0,0,0.9)] flex flex-col h-full animate-in slide-in-from-right duration-700 ease-[cubic-bezier(0.2,0.8,0.2,1)]">
        <div className="p-8 border-b border-white/[0.03] flex items-center justify-between bg-gradient-to-r from-blue-500/[0.02] to-transparent">
          <div className="flex items-center gap-5">
            <div className="w-14 h-14 rounded-[20px] bg-gradient-to-br from-blue-600/20 to-indigo-600/20 border border-blue-500/10 flex items-center justify-center text-blue-400">
              <Mail size={26} strokeWidth={1.5} />
            </div>
            <div>
              <h2 className="text-[20px] font-black text-white tracking-tight leading-none mb-2">Message Intelligence</h2>
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></div>
                <p className="text-[10px] font-black text-slate-500 uppercase tracking-[4px]">SECURE CHANNEL</p>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={onRefresh} className="p-4 bg-white/5 hover:bg-white/10 rounded-2xl transition-all text-slate-400 hover:text-white active:scale-95 border border-white/5 cursor-pointer" title="Reload Message Content" aria-label="Reload message content">
              <RefreshCw size={20} className={loadingDetail ? 'animate-spin' : ''} />
            </button>
            <button onClick={onClose} aria-label="Close message" className="p-4 bg-rose-500/10 hover:bg-rose-500/20 rounded-2xl transition-all text-rose-500 hover:text-rose-400 active:scale-95 shadow-xl border border-rose-500/10 cursor-pointer">
              <X size={20} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-10 bg-gradient-to-b from-transparent to-[#080b13]">
          {loadingDetail ? (
            <div className="space-y-12">
              <div className="space-y-4">
                <div className="h-10 w-[70%] bg-white/5 rounded-2xl animate-pulse"></div>
                <div className="h-6 w-[40%] bg-white/5 rounded-2xl animate-pulse delay-75"></div>
              </div>
              <div className="pt-12 border-t border-white/5 space-y-6">
                <div className="h-4 w-full bg-white/5 rounded-full animate-pulse"></div>
                <div className="h-4 w-full bg-white/5 rounded-full animate-pulse delay-100"></div>
                <div className="h-4 w-[60%] bg-white/5 rounded-full animate-pulse delay-200"></div>
              </div>
            </div>
          ) : (
            <div className="animate-in fade-in slide-in-from-bottom-6 duration-700">
              <div className="mb-12">
                <div className="text-[10px] font-black text-blue-500 uppercase tracking-[6px] mb-6">Verified Transmission</div>
                <h1 className="text-[32px] font-black text-white leading-[1.1] mb-10 tracking-tighter drop-shadow-lg">{msgDetail?.subject}</h1>
                <div className="flex items-center justify-between p-6 bg-white/[0.02] border border-white/5 rounded-[32px]">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center text-white font-black shadow-lg">
                      {msgDetail?.from[0]}
                    </div>
                    <div>
                      <div className="text-[14px] font-black text-white">{msgDetail?.from.split('<')[0]}</div>
                      <div className="text-[10px] font-bold text-slate-600 uppercase tracking-widest leading-none mt-1">{msgDetail?.from.split('<')[1]?.replace('>', '')}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[13px] font-black text-blue-400 tabular-nums">{formatIST(msgDetail?.date)}</div>
                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest mt-1">IST Timestamp</div>
                  </div>
                </div>
              </div>

              <div className="pt-10 mb-20">
                <div className="bg-[#0f172a] p-10 rounded-[40px] shadow-2xl overflow-hidden border border-white/5">
                  <div className="text-slate-300 whitespace-pre-wrap break-words text-[15px] leading-[1.8] font-sans email-content-container">
                    {renderEmailContent(msgDetail?.body)}
                  </div>
                  {!msgDetail?.body && (
                    <div className="py-10 text-center opacity-40 italic text-sm text-slate-400">
                      No message content available in this format.
                    </div>
                  )}
                </div>
                {msgDetail?.is_restricted && (
                  <div className="mt-8 p-8 bg-amber-500/10 border border-amber-500/20 rounded-[32px] flex flex-col gap-6 shadow-2xl">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-2xl bg-amber-500/20 flex items-center justify-center text-amber-500 shadow-inner">
                        <ShieldAlert size={24} />
                      </div>
                      <div>
                        <div className="text-[11px] font-black text-amber-200 uppercase tracking-[4px] leading-none mb-1">Intelligence Restricted</div>
                        <p className="text-[12px] text-amber-200/50 font-medium">Full email body requires re-authorization.</p>
                      </div>
                    </div>
                    <button onClick={onGoogleLink} className="w-full py-4 bg-amber-500 hover:bg-amber-400 text-slate-950 text-[11px] font-black uppercase tracking-[4px] rounded-2xl transition-all shadow-xl shadow-amber-500/20 active:scale-95 cursor-pointer">
                      Fix Gmail Permissions Now
                    </button>
                  </div>
                )}
              </div>

              <div className="p-10 bg-gradient-to-r from-blue-600/10 to-indigo-600/10 border border-white/10 rounded-[40px] flex flex-col sm:flex-row items-center justify-between gap-8 mb-10 relative overflow-hidden group">
                <div className="relative z-10">
                  <h4 className="text-white font-black text-xl mb-1 tracking-tight">Warp <span className="text-blue-500 italic">Reply</span></h4>
                  <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Generate intelligent, context-aware email responses in seconds.</p>
                </div>
                <button className="relative z-10 px-8 py-4 bg-white text-slate-950 font-black text-[11px] uppercase tracking-[3px] rounded-2xl transition-all hover:scale-105 active:scale-95 shadow-2xl cursor-pointer">
                  Initialize Draft
                </button>
                <Sparkles className="absolute -right-4 -bottom-4 w-32 h-32 text-blue-500/10 group-hover:scale-110 transition-transform duration-1000" />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default MessageDrawer;
