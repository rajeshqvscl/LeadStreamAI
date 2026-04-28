import React, { useState } from 'react';
import { Download, Database, Shield, FileSpreadsheet, CheckCircle, Loader2, ArrowRight } from 'lucide-react';
import api from '../services/api';

const DataExport = () => {
  const [isExporting, setIsExporting] = useState(false);
  const [lastExport, setLastExport] = useState(null);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const res = await api.get('/api/leads/export-all');
      const data = res.data;
      
      if (data.length === 0) {
        alert("No lead data found to export.");
        return;
      }

      // Generate CSV
      const headers = [
        'ID', 'First Name', 'Last Name', 'Email', 'Company', 'Designation', 
        'LinkedIn', 'Phone', 'City', 'Country', 'Industry', 'Persona', 
        'Email Status', 'AI Intent', 'Meeting Time', 'Created At', 'Remarks'
      ];
      
      const csvRows = [
        headers.join(','),
        ...data.map(row => [
          row.id,
          `"${row.first_name || ''}"`,
          `"${row.last_name || ''}"`,
          `"${row.email || ''}"`,
          `"${row.company_name || ''}"`,
          `"${row.designation || ''}"`,
          `"${row.linkedin_url || ''}"`,
          `"${row.phone || ''}"`,
          `"${row.city || ''}"`,
          `"${row.country || ''}"`,
          `"${row.industry || ''}"`,
          `"${row.persona || ''}"`,
          `"${row.email_status || ''}"`,
          `"${row.reply_intent || ''}"`,
          `"${row.meeting_time || ''}"`,
          `"${row.created_at || ''}"`,
          `"${row.remarks || ''}"`
        ].join(','))
      ];

      const csvContent = csvRows.join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = `my_leads_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      setLastExport(new Date().toLocaleString());
    } catch (err) {
      console.error('Export failed:', err);
      alert('Export failed. Please try again.');
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-12 animate-in fade-in duration-700">
      <div className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <div className="px-3 py-1 bg-blue-500/10 border border-blue-500/20 rounded-full text-[10px] font-black text-blue-500 uppercase tracking-[3px]">
            Data Governance Center
          </div>
          <Shield className="w-4 h-4 text-blue-500" />
        </div>
        <h1 className="text-[42px] font-black text-white tracking-tight leading-none mb-4">
          Export your <span className="bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent italic">Lead Intelligence</span>
        </h1>
        <p className="text-slate-400 text-lg font-medium max-w-2xl">
          Securely download your entire lead database, including LinkedIn profiles, meeting schedules, and AI-detected intent.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Main Export Card */}
        <div className="bg-[#131722] border border-white/5 rounded-[40px] p-10 shadow-2xl relative overflow-hidden group">
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
            <Database className="w-32 h-32 text-white" />
          </div>
          
          <div className="relative z-10">
            <div className="w-16 h-16 rounded-2xl bg-blue-600/10 flex items-center justify-center text-blue-500 mb-8">
              <FileSpreadsheet className="w-8 h-8" />
            </div>
            
            <h3 className="text-2xl font-black text-white mb-4 uppercase tracking-tight">Full Archive Export</h3>
            <ul className="space-y-3 mb-10">
              {['Lead Identities & Contacts', 'LinkedIn URLs', 'Meeting Timestamps', 'AI Sentiment Labels', 'Manual Remarks'].map((item, idx) => (
                <li key={idx} className="flex items-center gap-3 text-slate-400 text-sm font-bold">
                  <CheckCircle className="w-4 h-4 text-emerald-500" /> {item}
                </li>
              ))}
            </ul>

            <button 
              onClick={handleExport}
              disabled={isExporting}
              className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 text-white py-5 rounded-[24px] font-black uppercase tracking-[2px] text-sm transition-all shadow-xl shadow-blue-600/20 cursor-pointer"
            >
              {isExporting ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Generating CSV...
                </>
              ) : (
                <>
                  <Download className="w-5 h-5" />
                  Download Full Report (.CSV)
                </>
              )}
            </button>

            {lastExport && (
              <p className="text-center text-[10px] font-black text-slate-600 uppercase tracking-widest mt-6">
                Last generated: {lastExport}
              </p>
            )}
          </div>
        </div>

        {/* Info Card */}
        <div className="flex flex-col gap-6">
          <div className="bg-white/5 border border-white/5 rounded-[32px] p-8">
            <h4 className="text-[10px] font-black text-blue-500 uppercase tracking-[3px] mb-4">Security Notice</h4>
            <p className="text-sm text-slate-300 leading-relaxed font-medium">
              Your export is scoped specifically to your account. Administrator logs will record this export activity for security auditing purposes. Ensure you handle downloaded data according to your company's privacy policy.
            </p>
          </div>
          
          <div className="bg-[#131722] border border-white/5 rounded-[32px] p-8 flex items-center justify-between">
            <div>
              <div className="text-[10px] font-black text-slate-500 uppercase tracking-widest mb-1">Total Available Fields</div>
              <div className="text-2xl font-black text-white">17</div>
            </div>
            <ArrowRight className="w-6 h-6 text-slate-700" />
          </div>

          <div className="bg-emerald-500/5 border border-emerald-500/10 rounded-[32px] p-8">
            <div className="flex items-center gap-3 mb-2">
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
                <div className="text-[10px] font-black text-emerald-500 uppercase tracking-widest">Ready for Import</div>
            </div>
            <p className="text-xs text-slate-400 font-medium">
              This CSV format is compatible with common CRM systems like Salesforce, HubSpot, and Pipedrive.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataExport;
