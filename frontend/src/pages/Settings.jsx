import React, { useState, useEffect, useRef } from 'react';
import { Save, Loader2, CheckCircle, AlertCircle, Mail, Type, Users, Shield, ChevronDown } from 'lucide-react';
import api from '../services/api';

const FONTS = [
  { label: 'Sans Serif', value: 'sans-serif' },
  { label: 'Arial', value: 'Arial, Helvetica, sans-serif' },
  { label: 'Times New Roman', value: '"Times New Roman", Times, serif' },
  { label: 'Georgia', value: 'Georgia, serif' },
  { label: 'Courier New', value: '"Courier New", monospace' },
  { label: 'Tahoma', value: 'Tahoma, Geneva, sans-serif' },
  { label: 'Trebuchet MS', value: '"Trebuchet MS", sans-serif' },
  { label: 'Verdana', value: 'Verdana, Geneva, sans-serif' },
  { label: 'Comic Sans MS', value: '"Comic Sans MS", cursive' },
  { label: 'Impact', value: 'Impact, Charcoal, sans-serif' },
  { label: 'Lucida Console', value: '"Lucida Console", Monaco, monospace' },
];

const FONT_SIZES = Array.from({ length: 17 }, (_, i) => i + 6).map(n => `${n}px`);

const IMAGE_WIDTH_OPTIONS = ['100px', '150px', '200px', '250px', '300px', '350px', '400px', '500px', '600px', 'auto'];
const IMAGE_HEIGHT_OPTIONS = ['auto', '100px', '150px', '200px', '250px', '300px', '350px', '400px', '500px', '600px'];

const SAMPLE_TEXT = "Dear John,\n\nThank you for your time today. I wanted to follow up on our conversation about the partnership opportunity.\n\nBest regards,\nYour Name\nYour Title\nCompany Name\n+1 (555) 123-4567";

const FontSizeDropdown = ({ value, onChange, options }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-blue-500/50 outline-none flex items-center justify-between"
      >
        <span>{value}</span>
        <ChevronDown className={`w-4 h-4 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-2 w-full bg-[#0d1117] border border-white/10 rounded-xl shadow-2xl max-h-[240px] overflow-y-auto custom-scrollbar">
          {options.map(s => (
            <button
              type="button"
              key={s}
              onClick={() => { onChange(s); setOpen(false); }}
              className={`w-full text-left px-4 py-2 text-sm hover:bg-white/5 transition-colors ${s === value ? 'text-blue-400 font-bold' : 'text-white'}`}
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

const Settings = () => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  
  const [prefs, setPrefs] = useState({
    email_font: 'sans-serif',
    email_font_size: '13px',
    signature_font: 'sans-serif',
    signature_font_size: '13px',
    signature_mode: 'custom',
    team: 'CLIENT',
    image_width: '400px',
    image_height: 'auto',
  });

  useEffect(() => {
    const fetchPrefs = async () => {
      try {
        const response = await api.get('/api/auth/me');
        const user = response.data;
        setPrefs(prev => ({
          ...prev,
          email_font: user.email_font || 'sans-serif',
          email_font_size: user.email_font_size || '13px',
          signature_font: user.signature_font || 'sans-serif',
          signature_font_size: user.signature_font_size || '13px',
          signature_mode: user.signature_mode || 'custom',
          team: user.team || 'CLIENT',
          image_width: user.image_width || '400px',
          image_height: user.image_height || 'auto',
        }));
      } catch (err) {
        console.error('Failed to fetch preferences', err);
      }
    };
    fetchPrefs();
  }, []);

  const handleChange = (key, value) => {
    setPrefs(prev => ({ ...prev, [key]: value }));
    setSaved(false);
    setError('');
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      await api.put('/api/auth/preferences', {
        email_font: prefs.email_font,
        email_font_size: prefs.email_font_size,
        signature_font: prefs.signature_font,
        signature_font_size: prefs.signature_font_size,
        signature_mode: prefs.signature_mode,
        team: prefs.team,
        image_width: prefs.image_width,
        image_height: prefs.image_height,
      });
      
      const response = await api.get('/api/auth/me');
      const user = response.data;
      localStorage.setItem('user', JSON.stringify(user));
      
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const getSelectedFont = () => FONTS.find(f => f.value === prefs.email_font) || FONTS[0];

  return (
    <div className="max-w-2xl mx-auto py-6 animate-in fade-in slide-in-from-bottom-3 duration-500">
      <div className="mb-8">
        <h1 className="text-2xl font-black text-white tracking-tight">Settings</h1>
        <p className="text-slate-500 text-sm mt-1">Manage your email composition preferences</p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-sm flex items-center gap-2 animate-in slide-in-from-top-3">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}

      <div className="space-y-6">
        <section className="bg-[#0f172a]/60 border border-white/5 rounded-[20px] p-8">
          <div className="flex items-center gap-3 mb-6">
            <Mail className="w-5 h-5 text-blue-400" />
            <div>
              <h2 className="text-lg font-black text-white">Email Composition</h2>
              <p className="text-slate-500 text-xs">How your emails appear to recipients</p>
            </div>
          </div>

          <div className="grid gap-6 md:grid-cols-2">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Font Family
              </label>
              <select
                value={prefs.email_font}
                onChange={e => handleChange('email_font', e.target.value)}
                className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-blue-500/50 outline-none appearance-none"
              >
                {FONTS.map(f => (
                  <option key={f.value} value={f.value} style={{ fontFamily: f.value }}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Font Size
              </label>
              <FontSizeDropdown
                value={prefs.email_font_size}
                onChange={s => handleChange('email_font_size', s)}
                options={FONT_SIZES}
              />
            </div>
          </div>

          <div className="mt-6 pt-6 border-t border-white/5">
            <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
              Preview (13px)
            </label>
            <div className="bg-[#0a0d14] border border-white/5 rounded-xl p-5 min-h-[200px] font-sans leading-relaxed whitespace-pre-wrap" style={{ fontFamily: prefs.email_font, fontSize: prefs.email_font_size }}>
              {SAMPLE_TEXT}
            </div>
          </div>
        </section>

        <section className="bg-[#0f172a]/60 border border-white/5 rounded-[20px] p-8">
          <div className="flex items-center gap-3 mb-6">
            <Type className="w-5 h-5 text-purple-400" />
            <div>
              <h2 className="text-lg font-black text-white">Signature</h2>
              <p className="text-slate-500 text-xs">Default signature behavior for new drafts</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Default Mode
              </label>
              <select
                value={prefs.signature_mode}
                onChange={e => handleChange('signature_mode', e.target.value)}
                className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-purple-500/50 outline-none appearance-none"
              >
                <option value="custom">Custom — Use your saved signature</option>
                <option value="auto">Auto — Generate from template</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Signature Font
              </label>
              <select
                value={prefs.signature_font}
                onChange={e => handleChange('signature_font', e.target.value)}
                className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-purple-500/50 outline-none appearance-none"
              >
                {FONTS.map(f => (
                  <option key={f.value} value={f.value} style={{ fontFamily: f.value }}>
                    {f.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Signature Font Size
              </label>
              <FontSizeDropdown
                value={prefs.signature_font_size}
                onChange={s => handleChange('signature_font_size', s)}
                options={FONT_SIZES}
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Signature Image Width
              </label>
              <FontSizeDropdown
                value={prefs.image_width}
                onChange={s => handleChange('image_width', s)}
                options={IMAGE_WIDTH_OPTIONS}
              />
            </div>
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Signature Image Height
              </label>
              <FontSizeDropdown
                value={prefs.image_height}
                onChange={s => handleChange('image_height', s)}
                options={IMAGE_HEIGHT_OPTIONS}
              />
            </div>
          </div>
        </section>

        <section className="bg-[#0f172a]/60 border border-white/5 rounded-[20px] p-8">
          <div className="flex items-center gap-3 mb-6">
            <Users className="w-5 h-5 text-amber-400" />
            <div>
              <h2 className="text-lg font-black text-white">Account</h2>
              <p className="text-slate-500 text-xs">Team assignment affects lead routing & metrics</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">
                Team
              </label>
              <select
                value={prefs.team}
                onChange={e => handleChange('team', e.target.value)}
                className="w-full bg-black/40 border border-white/5 rounded-xl px-4 py-3 text-sm text-white focus:border-amber-500/50 outline-none appearance-none"
              >
                <option value="CLIENT">Client</option>
                <option value="INVESTOR">Investor</option>
              </select>
            </div>
          </div>
        </section>

        <div className="flex gap-4 pt-4 border-t border-white/5">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 py-3 px-6 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-black text-xs uppercase tracking-widest shadow-lg shadow-blue-500/20 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
          >
            {saving ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Saving...</span>
              </>
            ) : saved ? (
              <>
                <CheckCircle className="w-4 h-4" />
                <span>Saved!</span>
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                <span>Save Changes</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;