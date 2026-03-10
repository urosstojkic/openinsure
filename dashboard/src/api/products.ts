import client from './client';
import type { Product } from '../types';
import { mockProducts } from '../data/mock';

const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false';

export async function getProducts(): Promise<Product[]> {
  if (USE_MOCK) return mockProducts;
  const { data } = await client.get('/products');
  return Array.isArray(data) ? data : (data.items || []);
}
