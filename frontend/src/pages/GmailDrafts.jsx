import React, { useState, useEffect, useRef } from 'react';
import { Mail, Loader2, RefreshCw, ExternalLink, Calendar, Search, Filter, Edit3, Send, X, Save, Sparkles, Type, Bold, Italic, Wand2, Shield, Zap, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const GmailDrafts = () => {
  const [drafts, setDrafts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingDraft, setEditingDraft] = useState(null);
  const [notification, setNotification] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const editorRef = useRef(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const decodeHTMLEntities = (text) => {
    if (!text) return '';
    const textArea = document.createElement('textarea');
    textArea.innerHTML = text;
    return textArea.value;
  };

  const convertHTMLToMarkdown = (html) => {
    if (!html) return '';
    
    let text = html;
    
    // 1. Handle common block elements
    text = text.replace(/<p[^>]*>/gi, '');
    text = text.replace(/<\/p>/gi, '\n\n');
    text = text.replace(/<br\s*\/?>/gi, '\n');
    
    // 2. Handle lists
    text = text.replace(/<ul[^>]*>/gi, '');
    text = text.replace(/<\/ul>/gi, '\n');
    text = text.replace(/<li[^>]*>(.*?)<\/li>/gi, '* $1\n');
    
    // 3. Handle inline formatting
    text = text.replace(/<(b|strong)[^>]*>(.*?)<\/\1>/gi, '**$2**');
    text = text.replace(/<(i|em)[^>]*>(.*?)<\/\1>/gi, '_$2_');
    
    // 3.5 Handle links (must happen before stripping tags)
    // <a href="url">text</a> -> [text](url)
    text = text.replace(/<a\s+(?:[^>]*?\s+)?href=["']([^"']*)["'][^>]*>(.*?)<\/a>/gi, '[$2]($1)');

    
    // 4. Strip all remaining HTML tags
    text = text.replace(/<[^>]+>/g, '');
    
    // 5. Final decode and trim
    return decodeHTMLEntities(text).trim();
  };

  const fetchGmailDrafts = async (quiet = false) => {
    if (!quiet) setIsLoading(true);
    else setIsRefreshing(true);
    
    try {
      const res = await api.get(`/api/gmail/sync-drafts${quiet ? '?refresh=true' : ''}`);
      setDrafts(res.data);
    } catch (err) {
      console.error('Failed to fetch Gmail drafts:', err);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchGmailDrafts();
  }, []);

  const handleEditClick = async (draft) => {
    setIsProcessing(true);
    try {
        // Fetch full message content instead of just the snippet
        const res = await api.get(`/api/gmail/message/${draft.message_id}`);
        // Convert HTML back to clean Markdown for the editor
        const cleanBody = convertHTMLToMarkdown(res.data.body || draft.snippet);
        setEditingDraft({ ...draft, body: cleanBody });
    } catch (err) {
        console.error('Failed to fetch full draft content:', err);
        setEditingDraft({ ...draft, body: convertHTMLToMarkdown(draft.snippet) });
    } finally {
        setIsProcessing(false);
    }
  };

  const handleUpdateDraft = async () => {
    if (!editingDraft) return;
    setIsProcessing(true);
    try {
      await api.post(`/api/gmail/update-draft/${editingDraft.id}`, {
        subject: editingDraft.subject,
        body: editingDraft.body
      });
      showNotification('success', 'Draft updated on Gmail account');
      setEditingDraft(null);
      fetchGmailDrafts(true);
    } catch (err) {
      showNotification('error', 'Failed to update draft');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleSendDraft = async (draftId) => {
    if (!window.confirm('Are you sure you want to send this draft now?')) return;
    setIsProcessing(true);
    try {
      await api.post(`/api/gmail/send-draft/${draftId}`);
      showNotification('success', 'Email sent successfully via Gmail');
      fetchGmailDrafts(true);
    } catch (err) {
      showNotification('error', 'Failed to send email');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAIRefine = async (action) => {
    if (!editingDraft) return;
    setIsProcessing(true);
    try {
      const res = await api.post('/api/gmail/ai-refine', {
        content: editingDraft.body,
        action: action
      });
      setEditingDraft({ ...editingDraft, body: res.data.refined });
      showNotification('success', `AI ${action} completed!`);
    } catch (err) {
      showNotification('error', 'AI refinement failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const applyFormat = (tag) => {
    const textarea = editorRef.current;
    if (!textarea) return;
    
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = editingDraft.body;
    const selected = text.substring(start, end);
    
    if (!selected) return;

    const before = text.substring(0, start);
    const after = text.substring(end);
    
    let newBody;
    if (tag === 'b') newBody = `${before}**${selected}**${after}`;
    else if (tag === 'i') newBody = `${before}_${selected}_${after}`;
    else newBody = `${before}<${tag}>${selected}</${tag}>${after}`;

    setEditingDraft({ ...editingDraft, body: newBody });
    
    // Reset focus
    setTimeout(() => {
        textarea.focus();
        textarea.setSelectionRange(start, start + newBody.length - before.length - after.length);
    }, 10);
  };

  const renderEmailPreview = (text) => {
    if (!text) return 'Start typing to see preview...';

    // 1. Split into paragraphs
    const paragraphs = text.split('\n\n');
    let htmlParts = [];

    paragraphs.forEach(p => {
      const trimmed = p.trim();
      if (!trimmed) return;

      const lines = trimmed.split('\n');
      
      // Detect lists (must be star/dash/bullet followed by space)
      if (lines.some(l => /^\s*[\*\-•]\s+/.test(l))) {
        let listHtml = '<ul style="margin: 0.8em 0; padding-left: 0; list-style: none;">';
        lines.forEach(l => {
          const match = l.trim().match(/^[\*\-•]\s+(.*)/);
          if (match) {
            listHtml += `<li style="margin-bottom: 0.4em; position: relative; padding-left: 14px; line-height: 1.6; color: #cbd5e1;"><span style="position: absolute; left: 0; color: #94a3b8; font-size: 9px; top: 0px; display: inline-block; vertical-align: middle;">•</span>${match[1].trim()}</li>`;
          } else {
            listHtml += ` ${l.trim()}`;
          }
        });
        listHtml += '</ul>';
        htmlParts.push(listHtml);
      } else if (lines.length >= 2 && lines.every(l => !l.trim() || (l.trim().startsWith('|') && l.trim().endsWith('|')))) {
        let tableHtml = '<table style="width:100%;border-collapse:collapse;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;">';
        const dataLines = lines.filter(l => l.trim() && !l.trim().match(/^\|[-:\s]+\|$/));
        dataLines.forEach((line, i) => {
          const cells = line.trim().split('|').slice(1, -1).map(c => c.trim());
          const tag = i === 0 ? 'th' : 'td';
          const cellStyle = tag === 'th'
            ? 'border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;'
            : 'border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;';
          const cellHtml = cells.map(c => `<${tag} style="${cellStyle}">${c}</${tag}>`).join('');
          tableHtml += `<tr>${cellHtml}</tr>`;
        });
        tableHtml += '</table>';
        htmlParts.push(tableHtml);
      } else {
        // Paragraph: preserve single newlines as line breaks
        const content = trimmed.replace(/\n/g, '<br />');
        htmlParts.push(`<p style="margin-bottom: 1.2em; color: #cbd5e1; line-height: 1.6;">${content}</p>`);
      }
    });

    let finalHtml = htmlParts.join('');

    // 2. Inline Styles (Bold, Italic, Links)
    finalHtml = finalHtml
      .replace(/\*\*\*(.*?)\*\*\*/g, '<strong style="color: white; font-weight: 800;"><em>$1</em></strong>')
      .replace(/\*\*(.*?)\*\*/g, '<strong style="color: white; font-weight: 800;">$1</strong>')
      .replace(/_(.*?)_/g, '<em style="font-style:italic">$1</em>')
      .replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" style="color: #60a5fa; text-decoration: underline; font-weight: 700;">$1</a>');
    // Ensure all HTML tables have visible borders
    finalHtml = finalHtml
      .replace(/<table(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border-collapse:collapse;width:100%;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;"');
        }
        return m.replace('<table', '<table style="border-collapse:collapse;width:100%;margin-bottom:18px;font-family:Arial,sans-serif;font-size:13px;"');
      })
      .replace(/<th(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;"');
        }
        return m.replace('<th', '<th style="border:1px solid #475569;padding:8px 10px;text-align:left;font-weight:700;color:#e2e8f0;background:#1e293b;font-size:12px;text-transform:uppercase;"');
      })
      .replace(/<td(\s[^>]*)?>/gi, (m) => {
        if (m.includes('style="')) {
          return m.replace(/style="([^"]*)"/, 'style="$1;border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;"');
        }
        return m.replace('<td', '<td style="border:1px solid #475569;padding:8px 10px;text-align:left;color:#cbd5e1;font-size:13px;"');
      });
    return finalHtml;
  };

  const filteredDrafts = drafts.filter(d => 
    d.subject.toLowerCase().includes(searchTerm.toLowerCase()) || 
    d.to.toLowerCase().includes(searchTerm.toLowerCase()) ||
    d.snippet.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="animate-in fade-in duration-700">
      <div className="flex justify-between items-end mb-8">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-[28px] font-bold text-white tracking-tight">Gmail Sync</h1>
            <div className="px-2 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-[9px] font-black text-blue-500 uppercase tracking-widest">Live Drafts</div>
          </div>
          <p className="text-[#64748b] text-[12px] font-medium">
            Direct real-time synchronization with your linked Gmail account drafts.
          </p>
        </div>
        
        <button 
          onClick={() => fetchGmailDrafts(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-xl text-[11px] font-bold text-white uppercase tracking-widest transition-all disabled:opacity-50 cursor-pointer"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-blue-400' : ''}`} />
          {isRefreshing ? 'Syncing...' : 'Force Refresh'}
        </button>
      </div>

      {/* Control Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="md:col-span-3 relative">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input 
            type="text" 
            placeholder="Search within Gmail drafts..." 
            className="w-full bg-[#131722] border border-white/5 rounded-2xl py-3 pl-12 pr-4 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-blue-500/30 transition-all"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <div className="flex items-center justify-center bg-[#131722] border border-white/5 rounded-2xl px-4 py-3">
            <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Total: {drafts.length}</span>
        </div>
      </div>

      <div className="bg-[#131722] border border-[#ffffff08] rounded-[24px] overflow-hidden shadow-2xl relative">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#0f121b]/80 border-b border-[#ffffff08]">
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Recipient / Thread</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Subject & Context</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Draft Snippet</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px]">Last Modified</th>
                <th className="px-6 py-5 text-[9px] font-black text-[#64748b] uppercase tracking-[2px] text-right">Access</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ffffff08]">
              {isLoading ? (
                <tr>
                  <td colSpan="5" className="px-6 py-32 text-center">
                    <div className="flex flex-col items-center gap-4">
                        <Loader2 className="w-10 h-10 text-blue-500 animate-spin" />
                        <p className="text-[10px] font-black text-slate-500 uppercase tracking-[3px]">Polling Gmail Servers...</p>
                    </div>
                  </td>
                </tr>
              ) : filteredDrafts.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-32 text-center text-[#64748b] font-bold uppercase tracking-[2px] text-[10px]">
                    No drafts found in your Gmail account matching current filters.
                  </td>
                </tr>
              ) : filteredDrafts.map(draft => (
                <tr key={draft.id} className="hover:bg-white/[0.02] transition-colors group">
                  <td className="px-6 py-5">
                    <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center text-red-400 font-black text-[10px]">G</div>
                        <div>
                            <div className="text-[12px] font-bold text-white truncate max-w-[200px]">{draft.to || 'No Recipient'}</div>
                            <div className="text-[9px] text-slate-500 font-medium tracking-tight mt-0.5">Draft ID: {draft.id.substring(0,8)}...</div>
                        </div>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <div className="text-[12px] text-blue-400 font-bold tracking-tight mb-1">{draft.subject || '(No Subject)'}</div>
                    <div className="flex items-center gap-2">
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-[8px] font-black text-slate-400 uppercase tracking-tighter border border-white/5">Synced</span>
                    </div>
                  </td>
                  <td className="px-6 py-5">
                    <p className="text-[11px] text-[#94a3b8] font-medium line-clamp-2 max-w-[400px]">
                      {draft.snippet || 'No content snippet available.'}
                    </p>
                  </td>
                  <td className="px-6 py-5">
                    <div className="flex flex-col">
                        <span className="text-[11px] text-white font-bold">{draft.date ? new Date(draft.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'Recently'}</span>
                        <span className="text-[9px] text-slate-500 font-medium uppercase tracking-tighter mt-1">{draft.date ? new Date(draft.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}</span>
                    </div>
                  </td>
                  <td className="px-6 py-5 text-right">
                    <div className="flex justify-end gap-2">
                        <button 
                            onClick={() => handleEditClick(draft)}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all border border-white/5 cursor-pointer"
                            title="Edit Draft"
                        >
                            <Edit3 className="w-4 h-4" />
                        </button>
                        <button 
                            onClick={() => handleSendDraft(draft.id)}
                            className="p-2 bg-blue-600/10 hover:bg-blue-600 rounded-lg text-blue-400 hover:text-white transition-all border border-blue-600/20 cursor-pointer"
                            title="Send Draft Now"
                        >
                            <Send className="w-4 h-4" />
                        </button>
                        <a 
                        href="https://mail.google.com/mail/u/0/#drafts" 
                        target="_blank" 
                        rel="noreferrer"
                        className="p-2 bg-white/5 hover:bg-white/10 rounded-lg text-slate-400 hover:text-white transition-all border border-white/5 cursor-pointer"
                        title="View in Gmail"
                        >
                            <ExternalLink className="w-4 h-4" />
                        </a>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      <div className="mt-8 p-6 rounded-[24px] bg-gradient-to-br from-indigo-500/5 to-purple-500/5 border border-white/5 flex items-center justify-between">
          <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center text-blue-500">
                  <Mail className="w-6 h-6" />
              </div>
              <div>
                  <h4 className="text-[14px] font-bold text-white">Gmail Integration Active</h4>
                  <p className="text-[11px] text-slate-500 font-medium">Any changes made in your Gmail account will reflect here after a refresh.</p>
              </div>
          </div>
          <div className="flex gap-4">
              <div className="text-center px-6 border-r border-white/10">
                  <div className="text-[18px] font-black text-white">{drafts.length}</div>
                  <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mt-1">Stored Drafts</div>
              </div>
              <div className="text-center px-6">
                  <div className="text-[18px] font-black text-emerald-500 tracking-tighter flex items-center gap-1">
                      <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                      OK
                  </div>
                  <div className="text-[9px] font-black text-slate-500 uppercase tracking-widest mt-1">API Status</div>
              </div>
          </div>
      </div>

      {/* Edit Modal - UPDATED TWO-COLUMN LAYOUT */}
      {editingDraft && (
        <div className="fixed inset-0 z-[5000] flex items-center justify-center p-6 bg-black/80 backdrop-blur-xl animate-in fade-in duration-300">
            <div className="w-full max-w-[95vw] lg:max-w-7xl bg-[#0b0f19] border border-white/10 rounded-[32px] overflow-hidden shadow-2xl flex flex-col max-h-[95vh]">
                <div className="p-6 border-b border-white/5 flex items-center justify-between bg-[#0f121b]/50">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                            <Edit3 className="w-5 h-5" />
                        </div>
                        <div>
                            <h2 className="text-lg font-black text-white uppercase tracking-tight">Edit Gmail Draft</h2>
                            <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Recipient: {editingDraft.to}</p>
                        </div>
                    </div>
                    <button onClick={() => setEditingDraft(null)} className="p-2 hover:bg-white/5 rounded-full text-slate-500 transition-colors cursor-pointer">
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="flex-1 overflow-hidden flex flex-col lg:flex-row">
                    {/* Left Panel: Editor */}
                    <div className="w-full lg:w-1/2 overflow-y-auto p-8 space-y-6 border-r border-white/5 custom-scrollbar bg-[#0d111b]">
                        <div className="space-y-2">
                            <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Subject Line</label>
                            <input 
                                type="text" 
                                className="w-full bg-[#131722] border border-white/10 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-blue-500/30 transition-all font-bold"
                                value={editingDraft.subject}
                                onChange={(e) => setEditingDraft({...editingDraft, subject: e.target.value})}
                            />
                        </div>
                        
                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Email Body</label>
                                <div className="flex items-center gap-2">
                                    <div className="flex items-center bg-white/5 rounded-lg border border-white/5 p-1">
                                        <button 
                                            onClick={() => applyFormat('b')}
                                            className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-white transition-all cursor-pointer"
                                            title="Bold"
                                        >
                                            <Bold className="w-3.5 h-3.5" />
                                        </button>
                                        <button 
                                            onClick={() => applyFormat('i')}
                                            className="p-1.5 hover:bg-white/10 rounded text-slate-400 hover:text-white transition-all cursor-pointer"
                                            title="Italic"
                                        >
                                            <Italic className="w-3.5 h-3.5" />
                                        </button>
                                    </div>
                                    <div className="h-4 w-px bg-white/10 mx-1"></div>
                                    <div className="flex items-center gap-1.5">
                                        <button 
                                            onClick={() => handleAIRefine('professional')}
                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 rounded-lg text-[10px] font-black text-blue-400 uppercase tracking-tight transition-all cursor-pointer"
                                        >
                                            <Shield className="w-3 h-3" /> Professional
                                        </button>
                                        <button 
                                            onClick={() => handleAIRefine('shorten')}
                                            className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/20 rounded-lg text-[10px] font-black text-purple-400 uppercase tracking-tight transition-all cursor-pointer"
                                        >
                                            <Type className="w-3 h-3" /> Concise
                                        </button>
                                    </div>
                                </div>
                            </div>
                            
                            <textarea 
                                ref={editorRef}
                                className="w-full bg-[#131722] border border-white/10 rounded-xl px-4 py-4 text-white text-sm focus:outline-none focus:border-blue-500/30 transition-all min-h-[400px] leading-relaxed font-mono resize-none"
                                value={editingDraft.body}
                                onChange={(e) => setEditingDraft({...editingDraft, body: e.target.value})}
                            />
                            
                            <div className="flex items-center gap-3 p-4 rounded-2xl bg-blue-500/5 border border-blue-500/10">
                                <Sparkles className="w-4 h-4 text-blue-400" />
                                <div className="text-[10px] text-slate-400 font-medium leading-relaxed">
                                    <span className="text-white font-bold">Pro Tip:</span> Use <span className="text-blue-400">**text**</span> for bold and <span className="text-blue-400">* text</span> for lists. 
                                    Your draft will be saved to Gmail as a professional HTML message.
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Right Panel: Rendered Preview */}
                    <div className="w-full lg:w-1/2 overflow-y-auto p-10 bg-[#070b14] custom-scrollbar">
                        <div className="max-w-2xl mx-auto space-y-8">
                            <div className="flex items-center justify-between pb-6 border-b border-white/5">
                                <div className="flex items-center gap-4">
                                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white font-black text-lg shadow-lg">
                                        {editingDraft.to?.charAt(0).toUpperCase()}
                                    </div>
                                    <div>
                                        <div className="text-[14px] font-bold text-white">{editingDraft.to}</div>
                                        <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-0.5">Live Preview</div>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Platform</div>
                                    <div className="text-[11px] font-black text-red-500 uppercase tracking-widest flex items-center gap-1 justify-end mt-0.5">
                                        <div className="w-1.5 h-1.5 rounded-full bg-red-500"></div>
                                        Gmail
                                    </div>
                                </div>
                            </div>

                            <div className="space-y-6">
                                <div className="flex gap-3 text-[13px]">
                                    <span className="text-slate-500 font-bold uppercase tracking-widest text-[9px] mt-1">Subject:</span>
                                    <span className="text-white font-bold leading-tight">{editingDraft.subject || '(No Subject)'}</span>
                                </div>

                                <div className="p-1 rounded-xl bg-white/[0.01] border border-white/[0.03]">
                                    <div 
                                        className="text-[14px] text-slate-300 leading-relaxed font-medium p-4"
                                        dangerouslySetInnerHTML={{ __html: renderEmailPreview(editingDraft.body) }}
                                    />
                                </div>
                            </div>

                            {/* Mock Attachments (Visual Placeholder for context) */}
                            <div className="pt-10 mt-10 border-t border-white/5">
                                <div className="flex items-center gap-2 mb-4">
                                    <div className="w-1.5 h-1.5 rounded-full bg-slate-700"></div>
                                    <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Shared Assets</span>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 opacity-40 grayscale">
                                    <div className="flex items-center gap-3 p-3 rounded-lg bg-white/5 border border-white/5">
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
                </div>

                <div className="p-6 bg-[#0f121b] border-t border-white/5 flex items-center justify-between">
                    <button 
                        onClick={() => setEditingDraft(null)}
                        className="px-6 py-3 text-slate-500 hover:text-white text-[11px] font-black uppercase tracking-widest transition-colors cursor-pointer"
                    >
                        Discard Changes
                    </button>
                    <div className="flex items-center gap-3">
                        <button 
                            onClick={handleUpdateDraft}
                            disabled={isProcessing}
                            className="flex items-center gap-2 px-6 py-3 bg-white/5 hover:bg-white/10 border border-white/10 text-white text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all cursor-pointer"
                        >
                            {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                            Sync to Gmail
                        </button>
                        <button 
                            onClick={() => handleSendDraft(editingDraft.id)}
                            disabled={isProcessing}
                            className="flex items-center gap-2 px-8 py-3 bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-black uppercase tracking-widest rounded-2xl transition-all shadow-lg shadow-blue-600/20 cursor-pointer"
                        >
                            {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                            Send Now
                        </button>
                    </div>
                </div>
            </div>
        </div>
      )}

      {/* Notification Toast */}
      {notification && (
        <div className="fixed bottom-8 right-8 z-[6000] animate-in slide-in-from-bottom-4 duration-300">
          <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md ${
            notification.type === 'success' ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border-red-500/20 text-red-400'
          }`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <p className="text-[12px] font-bold tracking-tight">{notification.message}</p>
            <button onClick={() => setNotification(null)} className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors cursor-pointer">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default GmailDrafts;
