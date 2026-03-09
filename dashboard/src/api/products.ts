import client from './client';
import type { Product } from '../types';
import { mockProducts } from '../data/mock';

const USE_MOCK = true;

export async function getProducts(): Promise<Product[]> {
  if (USE_MOCK) return mockProducts;
  const { data } = await client.get<Product[]>('/products');
  return data;
}
