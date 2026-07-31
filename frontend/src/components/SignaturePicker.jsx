import React from 'react';
import { Loader2, Star, Check } from 'lucide-react';

/**
 * Reusable Signature Picker — purely presentational.
 *
 * Handles all states automatically based on props:
 *   loading=true   → animated spinner
 *   signatures=[]  → "No Signatures Found" message
 *   signatures=[s] → auto-selected confirmation card
 *   signatures=[s1,s2,...] → radio-card selection UI
 *
 * Props:
 *   signatures   — array of { id, name, content, is_default }
 *   loading      — boolean
 *   selectedId   — number | null (controlled)
 *   onSelect     — (sigId: number | null, sigName: string) => void
 *   className    — optional wrapper class
 */
const SignaturePicker = ({ signatures = [], loading = false, selectedId = null, onSelect, className = '' }) => {
  // ── Loading ──
  if (loading) {
    return (
      <div className={`flex items-center justify-center py-12 ${className}`}>
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <Loader2 className="w-7 h-7 text-amber-400 animate-spin" />
            <div className="absolute inset-0 animate-ping opacity-20">
              <div className="w-7 h-7 rounded-full bg-amber-400" />
            </div>
          </div>
          <p className="text-slate-500 text-[11px] font-medium">Loading signatures...</p>
        </div>
      </div>
    );
  }

  // ── No Signatures ──
  if (signatures.length === 0) {
    return (
      <div className={`flex flex-col items-center justify-center py-12 text-center ${className}`}>
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-amber-500/10 to-orange-500/10 border border-amber-500/20 flex items-center justify-center mb-5 shadow-lg shadow-amber-500/5">
          <Star className="w-7 h-7 text-amber-400" />
        </div>
        <p className="text-white font-bold text-base mb-1.5">No Signatures Found</p>
        <p className="text-slate-500 text-[12px] max-w-[280px] leading-relaxed">
          Create one on the{' '}
          <a href="/dashboard/signatures" className="text-amber-400 hover:text-amber-300 underline font-semibold transition-colors">
            Signatures
          </a>{' '}
          page to personalize your emails.
        </p>
        <div className="mt-5 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/5">
          <p className="text-slate-600 text-[10px] font-medium">Drafts will be generated without a signature.</p>
        </div>
      </div>
    );
  }

  // ── Single Signature (auto-selected) ──
  if (signatures.length === 1) {
    const sig = signatures[0];
    return (
      <div className={`flex flex-col items-center justify-center py-10 text-center ${className}`}>
        <div className="relative mb-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/10 to-green-500/10 border border-emerald-500/20 flex items-center justify-center shadow-lg shadow-emerald-500/5">
            <Check className="w-7 h-7 text-emerald-400" />
          </div>
          <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center">
            <Check className="w-3 h-3 text-white" />
          </div>
        </div>
        <p className="text-white font-bold text-sm mb-3">Signature Selected</p>
        <div className="flex items-center gap-2.5 px-5 py-3 rounded-2xl bg-gradient-to-r from-amber-500/10 to-amber-500/5 border border-amber-500/20">
          <span className="text-base">✍️</span>
          <div className="text-left">
            <p className="text-white font-bold text-sm">{sig.name}</p>
            {sig.content && (
              <p className="text-slate-500 text-[10px] mt-0.5 truncate max-w-[200px]">
                {sig.content.replace(/[#*[\]`>_]/g, '').replace(/\n/g, ' ').substring(0, 40)}
              </p>
            )}
          </div>
          {sig.is_default && (
            <span className="text-[9px] bg-amber-500/15 text-amber-400 border border-amber-500/25 px-2 py-0.5 rounded-lg font-black uppercase tracking-wider ml-2">
              Default
            </span>
          )}
        </div>
        <p className="text-slate-600 text-[10px] mt-4">Auto-selected — only one signature available.</p>
      </div>
    );
  }

  // ── Multiple Signatures ──
  return (
    <div className={className}>
      <div className="flex items-center gap-2.5 mb-4 px-1">
        <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-amber-500/15 to-orange-500/10 flex items-center justify-center">
          <Star className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <p className="text-slate-300 text-[12px] font-medium">
          You have <span className="text-white font-bold">{signatures.length}</span> signatures
        </p>
      </div>

      <div className="space-y-2 max-h-[320px] overflow-y-auto custom-scrollbar pr-1.5">
        {signatures.map((sig, idx) => {
          const previewText = sig.content
            ? sig.content.replace(/[#*[\]`>_]/g, '').replace(/\n/g, ' ').substring(0, 60)
            : '';
          const isSelected = selectedId === sig.id;

          return (
            <label
              key={sig.id}
              className={`group relative flex items-start gap-4 p-4 rounded-2xl border-2 cursor-pointer transition-all duration-200 ${
                isSelected
                  ? 'border-amber-500/60 bg-gradient-to-r from-amber-500/8 to-amber-500/3 shadow-[0_0_20px_rgba(251,191,36,0.06)]'
                  : 'border-white/[0.06] bg-white/[0.015] hover:bg-white/[0.03] hover:border-white/[0.12]'
              }`}
            >
              {/* Selection ring */}
              <div
                className={`mt-0.5 w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all duration-200 ${
                  isSelected
                    ? 'border-amber-500 bg-amber-500 shadow-[0_0_8px_rgba(251,191,36,0.3)]'
                    : 'border-slate-600 group-hover:border-slate-500'
                }`}
              >
                {isSelected && (
                  <div className="w-5 h-5 rounded-full bg-amber-500 flex items-center justify-center animate-in zoom-in duration-150">
                    <Check className="w-3 h-3 text-white" />
                  </div>
                )}
              </div>

              <input
                type="radio"
                name="sig-picker"
                value={sig.id}
                className="sr-only"
                checked={isSelected}
                onChange={() => onSelect && onSelect(sig.id, sig.name)}
              />

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <p className={`text-sm font-bold transition-colors ${isSelected ? 'text-white' : 'text-slate-200 group-hover:text-white'}`}>
                    ✍️ {sig.name}
                  </p>
                  {sig.is_default && (
                    <span className="text-[8px] bg-amber-500/12 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded-lg font-black uppercase tracking-wider">
                      Default
                    </span>
                  )}
                </div>

                {previewText && (
                  <div className="mt-2 relative">
                    <div className="text-slate-500 text-[10px] font-mono overflow-hidden leading-relaxed line-clamp-2">
                      {previewText}
                    </div>
                    {idx < signatures.length - 1 && (
                      <div className="absolute -bottom-1 left-0 right-0 h-4 bg-gradient-to-t from-[#0d1117] to-transparent pointer-events-none" />
                    )}
                  </div>
                )}
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
};

export default SignaturePicker;
