import client from './client';
import type { Submission } from '../types';
import { mockSubmissions } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapSubmission(s: any): Submission {
  return {
    ...s,
    id: s.id,
    submission_number: s.submission_number || undefined,
    applicant_name: s.applicant_name || '',
    company_name: s.company_name || '',
    lob: s.lob || s.line_of_business || 'cyber',
    status: s.status || 'received',
    risk_score: s.risk_score ?? (s.risk_data?.risk_score) ?? 0,
    priority: s.priority || 'medium',
    assigned_to: s.assigned_to || null,
    received_date: s.received_date || s.created_at || new Date().toISOString(),
    annual_revenue: s.annual_revenue || 0,
    employee_count: s.employee_count || 0,
    industry: s.industry || '',
    requested_coverage: s.requested_coverage || 0,
    documents: s.documents || [],
    decision_history: s.decision_history || [],
  };
}

export async function getSubmissions(): Promise<Submission[]> {
  if (USE_MOCK) return mockSubmissions;
  try {
    const { data } = await client.get('/submissions');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapSubmission);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockSubmissions;
  }
}

export async function getSubmission(id: string): Promise<Submission | undefined> {
  if (USE_MOCK) return mockSubmissions.find((s) => s.id === id);
  try {
    const { data } = await client.get(`/submissions/${id}`);
    return mapSubmission(data);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockSubmissions.find((s) => s.id === id);
  }
}

export async function createSubmission(payload: Record<string, unknown>): Promise<Submission> {
  try {
    const { data } = await client.post<Submission>('/submissions', payload);
    return data;
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return { id: `mock-${Date.now()}`, ...payload } as unknown as Submission;
  }
}

export async function processSubmission(id: string): Promise<{ message: string; [key: string]: unknown }> {
  const { data } = await client.post(`/submissions/${id}/process`);
  return data;
}
