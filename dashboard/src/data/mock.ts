import type {
  DashboardStats,
  Submission,
  Policy,
  Claim,
  AgentDecision,
  ComplianceSummary,
  Product,
  UnderwriterQueueItem,
  ClaimsQueueItem,
  DecisionAuditItem,
  OverrideLogEntry,
  BiasChartData,
  ExecutiveDashboardData,
  BrokerSubmission,
  BrokerPolicy,
  BrokerClaim,
  ReinsuranceTreaty,
  ReinsuranceCession,
  ReinsuranceRecovery,
  ReinsuranceDashboardData,
  ActuarialReserve,
  TriangleData,
  IBNRResult,
  RateAdequacyItem,
} from '../types';

// ── Dashboard Stats ──
export const mockDashboardStats: DashboardStats = {
  total_submissions: 247,
  active_policies: 1_832,
  open_claims: 64,
  pending_decisions: 12,
  approval_rate: 0.73,
  avg_processing_time_hours: 4.2,
  escalation_rate: 0.08,
  recent_activity: [
    { id: 'a1', timestamp: '2025-01-15T14:32:00Z', type: 'submission', description: 'New cyber submission from Acme Corp', actor: 'triage_agent', is_agent: true },
    { id: 'a2', timestamp: '2025-01-15T14:18:00Z', type: 'decision', description: 'Quote approved for TechStart Inc — $45,000 premium', actor: 'Sarah Chen', is_agent: false },
    { id: 'a3', timestamp: '2025-01-15T13:55:00Z', type: 'claim', description: 'Claim CLM-2025-0042 escalated to senior adjuster', actor: 'claims_agent', is_agent: true },
    { id: 'a4', timestamp: '2025-01-15T13:40:00Z', type: 'policy', description: 'Policy POL-2025-1847 bound for DataFlow Systems', actor: 'underwriting_agent', is_agent: true },
    { id: 'a5', timestamp: '2025-01-15T13:22:00Z', type: 'compliance', description: 'Bias monitoring check passed — all metrics within thresholds', actor: 'compliance_agent', is_agent: true },
    { id: 'a6', timestamp: '2025-01-15T12:58:00Z', type: 'submission', description: 'Submission SUB-2025-0248 declined — outside appetite', actor: 'triage_agent', is_agent: true },
    { id: 'a7', timestamp: '2025-01-15T12:34:00Z', type: 'decision', description: 'Manual review requested for CloudNine Security submission', actor: 'underwriting_agent', is_agent: true },
    { id: 'a8', timestamp: '2025-01-15T12:10:00Z', type: 'claim', description: 'Reserve increase on CLM-2025-0038 — $125,000 to $200,000', actor: 'Mike Johnson', is_agent: false },
    { id: 'a9', timestamp: '2025-01-15T11:45:00Z', type: 'submission', description: 'Professional liability submission from LegalEase LLP', actor: 'triage_agent', is_agent: true },
    { id: 'a10', timestamp: '2025-01-15T11:20:00Z', type: 'policy', description: 'Renewal notice sent for 15 policies expiring in 30 days', actor: 'System', is_agent: false },
  ],
  agent_statuses: [
    { name: 'triage_agent', display_name: 'Triage Agent', status: 'active', last_action: 'Processed submission SUB-2025-0249', decisions_today: 23 },
    { name: 'underwriting_agent', display_name: 'Underwriting Agent', status: 'active', last_action: 'Generated quote for SUB-2025-0245', decisions_today: 18 },
    { name: 'claims_agent', display_name: 'Claims Agent', status: 'idle', last_action: 'Assessed claim CLM-2025-0042', decisions_today: 7 },
    { name: 'compliance_agent', display_name: 'Compliance Agent', status: 'active', last_action: 'Ran bias monitoring check', decisions_today: 4 },
    { name: 'fraud_agent', display_name: 'Fraud Detection Agent', status: 'idle', last_action: 'Screened 12 new claims', decisions_today: 12 },
  ],
};

// ── Submissions ──
export const mockSubmissions: Submission[] = [
  {
    id: 'SUB-2025-0249', applicant_name: 'Jane Williams', lob: 'cyber', status: 'received',
    risk_score: 0, priority: 'medium', assigned_to: null, received_date: '2025-01-15T14:30:00Z',
    company_name: 'Acme Corp', annual_revenue: 25_000_000, employee_count: 200, industry: 'Technology',
    requested_coverage: 5_000_000, documents: [
      { id: 'd1', name: 'Application.pdf', type: 'application/pdf', size: 245_000, uploaded_at: '2025-01-15T14:30:00Z', url: '#' },
      { id: 'd2', name: 'Financials_2024.xlsx', type: 'application/xlsx', size: 128_000, uploaded_at: '2025-01-15T14:30:00Z', url: '#' },
    ],
    decision_history: [
      { id: 'dh1', timestamp: '2025-01-15T14:30:00Z', actor: 'System', action: 'Submission received', details: 'Cyber liability application from Acme Corp', is_agent: false },
    ],
  },
  {
    id: 'SUB-2025-0248', applicant_name: 'Robert Chen', lob: 'cyber', status: 'triaging',
    risk_score: 62, priority: 'high', assigned_to: 'triage_agent', received_date: '2025-01-15T12:00:00Z',
    company_name: 'CloudNine Security', annual_revenue: 50_000_000, employee_count: 350, industry: 'Cybersecurity',
    requested_coverage: 10_000_000, documents: [
      { id: 'd3', name: 'Application.pdf', type: 'application/pdf', size: 312_000, uploaded_at: '2025-01-15T12:00:00Z', url: '#' },
    ],
    triage_result: {
      appetite_match: true, risk_score: 62, priority: 'high',
      flags: ['High revenue', 'Cybersecurity industry — favorable'], recommended_lob: 'cyber', timestamp: '2025-01-15T12:05:00Z',
    },
    decision_history: [
      { id: 'dh2', timestamp: '2025-01-15T12:00:00Z', actor: 'System', action: 'Submission received', details: 'Cyber application from CloudNine Security', is_agent: false },
      { id: 'dh3', timestamp: '2025-01-15T12:05:00Z', actor: 'triage_agent', action: 'Triage completed', details: 'Appetite match confirmed, risk score 62', is_agent: true },
    ],
    cyber_risk_data: {
      security_rating: 82, open_vulnerabilities: 3, last_breach: null, mfa_enabled: true,
      encryption_at_rest: true, incident_response_plan: true, employee_training: true, third_party_risk_score: 71,
    },
  },
  {
    id: 'SUB-2025-0245', applicant_name: 'Emily Davis', lob: 'professional_liability', status: 'underwriting',
    risk_score: 45, priority: 'medium', assigned_to: 'Sarah Chen', received_date: '2025-01-14T09:15:00Z',
    company_name: 'TechStart Inc', annual_revenue: 8_000_000, employee_count: 55, industry: 'Software',
    requested_coverage: 2_000_000, documents: [
      { id: 'd4', name: 'Application.pdf', type: 'application/pdf', size: 198_000, uploaded_at: '2025-01-14T09:15:00Z', url: '#' },
      { id: 'd5', name: 'Loss_History.pdf', type: 'application/pdf', size: 56_000, uploaded_at: '2025-01-14T09:15:00Z', url: '#' },
    ],
    triage_result: {
      appetite_match: true, risk_score: 45, priority: 'medium',
      flags: ['Clean loss history'], recommended_lob: 'professional_liability', timestamp: '2025-01-14T09:20:00Z',
    },
    agent_recommendation: {
      agent: 'underwriting_agent', decision: 'quote', confidence: 0.87,
      reasoning: ['Clean loss history — no claims in 5 years', 'Industry within appetite', 'Revenue appropriate for coverage requested', 'Strong financials and growth trajectory'],
      recommended_premium: 45_000, recommended_terms: ['$2M aggregate limit', '$500K per occurrence', '$25K deductible', 'Standard exclusions'],
      timestamp: '2025-01-14T10:30:00Z',
    },
    decision_history: [
      { id: 'dh4', timestamp: '2025-01-14T09:15:00Z', actor: 'System', action: 'Submission received', details: 'Professional liability application', is_agent: false },
      { id: 'dh5', timestamp: '2025-01-14T09:20:00Z', actor: 'triage_agent', action: 'Triage completed', details: 'Appetite match, risk score 45', is_agent: true },
      { id: 'dh6', timestamp: '2025-01-14T10:30:00Z', actor: 'underwriting_agent', action: 'Quote generated', details: 'Premium $45,000, confidence 87%', is_agent: true },
      { id: 'dh7', timestamp: '2025-01-14T11:00:00Z', actor: 'Sarah Chen', action: 'Assigned for review', details: 'Human review of AI-generated quote', is_agent: false },
    ],
  },
  {
    id: 'SUB-2025-0240', applicant_name: 'Michael Torres', lob: 'cyber', status: 'quoted',
    risk_score: 55, priority: 'medium', assigned_to: 'Sarah Chen', received_date: '2025-01-13T11:00:00Z',
    company_name: 'DataFlow Systems', annual_revenue: 35_000_000, employee_count: 180, industry: 'Data Analytics',
    requested_coverage: 5_000_000, documents: [],
    agent_recommendation: {
      agent: 'underwriting_agent', decision: 'quote', confidence: 0.92,
      reasoning: ['Strong security posture', 'Industry leader in data analytics', 'No prior cyber incidents', 'Comprehensive IR plan in place'],
      recommended_premium: 72_000, timestamp: '2025-01-13T13:00:00Z',
    },
    decision_history: [
      { id: 'dh8', timestamp: '2025-01-13T11:00:00Z', actor: 'System', action: 'Submission received', details: 'Cyber application', is_agent: false },
      { id: 'dh9', timestamp: '2025-01-13T13:00:00Z', actor: 'underwriting_agent', action: 'Quote generated', details: 'Premium $72,000', is_agent: true },
      { id: 'dh10', timestamp: '2025-01-13T14:00:00Z', actor: 'Sarah Chen', action: 'Quote approved', details: 'Approved AI quote — terms acceptable', is_agent: false },
    ],
    cyber_risk_data: {
      security_rating: 88, open_vulnerabilities: 1, last_breach: null, mfa_enabled: true,
      encryption_at_rest: true, incident_response_plan: true, employee_training: true, third_party_risk_score: 85,
    },
  },
  {
    id: 'SUB-2025-0235', applicant_name: 'Lisa Park', lob: 'epli', status: 'bound',
    risk_score: 30, priority: 'low', assigned_to: 'James Wright', received_date: '2025-01-12T08:30:00Z',
    company_name: 'GreenTech Solutions', annual_revenue: 12_000_000, employee_count: 85, industry: 'Clean Energy',
    requested_coverage: 1_000_000, documents: [],
    decision_history: [
      { id: 'dh11', timestamp: '2025-01-12T08:30:00Z', actor: 'System', action: 'Submission received', details: 'EPLI application', is_agent: false },
      { id: 'dh12', timestamp: '2025-01-12T16:00:00Z', actor: 'James Wright', action: 'Policy bound', details: 'POL-2025-1847 issued', is_agent: false },
    ],
  },
  {
    id: 'SUB-2025-0230', applicant_name: 'David Kim', lob: 'dnol', status: 'declined',
    risk_score: 88, priority: 'high', assigned_to: 'underwriting_agent', received_date: '2025-01-11T10:00:00Z',
    company_name: 'CryptoVault Exchange', annual_revenue: 200_000_000, employee_count: 45, industry: 'Cryptocurrency',
    requested_coverage: 50_000_000, documents: [],
    agent_recommendation: {
      agent: 'underwriting_agent', decision: 'decline', confidence: 0.95,
      reasoning: ['Cryptocurrency exchange — outside risk appetite', 'Extremely high requested coverage relative to employee count', 'Industry regulatory uncertainty', 'High fraud risk profile'],
      timestamp: '2025-01-11T10:15:00Z',
    },
    decision_history: [
      { id: 'dh13', timestamp: '2025-01-11T10:00:00Z', actor: 'System', action: 'Submission received', details: 'D&O application', is_agent: false },
      { id: 'dh14', timestamp: '2025-01-11T10:15:00Z', actor: 'triage_agent', action: 'Declined', details: 'Outside appetite — cryptocurrency exchange', is_agent: true },
    ],
  },
  {
    id: 'SUB-2025-0228', applicant_name: 'Anna Kowalski', lob: 'general_liability', status: 'referred',
    risk_score: 72, priority: 'high', assigned_to: 'Sarah Chen', received_date: '2025-01-10T15:45:00Z',
    company_name: 'Metro Construction LLC', annual_revenue: 45_000_000, employee_count: 320, industry: 'Construction',
    requested_coverage: 10_000_000, documents: [],
    decision_history: [
      { id: 'dh15', timestamp: '2025-01-10T15:45:00Z', actor: 'System', action: 'Submission received', details: 'GL application', is_agent: false },
      { id: 'dh16', timestamp: '2025-01-10T16:00:00Z', actor: 'underwriting_agent', action: 'Referred', details: 'Construction risk requires senior review', is_agent: true },
    ],
  },
];

// ── Policies ──
export const mockPolicies: Policy[] = [
  { id: 'pol1', policy_number: 'POL-2025-1847', insured_name: 'GreenTech Solutions', lob: 'epli', status: 'active', effective_date: '2025-01-12', expiration_date: '2026-01-12', premium: 28_000, coverage_limit: 1_000_000, deductible: 10_000, submission_id: 'SUB-2025-0235' },
  { id: 'pol2', policy_number: 'POL-2025-1830', insured_name: 'DataFlow Systems', lob: 'cyber', status: 'active', effective_date: '2025-01-08', expiration_date: '2026-01-08', premium: 72_000, coverage_limit: 5_000_000, deductible: 50_000, submission_id: 'SUB-2025-0240' },
  { id: 'pol3', policy_number: 'POL-2024-1650', insured_name: 'Meridian Healthcare', lob: 'professional_liability', status: 'active', effective_date: '2024-06-01', expiration_date: '2025-06-01', premium: 95_000, coverage_limit: 10_000_000, deductible: 100_000, submission_id: 'SUB-2024-0180' },
  { id: 'pol4', policy_number: 'POL-2024-1580', insured_name: 'Summit Financial Group', lob: 'dnol', status: 'active', effective_date: '2024-04-15', expiration_date: '2025-04-15', premium: 120_000, coverage_limit: 15_000_000, deductible: 250_000, submission_id: 'SUB-2024-0120' },
  { id: 'pol5', policy_number: 'POL-2024-1500', insured_name: 'Pacific Logistics', lob: 'general_liability', status: 'expired', effective_date: '2024-01-01', expiration_date: '2025-01-01', premium: 55_000, coverage_limit: 5_000_000, deductible: 25_000, submission_id: 'SUB-2023-0890' },
  { id: 'pol6', policy_number: 'POL-2024-1420', insured_name: 'NovaTech Labs', lob: 'cyber', status: 'cancelled', effective_date: '2024-03-01', expiration_date: '2025-03-01', premium: 48_000, coverage_limit: 3_000_000, deductible: 25_000, submission_id: 'SUB-2024-0050' },
  { id: 'pol7', policy_number: 'POL-2025-1855', insured_name: 'BlueWave Consulting', lob: 'professional_liability', status: 'pending', effective_date: '2025-02-01', expiration_date: '2026-02-01', premium: 38_000, coverage_limit: 2_000_000, deductible: 15_000, submission_id: 'SUB-2025-0210' },
];

// ── Claims ──
export const mockClaims: Claim[] = [
  { id: 'clm1', claim_number: 'CLM-2025-0042', policy_id: 'pol3', policy_number: 'POL-2024-1650', status: 'investigating', loss_date: '2025-01-10', reported_date: '2025-01-12', severity: 'high', total_incurred: 250_000, total_paid: 0, total_reserved: 250_000, assigned_to: 'Mike Johnson', description: 'Alleged medical malpractice — patient injury during procedure', lob: 'professional_liability' },
  { id: 'clm2', claim_number: 'CLM-2025-0038', policy_id: 'pol2', policy_number: 'POL-2025-1830', status: 'reserved', loss_date: '2025-01-05', reported_date: '2025-01-06', severity: 'critical', total_incurred: 500_000, total_paid: 75_000, total_reserved: 425_000, assigned_to: 'Mike Johnson', description: 'Ransomware attack — data exfiltration and business interruption', lob: 'cyber' },
  { id: 'clm3', claim_number: 'CLM-2025-0035', policy_id: 'pol4', policy_number: 'POL-2024-1580', status: 'open', loss_date: '2025-01-02', reported_date: '2025-01-03', severity: 'medium', total_incurred: 125_000, total_paid: 0, total_reserved: 125_000, assigned_to: 'Lisa Park', description: 'Securities class action — alleged misrepresentation in Q3 earnings', lob: 'dnol' },
  { id: 'clm4', claim_number: 'CLM-2024-0198', policy_id: 'pol5', policy_number: 'POL-2024-1500', status: 'closed', loss_date: '2024-11-15', reported_date: '2024-11-16', severity: 'low', total_incurred: 15_000, total_paid: 15_000, total_reserved: 0, assigned_to: 'James Wright', description: 'Slip and fall at warehouse — minor injury', lob: 'general_liability' },
  { id: 'clm5', claim_number: 'CLM-2024-0185', policy_id: 'pol6', policy_number: 'POL-2024-1420', status: 'denied', loss_date: '2024-10-20', reported_date: '2024-10-28', severity: 'medium', total_incurred: 0, total_paid: 0, total_reserved: 0, assigned_to: 'Mike Johnson', description: 'Phishing incident — late reporting, policy exclusion applies', lob: 'cyber' },
  { id: 'clm6', claim_number: 'CLM-2025-0045', policy_id: 'pol1', policy_number: 'POL-2025-1847', status: 'open', loss_date: '2025-01-14', reported_date: '2025-01-14', severity: 'low', total_incurred: 35_000, total_paid: 0, total_reserved: 35_000, assigned_to: 'Lisa Park', description: 'Wrongful termination claim by former employee', lob: 'epli' },
];

// ── Agent Decisions ──
export const mockDecisions: AgentDecision[] = [
  { id: 'DEC-2025-0150', agent: 'triage_agent', decision_type: 'triage', confidence: 0.94, human_oversight: 'none', timestamp: '2025-01-15T14:32:00Z', submission_id: 'SUB-2025-0249', reasoning: ['Application complete', 'Cyber LOB identified from form data', 'Revenue within appetite range ($25M)', 'Technology sector — standard risk'], outcome: 'Triaged to underwriting queue', metadata: {} },
  { id: 'DEC-2025-0149', agent: 'underwriting_agent', decision_type: 'quote', confidence: 0.87, human_oversight: 'recommended', timestamp: '2025-01-15T13:45:00Z', submission_id: 'SUB-2025-0245', reasoning: ['Clean loss history — no claims in 5 years', 'Professional liability — standard underwriting', 'Revenue $8M, 55 employees — small tech firm', 'Recommended premium $45,000 based on rate model'], outcome: 'Quote generated — pending human review', metadata: {} },
  { id: 'DEC-2025-0148', agent: 'claims_agent', decision_type: 'claim_assessment', confidence: 0.72, human_oversight: 'recommended', timestamp: '2025-01-15T13:55:00Z', claim_id: 'clm1', reasoning: ['Medical malpractice claim — complex liability assessment', 'Initial documents suggest potential merit', 'Reserve recommendation: $250,000', 'Recommend senior adjuster involvement due to complexity'], outcome: 'Escalated to senior adjuster', metadata: {} },
  { id: 'DEC-2025-0147', agent: 'fraud_agent', decision_type: 'fraud_detection', confidence: 0.91, human_oversight: 'none', timestamp: '2025-01-15T12:30:00Z', claim_id: 'clm2', reasoning: ['Ransomware claim corroborated by third-party forensics', 'Timeline consistent with reported events', 'No fraud indicators detected', 'Policyholder has strong claims history'], outcome: 'No fraud detected — proceed with claim', metadata: {} },
  { id: 'DEC-2025-0146', agent: 'triage_agent', decision_type: 'decline', confidence: 0.95, human_oversight: 'none', timestamp: '2025-01-15T12:58:00Z', submission_id: 'SUB-2025-0230', reasoning: ['Cryptocurrency exchange — hard decline per underwriting guidelines', 'Regulatory uncertainty in crypto sector', 'Requested coverage ($50M) disproportionate to operations', 'Industry outside risk appetite'], outcome: 'Submission declined', metadata: {} },
  { id: 'DEC-2025-0145', agent: 'compliance_agent', decision_type: 'coverage_analysis', confidence: 0.88, human_oversight: 'none', timestamp: '2025-01-15T11:00:00Z', reasoning: ['Monthly bias monitoring check completed', 'All disparate impact ratios within thresholds', 'Decision distribution across industries shows no significant skew', 'Approval rates consistent across company sizes'], outcome: 'Compliance check passed', metadata: {} },
  { id: 'DEC-2025-0144', agent: 'underwriting_agent', decision_type: 'risk_assessment', confidence: 0.45, human_oversight: 'required', timestamp: '2025-01-15T10:20:00Z', submission_id: 'SUB-2025-0228', reasoning: ['Construction industry — elevated risk profile', 'Revenue $45M with 320 employees', 'Requested $10M GL coverage', 'Insufficient data for automated risk scoring', 'Recommend manual underwriting review'], outcome: 'Referred to senior underwriter', metadata: {} },
  { id: 'DEC-2025-0143', agent: 'underwriting_agent', decision_type: 'quote', confidence: 0.92, human_oversight: 'none', timestamp: '2025-01-14T16:00:00Z', submission_id: 'SUB-2025-0240', reasoning: ['DataFlow Systems — strong security posture (rating 88)', 'No prior cyber incidents', 'Comprehensive incident response plan', 'Premium recommendation: $72,000 for $5M limit'], outcome: 'Quote issued', metadata: {} },
  { id: 'DEC-2025-0142', agent: 'claims_agent', decision_type: 'claim_assessment', confidence: 0.38, human_oversight: 'required', timestamp: '2025-01-14T14:00:00Z', claim_id: 'clm3', reasoning: ['Securities class action — high complexity', 'Multiple plaintiffs involved', 'Allegations of earnings misrepresentation', 'Insufficient information for automated assessment', 'REQUIRES: Full legal review and D&O specialist input'], outcome: 'Flagged for human review — insufficient confidence', metadata: {} },
  { id: 'DEC-2025-0141', agent: 'fraud_agent', decision_type: 'fraud_detection', confidence: 0.65, human_oversight: 'recommended', timestamp: '2025-01-14T11:00:00Z', claim_id: 'clm5', reasoning: ['Late reporting — 8 days after incident', 'Phishing incident details vague', 'No third-party forensics report provided', 'Some inconsistencies in timeline', 'Recommend further investigation before proceeding'], outcome: 'Flagged for investigation', metadata: {} },
];

// ── Compliance ──
export const mockCompliance: ComplianceSummary = {
  total_decisions: 1_247,
  decisions_by_agent: { triage_agent: 485, underwriting_agent: 372, claims_agent: 198, compliance_agent: 96, fraud_agent: 96 },
  decisions_by_type: { triage: 485, quote: 210, risk_assessment: 162, claim_assessment: 198, fraud_detection: 96, decline: 52, coverage_analysis: 44 },
  oversight_required_count: 47,
  oversight_recommended_count: 156,
  avg_confidence: 0.82,
  bias_metrics: [
    { category: 'Industry', metric_name: 'Approval rate disparity', value: 0.92, threshold: 0.8, status: 'pass' },
    { category: 'Company Size', metric_name: 'Premium fairness index', value: 0.88, threshold: 0.8, status: 'pass' },
    { category: 'Geography', metric_name: 'Coverage limit equity', value: 0.79, threshold: 0.8, status: 'warning' },
    { category: 'Industry', metric_name: 'Decline rate disparity', value: 0.95, threshold: 0.8, status: 'pass' },
    { category: 'Revenue Band', metric_name: 'Processing time equity', value: 0.85, threshold: 0.8, status: 'pass' },
    { category: 'Sector', metric_name: 'Claims approval fairness', value: 0.71, threshold: 0.8, status: 'fail' },
  ],
  audit_trail: [
    { id: 'aud1', timestamp: '2025-01-15T14:32:00Z', actor: 'triage_agent', action: 'Decision recorded', resource_type: 'submission', resource_id: 'SUB-2025-0249', details: 'Triage decision — confidence 0.94' },
    { id: 'aud2', timestamp: '2025-01-15T13:55:00Z', actor: 'claims_agent', action: 'Escalation', resource_type: 'claim', resource_id: 'CLM-2025-0042', details: 'Escalated to senior adjuster — confidence 0.72' },
    { id: 'aud3', timestamp: '2025-01-15T12:58:00Z', actor: 'triage_agent', action: 'Decision recorded', resource_type: 'submission', resource_id: 'SUB-2025-0230', details: 'Declined — cryptocurrency exchange outside appetite' },
    { id: 'aud4', timestamp: '2025-01-15T11:00:00Z', actor: 'compliance_agent', action: 'Bias check', resource_type: 'system', resource_id: 'bias-monitor', details: 'Monthly bias monitoring — all thresholds met' },
    { id: 'aud5', timestamp: '2025-01-14T16:00:00Z', actor: 'underwriting_agent', action: 'Decision recorded', resource_type: 'submission', resource_id: 'SUB-2025-0240', details: 'Quote issued — $72,000 premium' },
    { id: 'aud6', timestamp: '2025-01-14T14:00:00Z', actor: 'Sarah Chen', action: 'Human override', resource_type: 'submission', resource_id: 'SUB-2025-0245', details: 'Approved AI-generated quote with modifications' },
  ],
  ai_systems: [
    { id: 'sys1', name: 'Triage Agent', version: '2.1.0', risk_category: 'high', status: 'active', last_audit: '2025-01-01', decisions_count: 485 },
    { id: 'sys2', name: 'Underwriting Agent', version: '1.8.0', risk_category: 'high', status: 'active', last_audit: '2025-01-01', decisions_count: 372 },
    { id: 'sys3', name: 'Claims Assessment Agent', version: '1.5.0', risk_category: 'high', status: 'active', last_audit: '2024-12-15', decisions_count: 198 },
    { id: 'sys4', name: 'Compliance Monitor', version: '1.2.0', risk_category: 'limited', status: 'active', last_audit: '2025-01-10', decisions_count: 96 },
    { id: 'sys5', name: 'Fraud Detection Agent', version: '1.3.0', risk_category: 'high', status: 'active', last_audit: '2024-12-20', decisions_count: 96 },
  ],
};

// ── Products ──
export const mockProducts: Product[] = [
  { id: 'prod1', name: 'Cyber Liability', lob: 'cyber', description: 'Comprehensive cyber insurance covering data breaches, ransomware, and business interruption', min_premium: 15_000, max_coverage: 25_000_000, available: true },
  { id: 'prod2', name: 'Professional Liability (E&O)', lob: 'professional_liability', description: 'Errors & omissions coverage for professional services firms', min_premium: 10_000, max_coverage: 20_000_000, available: true },
  { id: 'prod3', name: "Directors & Officers Liability", lob: 'dnol', description: 'D&O coverage protecting leadership from personal liability', min_premium: 25_000, max_coverage: 50_000_000, available: true },
  { id: 'prod4', name: 'Employment Practices Liability', lob: 'epli', description: 'EPLI coverage for wrongful termination, discrimination, and harassment claims', min_premium: 8_000, max_coverage: 10_000_000, available: true },
  { id: 'prod5', name: 'General Liability', lob: 'general_liability', description: 'Commercial general liability for bodily injury and property damage', min_premium: 5_000, max_coverage: 25_000_000, available: true },
];

// ── Underwriter Workbench Queue ──
export const mockUnderwriterQueue: UnderwriterQueueItem[] = [
  {
    id: 'SUB-2025-0248', applicant_name: 'Robert Chen', company_name: 'CloudNine Security', lob: 'cyber',
    status: 'underwriting', risk_score: 62, confidence: 0.78, agent_recommendation: 'Quote — needs review',
    priority: 'high', due_date: '2025-01-17T17:00:00Z', received_date: '2025-01-15T12:00:00Z',
    annual_revenue: 50_000_000, employee_count: 350, industry: 'Cybersecurity', requested_coverage: 10_000_000,
    documents: [
      { id: 'd3', name: 'Application.pdf', type: 'application/pdf', size: 312_000, uploaded_at: '2025-01-15T12:00:00Z', url: '#' },
      { id: 'd3b', name: 'Security_Audit_2024.pdf', type: 'application/pdf', size: 189_000, uploaded_at: '2025-01-15T12:00:00Z', url: '#' },
    ],
    risk_factors: [
      { factor: 'Security Rating', impact: 'positive', score: 82, description: 'Above-average security posture for industry' },
      { factor: 'Revenue Exposure', impact: 'negative', score: 65, description: 'High revenue creates larger target surface' },
      { factor: 'Industry Sector', impact: 'positive', score: 90, description: 'Cybersecurity firms demonstrate strong controls' },
      { factor: 'Employee Count', impact: 'neutral', score: 50, description: 'Moderate workforce — standard training requirements' },
      { factor: 'Third-Party Risk', impact: 'neutral', score: 71, description: 'Acceptable vendor management practices' },
    ],
    comparable_accounts: [
      { company: 'SecureNet Solutions', industry: 'Cybersecurity', premium: 135_000, limit: 10_000_000, loss_ratio: 0.28 },
      { company: 'CyberShield Inc', industry: 'Cybersecurity', premium: 118_000, limit: 10_000_000, loss_ratio: 0.35 },
      { company: 'DefensePoint Corp', industry: 'InfoSec', premium: 142_000, limit: 15_000_000, loss_ratio: 0.22 },
    ],
    recommended_terms: { limit: 10_000_000, deductible: 100_000, premium: 128_000, conditions: ['Mandatory MFA on all systems', '24hr incident reporting requirement', 'Annual penetration testing'] },
    reasoning_chain: [
      'Application data extracted and validated — all fields complete',
      'Cybersecurity sector identified — favorable industry classification',
      'Security rating 82/100 — above-average posture',
      'Revenue $50M with 350 employees — mid-market risk profile',
      '$10M coverage request within standard parameters',
      'Comparable accounts show 22-35% loss ratios for similar firms',
      'Recommended premium $128,000 based on actuarial model and comparables',
      'Confidence 78% — recommend human review due to high coverage amount',
    ],
    decision_history: [
      { id: 'dh2', timestamp: '2025-01-15T12:00:00Z', actor: 'System', action: 'Submission received', details: 'Cyber application from CloudNine Security', is_agent: false },
      { id: 'dh3', timestamp: '2025-01-15T12:05:00Z', actor: 'triage_agent', action: 'Triage completed', details: 'Appetite match confirmed, risk score 62', is_agent: true },
      { id: 'dh3b', timestamp: '2025-01-15T12:30:00Z', actor: 'underwriting_agent', action: 'Analysis complete', details: 'Quote recommendation generated — $128K premium', is_agent: true },
    ],
    cyber_risk_data: { security_rating: 82, open_vulnerabilities: 3, last_breach: null, mfa_enabled: true, encryption_at_rest: true, incident_response_plan: true, employee_training: true, third_party_risk_score: 71 },
  },
  {
    id: 'SUB-2025-0245', applicant_name: 'Emily Davis', company_name: 'TechStart Inc', lob: 'professional_liability',
    status: 'underwriting', risk_score: 45, confidence: 0.87, agent_recommendation: 'Approve quote',
    priority: 'medium', due_date: '2025-01-18T17:00:00Z', received_date: '2025-01-14T09:15:00Z',
    annual_revenue: 8_000_000, employee_count: 55, industry: 'Software', requested_coverage: 2_000_000,
    documents: [
      { id: 'd4', name: 'Application.pdf', type: 'application/pdf', size: 198_000, uploaded_at: '2025-01-14T09:15:00Z', url: '#' },
      { id: 'd5', name: 'Loss_History.pdf', type: 'application/pdf', size: 56_000, uploaded_at: '2025-01-14T09:15:00Z', url: '#' },
    ],
    risk_factors: [
      { factor: 'Loss History', impact: 'positive', score: 95, description: 'No claims in 5 years — excellent track record' },
      { factor: 'Industry Sector', impact: 'positive', score: 78, description: 'Software industry within standard appetite' },
      { factor: 'Revenue', impact: 'positive', score: 72, description: '$8M revenue appropriate for requested coverage' },
      { factor: 'Growth Rate', impact: 'neutral', score: 60, description: 'Moderate growth — no unusual risk concentration' },
    ],
    comparable_accounts: [
      { company: 'CodeBridge Solutions', industry: 'Software', premium: 42_000, limit: 2_000_000, loss_ratio: 0.18 },
      { company: 'AppLayer Inc', industry: 'Software', premium: 48_000, limit: 2_000_000, loss_ratio: 0.25 },
    ],
    recommended_terms: { limit: 2_000_000, deductible: 25_000, premium: 45_000, conditions: ['Standard E&O exclusions apply', 'Client contract review clause'] },
    reasoning_chain: [
      'Clean loss history — no claims in 5 years',
      'Software industry — within standard appetite',
      'Revenue $8M, 55 employees — small tech firm profile',
      'Professional liability coverage at $2M — standard request',
      'Premium recommendation $45,000 based on rate model',
      'High confidence — straightforward risk profile',
    ],
    decision_history: [
      { id: 'dh4', timestamp: '2025-01-14T09:15:00Z', actor: 'System', action: 'Submission received', details: 'Professional liability application', is_agent: false },
      { id: 'dh5', timestamp: '2025-01-14T09:20:00Z', actor: 'triage_agent', action: 'Triage completed', details: 'Appetite match, risk score 45', is_agent: true },
      { id: 'dh6', timestamp: '2025-01-14T10:30:00Z', actor: 'underwriting_agent', action: 'Quote generated', details: 'Premium $45,000, confidence 87%', is_agent: true },
      { id: 'dh7', timestamp: '2025-01-14T11:00:00Z', actor: 'Sarah Chen', action: 'Assigned for review', details: 'Human review of AI-generated quote', is_agent: false },
    ],
  },
  {
    id: 'SUB-2025-0228', applicant_name: 'Anna Kowalski', company_name: 'Metro Construction LLC', lob: 'general_liability',
    status: 'referred', risk_score: 72, confidence: 0.45, agent_recommendation: 'Refer — manual review required',
    priority: 'urgent', due_date: '2025-01-16T17:00:00Z', received_date: '2025-01-10T15:45:00Z',
    annual_revenue: 45_000_000, employee_count: 320, industry: 'Construction', requested_coverage: 10_000_000,
    documents: [
      { id: 'd10', name: 'Application.pdf', type: 'application/pdf', size: 287_000, uploaded_at: '2025-01-10T15:45:00Z', url: '#' },
      { id: 'd11', name: 'Safety_Record.pdf', type: 'application/pdf', size: 145_000, uploaded_at: '2025-01-10T15:45:00Z', url: '#' },
      { id: 'd12', name: 'Project_List_2024.xlsx', type: 'application/xlsx', size: 92_000, uploaded_at: '2025-01-10T15:45:00Z', url: '#' },
    ],
    risk_factors: [
      { factor: 'Industry Sector', impact: 'negative', score: 35, description: 'Construction — elevated bodily injury and property damage risk' },
      { factor: 'Employee Count', impact: 'negative', score: 40, description: '320 employees with field exposure' },
      { factor: 'Coverage Amount', impact: 'negative', score: 30, description: '$10M GL limit — high for construction sector' },
      { factor: 'Safety Record', impact: 'positive', score: 75, description: 'Strong OSHA compliance record' },
    ],
    comparable_accounts: [
      { company: 'BuildRight Corp', industry: 'Construction', premium: 185_000, limit: 10_000_000, loss_ratio: 0.52 },
      { company: 'Premier Builders', industry: 'Construction', premium: 210_000, limit: 10_000_000, loss_ratio: 0.48 },
    ],
    recommended_terms: { limit: 10_000_000, deductible: 100_000, premium: 195_000, conditions: ['Subcontractor insurance requirements', 'Monthly safety reporting', 'Excess coverage recommended'] },
    reasoning_chain: [
      'Construction industry — requires specialist underwriting review',
      'Elevated risk profile — 320 employees in field operations',
      'Revenue $45M — large-scale commercial projects',
      'Insufficient data for full automated risk scoring',
      'Recommend manual underwriting review before proceeding',
    ],
    decision_history: [
      { id: 'dh15', timestamp: '2025-01-10T15:45:00Z', actor: 'System', action: 'Submission received', details: 'GL application', is_agent: false },
      { id: 'dh16', timestamp: '2025-01-10T16:00:00Z', actor: 'underwriting_agent', action: 'Referred', details: 'Construction risk requires senior review', is_agent: true },
    ],
  },
  {
    id: 'SUB-2025-0252', applicant_name: 'James Morrison', company_name: 'FinEdge Capital', lob: 'dnol',
    status: 'underwriting', risk_score: 58, confidence: 0.71, agent_recommendation: 'Quote with conditions',
    priority: 'high', due_date: '2025-01-19T17:00:00Z', received_date: '2025-01-15T16:00:00Z',
    annual_revenue: 120_000_000, employee_count: 85, industry: 'Financial Services', requested_coverage: 25_000_000,
    documents: [
      { id: 'd20', name: 'Application.pdf', type: 'application/pdf', size: 340_000, uploaded_at: '2025-01-15T16:00:00Z', url: '#' },
      { id: 'd21', name: 'Annual_Report_2024.pdf', type: 'application/pdf', size: 520_000, uploaded_at: '2025-01-15T16:00:00Z', url: '#' },
    ],
    risk_factors: [
      { factor: 'Revenue Exposure', impact: 'negative', score: 55, description: '$120M revenue — significant D&O exposure' },
      { factor: 'Industry Sector', impact: 'neutral', score: 50, description: 'Financial services — standard regulatory environment' },
      { factor: 'Board Composition', impact: 'positive', score: 78, description: 'Experienced board with strong governance' },
      { factor: 'Litigation History', impact: 'positive', score: 82, description: 'No D&O claims in company history' },
    ],
    comparable_accounts: [
      { company: 'PeakView Advisors', industry: 'Financial Services', premium: 280_000, limit: 25_000_000, loss_ratio: 0.15 },
      { company: 'Granite Capital', industry: 'Financial Services', premium: 310_000, limit: 25_000_000, loss_ratio: 0.20 },
    ],
    recommended_terms: { limit: 25_000_000, deductible: 500_000, premium: 295_000, conditions: ['SEC compliance warranty', 'Prior acts exclusion date: 2020-01-01', 'Regulatory proceedings sublimit $5M'] },
    reasoning_chain: [
      'Financial services D&O — requires enhanced due diligence',
      'Board composition strong — experienced independent directors',
      'No prior D&O claims — favorable loss history',
      '$25M limit within underwriting authority but near threshold',
      'Recommend human review due to coverage amount proximity to authority limit',
    ],
    decision_history: [
      { id: 'dh20', timestamp: '2025-01-15T16:00:00Z', actor: 'System', action: 'Submission received', details: 'D&O application from FinEdge Capital', is_agent: false },
      { id: 'dh21', timestamp: '2025-01-15T16:10:00Z', actor: 'triage_agent', action: 'Triage completed', details: 'Appetite match, priority high', is_agent: true },
      { id: 'dh22', timestamp: '2025-01-15T17:00:00Z', actor: 'underwriting_agent', action: 'Analysis complete', details: 'Quote with conditions — $295K premium', is_agent: true },
    ],
  },
  {
    id: 'SUB-2025-0249', applicant_name: 'Jane Williams', company_name: 'Acme Corp', lob: 'cyber',
    status: 'received', risk_score: 0, confidence: 0, agent_recommendation: 'Pending triage',
    priority: 'medium', due_date: '2025-01-20T17:00:00Z', received_date: '2025-01-15T14:30:00Z',
    annual_revenue: 25_000_000, employee_count: 200, industry: 'Technology', requested_coverage: 5_000_000,
    documents: [
      { id: 'd1', name: 'Application.pdf', type: 'application/pdf', size: 245_000, uploaded_at: '2025-01-15T14:30:00Z', url: '#' },
      { id: 'd2', name: 'Financials_2024.xlsx', type: 'application/xlsx', size: 128_000, uploaded_at: '2025-01-15T14:30:00Z', url: '#' },
    ],
    risk_factors: [],
    comparable_accounts: [],
    recommended_terms: { limit: 0, deductible: 0, premium: 0, conditions: [] },
    reasoning_chain: ['Submission received — awaiting triage'],
    decision_history: [
      { id: 'dh1', timestamp: '2025-01-15T14:30:00Z', actor: 'System', action: 'Submission received', details: 'Cyber liability application from Acme Corp', is_agent: false },
    ],
  },
];

// ── Claims Workbench Queue ──
export const mockClaimsQueue: ClaimsQueueItem[] = [
  {
    id: 'clm2', claim_number: 'CLM-2025-0038', policy_id: 'pol2', policy_number: 'POL-2025-1830',
    insured_name: 'DataFlow Systems', status: 'reserved', severity: 'critical', loss_date: '2025-01-05',
    reserve: 425_000, days_open: 10, fraud_score: 0.08, description: 'Ransomware attack — data exfiltration and business interruption', lob: 'cyber',
    coverage_verification: { status: 'verified', policy_active: true, within_coverage: true, exclusions_checked: ['War exclusion', 'Nation-state exclusion', 'Intentional acts'], notes: 'All coverage requirements met. Policy active, incident within coverage period.' },
    reserve_recommendation: { recommended_indemnity: 350_000, recommended_expense: 75_000, confidence: 0.82, basis: 'Based on comparable ransomware claims for mid-market data firms. Includes estimated forensics, notification, and business interruption costs.' },
    comparable_claims: [
      { claim_number: 'CLM-2024-0089', type: 'Ransomware', settled_amount: 380_000, duration_days: 45 },
      { claim_number: 'CLM-2024-0102', type: 'Data Breach', settled_amount: 520_000, duration_days: 62 },
      { claim_number: 'CLM-2023-0245', type: 'Ransomware', settled_amount: 290_000, duration_days: 38 },
    ],
    fraud_indicators: [
      { indicator: 'Reporting Timeline', severity: 'low', description: 'Reported within 24 hours — consistent with genuine incident' },
      { indicator: 'Third-Party Validation', severity: 'low', description: 'CrowdStrike forensics report corroborates claims' },
    ],
    timeline: [
      { timestamp: '2025-01-05T03:00:00Z', event: 'Incident Occurred', actor: 'System', details: 'Ransomware encryption detected on primary servers', is_agent: false },
      { timestamp: '2025-01-06T09:00:00Z', event: 'FNOL Filed', actor: 'DataFlow Systems', details: 'First notice of loss submitted via portal', is_agent: false },
      { timestamp: '2025-01-06T09:15:00Z', event: 'Claim Created', actor: 'claims_agent', details: 'Automated claim creation and initial assessment', is_agent: true },
      { timestamp: '2025-01-06T10:00:00Z', event: 'Coverage Verified', actor: 'claims_agent', details: 'Policy active, coverage confirmed', is_agent: true },
      { timestamp: '2025-01-06T14:00:00Z', event: 'Assigned', actor: 'System', details: 'Assigned to Mike Johnson — senior cyber adjuster', is_agent: false },
      { timestamp: '2025-01-08T11:00:00Z', event: 'Reserve Set', actor: 'Mike Johnson', details: 'Initial reserve $250,000 based on preliminary assessment', is_agent: false },
      { timestamp: '2025-01-10T15:00:00Z', event: 'Reserve Increased', actor: 'Mike Johnson', details: 'Reserve increased to $425,000 after forensics report received', is_agent: false },
      { timestamp: '2025-01-12T09:00:00Z', event: 'Payment Authorized', actor: 'Mike Johnson', details: '$75,000 emergency payment for incident response costs', is_agent: false },
    ],
    claim_documents: [
      { id: 'cd1', name: 'FNOL_Report.pdf', type: 'application/pdf', uploaded_at: '2025-01-06T09:00:00Z', category: 'fnol' },
      { id: 'cd2', name: 'CrowdStrike_Forensics.pdf', type: 'application/pdf', uploaded_at: '2025-01-08T14:00:00Z', category: 'adjuster_notes' },
      { id: 'cd3', name: 'IR_Vendor_Invoice.pdf', type: 'application/pdf', uploaded_at: '2025-01-10T10:00:00Z', category: 'invoice' },
      { id: 'cd4', name: 'Adjuster_Notes_Jan10.pdf', type: 'application/pdf', uploaded_at: '2025-01-10T16:00:00Z', category: 'adjuster_notes' },
    ],
    financials: { indemnity_reserve: 350_000, expense_reserve: 75_000, indemnity_paid: 0, expense_paid: 75_000, total_incurred: 500_000, recovery: 0 },
  },
  {
    id: 'clm1', claim_number: 'CLM-2025-0042', policy_id: 'pol3', policy_number: 'POL-2024-1650',
    insured_name: 'Meridian Healthcare', status: 'investigating', severity: 'high', loss_date: '2025-01-10',
    reserve: 250_000, days_open: 5, fraud_score: 0.12, description: 'Alleged medical malpractice — patient injury during procedure', lob: 'professional_liability',
    coverage_verification: { status: 'verified', policy_active: true, within_coverage: true, exclusions_checked: ['Criminal acts', 'Intentional misconduct', 'Punitive damages'], notes: 'Professional liability policy covers alleged malpractice. Claims-made trigger verified.' },
    reserve_recommendation: { recommended_indemnity: 200_000, recommended_expense: 50_000, confidence: 0.72, basis: 'Medical malpractice claims in this jurisdiction average $180K-$350K for similar procedures.' },
    comparable_claims: [
      { claim_number: 'CLM-2024-0156', type: 'Medical Malpractice', settled_amount: 275_000, duration_days: 180 },
      { claim_number: 'CLM-2023-0312', type: 'Medical Malpractice', settled_amount: 195_000, duration_days: 120 },
    ],
    fraud_indicators: [
      { indicator: 'Claim Pattern', severity: 'low', description: 'No unusual claim patterns for this insured' },
      { indicator: 'Documentation', severity: 'medium', description: 'Medical records pending — unable to fully verify at this stage' },
    ],
    timeline: [
      { timestamp: '2025-01-10T14:00:00Z', event: 'Incident Occurred', actor: 'System', details: 'Patient injury during surgical procedure', is_agent: false },
      { timestamp: '2025-01-12T10:00:00Z', event: 'FNOL Filed', actor: 'Meridian Healthcare', details: 'First notice of loss filed', is_agent: false },
      { timestamp: '2025-01-12T10:30:00Z', event: 'Claim Created', actor: 'claims_agent', details: 'Claim assessed — severity high, escalation recommended', is_agent: true },
      { timestamp: '2025-01-12T14:00:00Z', event: 'Assigned', actor: 'System', details: 'Assigned to Mike Johnson', is_agent: false },
      { timestamp: '2025-01-13T09:00:00Z', event: 'Investigation Started', actor: 'Mike Johnson', details: 'Medical records requested from hospital', is_agent: false },
    ],
    claim_documents: [
      { id: 'cd5', name: 'FNOL_Malpractice.pdf', type: 'application/pdf', uploaded_at: '2025-01-12T10:00:00Z', category: 'fnol' },
      { id: 'cd6', name: 'Initial_Assessment.pdf', type: 'application/pdf', uploaded_at: '2025-01-12T10:30:00Z', category: 'adjuster_notes' },
    ],
    financials: { indemnity_reserve: 200_000, expense_reserve: 50_000, indemnity_paid: 0, expense_paid: 0, total_incurred: 250_000, recovery: 0 },
  },
  {
    id: 'clm3', claim_number: 'CLM-2025-0035', policy_id: 'pol4', policy_number: 'POL-2024-1580',
    insured_name: 'Summit Financial Group', status: 'open', severity: 'medium', loss_date: '2025-01-02',
    reserve: 125_000, days_open: 13, fraud_score: 0.05, description: 'Securities class action — alleged misrepresentation in Q3 earnings', lob: 'dnol',
    coverage_verification: { status: 'pending', policy_active: true, within_coverage: true, exclusions_checked: ['Prior knowledge', 'Fraud exclusion'], notes: 'Coverage likely applies but pending full legal review of allegations.' },
    reserve_recommendation: { recommended_indemnity: 100_000, recommended_expense: 25_000, confidence: 0.38, basis: 'Insufficient data for full automated assessment — securities class actions highly variable.' },
    comparable_claims: [
      { claim_number: 'CLM-2024-0078', type: 'Securities Class Action', settled_amount: 850_000, duration_days: 365 },
      { claim_number: 'CLM-2023-0189', type: 'D&O Claim', settled_amount: 220_000, duration_days: 210 },
    ],
    fraud_indicators: [
      { indicator: 'Claim Timing', severity: 'low', description: 'Claim filed shortly after earnings restatement — typical pattern' },
    ],
    timeline: [
      { timestamp: '2025-01-02T00:00:00Z', event: 'Loss Date', actor: 'System', details: 'Q3 earnings restatement announced', is_agent: false },
      { timestamp: '2025-01-03T11:00:00Z', event: 'FNOL Filed', actor: 'Summit Financial', details: 'Class action lawsuit served', is_agent: false },
      { timestamp: '2025-01-03T11:30:00Z', event: 'Claim Created', actor: 'claims_agent', details: 'Automated assessment — low confidence, human review required', is_agent: true },
      { timestamp: '2025-01-04T09:00:00Z', event: 'Assigned', actor: 'System', details: 'Assigned to Lisa Park — D&O specialist', is_agent: false },
    ],
    claim_documents: [
      { id: 'cd7', name: 'Class_Action_Complaint.pdf', type: 'application/pdf', uploaded_at: '2025-01-03T11:00:00Z', category: 'legal' },
      { id: 'cd8', name: 'Initial_Assessment.pdf', type: 'application/pdf', uploaded_at: '2025-01-03T11:30:00Z', category: 'adjuster_notes' },
    ],
    financials: { indemnity_reserve: 100_000, expense_reserve: 25_000, indemnity_paid: 0, expense_paid: 0, total_incurred: 125_000, recovery: 0 },
  },
  {
    id: 'clm6', claim_number: 'CLM-2025-0045', policy_id: 'pol1', policy_number: 'POL-2025-1847',
    insured_name: 'GreenTech Solutions', status: 'open', severity: 'low', loss_date: '2025-01-14',
    reserve: 35_000, days_open: 1, fraud_score: 0.03, description: 'Wrongful termination claim by former employee', lob: 'epli',
    coverage_verification: { status: 'verified', policy_active: true, within_coverage: true, exclusions_checked: ['Intentional violation of law', 'Contractual liability'], notes: 'EPLI policy covers wrongful termination allegations.' },
    reserve_recommendation: { recommended_indemnity: 25_000, recommended_expense: 10_000, confidence: 0.88, basis: 'Single-plaintiff EPLI claims in this jurisdiction typically settle $20K-$50K.' },
    comparable_claims: [
      { claim_number: 'CLM-2024-0201', type: 'Wrongful Termination', settled_amount: 32_000, duration_days: 90 },
      { claim_number: 'CLM-2024-0178', type: 'Wrongful Termination', settled_amount: 28_000, duration_days: 75 },
    ],
    fraud_indicators: [],
    timeline: [
      { timestamp: '2025-01-14T09:00:00Z', event: 'FNOL Filed', actor: 'GreenTech Solutions', details: 'Former employee filed wrongful termination complaint', is_agent: false },
      { timestamp: '2025-01-14T09:15:00Z', event: 'Claim Created', actor: 'claims_agent', details: 'Standard EPLI claim — low severity', is_agent: true },
      { timestamp: '2025-01-14T10:00:00Z', event: 'Assigned', actor: 'System', details: 'Assigned to Lisa Park', is_agent: false },
    ],
    claim_documents: [
      { id: 'cd9', name: 'FNOL_Termination.pdf', type: 'application/pdf', uploaded_at: '2025-01-14T09:00:00Z', category: 'fnol' },
    ],
    financials: { indemnity_reserve: 25_000, expense_reserve: 10_000, indemnity_paid: 0, expense_paid: 0, total_incurred: 35_000, recovery: 0 },
  },
];

// ── Compliance Workbench — Decision Audit ──
export const mockDecisionAudit: DecisionAuditItem[] = [
  { id: 'DA-001', agent: 'Triage Agent', decision_type: 'Triage', confidence: 0.94, input_summary: 'Cyber application from Acme Corp — $25M revenue, 200 employees, Technology sector', output: 'Triaged to underwriting queue — priority medium', reasoning_chain: ['Application complete', 'Cyber LOB identified', 'Revenue within appetite range', 'Technology sector — standard risk'], timestamp: '2025-01-15T14:32:00Z', reviewed: false, flagged: false },
  { id: 'DA-002', agent: 'Underwriting Agent', decision_type: 'Quote', confidence: 0.87, input_summary: 'Professional liability for TechStart Inc — $8M revenue, 55 employees, Software', output: 'Quote generated — $45,000 premium, $2M limit', reasoning_chain: ['Clean loss history', 'Industry within appetite', 'Revenue appropriate', 'Strong financials'], timestamp: '2025-01-15T13:45:00Z', reviewed: true, flagged: false },
  { id: 'DA-003', agent: 'Claims Agent', decision_type: 'Claim Assessment', confidence: 0.72, input_summary: 'Medical malpractice claim CLM-2025-0042 — Meridian Healthcare', output: 'Escalated to senior adjuster — complex liability assessment', reasoning_chain: ['Complex liability', 'Initial documents suggest merit', 'Reserve $250K recommended', 'Senior adjuster needed'], timestamp: '2025-01-15T13:55:00Z', reviewed: false, flagged: false },
  { id: 'DA-004', agent: 'Fraud Detection', decision_type: 'Fraud Screening', confidence: 0.91, input_summary: 'Ransomware claim CLM-2025-0038 — DataFlow Systems', output: 'No fraud detected — proceed with claim', reasoning_chain: ['Third-party forensics corroborate', 'Timeline consistent', 'No fraud indicators', 'Strong claims history'], timestamp: '2025-01-15T12:30:00Z', reviewed: true, flagged: false },
  { id: 'DA-005', agent: 'Triage Agent', decision_type: 'Decline', confidence: 0.95, input_summary: 'D&O application from CryptoVault Exchange — $200M revenue, Cryptocurrency', output: 'Submission declined — outside appetite', reasoning_chain: ['Cryptocurrency exchange', 'Regulatory uncertainty', 'Coverage disproportionate to operations', 'Outside risk appetite'], timestamp: '2025-01-15T12:58:00Z', reviewed: false, flagged: false },
  { id: 'DA-006', agent: 'Underwriting Agent', decision_type: 'Risk Assessment', confidence: 0.45, input_summary: 'GL application from Metro Construction — $45M revenue, 320 employees, Construction', output: 'Referred to senior underwriter — insufficient data for automation', reasoning_chain: ['Construction — elevated risk', 'Large workforce with field exposure', 'Insufficient data for automated scoring', 'Manual review recommended'], timestamp: '2025-01-15T10:20:00Z', reviewed: false, flagged: true },
];

// ── Compliance Workbench — Override Log ──
export const mockOverrideLog: OverrideLogEntry[] = [
  { id: 'OV-001', who: 'Sarah Chen', decision_type: 'Quote Terms', original_recommendation: 'Premium $45,000 / Deductible $25,000', override_to: 'Premium $42,000 / Deductible $25,000', reason: 'Adjusted premium down 7% to match competitive market conditions for renewal account', timestamp: '2025-01-15T11:30:00Z' },
  { id: 'OV-002', who: 'James Wright', decision_type: 'Claim Reserve', original_recommendation: 'Reserve $250,000', override_to: 'Reserve $425,000', reason: 'Forensics report indicates broader impact than initially assessed — increased BI costs', timestamp: '2025-01-14T15:00:00Z' },
  { id: 'OV-003', who: 'Mike Johnson', decision_type: 'Fraud Screening', original_recommendation: 'Flag for investigation — confidence 65%', override_to: 'Proceed with denial review', reason: 'Late reporting combined with policy exclusion clause — proceeding to coverage review', timestamp: '2025-01-14T11:30:00Z' },
  { id: 'OV-004', who: 'Sarah Chen', decision_type: 'Triage Decision', original_recommendation: 'Auto-decline — outside appetite', override_to: 'Accept for manual review', reason: 'Client has existing relationship and is transitioning out of excluded sector', timestamp: '2025-01-13T09:45:00Z' },
  { id: 'OV-005', who: 'James Wright', decision_type: 'Quote Terms', original_recommendation: 'Premium $72,000 / Limit $5M', override_to: 'Premium $68,000 / Limit $5M', reason: 'Multi-policy discount applied — insured also has D&O coverage with us', timestamp: '2025-01-12T14:20:00Z' },
];

// ── Compliance Workbench — Bias Chart Data ──
export const mockBiasChartData: BiasChartData = {
  approval_by_sector: [
    { sector: 'Technology', rate: 0.78 },
    { sector: 'Healthcare', rate: 0.72 },
    { sector: 'Financial Services', rate: 0.75 },
    { sector: 'Manufacturing', rate: 0.68 },
    { sector: 'Construction', rate: 0.45 },
    { sector: 'Retail', rate: 0.71 },
    { sector: 'Energy', rate: 0.65 },
  ],
  premium_by_size: [
    { size: '<$5M', min: 8_000, q1: 12_000, median: 18_000, q3: 25_000, max: 35_000 },
    { size: '$5M-$25M', min: 15_000, q1: 28_000, median: 45_000, q3: 72_000, max: 95_000 },
    { size: '$25M-$100M', min: 35_000, q1: 65_000, median: 95_000, q3: 140_000, max: 210_000 },
    { size: '$100M-$500M', min: 80_000, q1: 130_000, median: 195_000, q3: 280_000, max: 450_000 },
    { size: '>$500M', min: 150_000, q1: 250_000, median: 380_000, q3: 520_000, max: 800_000 },
  ],
  disparate_impact: [
    { category: 'Industry Sector', ratio: 0.92, threshold: 0.8 },
    { category: 'Company Size', ratio: 0.88, threshold: 0.8 },
    { category: 'Geography', ratio: 0.79, threshold: 0.8 },
    { category: 'Revenue Band', ratio: 0.85, threshold: 0.8 },
    { category: 'Employee Count', ratio: 0.91, threshold: 0.8 },
  ],
};

// ── Executive Dashboard ──
export const mockExecutiveData: ExecutiveDashboardData = {
  kpis: { gwp: 12_450_000, nwp: 10_875_000, loss_ratio: 0.58, combined_ratio: 0.92, growth_rate: 0.18 },
  premium_trend: [
    { month: 'Feb 2024', premium: 820_000 },
    { month: 'Mar 2024', premium: 910_000 },
    { month: 'Apr 2024', premium: 875_000 },
    { month: 'May 2024', premium: 980_000 },
    { month: 'Jun 2024', premium: 1_050_000 },
    { month: 'Jul 2024', premium: 1_020_000 },
    { month: 'Aug 2024', premium: 1_100_000 },
    { month: 'Sep 2024', premium: 1_150_000 },
    { month: 'Oct 2024', premium: 1_080_000 },
    { month: 'Nov 2024', premium: 1_200_000 },
    { month: 'Dec 2024', premium: 1_250_000 },
    { month: 'Jan 2025', premium: 1_015_000 },
  ],
  loss_ratio_by_lob: [
    { lob: 'Cyber', loss_ratio: 0.52 },
    { lob: 'Prof Liability', loss_ratio: 0.48 },
    { lob: 'D&O', loss_ratio: 0.65 },
    { lob: 'EPLI', loss_ratio: 0.42 },
    { lob: 'General Liability', loss_ratio: 0.71 },
  ],
  exposure_concentrations: [
    { name: 'Technology', exposure: 4_200_000 },
    { name: 'Financial Services', exposure: 3_100_000 },
    { name: 'Healthcare', exposure: 2_800_000 },
    { name: 'Manufacturing', exposure: 1_500_000 },
    { name: 'Construction', exposure: 850_000 },
  ],
  pipeline: [
    { stage: 'Received', count: 45 },
    { stage: 'Triaging', count: 28 },
    { stage: 'Underwriting', count: 18 },
    { stage: 'Quoted', count: 12 },
    { stage: 'Bound', count: 8 },
  ],
  agent_impact: { processing_time_reduction: 68, auto_bind_rate: 34, escalation_rate: 8 },
};

// ── Broker Portal ──
export const mockBrokerSubmissions: BrokerSubmission[] = [
  { id: 'SUB-2025-0248', applicant_name: 'CloudNine Security', lob: 'cyber', status: 'underwriting', submitted_date: '2025-01-15', last_update: '2025-01-15T12:30:00Z', status_timeline: [
    { timestamp: '2025-01-15T12:00:00Z', status: 'Received', description: 'Application received and acknowledged' },
    { timestamp: '2025-01-15T12:05:00Z', status: 'In Review', description: 'Your submission is being reviewed by our underwriting team' },
  ]},
  { id: 'SUB-2025-0245', applicant_name: 'TechStart Inc', lob: 'professional_liability', status: 'quoted', submitted_date: '2025-01-14', last_update: '2025-01-14T10:30:00Z', status_timeline: [
    { timestamp: '2025-01-14T09:15:00Z', status: 'Received', description: 'Application received and acknowledged' },
    { timestamp: '2025-01-14T09:20:00Z', status: 'In Review', description: 'Your submission is being reviewed' },
    { timestamp: '2025-01-14T10:30:00Z', status: 'Quote Ready', description: 'A quote has been prepared for your review' },
  ]},
  { id: 'SUB-2025-0240', applicant_name: 'DataFlow Systems', lob: 'cyber', status: 'bound', submitted_date: '2025-01-13', last_update: '2025-01-13T16:00:00Z', status_timeline: [
    { timestamp: '2025-01-13T11:00:00Z', status: 'Received', description: 'Application received' },
    { timestamp: '2025-01-13T13:00:00Z', status: 'Quote Ready', description: 'Quote prepared' },
    { timestamp: '2025-01-13T14:00:00Z', status: 'Quote Approved', description: 'Quote approved by underwriting' },
    { timestamp: '2025-01-13T16:00:00Z', status: 'Bound', description: 'Policy bound — documents will follow' },
  ]},
  { id: 'SUB-2025-0235', applicant_name: 'GreenTech Solutions', lob: 'epli', status: 'bound', submitted_date: '2025-01-12', last_update: '2025-01-12T16:00:00Z', status_timeline: [
    { timestamp: '2025-01-12T08:30:00Z', status: 'Received', description: 'Application received' },
    { timestamp: '2025-01-12T12:00:00Z', status: 'Quote Ready', description: 'Quote prepared' },
    { timestamp: '2025-01-12T16:00:00Z', status: 'Bound', description: 'Policy issued' },
  ]},
];

export const mockBrokerPolicies: BrokerPolicy[] = [
  { id: 'pol2', policy_number: 'POL-2025-1830', insured_name: 'DataFlow Systems', lob: 'cyber', effective_date: '2025-01-08', expiry_date: '2026-01-08', premium: 72_000 },
  { id: 'pol1', policy_number: 'POL-2025-1847', insured_name: 'GreenTech Solutions', lob: 'epli', effective_date: '2025-01-12', expiry_date: '2026-01-12', premium: 28_000 },
  { id: 'pol3', policy_number: 'POL-2024-1650', insured_name: 'Meridian Healthcare', lob: 'professional_liability', effective_date: '2024-06-01', expiry_date: '2025-06-01', premium: 95_000 },
  { id: 'pol4', policy_number: 'POL-2024-1580', insured_name: 'Summit Financial Group', lob: 'dnol', effective_date: '2024-04-15', expiry_date: '2025-04-15', premium: 120_000 },
];

export const mockBrokerClaims: BrokerClaim[] = [
  { id: 'clm2', claim_number: 'CLM-2025-0038', policy_number: 'POL-2025-1830', status: 'reserved', loss_date: '2025-01-05' },
  { id: 'clm1', claim_number: 'CLM-2025-0042', policy_number: 'POL-2024-1650', status: 'investigating', loss_date: '2025-01-10' },
  { id: 'clm6', claim_number: 'CLM-2025-0045', policy_number: 'POL-2025-1847', status: 'open', loss_date: '2025-01-14' },
];

// ── Reinsurance (Carrier-only) ──

export const mockReinsuranceTreaties: ReinsuranceTreaty[] = [
  {
    id: 'tre-1', treaty_number: 'TRE-2025-QS01', treaty_type: 'quota_share', reinsurer_name: 'Swiss Re',
    status: 'active', effective_date: '2025-01-01', expiration_date: '2025-12-31',
    lines_of_business: ['cyber', 'professional_liability'], retention: 5_000_000, limit: 20_000_000,
    rate: 25, capacity_total: 50_000_000, capacity_used: 32_500_000, reinstatements: 2,
    description: 'Cyber & Prof Liability quota share — 25% cession',
  },
  {
    id: 'tre-2', treaty_number: 'TRE-2025-XL01', treaty_type: 'excess_of_loss', reinsurer_name: 'Munich Re',
    status: 'active', effective_date: '2025-01-01', expiration_date: '2025-12-31',
    lines_of_business: ['cyber'], retention: 2_000_000, limit: 10_000_000,
    rate: 12, capacity_total: 30_000_000, capacity_used: 8_400_000, reinstatements: 1,
    description: 'Cyber excess of loss — $2M xs $2M',
  },
  {
    id: 'tre-3', treaty_number: 'TRE-2025-SU01', treaty_type: 'surplus', reinsurer_name: 'Hannover Re',
    status: 'active', effective_date: '2025-01-01', expiration_date: '2025-12-31',
    lines_of_business: ['dnol', 'epli'], retention: 1_000_000, limit: 15_000_000,
    rate: 18, capacity_total: 40_000_000, capacity_used: 22_000_000, reinstatements: 2,
    description: 'D&O / EPLI surplus treaty — 5 lines',
  },
  {
    id: 'tre-4', treaty_number: 'TRE-2024-QS01', treaty_type: 'quota_share', reinsurer_name: 'Gen Re',
    status: 'expired', effective_date: '2024-01-01', expiration_date: '2024-12-31',
    lines_of_business: ['professional_liability'], retention: 3_000_000, limit: 12_000_000,
    rate: 20, capacity_total: 25_000_000, capacity_used: 25_000_000, reinstatements: 0,
    description: 'Prior year prof liability QS (expired)',
  },
  {
    id: 'tre-5', treaty_number: 'TRE-2025-FA01', treaty_type: 'facultative', reinsurer_name: 'Lloyd\'s Syndicate 2001',
    status: 'active', effective_date: '2025-03-01', expiration_date: '2026-02-28',
    lines_of_business: ['cyber'], retention: 500_000, limit: 5_000_000,
    rate: 30, capacity_total: 10_000_000, capacity_used: 3_200_000, reinstatements: 1,
    description: 'Facultative placement — large cyber risk',
  },
];

export const mockReinsuranceCessions: ReinsuranceCession[] = [
  { id: 'ces-1', treaty_id: 'tre-1', policy_id: 'pol-100', policy_number: 'POL-2025-1830', ceded_premium: 11_250, ceded_limit: 250_000, cession_date: '2025-01-10' },
  { id: 'ces-2', treaty_id: 'tre-1', policy_id: 'pol-101', policy_number: 'POL-2025-1847', ceded_premium: 7_000, ceded_limit: 175_000, cession_date: '2025-01-12' },
  { id: 'ces-3', treaty_id: 'tre-2', policy_id: 'pol-102', policy_number: 'POL-2025-1855', ceded_premium: 18_600, ceded_limit: 500_000, cession_date: '2025-01-14' },
  { id: 'ces-4', treaty_id: 'tre-3', policy_id: 'pol-103', policy_number: 'POL-2025-1860', ceded_premium: 21_600, ceded_limit: 600_000, cession_date: '2025-01-15' },
  { id: 'ces-5', treaty_id: 'tre-5', policy_id: 'pol-104', policy_number: 'POL-2025-1870', ceded_premium: 45_000, ceded_limit: 1_500_000, cession_date: '2025-01-16' },
  { id: 'ces-6', treaty_id: 'tre-1', policy_id: 'pol-105', policy_number: 'POL-2025-1872', ceded_premium: 8_750, ceded_limit: 200_000, cession_date: '2025-01-17' },
];

export const mockReinsuranceRecoveries: ReinsuranceRecovery[] = [
  { id: 'rec-1', treaty_id: 'tre-1', claim_id: 'clm-200', claim_number: 'CLM-2025-0038', recovery_amount: 62_500, recovery_date: '2025-01-20', status: 'billed' },
  { id: 'rec-2', treaty_id: 'tre-2', claim_id: 'clm-201', claim_number: 'CLM-2025-0042', recovery_amount: 150_000, recovery_date: '2025-01-22', status: 'pending' },
  { id: 'rec-3', treaty_id: 'tre-3', claim_id: 'clm-202', claim_number: 'CLM-2025-0045', recovery_amount: 85_000, recovery_date: '2025-01-18', status: 'collected' },
  { id: 'rec-4', treaty_id: 'tre-1', claim_id: 'clm-203', claim_number: 'CLM-2025-0050', recovery_amount: 37_500, recovery_date: '2025-01-25', status: 'pending' },
];

export const mockReinsuranceData: ReinsuranceDashboardData = {
  treaties: mockReinsuranceTreaties,
  cessions: mockReinsuranceCessions,
  recoveries: mockReinsuranceRecoveries,
};

// ── Actuarial Mock Data ──

export const mockActuarialReserves: ActuarialReserve[] = [
  { id: 'res-001', line_of_business: 'cyber', accident_year: 2023, reserve_type: 'case', carried_amount: 4_500_000, indicated_amount: 4_800_000, selected_amount: 4_650_000, as_of_date: '2026-03-31', analyst: 'Sarah Chen', approved_by: 'Michael Torres', notes: '' },
  { id: 'res-002', line_of_business: 'cyber', accident_year: 2023, reserve_type: 'ibnr', carried_amount: 2_100_000, indicated_amount: 2_350_000, selected_amount: 2_200_000, as_of_date: '2026-03-31', analyst: 'Sarah Chen', approved_by: 'Michael Torres', notes: '' },
  { id: 'res-003', line_of_business: 'cyber', accident_year: 2024, reserve_type: 'case', carried_amount: 3_200_000, indicated_amount: 3_400_000, selected_amount: 3_300_000, as_of_date: '2026-03-31', analyst: 'Sarah Chen', approved_by: '', notes: 'Pending CFO approval' },
  { id: 'res-004', line_of_business: 'cyber', accident_year: 2024, reserve_type: 'ibnr', carried_amount: 1_800_000, indicated_amount: 2_000_000, selected_amount: 1_900_000, as_of_date: '2026-03-31', analyst: 'Sarah Chen', approved_by: '', notes: '' },
  { id: 'res-005', line_of_business: 'professional_liability', accident_year: 2023, reserve_type: 'case', carried_amount: 6_000_000, indicated_amount: 6_200_000, selected_amount: 6_100_000, as_of_date: '2026-03-31', analyst: 'James Wright', approved_by: 'Michael Torres', notes: '' },
  { id: 'res-006', line_of_business: 'professional_liability', accident_year: 2023, reserve_type: 'ibnr', carried_amount: 3_500_000, indicated_amount: 3_800_000, selected_amount: 3_600_000, as_of_date: '2026-03-31', analyst: 'James Wright', approved_by: 'Michael Torres', notes: '' },
];

export const mockTriangleData: TriangleData = {
  line_of_business: 'cyber',
  accident_years: [2021, 2022, 2023, 2024],
  development_months: [12, 24, 36, 48, 60],
  entries: [
    { accident_year: 2021, development_month: 12, incurred_amount: 1_200_000, paid_amount: 600_000, case_reserve: 600_000, claim_count: 15 },
    { accident_year: 2021, development_month: 24, incurred_amount: 2_100_000, paid_amount: 1_400_000, case_reserve: 700_000, claim_count: 18 },
    { accident_year: 2021, development_month: 36, incurred_amount: 2_600_000, paid_amount: 2_000_000, case_reserve: 600_000, claim_count: 19 },
    { accident_year: 2021, development_month: 48, incurred_amount: 2_800_000, paid_amount: 2_500_000, case_reserve: 300_000, claim_count: 19 },
    { accident_year: 2021, development_month: 60, incurred_amount: 2_850_000, paid_amount: 2_700_000, case_reserve: 150_000, claim_count: 19 },
    { accident_year: 2022, development_month: 12, incurred_amount: 1_500_000, paid_amount: 700_000, case_reserve: 800_000, claim_count: 20 },
    { accident_year: 2022, development_month: 24, incurred_amount: 2_500_000, paid_amount: 1_600_000, case_reserve: 900_000, claim_count: 24 },
    { accident_year: 2022, development_month: 36, incurred_amount: 3_100_000, paid_amount: 2_400_000, case_reserve: 700_000, claim_count: 25 },
    { accident_year: 2022, development_month: 48, incurred_amount: 3_400_000, paid_amount: 3_000_000, case_reserve: 400_000, claim_count: 25 },
    { accident_year: 2023, development_month: 12, incurred_amount: 1_800_000, paid_amount: 800_000, case_reserve: 1_000_000, claim_count: 25 },
    { accident_year: 2023, development_month: 24, incurred_amount: 3_000_000, paid_amount: 1_900_000, case_reserve: 1_100_000, claim_count: 30 },
    { accident_year: 2023, development_month: 36, incurred_amount: 3_800_000, paid_amount: 2_800_000, case_reserve: 1_000_000, claim_count: 32 },
    { accident_year: 2024, development_month: 12, incurred_amount: 2_000_000, paid_amount: 900_000, case_reserve: 1_100_000, claim_count: 28 },
    { accident_year: 2024, development_month: 24, incurred_amount: 3_400_000, paid_amount: 2_100_000, case_reserve: 1_300_000, claim_count: 34 },
  ],
};

export const mockIBNR: IBNRResult = {
  line_of_business: 'cyber',
  method: 'chain_ladder',
  factors: { '12': '1.7500', '24': '1.2381', '36': '1.0769', '48': '1.0179' },
  ultimates: { '2021': '2850.00', '2022': '3460.86', '2023': '4767.11', '2024': '7381.25' },
  ibnr_by_year: { '2021': '0.00', '2022': '60.86', '2023': '967.11', '2024': '3981.25' },
  total_ibnr: '5009.22',
};

export const mockRateAdequacy: RateAdequacyItem[] = [
  { line_of_business: 'cyber', segment: 'smb-technology', current_rate: '1.50', indicated_rate: '1.72', adequacy_ratio: '1.1467' },
  { line_of_business: 'cyber', segment: 'smb-healthcare', current_rate: '2.20', indicated_rate: '2.85', adequacy_ratio: '1.2955' },
  { line_of_business: 'cyber', segment: 'smb-financial', current_rate: '1.80', indicated_rate: '1.95', adequacy_ratio: '1.0833' },
  { line_of_business: 'cyber', segment: 'mid-market-technology', current_rate: '1.20', indicated_rate: '1.35', adequacy_ratio: '1.1250' },
  { line_of_business: 'cyber', segment: 'mid-market-retail', current_rate: '0.90', indicated_rate: '0.82', adequacy_ratio: '0.9111' },
  { line_of_business: 'professional_liability', segment: 'law-firms', current_rate: '3.10', indicated_rate: '3.45', adequacy_ratio: '1.1129' },
  { line_of_business: 'professional_liability', segment: 'accounting', current_rate: '2.50', indicated_rate: '2.30', adequacy_ratio: '0.9200' },
];
