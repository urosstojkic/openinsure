import client from './client';
import type {
  UnderwriterQueueItem,
  ClaimsQueueItem,
  DecisionAuditItem,
  OverrideLogEntry,
  BiasChartData,
  BiasReport,
  ExecutiveDashboardData,
  BrokerSubmission,
  BrokerPolicy,
  BrokerClaim,
  ComplianceSummary,
  ActuarialReserve,
  TriangleData,
  IBNRResult,
  RateAdequacyItem,
} from '../types';
import {
  mockUnderwriterQueue,
  mockClaimsQueue,
  mockDecisionAudit,
  mockOverrideLog,
  mockBiasChartData,
  mockExecutiveData,
  mockBrokerSubmissions,
  mockBrokerPolicies,
  mockBrokerClaims,
  mockCompliance,
  mockActuarialReserves,
  mockTriangleData,
  mockIBNR,
  mockRateAdequacy,
} from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

/* eslint-disable @typescript-eslint/no-explicit-any */
function mapToUWQueueItem(item: any): UnderwriterQueueItem {
  const rd = item.risk_data || {};
  return {
    id: item.id,
    submission_number: item.submission_number || '',
    applicant_name: item.applicant_name || '',
    company_name: item.company_name || item.applicant_name || '',
    lob: item.lob || item.line_of_business || 'cyber',
    status: item.status || 'received',
    risk_score: item.risk_score ?? rd.risk_score ?? 0,
    confidence: item.confidence ?? 0,
    agent_recommendation: item.agent_recommendation || item.recommendation || '',
    priority: item.priority || 'medium',
    due_date: item.due_date || '',
    received_date: item.received_date || item.created_at || '',
    annual_revenue: item.annual_revenue || rd.annual_revenue || 0,
    employee_count: item.employee_count || rd.employee_count || 0,
    industry: item.industry || rd.industry || '',
    requested_coverage: item.requested_coverage || rd.requested_coverage || 0,
    documents: item.documents || [],
    risk_factors: item.risk_factors || [],
    comparable_accounts: item.comparable_accounts || [],
    recommended_terms: item.recommended_terms || { limit: 0, deductible: 0, premium: item.quoted_premium || 0, conditions: [] },
    reasoning_chain: item.reasoning_chain || [],
    decision_history: item.decision_history || [],
    cyber_risk_data: item.cyber_risk_data,
    rating_breakdown: item.rating_breakdown || undefined,
  };
}

function mapToClaimsQueueItem(item: any): ClaimsQueueItem {
  const totalReserved = item.total_reserved ?? 0;
  const totalPaid = item.total_paid ?? 0;
  const totalIncurred = item.total_incurred || (totalReserved + totalPaid) || 0;
  return {
    id: item.id,
    claim_number: item.claim_number || item.id,
    policy_id: item.policy_id || '',
    policy_number: item.policy_number || '',
    insured_name: item.insured_name || '',
    status: item.status || 'reported',
    severity: item.severity || 'medium',
    loss_date: item.loss_date || item.date_of_loss || '',
    reserve: item.reserve ?? totalReserved ?? 0,
    days_open: item.days_open ?? 0,
    fraud_score: item.fraud_score ?? 0,
    description: item.description || '',
    lob: item.lob || 'cyber',
    coverage_verification: item.coverage_verification || { status: 'pending', policy_active: true, within_coverage: true, exclusions_checked: [], notes: '' },
    reserve_recommendation: item.reserve_recommendation || { recommended_indemnity: totalReserved, recommended_expense: 0, confidence: 0, basis: '' },
    comparable_claims: item.comparable_claims || [],
    fraud_indicators: item.fraud_indicators || [],
    timeline: item.timeline || [],
    claim_documents: item.claim_documents || [],
    financials: item.financials || { indemnity_reserve: totalReserved, expense_reserve: 0, indemnity_paid: totalPaid, expense_paid: 0, total_incurred: totalIncurred, recovery: 0 },
  };
}

/** Safely coerce a value to a displayable string (handles API objects). */
function toDisplayString(val: unknown): string {
  if (typeof val === 'string') return val;
  if (val && typeof val === 'object') {
    return Object.entries(val as Record<string, unknown>)
      .map(([k, v]) => `${k}: ${v}`)
      .join(', ');
  }
  return val != null ? String(val) : '';
}

function mapToDecisionAuditItem(item: any): DecisionAuditItem {
  const dt = String(item.decision_type || item.action || '');
  const agentLabel = DECISION_TYPE_TO_AGENT[dt] || dt.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) || 'Unknown';
  return {
    id: item.id || '',
    agent: item.agent || item.agent_name || agentLabel,
    decision_type: item.decision_type || item.action || '',
    confidence: item.confidence ?? 0,
    input_summary: toDisplayString(item.input_summary) || item.entity_id || item.resource_id || '',
    output: toDisplayString(item.output) || toDisplayString(item.output_summary) || item.explanation || item.details || '',
    reasoning_chain: Array.isArray(item.reasoning_chain) ? item.reasoning_chain : Array.isArray(item.reasoning) ? item.reasoning : [],
    timestamp: item.timestamp || item.created_at || '',
    reviewed: item.reviewed ?? false,
    flagged: item.flagged ?? false,
  };
}

function mapToOverrideLogEntry(item: any): OverrideLogEntry {
  return {
    id: item.id,
    who: item.who || item.resolved_by || '',
    decision_type: item.decision_type || item.action || '',
    original_recommendation: item.original_recommendation || item.reason || '',
    override_to: item.override_to || item.status || '',
    reason: item.reason || item.resolution_reason || '',
    timestamp: item.timestamp || item.resolved_at || item.created_at || '',
  };
}

function mapToBrokerSubmission(item: any): BrokerSubmission {
  return {
    id: item.id,
    applicant_name: item.applicant_name || '',
    lob: item.lob || item.line_of_business || 'cyber',
    status: item.status || 'received',
    submitted_date: item.submitted_date || item.created_at || item.received_date || '',
    last_update: item.last_update || item.updated_at || '',
    status_timeline: item.status_timeline || [],
  };
}

function mapToBrokerPolicy(item: any): BrokerPolicy {
  return {
    id: item.id,
    policy_number: item.policy_number || item.id,
    insured_name: item.insured_name || item.policyholder_name || '',
    lob: item.lob || item.line_of_business || 'cyber',
    effective_date: item.effective_date || '',
    expiry_date: item.expiry_date || item.expiration_date || '',
    premium: item.premium ?? item.total_premium ?? 0,
  };
}

function mapToBrokerClaim(item: any): BrokerClaim {
  return {
    id: item.id,
    claim_number: item.claim_number || item.id,
    policy_number: item.policy_number || '',
    status: item.status || 'reported',
    loss_date: item.loss_date || item.date_of_loss || '',
  };
}

function mapToActuarialReserve(item: any): ActuarialReserve {
  return {
    id: item.id,
    line_of_business: item.line_of_business || item.lob || '',
    accident_year: item.accident_year ?? 0,
    reserve_type: item.reserve_type || '',
    carried_amount: item.carried_amount ?? 0,
    indicated_amount: item.indicated_amount ?? 0,
    selected_amount: item.selected_amount ?? 0,
    as_of_date: item.as_of_date || null,
    analyst: item.analyst || '',
    approved_by: item.approved_by || '',
    notes: item.notes || '',
  };
}

function mapToRateAdequacyItem(item: any): RateAdequacyItem {
  return {
    line_of_business: item.line_of_business || item.lob || '',
    segment: item.segment || '',
    current_rate: String(item.current_rate ?? ''),
    indicated_rate: String(item.indicated_rate ?? ''),
    adequacy_ratio: String(item.adequacy_ratio ?? ''),
  };
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export async function getUnderwriterQueue(): Promise<UnderwriterQueueItem[]> {
  if (USE_MOCK) return mockUnderwriterQueue;
  try {
    const { data } = await client.get('/underwriter/queue');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToUWQueueItem);
  } catch (error) {
    console.warn('[API] UW queue fallback:', error);
    return mockUnderwriterQueue;
  }
}

export async function getClaimsQueue(): Promise<ClaimsQueueItem[]> {
  if (USE_MOCK) return mockClaimsQueue;
  try {
    const { data } = await client.get('/claims/queue');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToClaimsQueueItem);
  } catch (error) {
    console.warn('[API] Claims queue fallback:', error);
    return mockClaimsQueue;
  }
}

export async function getDecisionAudit(): Promise<DecisionAuditItem[]> {
  if (USE_MOCK) return mockDecisionAudit;
  try {
    const { data } = await client.get('/compliance/decisions');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToDecisionAuditItem);
  } catch (error) {
    console.warn('[API] Decision audit fallback:', error);
    return mockDecisionAudit;
  }
}

export async function getOverrideLog(): Promise<OverrideLogEntry[]> {
  if (USE_MOCK) return mockOverrideLog;
  try {
    const { data } = await client.get('/escalations', { params: { status: 'approved' } });
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToOverrideLogEntry);
  } catch (error) {
    console.warn('[API] Override log fallback:', error);
    return mockOverrideLog;
  }
}

export async function getBiasChartData(): Promise<BiasChartData> {
  if (USE_MOCK) return mockBiasChartData;
  try {
    const { data } = await client.post('/compliance/bias-report');
    const analyses = data.analyses || [];
    return {
      approval_by_sector: analyses
        .filter((a: Record<string, unknown>) => String(a.metric ?? '').toLowerCase().includes('industry'))
        .flatMap((a: Record<string, unknown>) =>
          Object.entries((a.groups || {}) as Record<string, { rate: number }>)
            .map(([sector, g]) => ({ sector, rate: g.rate })),
        ),
      premium_by_size: mockBiasChartData.premium_by_size,
      disparate_impact: analyses.map((a: Record<string, unknown>) => ({
        category: String(a.group_field || ''),
        ratio: Number(a.four_fifths_ratio || 0),
        threshold: 0.8,
      })),
    };
  } catch (error) {
    console.warn('[API] Bias chart fallback:', error);
    return mockBiasChartData;
  }
}

export async function getBiasReport(): Promise<BiasReport | null> {
  try {
    const { data } = await client.post<BiasReport>('/compliance/bias-report');
    if (!data || typeof data !== 'object' || !Array.isArray(data.analyses)) {
      console.warn('[API] Bias report returned unexpected shape:', typeof data);
      return null;
    }
    return data;
  } catch (error) {
    console.warn('[API] Bias report unavailable:', error);
    return null;
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

function deriveAgentNameFromDecision(d: Record<string, unknown>): string {
  if (typeof d.agent_name === 'string' && d.agent_name) return d.agent_name;
  if (typeof d.agent === 'string' && d.agent) return d.agent;
  const dt = String(d.decision_type || '');
  return DECISION_TYPE_TO_AGENT[dt] || dt.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) || 'Unknown';
}

export async function getComplianceWorkbenchData(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  try {
    const [decisions, audit, systems] = await Promise.all([
      client.get('/compliance/decisions').catch(() => ({ data: { items: [], total: 0 } })),
      client.get('/compliance/audit-trail').catch(() => ({ data: { items: [] } })),
      client.get('/compliance/system-inventory').catch(() => ({ data: { systems: [] } })),
    ]);
    const decisionItems = decisions.data.items || [];
    const auditItems = audit.data.items || [];
    const systemItems = systems.data.systems || [];

    const decisions_by_agent: Record<string, number> = {};
    const decisions_by_type: Record<string, number> = {};
    let oversightRequired = 0;
    let oversightRecommended = 0;
    let totalConfidence = 0;

    for (const d of decisionItems) {
      const agent = deriveAgentNameFromDecision(d);
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
      audit_trail: auditItems,
      ai_systems: systemItems,
    };
  } catch (error) {
    console.warn('[API] Compliance workbench fallback:', error);
    return mockCompliance;
  }
}

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardData> {
  if (USE_MOCK) return mockExecutiveData;
  try {
    const { data } = await client.get<ExecutiveDashboardData>('/metrics/executive');
    return data;
  } catch (error) {
    console.warn('[API] Executive dashboard fallback:', error);
    return mockExecutiveData;
  }
}

export async function getBrokerSubmissions(): Promise<BrokerSubmission[]> {
  if (USE_MOCK) return mockBrokerSubmissions;
  try {
    const { data } = await client.get('/broker/submissions');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToBrokerSubmission);
  } catch (error) {
    console.warn('[API] Broker submissions fallback:', error);
    return mockBrokerSubmissions;
  }
}

export async function getBrokerPolicies(): Promise<BrokerPolicy[]> {
  if (USE_MOCK) return mockBrokerPolicies;
  try {
    const { data } = await client.get('/broker/policies');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToBrokerPolicy);
  } catch (error) {
    console.warn('[API] Broker policies fallback:', error);
    return mockBrokerPolicies;
  }
}

export async function getBrokerClaims(): Promise<BrokerClaim[]> {
  if (USE_MOCK) return mockBrokerClaims;
  try {
    const { data } = await client.get('/broker/claims');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToBrokerClaim);
  } catch (error) {
    console.warn('[API] Broker claims fallback:', error);
    return mockBrokerClaims;
  }
}

// ── Actuarial Workbench ──

export async function getActuarialReserves(): Promise<ActuarialReserve[]> {
  if (USE_MOCK) return mockActuarialReserves;
  try {
    const { data } = await client.get('/actuarial/reserves');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToActuarialReserve);
  } catch (error) {
    console.warn('[API] Actuarial reserves fallback:', error);
    return mockActuarialReserves;
  }
}

export async function getTriangleData(lob = 'cyber'): Promise<TriangleData> {
  if (USE_MOCK) return mockTriangleData;
  try {
    const { data } = await client.get<TriangleData>(`/actuarial/triangles/${lob}`);
    return data;
  } catch (error) {
    console.warn('[API] Triangle data fallback:', error);
    return mockTriangleData;
  }
}

export async function getIBNR(lob = 'cyber'): Promise<IBNRResult> {
  if (USE_MOCK) return mockIBNR;
  try {
    const { data } = await client.get<IBNRResult>(`/actuarial/ibnr/${lob}`);
    return data;
  } catch (error) {
    console.warn('[API] IBNR fallback:', error);
    return mockIBNR;
  }
}

export async function getRateAdequacy(): Promise<RateAdequacyItem[]> {
  if (USE_MOCK) return mockRateAdequacy;
  try {
    const { data } = await client.get('/actuarial/rate-adequacy');
    const items = Array.isArray(data) ? data : (data.items || []);
    return items.map(mapToRateAdequacyItem);
  } catch (error) {
    console.warn('[API] Rate adequacy fallback:', error);
    return mockRateAdequacy;
  }
}
