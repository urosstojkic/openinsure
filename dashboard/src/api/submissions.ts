import client from './client';
import type { Submission } from '../types';
import { mockSubmissions } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getSubmissions(): Promise<Submission[]> {
  if (USE_MOCK) return mockSubmissions;
  const { data } = await client.get('/submissions');
  return Array.isArray(data) ? data : (data.items || []);
}

export async function getSubmission(id: string): Promise<Submission | undefined> {
  if (USE_MOCK) return mockSubmissions.find((s) => s.id === id);
  const { data } = await client.get<Submission>(`/submissions/${id}`);
  return data;
}

export async function createSubmission(payload: Record<string, unknown>): Promise<Submission> {
  const { data } = await client.post<Submission>('/submissions', payload);
  return data;
}
