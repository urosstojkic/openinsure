import client from './client';
import type { Claim } from '../types';
import { mockClaims } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapClaim(c: any): Claim {
  return {
    ...c,
    id: c.id,
    claim_number: c.claim_number || c.id,
    policy_id: c.policy_id || '',
    policy_number: c.policy_number || '',
    status: c.status || 'open',
    loss_date: c.loss_date || c.date_of_loss || '',
    reported_date: c.reported_date || '',
    severity: c.severity || 'medium',
    total_incurred: c.total_incurred || 0,
    total_paid: c.total_paid || 0,
    total_reserved: c.total_reserved || 0,
    assigned_to: c.assigned_to || 'Unassigned',
    description: c.description || '',
    lob: c.lob || 'cyber',
  };
}

export async function getClaims(): Promise<Claim[]> {
  if (USE_MOCK) return mockClaims;
  try {
    const { data } = await client.get('/claims');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapClaim);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockClaims;
  }
}

export async function getClaim(id: string): Promise<Claim | undefined> {
  if (USE_MOCK) return mockClaims.find((c) => c.id === id);
  try {
    const { data } = await client.get(`/claims/${id}`);
    return mapClaim(data);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockClaims.find((c) => c.id === id);
  }
}

export async function createClaim(payload: Record<string, unknown>): Promise<Claim> {
  try {
    const { data } = await client.post<Claim>('/claims', payload);
    return data;
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return { id: `mock-${Date.now()}`, ...payload } as unknown as Claim;
  }
}

export async function processClaim(id: string): Promise<{ message: string; [key: string]: unknown }> {
  const { data } = await client.post(`/claims/${id}/process`);
  return data;
}
