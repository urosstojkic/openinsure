import client from './client';
import type { Claim, ClaimStatus } from '../types';
import { mockClaims } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

const STATUS_MAP: Record<string, ClaimStatus> = {
  under_investigation: 'investigating',
  approved: 'closed',
  reopened: 'reported',
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function mapClaim(c: any): Claim {
  const totalReserved = c.total_reserved || 0;
  const totalPaid = c.total_paid || 0;
  const totalIncurred = c.total_incurred || (totalReserved + totalPaid) || 0;
  const rawStatus = c.status || 'reported';
  return {
    ...c,
    id: c.id,
    claim_number: c.claim_number || c.id,
    policy_id: c.policy_id || '',
    policy_number: c.policy_number || '',
    status: (STATUS_MAP[rawStatus] || rawStatus) as ClaimStatus,
    loss_date: c.loss_date || c.date_of_loss || '',
    reported_date: c.reported_date || c.created_at || '',
    severity: c.severity || 'medium',
    total_incurred: totalIncurred,
    total_paid: totalPaid,
    total_reserved: totalReserved,
    assigned_to: c.assigned_to || 'Unassigned',
    description: c.description || '',
    lob: c.lob || 'cyber',
    claim_type: c.claim_type || '',
    reported_by: c.reported_by || '',
    fraud_score: c.fraud_score ?? c.metadata?.fraud_score ?? c.risk_data?.fraud_score ?? c.assessment?.fraud_score ?? null,
    cause_of_loss: c.cause_of_loss || c.claim_type || '',
    reserves: c.reserves || [],
    payments: c.payments || [],
    metadata: c.metadata || {},
  };
}

export interface PaginatedClaims {
  items: Claim[];
  total: number;
  skip: number;
  limit: number;
}

export async function getClaims(): Promise<Claim[]> {
  if (USE_MOCK) return mockClaims;
  try {
    const { data } = await client.get('/claims', { params: { limit: 100 } });
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapClaim);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockClaims;
  }
}

export async function getClaimsPaginated(skip: number, limit: number): Promise<PaginatedClaims> {
  if (USE_MOCK) {
    const page = mockClaims.slice(skip, skip + limit);
    return { items: page, total: mockClaims.length, skip, limit };
  }
  try {
    const { data } = await client.get('/claims', { params: { skip, limit } });
    if (Array.isArray(data)) {
      return { items: data.map(mapClaim), total: data.length, skip, limit };
    }
    return {
      items: (data.items || []).map(mapClaim),
      total: data.total ?? data.items?.length ?? 0,
      skip: data.skip ?? skip,
      limit: data.limit ?? limit,
    };
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    const page = mockClaims.slice(skip, skip + limit);
    return { items: page, total: mockClaims.length, skip, limit };
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
  const { data } = await client.post<Claim>('/claims', payload);
  return data;
}

export async function processClaim(id: string): Promise<{ message: string; [key: string]: unknown }> {
  const { data } = await client.post(`/claims/${id}/process`, null, { timeout: 180_000 });
  return data;
}

export async function setReserve(id: string, payload: { category: string; amount: number; notes?: string }): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/claims/${id}/reserve`, payload);
  return data;
}

export async function closeClaim(id: string, payload: { reason: string; outcome?: string }): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/claims/${id}/close`, payload);
  return data;
}

export async function reopenClaim(id: string, payload: { reason: string }): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/claims/${id}/reopen`, payload);
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
    const { data } = await client.get(`/claims/${claimId}/subrogation`);
    const items = Array.isArray(data) ? data : (data?.items ?? []);
    return items;
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
