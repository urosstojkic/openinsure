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
  const subItems = Array.isArray(subs.data) ? subs.data : (subs.data.items || []);
  const polItems = Array.isArray(pols.data) ? pols.data : (pols.data.items || []);
  const claimItems = Array.isArray(claims.data) ? claims.data : (claims.data.items || []);
  return {
    total_submissions: subItems.length,
    active_policies: polItems.length,
    open_claims: claimItems.length,
    pending_decisions: 0,
    approval_rate: 0.73,
    avg_processing_time_hours: 4.2,
    escalation_rate: 0.08,
    recent_activity: [],
    agent_statuses: [],
  };
}
