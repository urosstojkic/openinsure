import client from './client';
import type { AgentDecision, ComplianceSummary } from '../types';
import { mockDecisions, mockCompliance } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getDecisions(): Promise<AgentDecision[]> {
  if (USE_MOCK) return mockDecisions;
  try {
    const { data } = await client.get('/decisions');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockDecisions;
  }
}

export async function getComplianceSummary(): Promise<ComplianceSummary> {
  if (USE_MOCK) return mockCompliance;
  try {
    const { data } = await client.get<ComplianceSummary>('/compliance/summary');
    return data;
  } catch (error) {
    console.warn('API call failed, falling back to mock:', error);
    return mockCompliance;
  }
}
