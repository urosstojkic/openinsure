import client from './client';

// --- UW Analytics (#81) ---

export interface ConversionFunnelStage {
  stage: string;
  count: number;
  rate: number;
}

export interface HitRatioMetric {
  period: string;
  submissions: number;
  quoted: number;
  hit_ratio: number;
}

export interface ProcessingTimeMetric {
  stage: string;
  avg_hours: number;
  p50_hours: number;
  p90_hours: number;
}

export interface AgentVsHumanMetric {
  total_decisions: number;
  agent_decisions: number;
  human_overrides: number;
  override_rate: number;
  agent_accuracy: number;
}

export interface UWAnalyticsData {
  period: string;
  hit_ratio: HitRatioMetric[];
  conversion_funnel: ConversionFunnelStage[];
  processing_time: ProcessingTimeMetric[];
  agent_vs_human: AgentVsHumanMetric;
  total_submissions: number;
  total_quoted: number;
  total_bound: number;
  total_declined: number;
}

export async function getUWAnalytics(months = 12): Promise<UWAnalyticsData> {
  const { data } = await client.get<UWAnalyticsData>('/analytics/underwriting', { params: { months } });
  return data;
}

// --- Claims Analytics (#82) ---

export interface FrequencySeverityPoint {
  period: string;
  claim_count: number;
  avg_severity: number;
  total_incurred: number;
}

export interface ReserveDevelopment {
  period: string;
  initial_reserve: number;
  current_reserve: number;
  paid_to_date: number;
}

export interface FraudDistributionBucket {
  range_start: number;
  range_end: number;
  count: number;
}

export interface ClaimsByType {
  claim_type: string;
  count: number;
  avg_severity: number;
  total_incurred: number;
}

export interface ClaimsAnalyticsData {
  period: string;
  frequency_severity: FrequencySeverityPoint[];
  reserve_development: ReserveDevelopment[];
  fraud_distribution: FraudDistributionBucket[];
  claims_by_type: ClaimsByType[];
  total_claims: number;
  total_open: number;
  total_incurred: number;
  avg_fraud_score: number;
}

export async function getClaimsAnalytics(months = 12): Promise<ClaimsAnalyticsData> {
  const { data } = await client.get<ClaimsAnalyticsData>('/analytics/claims', { params: { months } });
  return data;
}

// --- AI Insights (#83) ---

export interface AIInsight {
  category: string;
  title: string;
  summary: string;
  severity: string;
  data: Record<string, unknown>;
}

export interface AIInsightsData {
  generated_at: string;
  period: string;
  insights: AIInsight[];
  executive_summary: string;
  source: string;
}

export async function getAIInsights(period = 'last_12_months'): Promise<AIInsightsData> {
  const { data } = await client.get<AIInsightsData>('/analytics/ai-insights', { params: { period } });
  return data;
}
