import client from './client';
import type { AgentDecision, AgentName, DecisionType, OversightLevel, ComplianceSummary } from '../types';
import { mockDecisions, mockCompliance } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

const decisionTypeToAgent: Record<string, AgentName> = {
  triage: 'triage_agent',
  underwriting: 'underwriting_agent',
  pricing: 'underwriting_agent',
  claims: 'claims_agent',
  compliance: 'compliance_agent',
  fraud: 'fraud_agent',
  fraud_detection: 'fraud_agent',
};

function deriveOversight(d: Record<string, unknown>): OversightLevel {
  if (d.human_oversight && typeof d.human_oversight === 'string') return d.human_oversight as OversightLevel;
  if (d.human_override === true) return 'required';
  if (typeof d.confidence === 'number' && d.confidence < 0.7) return 'recommended';
  return 'none';
}

function deriveReasoning(d: Record<string, unknown>): string[] {
  if (Array.isArray(d.reasoning)) return d.reasoning as string[];
  const explanation = (d.explanation ?? d.reasoning ?? '') as string;
  if (!explanation) return [];
  return explanation.split(/\.\s+/).filter(Boolean).map((s) => (s.endsWith('.') ? s : `${s}.`));
}

function deriveOutcome(d: Record<string, unknown>): string {
  if (typeof d.outcome === 'string') return d.outcome;
  const summary = d.output_summary;
  if (!summary || typeof summary !== 'object') return '';
  const s = summary as Record<string, unknown>;
  if (s.authority_decision) return String(s.authority_decision).replace(/_/g, ' ');
  if (s.decision) return String(s.decision).replace(/_/g, ' ');
  return JSON.stringify(summary);
}

export async function getDecisions(): Promise<AgentDecision[]> {
  if (USE_MOCK) return mockDecisions;
  try {
    const { data } = await client.get('/compliance/decisions');
    const items: Record<string, unknown>[] = Array.isArray(data) ? data : (data.items || []);
    return items.map((d): AgentDecision => {
      const ts = (d.timestamp as string) || (d.created_at as string) || '';
      const entityType = (d.entity_type as string) || '';
      const entityId = (d.entity_id as string) || '';
      return {
        id: d.id as string,
        agent: (d.agent as AgentName) || decisionTypeToAgent[d.decision_type as string] || 'compliance_agent',
        decision_type: (d.decision_type as DecisionType) || ('triage' as DecisionType),
        confidence: (d.confidence as number) ?? 0,
        human_oversight: deriveOversight(d),
        timestamp: ts,
        created_at: (d.created_at as string) || ts,
        submission_id: entityType === 'submission' ? entityId : (d.submission_id as string) || undefined,
        claim_id: entityType === 'claim' ? entityId : (d.claim_id as string) || undefined,
        policy_id: entityType === 'policy' ? entityId : (d.policy_id as string) || undefined,
        reasoning: deriveReasoning(d),
        outcome: deriveOutcome(d),
        metadata: (d.metadata as Record<string, unknown>) || {},
      };
    });
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
