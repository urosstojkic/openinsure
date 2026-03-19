import client from './client';

export interface RenewalCandidate {
  id: string;
  policy_number: string;
  policyholder_name: string;
  status: string;
  effective_date: string;
  expiration_date: string;
  premium: number;
  days_to_expiry: number;
}

export interface UpcomingRenewals {
  total: number;
  within_30_days: number;
  within_60_days: number;
  within_90_days: number;
  renewals: RenewalCandidate[];
}

export interface RenewalRecord {
  id: string;
  original_policy_id: string;
  renewal_policy_id: string | null;
  status: string;
  expiring_premium: number;
  renewal_premium: number;
  rate_change_pct: number;
  recommendation: string;
  conditions: string[];
  generated_by: string;
  created_at: string;
  updated_at: string;
}

export async function getUpcomingRenewals(days = 90): Promise<UpcomingRenewals> {
  const { data } = await client.get<UpcomingRenewals>('/renewals/upcoming', { params: { days } });
  return data;
}

export async function generateRenewalTerms(policyId: string): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/renewals/${policyId}/generate`);
  return data;
}

export async function processRenewal(policyId: string): Promise<Record<string, unknown>> {
  const { data } = await client.post(`/renewals/${policyId}/process`);
  return data;
}

export async function getRenewalRecords(): Promise<RenewalRecord[]> {
  const { data } = await client.get('/renewals/records');
  return data.items ?? [];
}
