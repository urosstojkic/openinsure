import client from './client';

export async function getGuidelines(lob: string) {
  const { data } = await client.get(`/knowledge/guidelines/${lob}`);
  return data;
}

export async function getProducts() {
  const { data } = await client.get('/knowledge/products');
  return data;
}

export async function getClaimsPrecedents() {
  const { data } = await client.get('/knowledge/claims-precedents');
  return data;
}

export async function getComplianceRules() {
  const { data } = await client.get('/knowledge/compliance-rules');
  return data;
}
