import client from './client';

export interface MGAAuthority {
  mga_id: string;
  mga_name: string;
  status: string;
  effective_date: string | null;
  expiration_date: string | null;
  lines_of_business: string[];
  premium_authority: number;
  premium_written: number;
  claims_authority: number;
  loss_ratio: number;
  compliance_score: number;
  last_audit_date: string | null;
}

export interface MGABordereau {
  id: string;
  mga_id: string;
  period: string;
  premium_reported: number;
  claims_reported: number;
  loss_ratio: number;
  policy_count: number;
  claim_count: number;
  status: string;
  exceptions: string[];
}

export interface MGAPerformance {
  total_mgas: number;
  active_mgas: number;
  suspended_mgas: number;
  total_premium_written: number;
  total_premium_authority: number;
  average_loss_ratio: number;
  average_compliance_score: number;
  authorities: MGAAuthority[];
}

export async function getMGAAuthorities(status?: string): Promise<MGAAuthority[]> {
  const params = status ? { status } : {};
  const { data } = await client.get<MGAAuthority[]>('/mga/authorities', { params });
  return data;
}

export async function getMGAAuthority(mgaId: string): Promise<MGAAuthority> {
  const { data } = await client.get<MGAAuthority>(`/mga/authorities/${mgaId}`);
  return data;
}

export async function getMGABordereaux(mgaId?: string): Promise<MGABordereau[]> {
  const params = mgaId ? { mga_id: mgaId } : {};
  const { data } = await client.get<MGABordereau[]>('/mga/bordereaux', { params });
  return data;
}

export async function getMGAPerformance(): Promise<MGAPerformance> {
  const { data } = await client.get<MGAPerformance>('/mga/performance');
  return data;
}
