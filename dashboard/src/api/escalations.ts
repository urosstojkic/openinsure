import client from './client';

export interface Escalation {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  requested_by: string;
  requested_role: string;
  amount: number;
  required_role: string;
  escalation_chain: string[];
  reason: string;
  context: Record<string, unknown>;
  status: string;
  created_at: string;
  resolved_by: string | null;
  resolved_at: string | null;
  resolution_reason: string | null;
}

export async function getEscalations(status?: string): Promise<Escalation[]> {
  const params = status ? { status } : {};
  const { data } = await client.get('/escalations', { params });
  return data.items ?? [];
}

export async function getEscalation(id: string): Promise<Escalation> {
  const { data } = await client.get(`/escalations/${id}`);
  return data;
}

export async function getEscalationCount(): Promise<number> {
  const { data } = await client.get('/escalations/count');
  return data.pending;
}

export async function approveEscalation(id: string, resolved_by: string, reason: string): Promise<Escalation> {
  const { data } = await client.post(`/escalations/${id}/approve`, { resolved_by, reason });
  return data;
}

export async function rejectEscalation(id: string, resolved_by: string, reason: string): Promise<Escalation> {
  const { data } = await client.post(`/escalations/${id}/reject`, { resolved_by, reason });
  return data;
}
