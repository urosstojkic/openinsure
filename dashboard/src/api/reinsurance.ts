import client from './client';
import type { ReinsuranceDashboardData } from '../types';
import { mockReinsuranceData } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getReinsuranceDashboard(): Promise<ReinsuranceDashboardData> {
  if (USE_MOCK) return mockReinsuranceData;
  const [treaties, cessions, recoveries] = await Promise.all([
    client.get('/reinsurance/treaties'),
    client.get('/reinsurance/cessions'),
    client.get('/reinsurance/recoveries'),
  ]);
  return {
    treaties: Array.isArray(treaties.data) ? treaties.data : (treaties.data.items || []),
    cessions: Array.isArray(cessions.data) ? cessions.data : (cessions.data.items || []),
    recoveries: Array.isArray(recoveries.data) ? recoveries.data : (recoveries.data.items || []),
  };
}
