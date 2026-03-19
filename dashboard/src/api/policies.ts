import client from './client';
import type { Policy } from '../types';
import { mockPolicies } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapPolicy(p: any): Policy {
  return {
    ...p,
    id: p.id,
    policy_number: p.policy_number || p.id,
    insured_name: p.insured_name || p.policyholder_name || '',
    lob: p.lob || 'cyber',
    status: p.status || 'active',
    effective_date: p.effective_date || '',
    expiration_date: p.expiration_date || '',
    premium: p.premium || p.total_premium || 0,
    coverage_limit: p.coverage_limit || 0,
    deductible: p.deductible || 0,
    submission_id: p.submission_id || '',
  };
}

export async function getPolicies(): Promise<Policy[]> {
  if (USE_MOCK) return mockPolicies;
  try {
    const { data } = await client.get('/policies');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapPolicy);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockPolicies;
  }
}

export async function getPolicy(id: string): Promise<Policy | undefined> {
  if (USE_MOCK) return mockPolicies.find((p) => p.id === id);
  try {
    const { data } = await client.get(`/policies/${id}`);
    return mapPolicy(data);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockPolicies.find((p) => p.id === id);
  }
}

export async function createPolicy(payload: Record<string, unknown>): Promise<Policy> {
  try {
    const { data } = await client.post<Policy>('/policies', payload);
    return data;
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return { id: `mock-${Date.now()}`, ...payload } as unknown as Policy;
  }
}
