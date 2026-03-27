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
        model_id: (d.model_id as string) || undefined,
        model_version: (d.model_version as string) || undefined,
        entity_id: entityId || undefined,
        entity_type: entityType || undefined,
        input_summary: (d.input_summary as Record<string, unknown>) || undefined,
        output_summary: (d.output_summary as Record<string, unknown>) || undefined,
        processing_time_ms: (d.processing_time_ms as number) || undefined,
      };
    });
  } catch (error) {
    console.warn('[API] Decisions fallback:', error);
    return mockDecisions;
  }
}

const DECISION_TYPE_TO_AGENT: Record<string, string> = {
  triage: 'Submission Agent',
  underwriting: 'Underwriting Agent',
  pricing: 'Underwriting Agent',
  claims: 'Claims Agent',
  claims_assessment: 'Claims Agent',
  compliance: 'Compliance Agent',
  compliance_audit: 'Compliance Agent',
  fraud_detection: 'Fraud Agent',
  policy_review: 'Policy Agent',
  orchestration: 'Orchestrator',
  renewal: 'Renewal Agent',
};

export function deriveAgentName(d: Record<string, unknown>): string {
  if (typeof d.agent_name === 'string' && d.agent_name) return d.agent_name;
  if (typeof d.agent === 'string' && d.agent) return d.agent;
  const dt = String(d.decision_type || '');
  return DECISION_TYPE_TO_AGENT[dt] || dt.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()) || 'Unknown';
}

export async function getComplianceSummary(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  try {
    const [stats, audit, systems] = await Promise.all([
      client.get('/compliance/stats').catch(() => ({
        data: {
          total_decisions: 0,
          avg_confidence: 0,
          oversight_required_count: 0,
          oversight_recommended_count: 0,
          decisions_by_type: {},
          decisions_by_agent: {},
        },
      })),
      client.get('/compliance/audit-trail').catch(() => ({ data: { items: [] } })),
      client.get('/compliance/system-inventory').catch(() => ({ data: { systems: [] } })),
    ]);

    return {
      total_decisions: stats.data.total_decisions || 0,
      decisions_by_agent: stats.data.decisions_by_agent || {},
      decisions_by_type: stats.data.decisions_by_type || {},
      oversight_required_count: stats.data.oversight_required_count || 0,
      oversight_recommended_count: stats.data.oversight_recommended_count || 0,
      avg_confidence: stats.data.avg_confidence || 0,
      bias_metrics: [],
      audit_trail: audit.data.items || [],
      ai_systems: systems.data.systems || [],
    };
  } catch (error) {
    console.warn('[API] Compliance summary fallback:', error);
    return mockCompliance;
  }
}
