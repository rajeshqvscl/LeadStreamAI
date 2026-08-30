import axios, { AxiosError, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { queryClient, queryKeys, invalidateQueries } from './queryClient';

// API base URL from environment
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '');

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  timeout: 30_000,
});

// Request interceptor - add auth token and user ID
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  // Add auth token
  const token = localStorage.getItem('token') || localStorage.getItem('token_admin');
  if (token && token !== 'undefined') {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  // Add user ID header
  const userStr = localStorage.getItem('user') || localStorage.getItem('user_admin');
  if (userStr) {
    try {
      const user = JSON.parse(userStr);
      if (user && user.id) {
        config.headers['X-User-Id'] = user.id;
      }
    } catch (e) {
      console.error('Failed to parse user for X-User-Id', e);
    }
  }
  
  // Cache busting for GET requests
  if (config.method === 'get') {
    config.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate';
    config.headers['Pragma'] = 'no-cache';
    config.headers['Expires'] = '0';
    config.params = { ...config.params, _t: Date.now() };
  }
  
  return config;
});

// Response interceptor - handle 401 and token refresh
let isRefreshing = false;
let failedQueue: Array<{ resolve: (token: string) => void; reject: (error: Error) => void }> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
  failedQueue.forEach(prom => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token!);
    }
  });
  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };
    
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Wait for token refresh
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(token => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          return api(originalRequest);
        }).catch(err => Promise.reject(err));
      }
      
      originalRequest._retry = true;
      isRefreshing = true;
      
      try {
        const userStr = localStorage.getItem('user') || localStorage.getItem('user_admin');
        let userId = null;
        if (userStr) {
          const user = JSON.parse(userStr);
          userId = user.id;
        }
        
        if (!userId) {
          throw new Error('No user ID available for token refresh');
        }
        
        const response = await api.post('/api/auth/refresh', {}, {
          headers: {
            'X-User-Id': userId,
            'Authorization': `Bearer ${localStorage.getItem('token') || localStorage.getItem('token_admin')}`,
          },
        });
        
        const newToken = response.data.access_token;
        localStorage.setItem('token', newToken);
        
        // Update user data if returned — MERGE with existing to preserve
        // fields like image_width/image_height that the refresh endpoint omits
        if (response.data.user) {
          const existing = JSON.parse(localStorage.getItem('user') || '{}');
          localStorage.setItem('user', JSON.stringify({ ...existing, ...response.data.user }));
        }
        
        api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        
        processQueue(null, newToken);
        return api(originalRequest);
      } catch (err) {
        processQueue(err as Error, null);
        localStorage.removeItem('token');
        localStorage.removeItem('user');
        window.location.href = '/login';
        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }
    
    return Promise.reject(error);
  }
);

// Type definitions
export interface PaginatedResponse<T> {
  leads?: T[];
  data?: T[];
  total: number;
  page?: number;
  per_page?: number;
}

export interface Lead {
  id: number;
  first_name: string | null;
  last_name: string | null;
  email: string;
  company_name: string | null;
  designation: string | null;
  phone: string | null;
  city: string | null;
  country: string | null;
  linkedin_url: string | null;
  persona: string;
  fit_score: number;
  family_office_name: string | null;
  labels: string[];
  source: string;
  user_id: number | null;
  user_name: string | null;
  validation_status: string;
  email_status: string | null;
  status: string;
  is_unsubscribed: boolean;
  email_opt_in: boolean;
  remarks: string | null;
  created_at: string | null;
  scheduled_at: string | null;
  sector: string | null;
  industry: string | null;
  lead_type: string | null;
  followup_stage: number;
  followup_status: string;
  followup_draft: string | null;
  followup_approved: boolean;
  is_responded: boolean;
  reply_intent: string | null;
  deal_size: string | null;
  meeting_link: string | null;
  meeting_time: string | null;
  pitch_deck_url: string | null;
  tracking_token: string | null;
  draft_template_used: string | null;
  first_outreach_at: string | null;
  first_outreach_subject: string | null;
  email_draft: string | null;
  email_approved_by: string | null;
  cc_email: string | null;
  gmail_thread_id: string | null;
  gmail_message_id: string | null;
  last_outreach_at: string | null;
  last_outreach_subject: string | null;
}

export interface DashboardStats {
  total_leads: number;
  total_ingested: number;
  classified: number;
  pending: number;
  sent: number;
  conversion_rate: number;
  daily_sent_count: number;
  daily_limit: number;
  open_rate: number;
  unique_opens: number;
  click_rate: number;
  unique_clicks: number;
  engagement_rate: number;
  bounce_rate: number;
  total_bounces: number;
  total_unsubs: number;
  unsub_rate: number;
  recent_logs: Array<{
    id: number;
    action: string;
    details: string;
    performed_by: string;
    created_at: string;
  }>;
  persona_data: Record<string, number>;
  inboxMessages: Array<{
    id: string;
    from: string;
    subject: string;
    date: string;
    snippet: string;
  }>;
}

// API functions using React Query patterns
export const leadsApi = {
  getLeads: async (params?: Record<string, unknown>): Promise<PaginatedResponse<Lead>> => {
    const response = await api.get<PaginatedResponse<Lead>>('/api/v1/leads', { params });
    return response.data;
  },
  
  getLead: async (id: number): Promise<Lead> => {
    const response = await api.get<Lead>(`/api/v1/leads/${id}`);
    return response.data;
  },
  
  updateLead: async (id: number, data: Partial<Lead>): Promise<{ message: string }> => {
    const response = await api.patch<{ message: string }>(`/api/v1/leads/${id}`, data);
    return response.data;
  },
  
  createLead: async (data: {
    first_name: string;
    last_name?: string;
    email: string;
    company_name?: string;
    designation?: string;
    phone?: string;
    city?: string;
    country?: string;
    linkedin_url?: string;
    persona?: string;
    source?: string;
    remarks?: string;
  }): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>('/api/v1/leads', data);
    return response.data;
  },
  
  deleteLead: async (id: number): Promise<{ message: string }> => {
    const response = await api.delete<{ message: string }>(`/api/v1/leads/${id}`);
    return response.data;
  },
  
  bulkDelete: async (ids: number[]): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>('/api/v1/leads/bulk-delete', ids);
    return response.data;
  },
  
  bulkLabels: async (lead_ids: number[], labels: string[]): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>('/api/v1/leads/bulk-labels', { lead_ids, labels });
    return response.data;
  },
  
  bulkApprove: async (ids: number[]): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>('/api/v1/leads/bulk-approve', ids);
    return response.data;
  },
  
  exportAll: async (): Promise<Lead[]> => {
    const response = await api.get<Lead[]>('/api/v1/leads/export-all');
    return response.data;
  },
  
  importGsheet: async (url: string) => {
    const response = await api.post('/api/v1/leads/import-gsheet', { url });
    return response.data;
  },
  
  getUniqueCompanies: async (): Promise<string[]> => {
    const response = await api.get<string[]>('/api/v1/leads/unique-companies');
    return response.data;
  },
  
  getLeadTimeline: async (id: number) => {
    const response = await api.get(`/api/v1/leads/${id}/timeline`);
    return response.data;
  },
  
  markResponded: async (id: number): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>(`/api/v1/leads/${id}/respond`);
    return response.data;
  },
};

export const dashboardApi = {
  getStats: async (params?: { month?: number; year?: number }): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/api/v1/health', { params });
    return response.data;
  },
  
  getCardDetail: async (cardType: string, params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/dashboard/card-detail', { params: { card_type: cardType, ...params } });
    return response.data;
  },
};

export const authApi = {
  login: async (username: string, password: string) => {
    const response = await api.post('/api/v1/auth/login', { username, password });
    return response.data;
  },
  
  logout: async () => {
    const response = await api.post('/api/v1/auth/logout');
    return response.data;
  },
  
  me: async () => {
    const response = await api.get('/api/v1/auth/me');
    return response.data;
  },
  
  refresh: async () => {
    const response = await api.post('/api/v1/auth/refresh');
    return response.data;
  },
  
  logout: async () => {
    const response = await api.post('/api/v1/auth/logout');
    return response.data;
  },
  
  updatePreferences: async (data: Record<string, unknown>) => {
    const response = await api.put('/api/v1/auth/preferences', data);
    return response.data;
  },
  
  requestAccess: async (userId: number) => {
    const response = await api.post('/api/v1/auth/request-access', { user_id: userId });
    return response.data;
  },
};

export const gmailApi = {
  getInbox: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/gmail/inbox', { params });
    return response.data;
  },
  
  getSent: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/gmail/sent', { params });
    return response.data;
  },
  
  getDrafts: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/gmail/drafts', { params });
    return response.data;
  },
  
  syncInbound: async () => {
    const response = await api.post('/api/v1/gmail/sync-inbound');
    return response.data;
  },
  
  getMessage: async (id: string) => {
    const response = await api.get(`/api/v1/gmail/message/${id}`);
    return response.data;
  },
};

export const followupsApi = {
  getFollowups: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/followups', { params });
    return response.data;
  },
  
  approveFollowup: async (leadId: number, customBody?: string) => {
    const response = await api.post(`/api/v1/leads/${leadId}/approve-followup`, { custom_body: customBody });
    return response.data;
  },
  
  bulkApproveFollowups: async (leadIds: number[]) => {
    const response = await api.post('/api/v1/leads/bulk-approve-followups', { lead_ids: leadIds });
    return response.data;
  },
  
  getPreview: async (leadId: number) => {
    const response = await api.get(`/api/v1/leads/${leadId}/followup-preview`);
    return response.data;
  },
};

export const campaignsApi = {
  getCampaigns: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/campaigns', { params });
    return response.data;
  },
  
  createCampaign: async (data: Record<string, unknown>) => {
    const response = await api.post('/api/v1/campaigns', data);
    return response.data;
  },
  
  updateCampaign: async (id: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/api/v1/campaigns/${id}`, data);
    return response.data;
  },
  
  deleteCampaign: async (id: number) => {
    const response = await api.delete(`/api/v1/campaigns/${id}`);
    return response.data;
  },
};

export const emailsApi = {
  getEmails: async (status?: string, params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/emails', { params: { status, ...params } });
    return response.data;
  },
  
  sendEmail: async (data: Record<string, unknown>) => {
    const response = await api.post('/api/v1/emails/send', data);
    return response.data;
  },
};

export const intelligenceApi = {
  getIntelligence: async (leadId: number) => {
    const response = await api.get(`/api/v1/intelligence/${leadId}`);
    return response.data;
  },
  
  generateIntelligence: async (leadId: number) => {
    const response = await api.post(`/api/v1/intelligence/${leadId}/generate`);
    return response.data;
  },
};

export const remindersApi = {
  getReminders: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/reminders', { params });
    return response.data;
  },
  
  createReminder: async (data: Record<string, unknown>) => {
    const response = await api.post('/api/v1/reminders', data);
    return response.data;
  },
  
  updateReminder: async (id: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/api/v1/reminders/${id}`, data);
    return response.data;
  },
  
  deleteReminder: async (id: number) => {
    const response = await api.delete(`/api/v1/reminders/${id}`);
    return response.data;
  },
};

export const companiesApi = {
  getCompanies: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/companies', { params });
    return response.data;
  },
  
  importGsheet: async (url: string) => {
    const response = await api.post('/api/v1/companies/import-gsheet', { url });
    return response.data;
  },
};

export const familyOfficesApi = {
  getFamilyOffices: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/family-offices', { params });
    return response.data;
  },
  
  getFamilyOffice: async (id: number) => {
    const response = await api.get(`/api/v1/family-offices/${id}`);
    return response.data;
  },
};

export const rocketreachApi = {
  search: async (params: Record<string, unknown>) => {
    const response = await api.post('/api/v1/rocketreach/search', params);
    return response.data;
  },
};

export const promptsApi = {
  getPrompts: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/prompts', { params });
    return response.data;
  },
  
  createPrompt: async (data: Record<string, unknown>) => {
    const response = await api.post('/api/v1/prompts', data);
    return response.data;
  },
  
  updatePrompt: async (id: number, data: Record<string, unknown>) => {
    const response = await api.patch(`/api/v1/prompts/${id}`, data);
    return response.data;
  },
  
  deletePrompt: async (id: number) => {
    const response = await api.delete(`/api/v1/prompts/${id}`);
    return response.data;
  },
};

export const metricsApi = {
  getMetrics: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/metrics', { params });
    return response.data;
  },
};

export const adminApi = {
  getUsers: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/admin/users', { params });
    return response.data;
  },
  
  getAuditLogs: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/admin/audit-logs', { params });
    return response.data;
  },
  
  getVelocity: async (period: string = 'daily') => {
    const response = await api.get('/api/v1/admin/velocity', { params: { period } });
    return response.data;
  },
  
  getProductivity: async () => {
    const response = await api.get('/api/v1/admin/productivity');
    return response.data;
  },
  
  getActiveUsers: async () => {
    const response = await api.get('/api/v1/admin/active-users');
    return response.data;
  },
  
  dispatchReport: async () => {
    const response = await api.post('/api/v1/admin/dispatch-report');
    return response.data;
  },
};

export const historyApi = {
  getHistory: async (params?: Record<string, unknown>) => {
    const response = await api.get('/api/v1/history', { params });
    return response.data;
  },
};

// Re-export for convenience
export { queryClient, queryKeys, invalidateQueries } from './queryClient';
export { api } from './api';