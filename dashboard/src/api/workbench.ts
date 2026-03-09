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
} from '../data/mock';

const USE_MOCK = true;

export async function getUnderwriterQueue(): Promise<UnderwriterQueueItem[]> {
  if (USE_MOCK) return mockUnderwriterQueue;
  return [];
}

export async function getClaimsQueue(): Promise<ClaimsQueueItem[]> {
  if (USE_MOCK) return mockClaimsQueue;
  return [];
}

export async function getDecisionAudit(): Promise<DecisionAuditItem[]> {
  if (USE_MOCK) return mockDecisionAudit;
  return [];
}

export async function getOverrideLog(): Promise<OverrideLogEntry[]> {
  if (USE_MOCK) return mockOverrideLog;
  return [];
}

export async function getBiasChartData(): Promise<BiasChartData> {
  if (USE_MOCK) return mockBiasChartData;
  return { approval_by_sector: [], premium_by_size: [], disparate_impact: [] };
}

export async function getComplianceWorkbenchData(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  return {} as ComplianceSummary;
}

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardData> {
  if (USE_MOCK) return mockExecutiveData;
  return {} as ExecutiveDashboardData;
}

export async function getBrokerSubmissions(): Promise<BrokerSubmission[]> {
  if (USE_MOCK) return mockBrokerSubmissions;
  return [];
}

export async function getBrokerPolicies(): Promise<BrokerPolicy[]> {
  if (USE_MOCK) return mockBrokerPolicies;
  return [];
}

export async function getBrokerClaims(): Promise<BrokerClaim[]> {
  if (USE_MOCK) return mockBrokerClaims;
  return [];
}
