import client from './client';
import type { Claim } from '../types';
import { mockClaims } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapClaim(c: any): Claim {
  const totalReserved = c.total_reserved || 0;
  const totalPaid = c.total_paid || 0;
  const totalIncurred = c.total_incurred || (totalReserved + totalPaid) || 0;
  return {
    ...c,
    id: c.id,
    claim_number: c.claim_number || c.id,
    policy_id: c.policy_id || '',
    policy_number: c.policy_number || '',
    status: c.status || 'reported',
    loss_date: c.loss_date || c.date_of_loss || '',
    reported_date: c.reported_date || '',
    severity: c.severity || 'medium',
    total_incurred: totalIncurred,
    total_paid: totalPaid,
    total_reserved: totalReserved,
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

// --- Subrogation (#79) ---

export interface SubrogationRecord {
  id: string;
  claim_id: string;
  status: string;
  liable_party: string;
  basis: string;
  estimated_recovery: number;
  actual_recovery: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export async function getSubrogation(claimId: string): Promise<SubrogationRecord[]> {
  try {
    const { data } = await client.get<SubrogationRecord[]>(`/claims/${claimId}/subrogation`);
    return data;
  } catch {
    return [];
  }
}

export async function createSubrogation(
  claimId: string,
  payload: { liable_party: string; basis: string; estimated_recovery: number; notes?: string },
): Promise<SubrogationRecord> {
  const { data } = await client.post<SubrogationRecord>(`/claims/${claimId}/subrogation`, payload);
  return data;
}
