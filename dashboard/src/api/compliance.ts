import client from './client';
import type { AgentDecision, ComplianceSummary } from '../types';
import { mockDecisions, mockCompliance } from '../data/mock';

const USE_MOCK = true;

export async function getDecisions(): Promise<AgentDecision[]> {
  if (USE_MOCK) return mockDecisions;
  const { data } = await client.get<AgentDecision[]>('/decisions');
  return data;
}

export async function getComplianceSummary(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  const { data } = await client.get<ComplianceSummary>('/compliance/summary');
  return data;
}
