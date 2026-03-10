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

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getUnderwriterQueue(): Promise<UnderwriterQueueItem[]> {
  if (USE_MOCK) return mockUnderwriterQueue;
  try {
    const { data } = await client.get('/underwriter/queue');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockUnderwriterQueue;
  }
}

export async function getClaimsQueue(): Promise<ClaimsQueueItem[]> {
  if (USE_MOCK) return mockClaimsQueue;
  try {
    const { data } = await client.get('/claims/queue');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockClaimsQueue;
  }
}

export async function getDecisionAudit(): Promise<DecisionAuditItem[]> {
  if (USE_MOCK) return mockDecisionAudit;
  try {
    const { data } = await client.get('/decisions/audit');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockDecisionAudit;
  }
}

export async function getOverrideLog(): Promise<OverrideLogEntry[]> {
  if (USE_MOCK) return mockOverrideLog;
  try {
    const { data } = await client.get('/decisions/overrides');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockOverrideLog;
  }
}

export async function getBiasChartData(): Promise<BiasChartData> {
  if (USE_MOCK) return mockBiasChartData;
  try {
    const { data } = await client.get<BiasChartData>('/compliance/bias');
    return data;
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockBiasChartData;
  }
}

export async function getComplianceWorkbenchData(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  try {
    const { data } = await client.get<ComplianceSummary>('/compliance/summary');
    return data;
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockCompliance;
  }
}

export async function getExecutiveDashboard(): Promise<ExecutiveDashboardData> {
  if (USE_MOCK) return mockExecutiveData;
  try {
    const { data } = await client.get<ExecutiveDashboardData>('/dashboard/executive');
    return data;
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockExecutiveData;
  }
}

export async function getBrokerSubmissions(): Promise<BrokerSubmission[]> {
  if (USE_MOCK) return mockBrokerSubmissions;
  try {
    const { data } = await client.get('/broker/submissions');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockBrokerSubmissions;
  }
}

export async function getBrokerPolicies(): Promise<BrokerPolicy[]> {
  if (USE_MOCK) return mockBrokerPolicies;
  try {
    const { data } = await client.get('/broker/policies');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockBrokerPolicies;
  }
}

export async function getBrokerClaims(): Promise<BrokerClaim[]> {
  if (USE_MOCK) return mockBrokerClaims;
  try {
    const { data } = await client.get('/broker/claims');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockBrokerClaims;
  }
}
