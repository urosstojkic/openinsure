import client from './client';

export async function getGuidelines(lob: string) {
  const { data } = await client.get(`/knowledge/guidelines/${lob}`);
  return data;
}

export async function getRatingFactors(lob: string) {
  const { data } = await client.get(`/knowledge/rating-factors/${lob}`);
  return data;
}

export async function getCoverageOptions(lob: string) {
  const { data } = await client.get(`/knowledge/coverage-options/${lob}`);
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

export async function getClaimsPrecedentsByType(claimType: string) {
  const { data } = await client.get(`/knowledge/claims-precedents/${claimType}`);
  return data;
}

export async function getComplianceRules() {
  const { data } = await client.get('/knowledge/compliance-rules');
  return data;
}

export async function getComplianceRulesByFramework(framework: string) {
  const { data } = await client.get(`/knowledge/compliance-rules/${framework}`);
  return data;
}

export async function updateGuidelines(lob: string, data: Record<string, unknown>) {
  const { data: result } = await client.put(`/knowledge/guidelines/${lob}`, data);
  return result;
}

export async function searchKnowledge(query: string) {
  const { data } = await client.get('/knowledge/search', { params: { q: query } });
  return data;
}
