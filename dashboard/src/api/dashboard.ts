import client from './client';
import type { DashboardStats, AgentStatus, ActivityEvent, AgentName } from '../types';
import { mockDashboardStats } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

/** The 6 Foundry agents */
const FOUNDRY_AGENTS: { name: AgentName; display_name: string }[] = [
  { name: 'triage_agent', display_name: 'Triage Agent' },
  { name: 'underwriting_agent', display_name: 'Underwriting Agent' },
  { name: 'claims_agent', display_name: 'Claims Agent' },
  { name: 'compliance_agent', display_name: 'Compliance Agent' },
  { name: 'fraud_agent', display_name: 'Fraud Detection Agent' },
  // orchestrator counted as a logical agent
  { name: 'triage_agent' as AgentName, display_name: 'Orchestrator Agent' },
];

export async function getDashboardStats(): Promise<DashboardStats> {
  if (USE_MOCK) return mockDashboardStats;
  try {
    // Fetch core metrics, decisions, and recent submissions in parallel
    const [metricsRes, decisionsRes, submissionsRes, claimsRes] = await Promise.all([
      client.get('/metrics/summary').catch(() => null),
      client.get('/compliance/decisions', { params: { limit: 10 } }).catch(() => null),
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

    // ── Agent Decisions Today (#74) ──
    const decisionItems: Record<string, unknown>[] = decisionsRes?.data?.items || (Array.isArray(decisionsRes?.data) ? decisionsRes.data : []);
    const today = new Date().toISOString().slice(0, 10);
    const todayDecisions = decisionItems.filter(
      (d) => ((d.timestamp as string) || (d.created_at as string) || '').slice(0, 10) === today,
    );
    const agentDecisionCounts: Record<string, number> = {};
    const agentLastAction: Record<string, string> = {};
    for (const d of todayDecisions) {
      const agent = (d.agent_name as string) || (d.agent as string) || 'unknown';
      agentDecisionCounts[agent] = (agentDecisionCounts[agent] || 0) + 1;
      if (!agentLastAction[agent]) {
        agentLastAction[agent] = (d.outcome as string) || (d.decision_type as string) || '';
      }
    }

    // ── Agent Status (#74) — show all 6 Foundry agents ──
    const agentStatuses: AgentStatus[] = FOUNDRY_AGENTS.slice(0, 6).map(({ name, display_name }) => {
      const count = agentDecisionCounts[name] || 0;
      return {
        name,
        display_name,
        status: count > 0 ? 'active' as const : 'idle' as const,
        last_action: agentLastAction[name] || (count > 0 ? 'Processed decisions today' : 'Ready'),
        decisions_today: count,
      };
    });

    // ── Recent Activity (#74) — last 5 submissions + claims ──
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
    console.warn('[API] Metrics fallback:', error);
    return mockDashboardStats;
  }
}
