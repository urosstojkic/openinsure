import client from './client';
import type { DashboardStats } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  try {
    const { data } = await client.get('/metrics/summary');
    const openClaims = data.claims.by_status?.open
      ?? data.claims.by_status?.reported
      ?? data.kpis.open_claims
      ?? data.claims.total
      ?? 0;
    return {
      total_submissions: data.submissions.total,
      active_policies: data.policies.active,
      open_claims: openClaims,
      pending_decisions: data.kpis.pending_escalations || 0,
      approval_rate: data.submissions.bind_rate / 100,
      avg_processing_time_hours: 0,
      escalation_rate: (100 - data.submissions.bind_rate - data.submissions.decline_rate) / 100,
      recent_activity: [],
      agent_statuses: [],
    };
  } catch (error) {
    console.warn('[API] Metrics fallback:', error);
    return mockDashboardStats;
  }
}
