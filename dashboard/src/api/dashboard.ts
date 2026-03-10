import client from './client';
import type { DashboardStats } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  try {
    const { data } = await client.get<DashboardStats>('/dashboard/stats');
    return data;
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockDashboardStats;
  }
}
