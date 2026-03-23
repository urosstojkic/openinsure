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

export type ClaimStatus = 'reported' | 'open' | 'investigating' | 'reserved' | 'closed' | 'denied' | 'litigation';

export type ClaimSeverity = 'low' | 'medium' | 'high' | 'critical';

export type DecisionType =
  | 'triage'
  | 'underwriting'
  | 'risk_assessment'
  | 'quote'
  | 'bind'
  | 'decline'
  | 'claims'
  | 'claim_assessment'
  | 'fraud_detection'
  | 'coverage_analysis'
  | 'policy_review';

export type AgentName =
  | 'triage_agent'
  | 'underwriting_agent'
  | 'claims_agent'
  | 'compliance_agent'
  | 'fraud_agent';

export type OversightLevel = 'none' | 'recommended' | 'required';

export interface Submission {
  id: string;
  submission_number?: string;
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
  created_at?: string;
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

// ── Underwriter Workbench ──

export interface RiskFactor {
  factor: string;
  impact: 'positive' | 'negative' | 'neutral';
  score: number;
  description: string;
}

export interface ComparableAccount {
  company: string;
  industry: string;
  premium: number;
  limit: number;
  loss_ratio: number;
}

export interface RecommendedTerms {
  limit: number;
  deductible: number;
  premium: number;
  conditions: string[];
}

export interface UnderwriterQueueItem {
  id: string;
  submission_number?: string;
  applicant_name: string;
  company_name: string;
  lob: LOB;
  status: SubmissionStatus;
  risk_score: number;
  confidence: number;
  agent_recommendation: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  due_date: string;
  received_date: string;
  annual_revenue: number;
  employee_count: number;
  industry: string;
  requested_coverage: number;
  documents: Document[];
  risk_factors: RiskFactor[];
  comparable_accounts: ComparableAccount[];
  recommended_terms: RecommendedTerms;
  reasoning_chain: string[];
  decision_history: DecisionEvent[];
  cyber_risk_data?: CyberRiskData;
}

// ── Claims Workbench ──

export interface CoverageVerification {
  status: 'verified' | 'pending' | 'issue';
  policy_active: boolean;
  within_coverage: boolean;
  exclusions_checked: string[];
  notes: string;
}

export interface ReserveRecommendation {
  recommended_indemnity: number;
  recommended_expense: number;
  confidence: number;
  basis: string;
}

export interface ComparableClaim {
  claim_number: string;
  type: string;
  settled_amount: number;
  duration_days: number;
}

export interface FraudIndicator {
  indicator: string;
  severity: 'low' | 'medium' | 'high';
  description: string;
}

export interface ClaimTimelineEvent {
  timestamp: string;
  event: string;
  actor: string;
  details: string;
  is_agent: boolean;
}

export interface ClaimDocument {
  id: string;
  name: string;
  type: string;
  uploaded_at: string;
  category: 'fnol' | 'adjuster_notes' | 'invoice' | 'correspondence' | 'legal';
}

export interface ClaimFinancials {
  indemnity_reserve: number;
  expense_reserve: number;
  indemnity_paid: number;
  expense_paid: number;
  total_incurred: number;
  recovery: number;
}

export interface ClaimsQueueItem {
  id: string;
  claim_number: string;
  policy_id: string;
  policy_number: string;
  insured_name: string;
  status: ClaimStatus;
  severity: ClaimSeverity;
  loss_date: string;
  reserve: number;
  days_open: number;
  fraud_score: number;
  description: string;
  lob: LOB;
  coverage_verification: CoverageVerification;
  reserve_recommendation: ReserveRecommendation;
  comparable_claims: ComparableClaim[];
  fraud_indicators: FraudIndicator[];
  timeline: ClaimTimelineEvent[];
  claim_documents: ClaimDocument[];
  financials: ClaimFinancials;
}

// ── Compliance Workbench ──

export interface DecisionAuditItem {
  id: string;
  agent: string;
  decision_type: string;
  confidence: number;
  input_summary: string;
  output: string;
  reasoning_chain: string[];
  timestamp: string;
  reviewed: boolean;
  flagged: boolean;
}

export interface OverrideLogEntry {
  id: string;
  who: string;
  decision_type: string;
  original_recommendation: string;
  override_to: string;
  reason: string;
  timestamp: string;
}

export interface BiasChartData {
  approval_by_sector: { sector: string; rate: number }[];
  premium_by_size: { size: string; min: number; q1: number; median: number; q3: number; max: number }[];
  disparate_impact: { category: string; ratio: number; threshold: number }[];
}

export interface BiasGroupData {
  total: number;
  positive: number;
  rate: number;
  gap_percentage?: number;
  flagged?: boolean;
}

export interface BiasAnalysis {
  metric: string;
  group_field: string;
  groups: Record<string, BiasGroupData>;
  four_fifths_ratio: number;
  passes_threshold: boolean;
  flagged_groups: string[];
  timestamp: string;
}

export interface BiasReport {
  report_id: string;
  generated_at: string;
  period: string;
  total_submissions_analyzed: number;
  analyses: BiasAnalysis[];
  overall_status: 'compliant' | 'flagged';
  eu_ai_act_reference: string;
  recommendation: string;
}

// ── Executive Dashboard ──

export interface ExecutiveKPIs {
  gwp: number;
  nwp: number;
  loss_ratio: number;
  combined_ratio: number;
  growth_rate: number;
}

export interface PremiumTrendPoint {
  month: string;
  premium: number;
}

export interface LossRatioByLOB {
  lob: string;
  loss_ratio: number;
}

export interface ExposureConcentration {
  name: string;
  exposure: number;
}

export interface PipelineStage {
  stage: string;
  count: number;
}

export interface AgentImpactMetrics {
  processing_time_reduction: number;
  auto_bind_rate: number;
  escalation_rate: number;
}

export interface ExecutiveDashboardData {
  kpis: ExecutiveKPIs;
  premium_trend: PremiumTrendPoint[];
  loss_ratio_by_lob: LossRatioByLOB[];
  exposure_concentrations: ExposureConcentration[];
  pipeline: PipelineStage[];
  agent_impact: AgentImpactMetrics;
}

// ── Broker Portal ──

export interface BrokerTimelineEvent {
  timestamp: string;
  status: string;
  description: string;
}

export interface BrokerSubmission {
  id: string;
  applicant_name: string;
  lob: LOB;
  status: SubmissionStatus;
  submitted_date: string;
  last_update: string;
  status_timeline: BrokerTimelineEvent[];
}

export interface BrokerPolicy {
  id: string;
  policy_number: string;
  insured_name: string;
  lob: LOB;
  effective_date: string;
  expiry_date: string;
  premium: number;
}

export interface BrokerClaim {
  id: string;
  claim_number: string;
  policy_number: string;
  status: ClaimStatus;
  loss_date: string;
}

// ── Reinsurance (Carrier-only) ──

export type TreatyType = 'quota_share' | 'excess_of_loss' | 'surplus' | 'facultative';
export type TreatyStatus = 'active' | 'expired' | 'pending';

export interface ReinsuranceTreaty {
  id: string;
  treaty_number: string;
  treaty_type: TreatyType;
  reinsurer_name: string;
  status: TreatyStatus;
  effective_date: string;
  expiration_date: string;
  lines_of_business: string[];
  retention: number;
  limit: number;
  rate: number;
  capacity_total: number;
  capacity_used: number;
  reinstatements: number;
  description: string;
}

export interface ReinsuranceCession {
  id: string;
  treaty_id: string;
  policy_id: string;
  policy_number: string;
  ceded_premium: number;
  ceded_limit: number;
  cession_date: string;
}

export interface ReinsuranceRecovery {
  id: string;
  treaty_id: string;
  claim_id: string;
  claim_number: string;
  recovery_amount: number;
  recovery_date: string;
  status: 'pending' | 'billed' | 'collected';
}

export interface ReinsuranceDashboardData {
  treaties: ReinsuranceTreaty[];
  cessions: ReinsuranceCession[];
  recoveries: ReinsuranceRecovery[];
}

// ── Actuarial ──

export interface ActuarialReserve {
  id: string;
  line_of_business: string;
  accident_year: number;
  reserve_type: string;
  carried_amount: number;
  indicated_amount: number;
  selected_amount: number;
  as_of_date: string | null;
  analyst: string;
  approved_by: string;
  notes: string;
}

export interface TriangleEntry {
  accident_year: number;
  development_month: number;
  incurred_amount: number;
  paid_amount: number;
  case_reserve: number;
  claim_count: number;
}

export interface TriangleData {
  line_of_business: string;
  entries: TriangleEntry[];
  accident_years: number[];
  development_months: number[];
}

export interface IBNRResult {
  line_of_business: string;
  method: string;
  factors: Record<string, string>;
  ultimates: Record<string, string>;
  ibnr_by_year: Record<string, string>;
  total_ibnr: string;
}

export interface RateAdequacyItem {
  line_of_business: string;
  segment: string;
  current_rate: string;
  indicated_rate: string;
  adequacy_ratio: string;
}

export interface ActuarialWorkbenchData {
  reserves: ActuarialReserve[];
  triangle: TriangleData;
  ibnr: IBNRResult;
  rateAdequacy: RateAdequacyItem[];
}
