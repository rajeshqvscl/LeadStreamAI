export const FOLLOWUP_CONFIG = {
  CLIENT: {
    maxStages: 2,
    scheduleDays: [2, 4],
    getStageLabel: (stage) => {
      const labels = ['Day 2', 'Day 4'];
      return labels[stage] || `${stage + 1}th Follow-up`;
    }
  },
  INVESTOR: {
    maxStages: 3,
    scheduleDays: [2, 5, 8],
    getStageLabel: (stage) => {
      const labels = ['Day 2', 'Day 5', 'Day 8'];
      return labels[stage] || `${stage + 1}th Follow-up`;
    }
  }
};

export const LEAD_TYPES = ['All', 'Investor', 'Client'];

export const STATUS_OPTIONS = ['DUE', 'SENT', 'REPLIED', 'IN_PROGRESS', 'STOPPED', 'COMPLETED'];

const INVESTOR_KEYWORDS = [
  'VENTURE', 'CAPITAL', 'EQUITY', 'INVEST', 'PARTNER', 'ASSET',
  'FAMILY OFFICE', 'ANGEL', 'CIRCLE', 'NETWORK', 'FUND', 'VC', 'PE', 'ADVISORY',
  'HOLDING', 'SFO', 'OFFICE', 'MANAGEMENT', 'PRIVATE', 'TRUST', 'WEALTH',
  'ASSOCIATES', 'GROUP', 'PARTNERS', 'ADVISORS', 'FOUNDATION'
];

const CLIENT_KEYWORDS = ['SAAS', 'FINTECH', 'SOFTWARE', 'CLIENT', 'CUSTOMER', 'PRODUCT', 'SERVICES'];

export const getLeadType = (lead) => {
  const text = String(`${lead.company_name || lead.company || ''} ${lead.sector || ''} ${lead.persona || ''}`).toUpperCase();

  if (INVESTOR_KEYWORDS.some(kw => text.includes(kw))) return 'Investor';

  if (lead.lead_type) {
    const lt = String(lead.lead_type).toUpperCase();
    if (lt.includes('CLIENT')) return 'Client';
    if (lt.includes('INVESTOR')) return 'Investor';
  }

  if (CLIENT_KEYWORDS.some(kw => text.includes(kw))) return 'Client';

  return 'Investor';
};

export const getStageColor = (stage) => {
  if (stage === 0) return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
  if (stage === 1) return 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
  if (stage === 2) return 'bg-violet-500/10 text-violet-400 border-violet-500/20';
  if (stage === 3) return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (stage === 4) return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  if (stage >= 5) return 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
};

export const getStageConfigs = (typeFilter) => {
  if (typeFilter === 'All') {
    return [
      { label: 'Day 2', stage: 0, type: 'Investor' },
      { label: 'Day 5', stage: 1, type: 'Investor' },
      { label: 'Day 8', stage: 2, type: 'Investor' },
    ];
  }
  const config = FOLLOWUP_CONFIG[typeFilter.toUpperCase()];
  if (!config) return [];
  return config.scheduleDays.map((days, i) => ({
    label: `Day ${days}`,
    stage: i
  }));
};

export const getStageLabel = (lead) => {
  const leadType = getLeadType(lead);
  const config = FOLLOWUP_CONFIG[leadType.toUpperCase()];
  if (!config) return `${lead.followup_stage + 1}th Follow-up`;
  return config.getStageLabel(lead.followup_stage);
};
