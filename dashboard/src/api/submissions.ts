import client from './client';
import type { Submission } from '../types';
import { mockSubmissions } from '../data/mock';

const USE_MOCK = true;

export async function getSubmissions(): Promise<Submission[]> {
  if (USE_MOCK) return mockSubmissions;
  const { data } = await client.get<Submission[]>('/submissions');
  return data;
}

export async function getSubmission(id: string): Promise<Submission | undefined> {
  if (USE_MOCK) return mockSubmissions.find((s) => s.id === id);
  const { data } = await client.get<Submission>(`/submissions/${id}`);
  return data;
}

export async function createSubmission(payload: Partial<Submission>): Promise<Submission> {
  const { data } = await client.post<Submission>('/submissions', payload);
  return data;
}
