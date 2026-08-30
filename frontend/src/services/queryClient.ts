import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Cache data for 10 seconds by default
      staleTime: 10_000,
      // Retry failed requests once
      retry: 1,
      // Don't refetch on window focus (can be noisy)
      refetchOnWindowFocus: false,
      // Refetch when component remounts if data is stale
      refetchOnMount: 'always',
      // Refetch on reconnect
      refetchOnReconnect: 'always',
    },
    mutations: {
      // Retry mutations once
      retry: 1,
    },
  },
});

// Query key factories for consistent keys across the app
export const queryKeys = {
  // Auth
  user: () => ['user'] as const,
  
  // Leads
  leads: (params?: Record<string, unknown>) => ['leads', params] as const,
  lead: (id: number) => ['lead', id] as const,
  leadTimeline: (id: number) => ['lead', id, 'timeline'] as const,
  
  // Emails
  emails: (status?: string, params?: Record<string, unknown>) => ['emails', status, params] as const,
  email: (id: number) => ['email', id] as const,
  
  // Dashboard
  dashboardStats: (params?: Record<string, unknown>) => ['dashboard', 'stats', params] as const,
  dashboardCardDetail: (cardType: string, params?: Record<string, unknown>) => ['dashboard', 'card-detail', cardType, params] as const,
  
  // Follow-ups
  followups: (params?: Record<string, unknown>) => ['followups', params] as const,
  followupPreview: (leadId: number) => ['followup', 'preview', leadId] as const,
  
  // Campaigns
  campaigns: (params?: Record<string, unknown>) => ['campaigns', params] as const,
  campaign: (id: number) => ['campaign', id] as const,
  
  // Gmail
  inbox: (params?: Record<string, unknown>) => ['gmail', 'inbox', params] as const,
  sent: (params?: Record<string, unknown>) => ['gmail', 'sent', params] as const,
  drafts: (params?: Record<string, unknown>) => ['gmail', 'drafts', params] as const,
  gmailMessage: (id: string) => ['gmail', 'message', id] as const,
  
  // Inbound Deals
  inboundDeals: (params?: Record<string, unknown>) => ['inbound-deals', params] as const,
  
  // Meetings
  meetings: (params?: Record<string, unknown>) => ['meetings', params] as const,
  
  // Reminders
  reminders: (params?: Record<string, unknown>) => ['reminders', params] as const,
  
  // Intelligence
  intelligence: (leadId: number) => ['intelligence', leadId] as const,
  
  // Companies
  companies: (params?: Record<string, unknown>) => ['companies', params] as const,
  
  // Family Offices
  familyOffices: (params?: Record<string, unknown>) => ['family-offices', params] as const,
  familyOffice: (id: number) => ['family-office', id] as const,
  
  // RocketReach
  rocketreachSearch: (params?: Record<string, unknown>) => ['rocketreach', 'search', params] as const,
  
  // Prompts
  prompts: (params?: Record<string, unknown>) => ['prompts', params] as const,
  
  // Metrics
  metrics: (params?: Record<string, unknown>) => ['metrics', params] as const,
  
  // Admin
  adminUsers: (params?: Record<string, unknown>) => ['admin', 'users', params] as const,
  adminAuditLogs: (params?: Record<string, unknown>) => ['admin', 'audit-logs', params] as const,
  adminVelocity: (period?: string) => ['admin', 'velocity', period] as const,
  adminProductivity: () => ['admin', 'productivity'] as const,
  adminActiveUsers: () => ['admin', 'active-users'] as const,
  
  // History
  history: (params?: Record<string, unknown>) => ['history', params] as const,
};

// Helper to invalidate related queries
export const invalidateQueries = {
  allLeads: () => queryClient.invalidateQueries({ queryKey: ['leads'] }),
  lead: (id: number) => queryClient.invalidateQueries({ queryKey: ['lead', id] }),
  leadTimeline: (id: number) => queryClient.invalidateQueries({ queryKey: ['lead', id, 'timeline'] }),
  
  allEmails: () => queryClient.invalidateQueries({ queryKey: ['emails'] }),
  email: (id: number) => queryClient.invalidateQueries({ queryKey: ['email', id] }),
  
  dashboard: () => queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
  
  allFollowups: () => queryClient.invalidateQueries({ queryKey: ['followups'] }),
  
  allCampaigns: () => queryClient.invalidateQueries({ queryKey: ['campaigns'] }),
  
  gmailInbox: () => queryClient.invalidateQueries({ queryKey: ['gmail', 'inbox'] }),
  gmailSent: () => queryClient.invalidateQueries({ queryKey: ['gmail', 'sent'] }),
  gmailDrafts: () => queryClient.invalidateQueries({ queryKey: ['gmail', 'drafts'] }),
  
  inboundDeals: () => queryClient.invalidateQueries({ queryKey: ['inbound-deals'] }),
  
  meetings: () => queryClient.invalidateQueries({ queryKey: ['meetings'] }),
  
  reminders: () => queryClient.invalidateQueries({ queryKey: ['reminders'] }),
  
  intelligence: (id: number) => queryClient.invalidateQueries({ queryKey: ['intelligence', id] }),
  
  companies: () => queryClient.invalidateQueries({ queryKey: ['companies'] }),
  
  familyOffices: () => queryClient.invalidateQueries({ queryKey: ['family-offices'] }),
  
  prompts: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
  
  metrics: () => queryClient.invalidateQueries({ queryKey: ['metrics'] }),
  
  admin: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  
  history: () => queryClient.invalidateQueries({ queryKey: ['history'] }),
};