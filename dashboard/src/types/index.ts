// ── Domain Types for OpenInsure Dashboard ──

export type LOB = 'cyber' | 'professional_liability' | 'dnol' | 'epli' | 'general_liability';

export type SubmissionStatus =
  | 'received'
  | 'triaging'
  | 'underwriting'
  | 'quoted'
  | 'bound'
  | 'declined'
  | 'referred';

export type PolicyStatus = 'active' | 'expired' | 'cancelled' | 'pending';

export type ClaimStatus = 'open' | 'investigating' | 'reserved' | 'closed' | 'denied' | 'litigation';

export type ClaimSeverity = 'low' | 'medium' | 'high' | 'critical';

export type DecisionType =
  | 'triage'
  | 'risk_assessment'
  | 'quote'
  | 'bind'
  | 'decline'
  | 'claim_assessment'
  | 'fraud_detection'
  | 'coverage_analysis';

export type AgentName =
  | 'triage_agent'
  | 'underwriting_agent'
  | 'claims_agent'
  | 'compliance_agent'
  | 'fraud_agent';

export type OversightLevel = 'none' | 'recommended' | 'required';

export interface Submission {
  id: string;
  applicant_name: string;
  lob: LOB;
  status: SubmissionStatus;
  risk_score: number;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  assigned_to: string | null;
  received_date: string;
  company_name: string;
  annual_revenue: number;
  employee_count: number;
  industry: string;
  requested_coverage: number;
  documents: Document[];
  triage_result?: TriageResult;
  agent_recommendation?: AgentRecommendation;
  decision_history: DecisionEvent[];
  cyber_risk_data?: CyberRiskData;
}

export interface Document {
  id: string;
  name: string;
  type: string;
  size: number;
  uploaded_at: string;
  url: string;
}

export interface TriageResult {
  appetite_match: boolean;
  risk_score: number;
  priority: string;
  flags: string[];
  recommended_lob: LOB;
  timestamp: string;
}

export interface AgentRecommendation {
  agent: AgentName;
  decision: string;
  confidence: number;
  reasoning: string[];
  recommended_premium?: number;
  recommended_terms?: string[];
  timestamp: string;
}

export interface DecisionEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  details: string;
  is_agent: boolean;
}

export interface CyberRiskData {
  security_rating: number;
  open_vulnerabilities: number;
  last_breach: string | null;
  mfa_enabled: boolean;
  encryption_at_rest: boolean;
  incident_response_plan: boolean;
  employee_training: boolean;
  third_party_risk_score: number;
}

export interface Policy {
  id: string;
  policy_number: string;
  insured_name: string;
  lob: LOB;
  status: PolicyStatus;
  effective_date: string;
  expiration_date: string;
  premium: number;
  coverage_limit: number;
  deductible: number;
  submission_id: string;
}

export interface Claim {
  id: string;
  claim_number: string;
  policy_id: string;
  policy_number: string;
  status: ClaimStatus;
  loss_date: string;
  reported_date: string;
  severity: ClaimSeverity;
  total_incurred: number;
  total_paid: number;
  total_reserved: number;
  assigned_to: string;
  description: string;
  lob: LOB;
}

export interface AgentDecision {
  id: string;
  agent: AgentName;
  decision_type: DecisionType;
  confidence: number;
  human_oversight: OversightLevel;
  timestamp: string;
  submission_id?: string;
  claim_id?: string;
  policy_id?: string;
  reasoning: string[];
  outcome: string;
  metadata: Record<string, unknown>;
}

export interface ComplianceSummary {
  total_decisions: number;
  decisions_by_agent: Record<string, number>;
  decisions_by_type: Record<string, number>;
  oversight_required_count: number;
  oversight_recommended_count: number;
  avg_confidence: number;
  bias_metrics: BiasMetric[];
  audit_trail: AuditEntry[];
  ai_systems: AISystemInfo[];
}

export interface BiasMetric {
  category: string;
  metric_name: string;
  value: number;
  threshold: number;
  status: 'pass' | 'warning' | 'fail';
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string;
  details: string;
}

export interface AISystemInfo {
  id: string;
  name: string;
  version: string;
  risk_category: 'high' | 'limited' | 'minimal';
  status: 'active' | 'inactive' | 'testing';
  last_audit: string;
  decisions_count: number;
}

export interface DashboardStats {
  total_submissions: number;
  active_policies: number;
  open_claims: number;
  pending_decisions: number;
  approval_rate: number;
  avg_processing_time_hours: number;
  escalation_rate: number;
  recent_activity: ActivityEvent[];
  agent_statuses: AgentStatus[];
}

export interface ActivityEvent {
  id: string;
  timestamp: string;
  type: string;
  description: string;
  actor: string;
  is_agent: boolean;
}

export interface AgentStatus {
  name: AgentName;
  display_name: string;
  status: 'active' | 'idle' | 'error';
  last_action: string;
  decisions_today: number;
}

export interface Product {
  id: string;
  name: string;
  lob: LOB;
  description: string;
  min_premium: number;
  max_coverage: number;
  available: boolean;
}
