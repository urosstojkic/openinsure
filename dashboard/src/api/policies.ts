import client from './client';
import type { Policy } from '../types';
import { mockPolicies } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getPolicies(): Promise<Policy[]> {
  if (USE_MOCK) return mockPolicies;
  try {
    const { data } = await client.get('/policies');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockPolicies;
  }
}

export async function getPolicy(id: string): Promise<Policy | undefined> {
  if (USE_MOCK) return mockPolicies.find((p) => p.id === id);
  try {
    const { data } = await client.get<Policy>(`/policies/${id}`);
    return data;
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
