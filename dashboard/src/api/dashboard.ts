import client from './client';
import type { DashboardStats } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = true;

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  const { data } = await client.get<DashboardStats>('/dashboard/stats');
  return data;
}
