import client from './client';
import type {
  UnderwriterQueueItem,
  ClaimsQueueItem,
  DecisionAuditItem,
  OverrideLogEntry,
  BiasChartData,
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

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getUnderwriterQueue(): Promise<UnderwriterQueueItem[]> {
  if (USE_MOCK) return mockUnderwriterQueue;
  const { data } = await client.get('/underwriter/queue');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getClaimsQueue(): Promise<ClaimsQueueItem[]> {
  if (USE_MOCK) return mockClaimsQueue;
  const { data } = await client.get('/claims/queue');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getDecisionAudit(): Promise<DecisionAuditItem[]> {
  if (USE_MOCK) return mockDecisionAudit;
  const { data } = await client.get('/decisions/audit');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getOverrideLog(): Promise<OverrideLogEntry[]> {
  if (USE_MOCK) return mockOverrideLog;
  const { data } = await client.get('/decisions/overrides');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getBiasChartData(): Promise<BiasChartData> {
  if (USE_MOCK) return mockBiasChartData;
  const { data } = await client.get<BiasChartData>('/compliance/bias');
  return data;
}

export async function getComplianceWorkbenchData(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  const { data } = await client.get<ComplianceSummary>('/compliance/summary');
  return data;
}

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardData> {
  if (USE_MOCK) return mockExecutiveData;
  const { data } = await client.get<ExecutiveDashboardData>('/dashboard/executive');
  return data;
}

export async function getBrokerSubmissions(): Promise<BrokerSubmission[]> {
  if (USE_MOCK) return mockBrokerSubmissions;
  const { data } = await client.get('/broker/submissions');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getBrokerPolicies(): Promise<BrokerPolicy[]> {
  if (USE_MOCK) return mockBrokerPolicies;
  const { data } = await client.get('/broker/policies');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getBrokerClaims(): Promise<BrokerClaim[]> {
  if (USE_MOCK) return mockBrokerClaims;
  const { data } = await client.get('/broker/claims');
  return Array.isArray(data) ? data : (data.items || []);
}

// ── Actuarial Workbench ──

export async function getActuarialReserves(): Promise<ActuarialReserve[]> {
  if (USE_MOCK) return mockActuarialReserves;
  const { data } = await client.get('/actuarial/reserves');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getTriangleData(lob = 'cyber'): Promise<TriangleData> {
  if (USE_MOCK) return mockTriangleData;
  const { data } = await client.get<TriangleData>(`/actuarial/triangles/${lob}`);
  return data;
}

export async function getIBNR(lob = 'cyber'): Promise<IBNRResult> {
  if (USE_MOCK) return mockIBNR;
  const { data } = await client.get<IBNRResult>(`/actuarial/ibnr/${lob}`);
  return data;
}

export async function getRateAdequacy(): Promise<RateAdequacyItem[]> {
  if (USE_MOCK) return mockRateAdequacy;
  const { data } = await client.get('/actuarial/rate-adequacy');
  return Array.isArray(data) ? data : (data.items || []);
}
