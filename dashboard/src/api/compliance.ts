import client from './client';
import type { AgentDecision, ComplianceSummary } from '../types';
import { mockDecisions, mockCompliance } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

export async function getDecisions(): Promise<AgentDecision[]> {
  if (USE_MOCK) return mockDecisions;
  try {
    const { data } = await client.get('/compliance/decisions');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('[API] Decisions fallback:', error);
    return mockDecisions;
  }
}

export async function getComplianceSummary(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  try {
    const [decisions, audit, systems] = await Promise.all([
      client.get('/compliance/decisions').catch(() => ({ data: { items: [], total: 0 } })),
      client.get('/compliance/audit-trail').catch(() => ({ data: { items: [] } })),
      client.get('/compliance/system-inventory').catch(() => ({ data: { systems: [] } })),
    ]);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const decisionItems: any[] = decisions.data.items || [];
    const decisions_by_agent: Record<string, number> = {};
    const decisions_by_type: Record<string, number> = {};
    let oversightRequired = 0;
    let oversightRecommended = 0;
    let totalConfidence = 0;

    for (const d of decisionItems) {
      const agent = d.agent_name || d.agent || 'unknown';
      const dtype = d.decision_type || 'unknown';
      decisions_by_agent[agent] = (decisions_by_agent[agent] || 0) + 1;
      decisions_by_type[dtype] = (decisions_by_type[dtype] || 0) + 1;
      if (d.human_oversight === 'required') oversightRequired++;
      if (d.human_oversight === 'recommended') oversightRecommended++;
      totalConfidence += d.confidence || 0;
    }

    return {
      total_decisions: decisions.data.total || decisionItems.length,
      decisions_by_agent,
      decisions_by_type,
      oversight_required_count: oversightRequired,
      oversight_recommended_count: oversightRecommended,
      avg_confidence: decisionItems.length > 0 ? totalConfidence / decisionItems.length : 0,
      bias_metrics: [],
      audit_trail: audit.data.items || [],
      ai_systems: systems.data.systems || [],
    };
  } catch (error) {
    console.warn('[API] Compliance summary fallback:', error);
    return mockCompliance;
  }
}
