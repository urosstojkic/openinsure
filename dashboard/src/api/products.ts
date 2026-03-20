import client from './client';
import type { Product } from '../types';
import { mockProducts } from '../data/mock';

const USE_MOCK = typeof window !== 'undefined' && localStorage.getItem('openinsure_mock') === 'true';

export async function getProducts(): Promise<Product[]> {
  if (USE_MOCK) return mockProducts;
  try {
    const { data } = await client.get('/products');
    return Array.isArray(data) ? data : (data.items || []);
  } catch (error) {
    console.warn('[API] Falling back to demo data:', error);
    return mockProducts;
  }
}
