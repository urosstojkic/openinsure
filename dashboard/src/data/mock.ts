import type {
  DashboardStats,
  Submission,
  Policy,
  Claim,
  AgentDecision,
  ComplianceSummary,
  Product,
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
