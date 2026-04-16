import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  ChevronLeft, Linkedin, Trash2, UserMinus,
  Mail, History, CheckCircle2, XCircle, AlertCircle,
  Loader2, ExternalLink, Sparkles, Save, Phone,
  MapPin, Building2, User, Check, ChevronDown
} from 'lucide-react';
import api from '../services/api';

const COMPANY_OPTIONS = [
  "AI Accelera", "AI Infra Labs", "AI Intelligence Labs", "AI Tech Leads",
  "ARVR Labs", "AgriTech Labs", "Altos Incorporated", "Amazon",
  "Automotive Labs", "BS Deep Tech Consulting & Development", "Bacon Software",
  "Blinkit-AI", "Blockchain Labs", "Chris Hospitals"
];
const CITY_OPTIONS = [
  // North America
  "San Francisco", "New York", "Austin", "Seattle", "Toronto", "Vancouver", "Boston", "Chicago", "Los Angeles", "Miami", "Denver", "Eden Prairie", "Washington D.C.", "Atlanta", "Dallas",
  // Europe
  "London", "Berlin", "Paris", "Amsterdam", "Dublin", "Stockholm", "Zurich", "Madrid", "Munich", "Barcelona", "Copenhagen", "Helsinki", "Warsaw",
  // Asia Pacific
  "Tokyo", "Singapore", "Sydney", "Hong Kong", "Bangalore", "Seoul", "Melbourne", "Taipei", "Shanghai", "Beijing", "Mumbai", "Jakarta", "Kuala Lumpur",
  // Middle East & Africa
  "Dubai", "Tel Aviv", "Cape Town", "Abu Dhabi", "Riyadh", "Lagos", "Nairobi"
];
const ALL_COUNTRIES = [
  "Afghanistan", "Albania", "Algeria", "Andorra", "Angola", "Antigua and Barbuda", "Argentina", "Armenia", "Australia", "Austria", "Azerbaijan", "Bahamas", "Bahrain", "Bangladesh", "Barbados", "Belarus", "Belgium", "Belize", "Benin", "Bhutan", "Bolivia", "Bosnia and Herzegovina", "Botswana", "Brazil", "Brunei", "Bulgaria", "Burkina Faso", "Burundi", "Cabo Verde", "Cambodia", "Cameroon", "Canada", "Central African Republic", "Chad", "Chile", "China", "Colombia", "Comoros", "Congo", "Costa Rica", "Croatia", "Cuba", "Cyprus", "Czechia", "Denmark", "Djibouti", "Dominica", "Dominican Republic", "Ecuador", "Egypt", "El Salvador", "Equatorial Guinea", "Eritrea", "Estonia", "Eswatini", "Ethiopia", "Fiji", "Finland", "France", "Gabon", "Gambia", "Georgia", "Germany", "Ghana", "Greece", "Grenada", "Guatemala", "Guinea", "Guinea-Bissau", "Guyana", "Haiti", "Honduras", "Hungary", "Iceland", "India", "Indonesia", "Iran", "Iraq", "Ireland", "Israel", "Italy", "Jamaica", "Japan", "Jordan", "Kazakhstan", "Kenya", "Kiribati", "Kosovo", "Kuwait", "Kyrgyzstan", "Laos", "Latvia", "Lebanon", "Lesotho", "Liberia", "Libya", "Liechtenstein", "Lithuania", "Luxembourg", "Madagascar", "Malawi", "Malaysia", "Maldives", "Mali", "Malta", "Marshall Islands", "Mauritania", "Mauritius", "Mexico", "Micronesia", "Moldova", "Monaco", "Mongolia", "Montenegro", "Morocco", "Mozambique", "Myanmar", "Namibia", "Nauru", "Nepal", "Netherlands", "New Zealand", "Nicaragua", "Niger", "Nigeria", "North Korea", "North Macedonia", "Norway", "Oman", "Pakistan", "Palau", "Palestine", "Panama", "Papua New Guinea", "Paraguay", "Peru", "Philippines", "Poland", "Portugal", "Qatar", "Romania", "Russia", "Rwanda", "Saint Kitts and Nevis", "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "San Marino", "Sao Tome and Principe", "Saudi Arabia", "Senegal", "Serbia", "Seychelles", "Sierra Leone", "Singapore", "Slovakia", "Slovenia", "Solomon Islands", "Somalia", "South Africa", "South Korea", "South Sudan", "Spain", "Sri Lanka", "Sudan", "Suriname", "Sweden", "Switzerland", "Syria", "Taiwan", "Tajikistan", "Tanzania", "Thailand", "Timor-Leste", "Togo", "Tonga", "Trinidad and Tobago", "Tunisia", "Turkey", "Turkmenistan", "Tuvalu", "Uganda", "Ukraine", "United Arab Emirates", "United Kingdom", "United States", "Uruguay", "Uzbekistan", "Vanuatu", "Vatican City", "Venezuela", "Vietnam", "Yemen", "Zambia", "Zimbabwe"
];
const CAMPAIGN_OPTIONS = ["Investor Outreach", "Test Tracking 3", "Q1 Marketing", "Cold Outreach"];

const CustomDropdown = ({ label, value, onChange, options, placeholder, searchable = true }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [dropdownStyle, setDropdownStyle] = useState({});
  const triggerRef = React.useRef(null);
  const allOptions = Array.from(new Set([...options, value].filter(Boolean)));
  const filtered = search.trim()
    ? allOptions.filter(o => o.toLowerCase().includes(search.toLowerCase()))
    : allOptions;

  const handleOpen = () => {
    if (triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setDropdownStyle({
        position: 'fixed',
        top: rect.bottom + 6,
        left: rect.left,
        width: rect.width,
        zIndex: 9999,
      });
    }
    setIsOpen(prev => !prev);
    setSearch('');
  };

  return (
    <div className="relative">
      {label && <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">{label}</label>}
      <div
        ref={triggerRef}
        className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-[11px] font-medium transition-colors cursor-pointer flex justify-between items-center hover:border-blue-500/30"
        onClick={handleOpen}
      >
        <span className={value ? "text-white" : "text-slate-500"}>{value || placeholder}</span>
        <ChevronDown className={`w-3.5 h-3.5 text-slate-500 transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`} />
      </div>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-[9998]" onClick={() => { setIsOpen(false); setSearch(''); }} />
          <div
            style={dropdownStyle}
            className="bg-[#0f121b] border border-[#ffffff15] rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200"
          >
            {searchable && (
              <div className="p-2 border-b border-white/5">
                <input
                  autoFocus
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search..."
                  className="w-full bg-[#131722] border border-white/5 rounded-lg px-3 py-2 text-[11px] text-white placeholder:text-slate-600 outline-none focus:border-blue-500/40"
                  onClick={e => e.stopPropagation()}
                />
              </div>
            )}
            <div className="overflow-y-auto max-h-[240px] p-1.5">
              <div
                className="flex items-center gap-2 px-3 py-2.5 text-[11px] rounded-lg cursor-pointer text-slate-500 hover:bg-white/5 transition-colors italic"
                onClick={() => { onChange(''); setIsOpen(false); setSearch(''); }}
              >
                — {placeholder} —
              </div>
              {filtered.length === 0 && (
                <div className="px-3 py-4 text-[11px] text-slate-600 text-center">No results found</div>
              )}
              {filtered.map((opt, i) => {
                const isSelected = value === opt;
                return (
                  <div
                    key={i}
                    className={`flex items-center gap-2 px-3 py-2.5 text-[11px] rounded-lg cursor-pointer transition-colors ${isSelected ? 'bg-[#2563eb] text-white font-bold' : 'text-slate-300 hover:bg-white/5'
                      }`}
                    onClick={() => { onChange(opt); setIsOpen(false); setSearch(''); }}
                  >
                    {isSelected ? <Check className="w-3.5 h-3.5 shrink-0" /> : <span className="w-3.5 h-3.5 shrink-0" />}
                    {opt}
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

const CampaignField = ({ value, onChange, options }) => {
  const [isSelectMode, setIsSelectMode] = useState(true);

  return (
    <div className="w-full">
      <div className="flex justify-between items-center mb-1.5 px-0.5">
        <label className="block text-[10px] font-bold text-[#64748b]">Campaign</label>
        <button
          type="button"
          onClick={() => setIsSelectMode(!isSelectMode)}
          className="text-[#60a5fa] text-[9px] font-bold hover:text-blue-400 transition-colors"
        >
          {isSelectMode ? "+ Add New" : "Select Existing"}
        </button>
      </div>
      {isSelectMode ? (
        <CustomDropdown label="" value={value} onChange={onChange} options={options} placeholder="Select Campaign" />
      ) : (
        <input
          type="text" value={value || ''} onChange={(e) => onChange(e.target.value)}
          placeholder="Enter new campaign name..."
          className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors"
        />
      )}
    </div>
  );
};

const LeadDetail = () => {
  const { leadId } = useParams();
  const navigate = useNavigate();
  const [lead, setLead] = useState(null);
  const [logs, setLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [drafts, setDrafts] = useState([]);
  const [notification, setNotification] = useState(null);
  const [error, setError] = useState(null);
  const [familyOffices, setFamilyOffices] = useState([]);

  // Form state - synced dynamically from lead data
  const [form, setForm] = useState({});
  const [isDirty, setIsDirty] = useState(false);
  const [pendingOptOut, setPendingOptOut] = useState(false);
  const [pendingDelete, setPendingDelete] = useState(false);

  const showNotification = (type, message) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [leadRes, logsRes] = await Promise.all([
        api.get(`/api/leads/${leadId}`),
        api.get(`/api/leads/${leadId}/activity`)
      ]);
      const l = leadRes.data;
      setLead(l);

      // Explicitly map all fields from API to ensure proper state binding
      setForm({
        ...l,
        first_name: l.first_name || '',
        last_name: l.last_name || '',
        email: l.email || '',
        designation: l.designation || '',
        industry: l.industry || '',
        phone: l.phone || '',
        linkedin_url: l.linkedin_url || l.linkedin || '',
        city: l.city || '',
        country: l.country || '',
        campaign_id: l.campaign_id || null,
        company_name: l.company_name || '',
        family_office_name: l.family_office_name || '',
        remarks: l.remarks || ''
      });
      setLogs(logsRes.data || []);

      try {
        const foRes = await api.get('/api/family-offices');
        setFamilyOffices(foRes.data || []);
      } catch {
        setFamilyOffices([]);
      }

      try {
        const emailsRes = await api.get(`/api/emails`);
        const allDrafts = emailsRes.data?.drafts || [];
        setDrafts(allDrafts.filter(d => String(d.lead_id) === String(leadId)));
      } catch {
        setDrafts([]);
      }
    } catch (err) {
      console.error('Failed to fetch lead details', err);
      setError(err.response?.data?.detail || 'This lead profile could not be retrieved. It may have been deleted or you may not have permission to view it.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [leadId]);

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    setIsDirty(true);
  };

  const handleUpdate = async (e) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      // Sanitize fields before sending to API
      const sanitizedForm = { ...form };
      
      // Convert campaign_id to integer or null
      if (typeof sanitizedForm.campaign_id === 'string') {
        if (sanitizedForm.campaign_id.trim() === '') {
          sanitizedForm.campaign_id = null;
        } else if (!isNaN(parseInt(sanitizedForm.campaign_id))) {
          sanitizedForm.campaign_id = parseInt(sanitizedForm.campaign_id);
        }
      }

      // Ensure fit_score is int
      if (sanitizedForm.fit_score && typeof sanitizedForm.fit_score === 'string') {
        sanitizedForm.fit_score = parseInt(sanitizedForm.fit_score);
      }

      await api.patch(`/api/leads/${leadId}`, sanitizedForm);
      showNotification('success', 'Lead updated successfully');
      setIsDirty(false);
      fetchData();
    } catch (err) {
      console.error('Update failed:', err);
      showNotification('error', err.response?.data?.detail || 'Failed to update lead');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = () => {
    setPendingDelete(true);
  };

  const confirmDelete = async () => {
    setPendingDelete(false);
    try {
      await api.post('/api/leads/bulk-delete', [parseInt(leadId)]);
      navigate('/dashboard/leads');
    } catch (err) {
      showNotification('error', 'Failed to delete lead: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUnsubscribe = () => {
    setPendingOptOut(true);
  };

  const confirmOptOut = async () => {
    setPendingOptOut(false);
    try {
      await api.post(`/api/leads/${leadId}/unsubscribe`);
      fetchData();
      showNotification('success', 'Lead opted out and blacklisted');
    } catch {
      showNotification('error', 'Failed to opt-out lead');
    }
  };

  const handleGenerateDraft = async () => {
    setIsGenerating(true);
    try {
      await api.post('/api/generate-email', { lead_id: parseInt(leadId) });
      showNotification('success', 'Email created! You can now view it in the drafts section below.');
      fetchData();
    } catch {
      showNotification('error', 'Failed to generate draft');
    } finally {
      setIsGenerating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="py-20 flex flex-col items-center justify-center">
        <Loader2 className="w-10 h-10 text-blue-500 animate-spin mb-4" />
        <p className="text-slate-500 font-bold uppercase tracking-widest text-[10px]">Loading Profile...</p>
      </div>
    );
  }

  if (error || !lead) {
    return (
      <div className="py-20 flex flex-col items-center justify-center text-center px-4">
        <div className="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mb-6">
          <AlertCircle className="w-8 h-8 text-red-500" />
        </div>
        <h2 className="text-white text-xl font-bold mb-3">Lead Access Denied or Not Found</h2>
        <p className="text-slate-400 text-sm max-w-md mb-8 leading-relaxed">
          {error || "The requested lead record could not be found in the database. It might have been deleted or unassigned from your account."}
        </p>
        <Link
          to="/dashboard/leads"
          className="btn btn-ghost px-8 py-3 rounded-xl border border-white/10 hover:bg-white/5 text-slate-300 font-bold"
        >
          Return to Pipeline
        </Link>
      </div>
    );
  }

  const initials = `${lead.first_name?.[0] || ''}${lead.last_name?.[0] || ''}`.toUpperCase() || lead.name?.substring(0, 2).toUpperCase() || '?';
  const fullName = lead.name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim();

  return (
    <div className="animate-in fade-in duration-500 pb-20">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div className="flex items-center gap-5">
          <Link
            to="/dashboard/leads"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-[#1e293b] border border-transparent text-[#94a3b8] hover:text-white hover:bg-[#334155] transition-all text-[11px] font-bold"
          >
            ← Back
          </Link>
          <div className="w-[48px] h-[48px] rounded-full bg-[#2563eb] flex items-center justify-center text-white font-black text-lg">
            {initials}
          </div>
          <div>
            <div className="flex items-center gap-3 mb-0.5">
              <h1 className="text-[20px] font-black text-white tracking-tight">{fullName}</h1>
              {lead.linkedin_url && (
                <a
                  href={lead.linkedin_url} target="_blank" rel="noreferrer"
                  className="flex items-center gap-1 text-[#60a5fa] hover:text-blue-400 transition-colors text-[11px] font-bold"
                >
                  <Linkedin className="w-3 h-3" /> LinkedIn
                </a>
              )}
            </div>
            <p className="text-[#64748b] text-[12px] font-medium flex items-center gap-1.5 flex-wrap">
              {lead.email && <span>{lead.email}</span>}
              {lead.designation && <><span className="text-[#334155]">·</span><span>{lead.designation}</span></>}
              {lead.company_name && <><span className="text-[#334155]">·</span><span>{lead.company_name}</span></>}
            </p>
          </div>
        </div>
        <div className="flex gap-2.5">
          <button
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-[#1e293b] text-[#94a3b8] text-[11px] font-bold hover:bg-[#334155] hover:text-white transition-all cursor-pointer"
            onClick={handleDelete}
          >
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
          {lead.is_unsubscribed ? (
            <span className="px-3.5 py-1.5 flex items-center bg-red-500/10 rounded-md text-red-500 text-[11px] font-bold gap-1.5">
              Opted Out
            </span>
          ) : (
            <button
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-[#ef4444] text-white text-[11px] font-bold hover:bg-[#dc2626] transition-all cursor-pointer"
              onClick={handleUnsubscribe}
            >
              Opt-out Lead
            </button>
          )}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Edit Form + Activity */}
        <div className="lg:col-span-2 space-y-6">
          {/* Edit Profile Card */}
          <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden">
            <div className="px-6 py-5 flex items-center justify-between border-b border-[#ffffff08]">
              <div className="flex items-center gap-2">
                <span className="text-amber-500 text-sm">✏️</span>
                <h3 className="text-[13px] font-bold text-slate-300 tracking-wide">Edit Lead Profile</h3>
              </div>
              <button
                type="button"
                onClick={handleUpdate}
                disabled={isSaving}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[11px] font-bold transition-all ${
                  isDirty 
                    ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20' 
                    : 'bg-white/5 text-slate-500 cursor-not-allowed border border-white/5'
                }`}
              >
                {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                {isSaving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>
            <div className="p-6 pt-0">
              <form onSubmit={handleUpdate} className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Name</label>
                    <input
                      type="text"
                      name="name"
                      value={form.first_name + (form.last_name ? ' ' + form.last_name : '')}
                      onChange={(e) => {
                        const parts = e.target.value.split(' ');
                        setForm(prev => ({ ...prev, first_name: parts[0] || '', last_name: parts.slice(1).join(' ') || '' }));
                        setIsDirty(true);
                      }}
                      className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Email</label>
                    <input
                      type="email"
                      name="email"
                      value={form.email || ''}
                      onChange={handleChange}
                      className={`w-full bg-[#0f121b] border rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-all ${isDirty ? 'border-amber-500/30' : 'border-[#ffffff08]'}`}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Designation</label>
                    <input
                      type="text"
                      name="designation"
                      value={form.designation || ''}
                      onChange={handleChange}
                      className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Phone</label>
                    <input
                      type="text"
                      name="phone"
                      value={form.phone || ''}
                      onChange={handleChange}
                      placeholder="+1 (555) 000-0000"
                      className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Industry</label>
                  <input
                    type="text"
                    name="industry"
                    value={form.industry || ''}
                    onChange={handleChange}
                    className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">LinkedIn</label>
                  <div className="relative">
                    {form.linkedin_url && (
                      <div className="absolute left-3 top-1/2 -translate-y-1/2">
                        <Linkedin className="w-3.5 h-3.5 text-[#60a5fa]" />
                      </div>
                    )}
                    <input
                      type="text"
                      name="linkedin_url"
                      value={form.linkedin_url || ''}
                      onChange={handleChange}
                      className={`w-full bg-[#0f121b] border border-[#ffffff08] rounded-md py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors ${form.linkedin_url ? 'pl-9 pr-3' : 'px-3'}`}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <CustomDropdown
                    label="City (Scroll List)"
                    value={form.city}
                    onChange={(val) => { setForm(prev => ({ ...prev, city: val })); setIsDirty(true); }}
                    options={CITY_OPTIONS}
                    placeholder="Select City"
                  />
                  <CustomDropdown
                    label="Country (Scroll List)"
                    value={form.country}
                    onChange={(val) => { setForm(prev => ({ ...prev, country: val })); setIsDirty(true); }}
                    options={ALL_COUNTRIES}
                    placeholder="Select Country"
                  />
                </div>

                <CampaignField
                  value={form.campaign_id}
                  onChange={(val) => { setForm(prev => ({ ...prev, campaign_id: val })); setIsDirty(true); }}
                  options={CAMPAIGN_OPTIONS}
                />

                <CustomDropdown
                  label="Company (Scroll Options)"
                  value={form.company_name}
                  onChange={(val) => { setForm(prev => ({ ...prev, company_name: val })); setIsDirty(true); }}
                  options={COMPANY_OPTIONS}
                  placeholder="Select Company"
                />

                <div className="relative">
                  <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Family Office (Linked Entity)</label>
                  <CustomDropdown
                    label=""
                    value={form.family_office_name}
                    onChange={(val) => { setForm(prev => ({ ...prev, family_office_name: val })); setIsDirty(true); }}
                    options={familyOffices.map(fo => fo.name)}
                    placeholder="None"
                  />
                </div>

                <div>
                  <label className="block text-[10px] font-bold text-[#64748b] mb-1.5">Remarks / Internal Notes</label>
                  <textarea
                    name="remarks"
                    value={form.remarks || ''}
                    onChange={handleChange}
                    placeholder="Add private notes about this lead..."
                    className="w-full bg-[#0f121b] border border-[#ffffff08] rounded-md px-3 py-2.5 text-white text-[11px] font-medium focus:border-blue-500/50 outline-none transition-colors min-h-[100px] resize-none"
                  />
                </div>

              </form>
            </div>
          </div>

          {/* Activity Log */}
          <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden">
            <div className="px-6 py-5 flex items-center gap-2 border-b border-[#ffffff08]">
              <span className="text-amber-500 text-sm">⚡</span>
              <h3 className="text-[13px] font-bold text-slate-300 tracking-wide">Activity Log</h3>
            </div>
            <div className="p-6">
              {logs.length > 0 ? (
                <div className="space-y-4">
                  {logs.map((log, idx) => (
                    <div key={idx} className="flex gap-3 items-start">
                      <div className="mt-0.5 flex flex-col items-center">
                        <div className="w-2 h-2 rounded-full bg-blue-500 shrink-0" />
                        {idx !== logs.length - 1 && <div className="w-px flex-1 bg-white/5 mt-1.5 mb-0" style={{ minHeight: '20px' }} />}
                      </div>
                      <div className="flex-1 pb-2">
                        <div className="text-[11px] font-black text-white tracking-wider">{log.action}</div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          {log.created_at
                            ? new Date(log.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) +
                            ', ' +
                            new Date(log.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })
                            : '—'} · {log.performed_by || 'system'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[#64748b] text-[11px] font-medium">No activity recorded.</div>
              )}
            </div>
          </div>
        </div>

        {/* Right: Details Sidebar */}
        <div className="space-y-6">
          {/* Classification Details */}
          <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden">
            <div className="px-6 py-5 flex items-center gap-2 border-b border-[#ffffff08]">
              <span className="text-slate-400 text-sm">📋</span>
              <h3 className="text-[13px] font-bold text-white tracking-wide">Details</h3>
            </div>
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-6">STATUS</span>
                <div className="col-span-2">
                  <span className="px-2 py-0.5 rounded text-[9px] font-black uppercase tracking-widest bg-[#f59e0b]/10 text-[#fbbf24]">
                    {lead.validation_status || 'PENDING'}
                  </span>
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">COMPANY</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5">
                  {lead.company_name || '—'}
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">PHONE</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5 tabular-nums">
                  {lead.phone || '—'}
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">SOURCE</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5 lowercase">
                  {lead.source || 'rocketreach'}
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">CAMPAIGN</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5">
                  —
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">CITY</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5">
                  {lead.city || '—'}
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">COUNTRY</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5">
                  {lead.country || '—'}
                </div>
              </div>
              <div className="grid grid-cols-3">
                <span className="text-[#64748b] text-[10px] font-bold uppercase tracking-widest leading-5">CREATED</span>
                <div className="col-span-2 text-white text-[11px] font-medium leading-5">
                  {lead.created_at ? new Date(lead.created_at).toISOString().replace('T', ' ').substring(0, 16) : '—'}
                </div>
              </div>
            </div>
          </div>

          {/* Email Drafts */}
          <div className="bg-[#131722] border border-[#ffffff08] rounded-[16px] overflow-hidden">
            <div className="px-6 py-5 flex items-center justify-between border-b border-[#ffffff08]">
              <div className="flex items-center gap-2">
                <span className="text-white text-sm">✉️</span>
                <h3 className="text-[13px] font-bold text-white tracking-wide">Email Drafts</h3>
              </div>
              <button onClick={handleGenerateDraft} disabled={isGenerating} className="bg-[#2563eb] hover:bg-blue-600 text-white text-[10px] font-extrabold px-3 py-1.5 rounded-md flex items-center gap-1.5 transition-colors disabled:opacity-50 cursor-pointer">
                {isGenerating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                {isGenerating ? 'Generating...' : 'Draft AI Email'}
              </button>
            </div>
            <div className="p-6">
              {drafts.length > 0 ? (
                <div className="space-y-3">
                  {drafts.map(d => (
                    <div key={d.id} className="bg-[#0f121b] border border-[#ffffff08] rounded-xl p-4 cursor-pointer hover:border-blue-500/50 transition-colors shadow-md group" onClick={() => navigate(`/dashboard/emails/${d.id}/edit`)}>
                      <div className="flex justify-between items-start mb-2 gap-3">
                        <h4 className="text-[11px] font-bold text-white line-clamp-2 leading-relaxed flex-1 group-hover:text-blue-400 transition-colors">{d.subject || 'Follow-up on operational strategies'}</h4>
                        <span className={`shrink-0 px-2 py-0.5 rounded text-[8px] font-black uppercase tracking-widest ${d.status === 'SENT' ? 'bg-[#10b981]/20 text-[#10b981]' : 'bg-emerald-500/10 text-emerald-400'
                          }`}>
                          {d.status || 'DRAFT'}
                        </span>
                      </div>
                      <p className="text-[10px] text-[#64748b] font-medium">Click to review and refine →</p>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-6">
                  <div className="text-slate-600 text-[11px] font-bold mb-3 pb-3 border-b border-white/5 uppercase tracking-widest">No drafts generated</div>
                  <p className="text-[10px] text-slate-500 max-w-[200px] mx-auto leading-relaxed">Use the Draft AI Email button above to generate a highly personalized message using our AI models.</p>
                </div>
              )}
            </div>
          </div>

        </div>
      </div>

      {/* Floating Save Button */}
      {isDirty && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[4000] animate-in slide-in-from-bottom-8 duration-500">
          <button
            onClick={handleUpdate}
            disabled={isSaving}
            className="flex items-center gap-2.5 px-8 py-4 rounded-2xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-[13px] font-black uppercase tracking-widest hover:scale-105 active:scale-95 transition-all shadow-2xl shadow-blue-500/40 cursor-pointer group"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4 group-hover:rotate-12 transition-transform" />}
            {isSaving ? 'Saving Changes...' : 'Save Changes Now'}
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-amber-500 rounded-full animate-pulse border-2 border-[#0a0f1a]" />
          </button>
        </div>
      )}

      {/* Action Toast (Confirmation) */}
      {(pendingOptOut || pendingDelete) && (
        <div className="fixed bottom-8 right-8 z-[3000] animate-in slide-in-from-bottom-4 duration-300">
          <div className="bg-[#131722] border border-red-500/30 px-6 py-5 rounded-2xl shadow-2xl backdrop-blur-xl max-w-md">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center text-red-500 shrink-0">
                <Trash2 className="w-5 h-5" />
              </div>
              <div>
                <h4 className="text-white font-bold text-sm mb-1">
                  {pendingDelete ? 'Delete Lead?' : 'Opt-out Lead?'}
                </h4>
                <p className="text-[#64748b] text-[12px] font-medium leading-relaxed mb-4">
                  {pendingDelete
                    ? 'Permanently delete this lead? This action cannot be undone and all associated data will be removed.'
                    : 'Are you sure you want to opt-out this lead? They will be blacklisted from all future outreach.'}
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={pendingDelete ? confirmDelete : confirmOptOut}
                    className="bg-red-500 hover:bg-red-600 text-white text-[11px] font-bold px-4 py-2 rounded-lg transition-colors cursor-pointer"
                  >
                    Confirm {pendingDelete ? 'Delete' : 'Opt-out'}
                  </button>
                  <button
                    onClick={() => { setPendingOptOut(false); setPendingDelete(false); }}
                    className="bg-white/5 hover:bg-white/10 text-slate-300 text-[11px] font-bold px-4 py-2 rounded-lg transition-colors cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Notification Toast */}
      {notification && !pendingOptOut && !pendingDelete && (
        <div className="fixed bottom-8 right-8 z-[2000] animate-in slide-in-from-bottom-4">
          <div className={`px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-md flex items-center gap-3 ${notification.type === 'success'
            ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
            : 'bg-red-500/10 border-red-500/20 text-red-500'
            }`}>
            {notification.type === 'success'
              ? <CheckCircle2 className="w-5 h-5" />
              : <AlertCircle className="w-5 h-5" />}
            <span className="font-bold text-sm">{notification.message}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default LeadDetail;
