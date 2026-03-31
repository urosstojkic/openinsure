import client from './client';
import type { DashboardStats, AgentStatus, ActivityEvent } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

/** Shape returned by GET /metrics/agent-status */
interface AgentStatusAPIItem {
  name: string;
  display_name: string;
  status: 'active' | 'idle' | 'error';
  last_action: string;
  decisions_today: number;
  total_decisions: number;
}

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  try {
    // Fetch core metrics, agent status, and recent submissions in parallel
    const [metricsRes, agentStatusRes, submissionsRes, claimsRes] = await Promise.all([
      client.get('/metrics/summary').catch(() => null),
      client.get('/metrics/agent-status').catch(() => null),
      client.get('/submissions').catch(() => null),
      client.get('/claims').catch(() => null),
    ]);

    // ── Core KPIs ──
    const data = metricsRes?.data ?? {};
    const openClaims = data.claims?.by_status?.open
      ?? data.claims?.by_status?.reported
      ?? data.kpis?.open_claims
      ?? data.claims?.total
      ?? 0;

    // ── Agent Status — real data from /metrics/agent-status (#155) ──
    const agentItems: AgentStatusAPIItem[] = agentStatusRes?.data?.agents ?? [];
    const agentStatuses: AgentStatus[] = agentItems.map((a) => ({
      name: a.name as AgentStatus['name'],
      display_name: a.display_name,
      status: a.status,
      last_action: a.last_action || 'Ready',
      decisions_today: a.decisions_today,
    }));

    // ── Recent Activity — last 5 submissions + claims ──
    const recentActivity: ActivityEvent[] = [];
    const subs: Record<string, unknown>[] = submissionsRes?.data?.items || (Array.isArray(submissionsRes?.data) ? submissionsRes.data : []);
    for (const s of subs.slice(0, 5)) {
      recentActivity.push({
        id: `sub-${s.id}`,
        timestamp: (s.updated_at as string) || (s.created_at as string) || (s.received_date as string) || '',
        type: 'submission',
        description: `Submission ${(s.submission_number as string) || (s.id as string).slice(0, 8)} — ${(s.applicant_name as string) || 'Unknown'} (${s.status})`,
        actor: (s.assigned_to as string) || 'System',
        is_agent: !!((s.assigned_to as string) || '').includes('agent'),
      });
    }
    const claimsList: Record<string, unknown>[] = claimsRes?.data?.items || (Array.isArray(claimsRes?.data) ? claimsRes.data : []);
    for (const c of claimsList.slice(0, 3)) {
      recentActivity.push({
        id: `claim-${c.id}`,
        timestamp: (c.updated_at as string) || (c.reported_date as string) || '',
        type: 'claim',
        description: `Claim ${(c.claim_number as string) || (c.id as string).slice(0, 8)} — ${c.status}`,
        actor: (c.assigned_to as string) || 'System',
        is_agent: false,
      });
    }
    // Sort by timestamp desc
    recentActivity.sort((a, b) => (b.timestamp > a.timestamp ? 1 : -1));

    return {
      total_submissions: data.submissions?.total ?? subs.length,
      active_policies: data.policies?.active ?? 0,
      open_claims: openClaims,
      pending_decisions: data.kpis?.pending_escalations || 0,
      approval_rate: data.submissions?.bind_rate ? data.submissions.bind_rate / 100 : 0,
      avg_processing_time_hours: 0,
      escalation_rate: data.submissions?.bind_rate ? (100 - data.submissions.bind_rate - (data.submissions.decline_rate ?? 0)) / 100 : 0,
      recent_activity: recentActivity.slice(0, 10),
      agent_statuses: agentStatuses,
    };
  } catch (error) {
    console.warn('[API] Metrics error:', error);
    if (USE_MOCK) return mockDashboardStats;
    // In live mode, return empty data structure instead of mock fallback
    return {
      total_submissions: 0,
      active_policies: 0,
      open_claims: 0,
      pending_decisions: 0,
      approval_rate: 0,
      avg_processing_time_hours: 0,
      escalation_rate: 0,
      recent_activity: [],
      agent_statuses: [],
    };
  }
}
