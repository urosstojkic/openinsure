import client from './client';

// ---------------------------------------------------------------------------
// Types matching the backend finance API response models
// ---------------------------------------------------------------------------

export interface FinancialSummary {
  premium_written: number;
  premium_earned: number;
  premium_unearned: number;
  claims_paid: number;
  claims_reserved: number;
  claims_incurred: number;
  loss_ratio: number;
  expense_ratio: number;
  combined_ratio: number;
  investment_income: number;
  operating_income: number;
}

export interface CashFlowMonth {
  month: string;
  collections: number;
  disbursements: number;
  net: number;
}

export interface CashFlowResponse {
  months: CashFlowMonth[];
  total_collections: number;
  total_disbursements: number;
  net_cash_flow: number;
}

export interface CommissionEntry {
  broker: string;
  policies: number;
  premium: number;
  commission_rate: number;
  commission_amount: number;
  status: string;
}

export interface CommissionSummary {
  total_commissions: number;
  paid: number;
  pending: number;
  overdue: number;
  entries: CommissionEntry[];
}

export interface ReconciliationItem {
  item: string;
  expected: number;
  actual: number;
  variance: number;
  status: string;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export async function getFinancialSummary(): Promise<FinancialSummary> {
  const { data } = await client.get<FinancialSummary>('/finance/summary');
  return data;
}

export async function getCashFlow(): Promise<CashFlowResponse> {
  const { data } = await client.get<CashFlowResponse>('/finance/cashflow');
  return data;
}

export async function getCommissions(): Promise<CommissionSummary> {
  const { data } = await client.get<CommissionSummary>('/finance/commissions');
  return data;
}

export async function getReconciliation(): Promise<ReconciliationItem[]> {
  const { data } = await client.get<ReconciliationItem[]>('/finance/reconciliation');
  return data;
}
