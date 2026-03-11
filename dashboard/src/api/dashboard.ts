import client from './client';
import type { DashboardStats } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  const [subs, pols, claims] = await Promise.all([
    client.get('/submissions'),
    client.get('/policies'),
    client.get('/claims'),
  ]);
  const subTotal = subs.data?.total ?? (Array.isArray(subs.data) ? subs.data : (subs.data.items || [])).length;
  const polTotal = pols.data?.total ?? (Array.isArray(pols.data) ? pols.data : (pols.data.items || [])).length;
  const claimTotal = claims.data?.total ?? (Array.isArray(claims.data) ? claims.data : (claims.data.items || [])).length;
  return {
    total_submissions: subTotal,
    active_policies: polTotal,
    open_claims: claimTotal,
    pending_decisions: 0,
    approval_rate: 0.73,
    avg_processing_time_hours: 4.2,
    escalation_rate: 0.08,
    recent_activity: [],
    agent_statuses: [],
  };
}
