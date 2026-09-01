import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ChevronLeft, Loader2, Save, Send, X, Sparkles, Shield, Type, CheckCircle2, AlertCircle, FileText, ExternalLink } from 'lucide-react';
import api from '../services/api';
import { sanitizeHtml } from '../utils/sanitizeHtml';
import ToolbarTextarea from '../components/ToolbarTextarea';

const convertHTMLToMarkdown = (html) => {
  if (!html) return '';
  let text = html;
  text = text.replace(/<p[^>]*>/gi, '');
  text = text.replace(/<\/p>/gi, '\n\n');
  text = text.replace(/<br\s*\/?>/gi, '\n');
  text = text.replace(/<ul[^>]*>/gi, '');
  text = text.replace(/<\/ul>/gi, '\n');
  text = text.replace(/<li[^>]*>(.*?)<\/li>/gi, '* $1\n');
  text = text.replace(/<(b|strong)[^>]*>(.*?)<\/\1>/gi, '**$2**');
  text = text.replace(/<(i|em)[^>]*>(.*?)<\/\1>/gi, '_$2_');
  text = text.replace(/<a\s+(?:[^>]*?\s+)?href=["']([^"']*)["'][^>]*>(.*?)<\/a>/gi, '[$2]($1)');
  text = text.replace(/<[^>]+>/g, '');
  const textArea = document.createElement('textarea');
  textArea.innerHTML = text;
  return textArea.value.trim();
};

const renderEmailPreview = (text) => {
  if (!text) return 'Start typing to see preview...';
  // Extract row/col padding from data attributes
  let _rowPad = '1';
  let _colPad = '4';
  if (text && /data-row-pad="([^"]+)"/i.test(text)) {
    const m = text.match(/data-row-pad="([^"]+)"/i);
    if (m) _rowPad = m[1];
  }
  if (text && /data-col-pad="([^"]+)"/i.test(text)) {
    const m = text.match(/data-col-pad="([^"]+)"/i);
    if (m) _colPad = m[1];
  }
  const paragraphs = text.split('\n\n');
  let htmlParts = [];
  paragraphs.forEach(p => {
    const trimmed = p.trim();
    if (!trimmed) return;
    const lines = trimmed.split('\n');
    if (lines.some(l => /^\s*[*\-•]\s+/.test(l))) {
      let listHtml = '<ul style="margin: 0.8em 0; padding-left: 0; list-style: none;">';
      lines.forEach(l => {
        const match = l.trim().match(/^[*\-•]\s+(.*)/);
        if (match) {
          listHtml += `<li style="margin-bottom: 0.4em; position: relative; padding-left: 14px; line-height: 1.6; color: #cbd5e1;"><span style="position: absolute; left: 0; color: #94a3b8; font-size: 9px; top: 0px; display: inline-block; vertical-align: middle;">•</span>${match[1].trim()}</li>`;
        } else {
          listHtml += ` ${l.trim()}`;
        }
      });
      listHtml += '</ul>';
      htmlParts.push(listHtml);
    } else if (lines.length >= 2 && lines.every(l => !l.trim() || (l.trim().startsWith('|') && l.trim().endsWith('|')))) {
      let tableHtml = '<table border="1" bordercolor="#999" style="width:100%;border-collapse:collapse;margin-bottom:12px;font-family:sans-serif;">';
      const dataLines = lines.filter(l => l.trim() && !l.trim().match(/^\|[-:\s]+\|$/));
      dataLines.forEach((line, i) => {
        const cells = line.trim().split('|').slice(1, -1).map(c => c.trim());
        const tag = i === 0 ? 'th' : 'td';
        const cellStyle = tag === 'th'
          ? `border:1px solid #999;padding:${_rowPad}px ${_colPad}px;text-align:left;font-weight:700;`
          : `border:1px solid #999;padding:${_rowPad}px ${_colPad}px;text-align:left;`;
        const cellHtml = cells.map(c => `<${tag} style="${cellStyle}">${c}</${tag}>`).join('');
        tableHtml += `<tr>${cellHtml}</tr>`;
      });
      tableHtml += '</table>';
      htmlParts.push(tableHtml);
    } else {
      const content = trimmed.replace(/\n/g, '<br />');
      htmlParts.push(`<p style="margin-bottom: 1.2em; color: #cbd5e1; line-height: 1.6;">${content}</p>`);
    }
  });
  let finalHtml = htmlParts.join('');
  finalHtml = finalHtml
    .replace(/\*\*\*(.*?)\*\*\*/g, '<strong style="color: white; font-weight: 800;"><em>$1</em></strong>')
    .replace(/\*\*(.*?)\*\*/g, '<strong style="color: white; font-weight: 800;">$1</strong>')
    .replace(/_(.*?)_/g, '<em style="font-style:italic">$1</em>')
    .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 700;">$1</a>');
  // Force border-collapse + border="1" on any existing HTML tables
  finalHtml = finalHtml.replace(/<table(\s[^>]*)?>/gi, (m) => {
    let attrs = m;
    if (!/border-collapse/i.test(attrs)) {
      if (attrs.includes('style="')) {
        attrs = attrs.replace(/style="([^"]*)"/, (_, s) => `style="border-collapse:collapse;${s}"`);
      } else {
        attrs = attrs.replace('>', ' style="border-collapse:collapse;">');
      }
    }
    if (!/border="/i.test(attrs)) attrs = attrs.replace('<table', '<table border="1" bordercolor="#999"');
    return attrs;
  });
  finalHtml = finalHtml.replace(/<(th|td)(\s[^>]*)?>/gi, (m) => {
    if (/border/i.test(m)) return m;
    if (m.includes('style="')) return m.replace(/style="([^"]*)"/, (_, s) => `style="border:1px solid #999;${s}"`);
    return m.replace(/>$/, ' style="border:1px solid #999;">');
  });
  return finalHtml;
};

const GmailDraftEdit = () => {
  const { draftId } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [aiInstruction, setAiInstruction] = useState('');
  const [notification, setNotification] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchDraft = async () => {
    setIsLoading(true);
    try {
      const res = await api.get(`/api/gmail/message/${draftId}`);
      const data = res.data;
      setDraft(data);
      setSubject(data.subject || '');
      const cleanBody = convertHTMLToMarkdown(data.body || data.snippet || '');
      setBody(cleanBody);
    } catch (err) {
      console.error('Failed to fetch Gmail draft:', err);
      showNotification('error', 'Failed to load draft');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDraft();
  }, [draftId]);

  const handleUpdateDraft = async () => {
    setIsSaving(true);
    try {
      await api.post(`/api/gmail/update-draft/${draftId}`, { subject, body });
      showNotification('success', 'Draft synced to Gmail');
    } catch (err) {
      showNotification('error', 'Failed to update draft');
    } finally {
      setIsSaving(false);
    }
  };

  const handleSendDraft = async () => {
    if (!window.confirm('Send this draft now via Gmail?')) return;
    setIsProcessing(true);
    try {
      await api.post(`/api/gmail/send-draft/${draftId}`);
      showNotification('success', 'Email sent successfully via Gmail');
      setTimeout(() => navigate('/dashboard/gmail-drafts'), 1500);
    } catch (err) {
      showNotification('error', 'Failed to send: ' + (err?.response?.data?.detail || err?.message || 'Unknown error'));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAIRefine = async (action) => {
    setIsProcessing(true);
    try {
      const res = await api.post('/api/gmail/ai-refine', { content: body, action });
      setBody(res.data.refined);
      showNotification('success', `AI ${action} applied`);
    } catch (_err) {
      showNotification('error', 'AI refinement failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAIRefineCustom = async () => {
    if (!aiInstruction) return;
    setIsProcessing(true);
    try {
      const res = await api.post('/api/gmail/ai-refine', { content: body, action: aiInstruction });
      setBody(res.data.refined);
      setAiInstruction('');
      showNotification('success', 'AI refinement applied');
    } catch (_err) {
      showNotification('error', 'AI refinement failed');
    } finally {
      setIsProcessing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center">
        <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading Gmail Draft...</p>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-500 min-h-screen bg-[#0a0f1a] pb-20 p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/dashboard/gmail-drafts')} className="px-3 py-1.5 flex items-center gap-1.5 rounded-md bg-[#131722] border border-[#ffffff10] text-slate-300 hover:text-white transition-colors text-[11px] font-bold cursor-pointer">
          <ChevronLeft className="w-3.5 h-3.5" /> Back
        </button>
        <div>
          <h1 className="text-[20px] font-bold text-white tracking-tight">Edit Gmail Draft</h1>
          <p className="text-[#64748b] text-[12px] font-medium mt-0.5">
            To: {draft?.to || 'Unknown'} {draft?.snippet ? `— ${draft.snippet.substring(0, 60)}...` : ''}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        {/* Left: Editor Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
          <div className="px-6 py-4 border-b border-[#ffffff08] flex items-center gap-2 bg-[#0f121b]/50">
            <span className="text-blue-400 text-sm">📧</span>
            <h3 className="text-white font-bold text-[13px] tracking-wide">Gmail Editor</h3>
          </div>

          <div className="p-6 flex-1 flex flex-col gap-6">
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-slate-400">Subject</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Enter email subject..."
                className="w-full bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white font-medium outline-none focus:border-blue-500/50"
              />
            </div>

            <div className="space-y-2 flex-1 flex flex-col">
              <label className="text-[11px] font-medium text-slate-400">Body</label>
              <div className="flex-1 min-h-[320px] rounded-md bg-[#0a0f1a] border border-[#ffffff10] overflow-y-auto custom-scrollbar">
                <ToolbarTextarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={16}
                  placeholder="Write your email here... Use the toolbar for formatting."
                />
              </div>
            </div>

            {/* AI Refinement */}
            <div className="space-y-4 pt-4">
              <div className="relative flex items-center bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-3 py-1 focus-within:border-blue-500/50 transition-colors">
                <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                <input
                  type="text"
                  value={aiInstruction}
                  onChange={(e) => setAiInstruction(e.target.value)}
                  placeholder="Edit with AI (e.g., 'Make it shorter', 'Add ROI data'...)"
                  className="flex-1 bg-transparent border-none text-[12px] text-slate-300 px-3 py-2 outline-none italic placeholder-slate-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleAIRefineCustom()}
                />
                <button
                  onClick={handleAIRefineCustom}
                  disabled={isProcessing || !aiInstruction}
                  className="bg-[#10b981] hover:bg-emerald-500 text-white text-[11px] font-bold px-4 py-1.5 rounded-md transition-colors disabled:opacity-50 flex items-center shadow-lg shadow-emerald-500/20 cursor-pointer"
                >
                  {isProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : ''}
                  {isProcessing ? 'Refining...' : 'Refine'}
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button onClick={() => handleAIRefine('professional')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors flex items-center gap-1.5">
                  <Shield className="w-3 h-3" /> Professional
                </button>
                <button onClick={() => handleAIRefine('shorten')} className="cursor-pointer px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors flex items-center gap-1.5">
                  <Type className="w-3 h-3" /> Concise
                </button>
              </div>

              <div className="pt-6 flex items-center gap-4">
                <button
                  onClick={handleUpdateDraft}
                  disabled={isSaving}
                  className="bg-[#1e293b] hover:bg-[#334155] text-white text-[12px] font-bold px-5 py-2.5 rounded-md transition-colors disabled:opacity-50 flex items-center border border-[#ffffff10] cursor-pointer shrink-0"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  Sync to Gmail
                </button>
                <button
                  onClick={handleSendDraft}
                  disabled={isProcessing}
                  className="flex-1 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white text-[12px] font-black uppercase tracking-widest px-4 py-2.5 rounded-md transition-all shadow-lg shadow-red-500/20 flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Send Now
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Preview Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
          {/* Preview Header */}
          <div className="p-6 border-b border-[#ffffff08] bg-[#0a0f1a]">
            <div className="flex justify-between items-start">
              <div className="flex gap-4 items-center">
                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">
                  {draft?.to?.charAt(0)?.toUpperCase() || '?'}
                </div>
                <div>
                  <h3 className="text-white font-bold text-[15px]">{draft?.to || 'Unknown Recipient'}</h3>
                  <p className="text-[12px] text-[#94a3b8] font-medium mt-0.5">Gmail Draft</p>
                </div>
              </div>
              <div className="text-right flex flex-col items-end gap-1">
                <span className="text-[#64748b] text-[9px] font-black uppercase tracking-[2px]">PLATFORM</span>
                <span className="text-red-400 text-[11px] font-black uppercase tracking-widest flex items-center gap-1">
                  <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                  Gmail
                </span>
              </div>
            </div>
          </div>

          {/* Preview Body */}
          <div className="p-8 flex-1 bg-[#131722] overflow-y-auto w-full custom-scrollbar">
            <div className="w-full space-y-8">
              <div className="text-[13px]">
                <span className="text-[#94a3b8] font-medium mr-2">Subject:</span>
                <span className={`font-bold ${subject ? 'text-blue-400' : 'text-slate-600 italic text-[11px]'}`}>
                  {subject || '(No subject)'}
                </span>
              </div>

              <div
                className={`text-[13px] leading-relaxed font-medium ${body ? 'text-slate-300' : 'text-slate-600 italic text-[11px]'}`}
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(renderEmailPreview(body)) }}
              />

              {/* Mock Attachment */}
              <div className="pt-10 mt-10 border-t border-[#ffffff05]">
                <div className="flex items-center gap-2 mb-4">
                  <span className="text-[#64748b] text-[10px] font-black uppercase tracking-[2px]">Shared Assets</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 opacity-40 grayscale">
                  <div className="flex items-center gap-3 p-3 rounded-lg bg-[#0a0f1a] border border-[#ffffff08]">
                    <FileText className="w-5 h-5 text-slate-500" />
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold text-slate-400 truncate">Pitch_Deck.pdf</p>
                      <p className="text-[8px] text-slate-600 font-bold uppercase">Stored in Gmail</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Preview Footer */}
          <div className="p-6 border-t border-[#ffffff08] bg-[#0a0f1a]">
            <div className="space-y-3 max-w-[400px]">
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px]">
                <span className="text-[#64748b] font-medium">Status</span>
                <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-[1px] text-amber-500 w-max">GMAIL DRAFT</span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Recipient</span>
                <span className="text-white">{draft?.to || '—'}</span>
              </div>
              <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                <span className="text-[#64748b]">Open in Gmail</span>
                <a href="https://mail.google.com/mail/u/0/#drafts" target="_blank" rel="noreferrer" className="text-blue-400 hover:underline flex items-center gap-1">
                  Gmail Drafts <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Notification Toast */}
      {notification && (
        <div className="fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4">
          <div className={`px-6 py-4 rounded-xl shadow-2xl border backdrop-blur-md flex items-center gap-3 ${notification.type === 'success' ? 'bg-[#10b981]/10 border-[#10b981]/20 text-[#10b981]' : 'bg-red-500/10 border-red-500/20 text-red-500'}`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="font-bold text-[13px]">{notification.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default GmailDraftEdit;
