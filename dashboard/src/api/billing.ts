import client from './client';

// ---------------------------------------------------------------------------
// Types matching the backend billing API response models
// ---------------------------------------------------------------------------

export interface BillingAccount {
  id: string;
  policy_id: string;
  policyholder_name: string;
  status: 'active' | 'paid_in_full' | 'past_due' | 'cancelled';
  total_premium: number;
  total_paid: number;
  balance_due: number;
  installments: number;
  currency: string;
  billing_email: string | null;
  payments: Payment[];
  invoices: Invoice[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Payment {
  payment_id: string;
  amount: number;
  method: string;
  reference: string | null;
  notes: string | null;
  created_at: string;
}

export interface Invoice {
  invoice_id: string;
  account_id: string;
  amount: number;
  status: 'draft' | 'issued' | 'paid' | 'void' | 'past_due';
  due_date: string;
  description: string;
  line_items: Record<string, unknown>[];
  created_at: string;
}

export interface LedgerEntry {
  entry_id: string;
  account_id: string;
  entry_type: string;
  amount: number;
  balance_after: number;
  description: string;
  reference_id: string;
  created_at: string;
}

export interface LedgerResponse {
  account_id: string;
  entries: LedgerEntry[];
  total: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getBillingAccounts(): Promise<BillingAccount[]> {
  // The billing API doesn't have a list-all endpoint, so we return empty.
  // In production, this would be fetched from the backend.
  return [];
}

export async function getBillingAccount(id: string): Promise<BillingAccount> {
  const { data } = await client.get<BillingAccount>(`/billing/accounts/${id}`);
  return data;
}

export async function createBillingAccount(payload: {
  policy_id: string;
  policyholder_name: string;
  total_premium: number;
  installments?: number;
}): Promise<BillingAccount> {
  const { data } = await client.post<BillingAccount>('/billing/accounts', payload);
  return data;
}

export async function getInvoices(accountId: string): Promise<Invoice[]> {
  const { data } = await client.get<{ items: Invoice[] }>(`/billing/accounts/${accountId}/invoices`);
  return data.items;
}

export async function getLedger(accountId: string): Promise<LedgerResponse> {
  const { data } = await client.get<LedgerResponse>(`/billing/accounts/${accountId}/ledger`);
  return data;
}

export async function recordPayment(accountId: string, payload: {
  amount: number;
  method: string;
  reference?: string;
}): Promise<unknown> {
  const { data } = await client.post(`/billing/accounts/${accountId}/payments`, payload);
  return data;
}
