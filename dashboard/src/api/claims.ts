import client from './client';
import type { Claim } from '../types';
import { mockClaims } from '../data/mock';

const USE_MOCK = true;

export async function getClaims(): Promise<Claim[]> {
  if (USE_MOCK) return mockClaims;
  const { data } = await client.get<Claim[]>('/claims');
  return data;
}

export async function getClaim(id: string): Promise<Claim | undefined> {
  if (USE_MOCK) return mockClaims.find((c) => c.id === id);
  const { data } = await client.get<Claim>(`/claims/${id}`);
  return data;
}

export async function createClaim(payload: Record<string, unknown>): Promise<Claim> {
  const { data } = await client.post<Claim>('/claims', payload);
  return data;
}
