import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { ChevronLeft, Sparkles, Loader2, Save, Wand2, Type, Briefcase, BarChart3, Smile, CheckCircle2, AlertCircle, Send, Link as LinkIcon } from 'lucide-react';
import api from '../services/api';

const EditEmail = () => {
  const { draftId } = useParams();
  const navigate = useNavigate();
  const [draft, setDraft] = useState(null);
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [aiInstruction, setAiInstruction] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [notification, setNotification] = useState(null);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchDraft = async () => {
    setIsLoading(true);
    try {
      // In our current API, draftId is the leadId
      const response = await api.get(`/api/leads/${draftId}`);
      const lead = response.data;
      
      // Robust extraction of subject and body
      const draftContent = lead.email_draft || "";
      let sub = "";
      let bd = "";
      
      if (draftContent.includes("Subject: ")) {
        const firstNewLine = draftContent.indexOf("\n\n");
        if (firstNewLine !== -1) {
          sub = draftContent.substring(0, firstNewLine).replace("Subject: ", "").trim();
          bd = draftContent.substring(firstNewLine + 2).trim();
        } else {
          sub = draftContent.replace("Subject: ", "").trim();
          bd = "";
        }
      } else {
        bd = draftContent;
      }

      setDraft(lead);
      setSubject(sub);
      setBody(bd);
    } catch (err) {
      console.error('Failed to fetch draft', err);
      showNotification('error', 'Failed to load draft');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDraft();
  }, [draftId]);

  const handleSave = async (silent = false) => {
    setIsSaving(true);
    try {
      const email_draft = `Subject: ${subject}\n\n${body}`;
      await api.patch(`/api/leads/${draftId}`, { email_draft });
      if (!silent) showNotification('success', 'Changes saved successfully');
    } catch {
      showNotification('error', 'Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  const handleRefine = async (instruction = null) => {
    const finalInstruction = instruction || aiInstruction;
    if (!finalInstruction) return;

    setIsRefining(true);
    try {
      const response = await api.post(`/api/refine-email/${draftId}`, {
        instruction: finalInstruction,
        subject,
        body
      });
      if (response.data.error) {
        showNotification('error', `AI refinement failed: ${response.data.error}`);
        return;
      }
      
      if (response.data.subject || response.data.body) {
        setSubject(response.data.subject || '');
        setBody(response.data.body || '');
        setAiInstruction('');
        showNotification('success', 'Email refined by AI! View the updated preview on the right.');
      }
    } catch {
      showNotification('error', 'AI refinement failed');
    } finally {
      setIsRefining(false);
    }
  };

  const handleApproveAndSend = async () => {
    await handleSave(true);
    try {
      await api.post(`/api/approve-email/${draftId}`);
      showNotification('success', 'Email approved and ready to send');
      setTimeout(() => navigate('/dashboard/emails'), 1500);
    } catch {
      showNotification('error', 'Approval failed');
    }
  };

  if (isLoading || !draft) {
    return (
      <div className="py-20 flex flex-col items-center justify-center">
        <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading Editor...</p>
      </div>
    );
  }

  return (
    <div className="animate-in fade-in duration-500 min-h-screen bg-[#0a0f1a] pb-20 p-8">
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <button onClick={() => navigate('/dashboard/emails')} className="px-3 py-1.5 flex items-center gap-1.5 rounded-md bg-[#131722] border border-[#ffffff10] text-slate-300 hover:text-white transition-colors text-[11px] font-bold">
          <ChevronLeft className="w-3.5 h-3.5" /> Back
        </button>
        <div>
          <h1 className="text-[20px] font-bold text-white tracking-tight">Edit Email Draft #{draftId}</h1>
          <p className="text-[#64748b] text-[12px] font-medium mt-0.5">
            To: {draft.first_name} {draft.last_name} ({draft.email})
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 items-start">
        {/* Left: Editor Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
          <div className="px-6 py-4 border-b border-[#ffffff08] flex items-center gap-2 bg-[#0f121b]/50">
            <span className="text-amber-500 text-sm">✏️</span>
            <h3 className="text-white font-bold text-[13px] tracking-wide">Edit Draft</h3>
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
              <textarea 
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Generate AI draft to begin or write your own message..."
                className="w-full h-full min-h-[300px] flex-1 bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-4 py-3 text-[13px] text-white font-medium outline-none focus:border-blue-500/50 resize-none leading-relaxed"
              />
            </div>

            {/* AI Refinement Tools */}
            <div className="space-y-4 pt-4">
              <div className="relative flex items-center bg-[#0a0f1a] border border-[#ffffff10] rounded-md px-3 py-1 focus-within:border-blue-500/50 transition-colors">
                <Sparkles className="w-4 h-4 text-amber-500 shrink-0" />
                <input 
                  type="text" 
                  value={aiInstruction}
                  onChange={(e) => setAiInstruction(e.target.value)}
                  placeholder="Edit with AI (e.g., 'Make it more formal', 'Add focus on ROI'...)"
                  className="flex-1 bg-transparent border-none text-[12px] text-slate-300 px-3 py-2 outline-none italic placeholder-slate-500"
                  onKeyDown={(e) => e.key === 'Enter' && handleRefine()}
                />
                <button 
                  onClick={() => handleRefine()}
                  disabled={isRefining || !aiInstruction}
                  className="bg-[#10b981] hover:bg-emerald-500 text-white text-[11px] font-bold px-4 py-1.5 rounded-md transition-colors disabled:opacity-50 flex items-center shadow-lg shadow-emerald-500/20"
                >
                  {isRefining ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : ''}
                  {isRefining ? 'Refining...' : 'Refine Draft'}
                </button>
              </div>

              <div className="flex flex-wrap gap-2">
                <button onClick={() => handleRefine('Shorten this email')} className="px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  SHORTEN
                </button>
                <button onClick={() => handleRefine('Make it more professional')} className="px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  MORE PROFESSIONAL
                </button>
                <button onClick={() => handleRefine('Add specific ROI data or metrics')} className="px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  ADD ROI DATA
                </button>
                <button onClick={() => handleRefine('Make it more friendly and conversational')} className="px-3 py-1.5 bg-[#ffffff05] border border-[#ffffff0a] text-[#94a3b8] hover:text-white hover:bg-[#ffffff0a] rounded-[4px] text-[10px] font-bold uppercase tracking-widest transition-colors">
                  FRIENDLY TONE
                </button>
              </div>

              <div className="pt-6 flex items-center gap-4">
                <button 
                  onClick={() => handleSave()}
                  disabled={isSaving}
                  className="bg-[#1e293b] hover:bg-[#334155] text-white text-[12px] font-bold px-5 py-2.5 rounded-md transition-colors disabled:opacity-50 flex items-center border border-[#ffffff10]"
                >
                  {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  Save Changes
                </button>
                <button 
                  onClick={handleApproveAndSend}
                  className="flex-1 bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-600 hover:to-red-700 text-white text-[12px] font-black uppercase tracking-widest px-6 py-2.5 rounded-md transition-all shadow-lg shadow-red-500/20 flex items-center justify-center gap-2"
                >
                  Approve & Send Outreach <Send className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Email Preview Panel */}
        <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden shadow-2xl flex flex-col min-h-[700px]">
           {/* Preview Header */}
           <div className="p-6 border-b border-[#ffffff08] bg-[#0a0f1a]">
             <div className="flex justify-between items-start">
               <div className="flex gap-4 items-center">
                 <div className="w-12 h-12 rounded-full bg-[#8b5cf6] flex items-center justify-center text-white font-bold text-lg shadow-lg">
                   {draft.first_name?.charAt(0)}{draft.last_name?.charAt(0)}
                 </div>
                 <div>
                   <h3 className="text-white font-bold text-[15px] flex items-center gap-2">
                     {draft.first_name} {draft.last_name}
                   </h3>
                   <div className="flex items-center gap-2 mt-0.5">
                     <p className="text-[12px] text-[#94a3b8] font-medium">{draft.designation} at {draft.company_name}, {draft.city}</p>
                     {draft.linkedin_url && (
                       <a href={draft.linkedin_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-blue-400 hover:underline">
                         <LinkIcon className="w-3 h-3" /> LinkedIn
                       </a>
                     )}
                   </div>
                 </div>
               </div>
               
               <div className="text-right flex flex-col items-end gap-1">
                 <span className="text-[#64748b] text-[9px] font-black uppercase tracking-[2px]">PERSONA</span>
                 <span className="text-[#10b981] text-[12px] font-black uppercase tracking-[1px]">{draft.persona || 'PARTNER'}</span>
               </div>
             </div>
           </div>

           {/* Preview Body */}
           <div className="p-8 flex-1 bg-[#131722] overflow-y-auto w-full custom-scrollbar">
              <div className="w-full space-y-8">
                 <div className="text-[13px]">
                   <span className="text-[#94a3b8] font-medium mr-2">Subject:</span>
                   <span className={`font-bold ${subject ? 'text-blue-400' : 'text-slate-600 italic text-[11px]'}`}>
                     {subject || '(No subject specified)'}
                   </span>
                 </div>
                 
                 <div className={`text-[13px] leading-relaxed whitespace-pre-wrap font-medium ${body ? 'text-slate-300' : 'text-slate-600 italic text-[11px]'}`}>
                   {body || 'Generate AI draft to begin...'}
                 </div>
              </div>
           </div>

           {/* Preview Stats Footer */}
           <div className="p-8 border-t border-[#ffffff08] bg-[#0a0f1a]">
              <div className="space-y-4 max-w-[400px]">
                 <div className="grid grid-cols-[120px_1fr] items-center text-[11px]">
                    <span className="text-[#64748b] font-medium">Status</span>
                    {draft.status === 'REJECTED' ? (
                       <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-[1px] bg-transparent text-red-500 w-max">REJECTED</span>
                    ) : (
                       <span className="px-2 py-0.5 rounded text-[10px] font-black uppercase tracking-[1px] bg-transparent text-amber-500 w-max">{draft.status || 'PENDING APPROVAL'}</span>
                    )}
                 </div>
                 <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                    <span className="text-[#64748b]">Approved By</span>
                    <span className="text-slate-300">—</span>
                 </div>
                 <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                    <span className="text-[#64748b]">Sent At</span>
                    <span className="text-slate-300">—</span>
                 </div>
                 <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                    <span className="text-[#64748b]">Opens</span>
                    <span className="text-slate-300">0</span>
                 </div>
                 <div className="grid grid-cols-[120px_1fr] items-center text-[11px] font-medium border-t border-[#ffffff05] pt-3">
                    <span className="text-[#64748b]">Clicks</span>
                    <span className="text-slate-300">0</span>
                 </div>
              </div>
           </div>
        </div>
      </div>

      {notification && (
        <div className="fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4">
          <div className={`px-6 py-4 rounded-xl shadow-2xl border backdrop-blur-md flex items-center gap-3 ${
            notification.type === 'success' ? 'bg-[#10b981]/10 border-[#10b981]/20 text-[#10b981]' : 'bg-red-500/10 border-red-500/20 text-red-500'
          }`}>
            {notification.type === 'success' ? <CheckCircle2 className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
            <span className="font-bold text-[13px]">{notification.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default EditEmail;
