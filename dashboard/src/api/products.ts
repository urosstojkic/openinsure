import client from './client';
import { mockProducts } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

/* ── Types matching the enhanced backend models ── */

export interface CoverageDefinition {
  name: string;
  description: string;
  default_limit: number;
  max_limit: number;
  default_deductible: number;
  is_optional: boolean;
}

export interface RatingFactorEntry {
  key: string;
  multiplier: number;
  description: string;
}

export interface RatingFactorTable {
  name: string;
  description: string;
  entries: RatingFactorEntry[];
}

export interface AppetiteRule {
  name: string;
  field: string;
  operator: string;
  value: unknown;
  description: string;
}

export interface AuthorityLimit {
  max_auto_bind_premium: number;
  max_auto_bind_limit: number;
  requires_senior_review_above: number;
  requires_cuo_review_above: number;
}

export interface VersionInfo {
  version: string;
  created_at: string;
  created_by: string;
  change_summary: string;
}

export interface ProductDetail {
  id: string;
  name: string;
  product_line: string;
  description: string;
  version: string;
  status: 'draft' | 'active' | 'retired' | 'sunset';
  coverages: CoverageDefinition[];
  rating_rules: Record<string, unknown>;
  rating_factor_tables: RatingFactorTable[];
  underwriting_rules: Record<string, unknown>;
  appetite_rules: AppetiteRule[];
  authority_limits: AuthorityLimit | null;
  territories: string[];
  effective_date: string | null;
  expiration_date: string | null;
  forms: string[];
  metadata: Record<string, unknown>;
  version_history: VersionInfo[];
  created_at: string;
  updated_at: string;
}

export interface ProductPerformance {
  product_id: string;
  product_name: string;
  policies_in_force: number;
  total_gwp: number;
  loss_ratio: number;
  bind_rate: number;
  avg_premium: number;
  submissions_count: number;
  bound_count: number;
  declined_count: number;
  premium_trend: { month: string; premium: number }[];
}

/* ── API functions ── */

export async function getProducts(): Promise<ProductDetail[]> {
  if (USE_MOCK) return mockProducts as unknown as ProductDetail[];
  try {
    const { data } = await client.get('/products');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockProducts as unknown as ProductDetail[];
  }
}

export async function getProduct(id: string): Promise<ProductDetail> {
  const { data } = await client.get(`/products/${id}`);
  return data;
}

export async function createProduct(body: Partial<ProductDetail>): Promise<ProductDetail> {
  const { data } = await client.post('/products', body);
  return data;
}

export async function updateProduct(id: string, body: Partial<ProductDetail>): Promise<ProductDetail> {
  const { data } = await client.put(`/products/${id}`, body);
  return data;
}

export async function publishProduct(id: string, changeSummary = ''): Promise<ProductDetail> {
  const { data } = await client.post(`/products/${id}/publish`, { change_summary: changeSummary });
  return data;
}

export async function createProductVersion(id: string, changeSummary = ''): Promise<ProductDetail> {
  const { data } = await client.post(`/products/${id}/versions`, { change_summary: changeSummary });
  return data;
}

export async function getProductPerformance(id: string): Promise<ProductPerformance> {
  const { data } = await client.get(`/products/${id}/performance`);
  return data;
}
