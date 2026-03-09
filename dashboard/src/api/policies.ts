import client from './client';
import type { Policy } from '../types';
import { mockPolicies } from '../data/mock';

const USE_MOCK = true;

export async function getPolicies(): Promise<Policy[]> {
  if (USE_MOCK) return mockPolicies;
  const { data } = await client.get<Policy[]>('/policies');
  return data;
}

export async function getPolicy(id: string): Promise<Policy | undefined> {
  if (USE_MOCK) return mockPolicies.find((p) => p.id === id);
  const { data } = await client.get<Policy>(`/policies/${id}`);
  return data;
}
