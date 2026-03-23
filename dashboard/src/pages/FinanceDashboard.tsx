import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  DollarSign, TrendingDown, TrendingUp, CreditCard, PiggyBank, Receipt, FileText,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import {
  getFinancialSummary,
  getCashFlow,
  getCommissions,
  getReconciliation,
  type FinancialSummary,
  type CashFlowResponse,
  type CommissionSummary,
  type ReconciliationItem,
} from '../api/finance';
import { getBillingAccount, type BillingAccount, type Invoice } from '../api/billing';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

const statusBadge = (s: string) => {
  const colors: Record<string, string> = {
    paid: 'bg-green-100 text-green-700',
    pending: 'bg-blue-100 text-blue-700',
    overdue: 'bg-red-100 text-red-700',
    matched: 'bg-green-100 text-green-700',
    warning: 'bg-amber-100 text-amber-700',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors[s] ?? 'bg-slate-100 text-slate-600'}`}>
      {s}
    </span>
  );
};

const FinanceDashboard: React.FC = () => {
  const { data: summary, isLoading: summaryLoading } = useQuery<FinancialSummary>({
    queryKey: ['finance-summary'],
    queryFn: getFinancialSummary,
  });

  const { data: cashFlow, isLoading: cashFlowLoading } = useQuery<CashFlowResponse>({
    queryKey: ['finance-cashflow'],
    queryFn: getCashFlow,
  });

  const { data: commissionData, isLoading: commissionsLoading } = useQuery<CommissionSummary>({
    queryKey: ['finance-commissions'],
    queryFn: getCommissions,
  });

  const { data: reconciliationData, isLoading: reconLoading } = useQuery<ReconciliationItem[]>({
    queryKey: ['finance-reconciliation'],
    queryFn: getReconciliation,
  });

  const isLoading = summaryLoading || cashFlowLoading || commissionsLoading || reconLoading;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-7 w-48 rounded-lg bg-slate-200 animate-pulse" />
          <div className="mt-2 h-4 w-96 rounded bg-slate-100 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
        <ChartSkeleton />
      </div>
    );
  }

  const premiumCards = [
    { title: 'Premium Written', value: summary?.premium_written ?? 0, icon: <DollarSign size={20} /> },
    { title: 'Premium Earned', value: summary?.premium_earned ?? 0, icon: <TrendingUp size={20} /> },
    { title: 'Premium Unearned', value: summary?.premium_unearned ?? 0, icon: <PiggyBank size={20} /> },
  ];

  const claimsCards = [
    { title: 'Claims Paid', value: summary?.claims_paid ?? 0, icon: <CreditCard size={20} /> },
    { title: 'Claims Reserved', value: summary?.claims_reserved ?? 0, icon: <Receipt size={20} /> },
    { title: 'Claims Incurred', value: summary?.claims_incurred ?? 0, icon: <TrendingDown size={20} /> },
  ];

  const cashFlowChartData = (cashFlow?.months ?? []).map(m => ({
    month: m.month.replace(/^\d{4}-/, ''),
    collections: m.collections,
    disbursements: m.disbursements,
  }));

  const commissions = commissionData?.entries ?? [];
  const reconciliation = reconciliationData ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Finance Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Financial overview — premium, claims, cash flow & commissions
          {summary ? ` · Loss ratio ${pct(summary.loss_ratio)} · Combined ratio ${pct(summary.combined_ratio)}` : ''}
        </p>
      </div>

      {/* Premium Cards */}
      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Premium</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {premiumCards.map(c => (
            <StatCard key={c.title} title={c.title} value={money(c.value)} icon={c.icon} />
          ))}
        </div>
      </div>

      {/* Claims Cards */}
      <div>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Claims</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {claimsCards.map(c => (
            <StatCard key={c.title} title={c.title} value={money(c.value)} icon={c.icon} />
          ))}
        </div>
      </div>

      {/* Cash Flow Chart */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">
          Cash Flow (12 Months)
          {cashFlow ? ` · Net ${money(cashFlow.net_cash_flow)}` : ''}
        </h2>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={cashFlowChartData}>
            <defs>
              <linearGradient id="gradCollections" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22c55e" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradDisbursements" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#ef4444" stopOpacity={0.15} />
                <stop offset="100%" stopColor="#ef4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} axisLine={false} tickLine={false} />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
                    <p className="text-[11px] font-medium text-slate-400">{label}</p>
                    {payload.map((p: any) => (
                      <p key={p.dataKey} className="text-sm font-bold text-slate-800">{p.name}: {money(Number(p.value))}</p>
                    ))}
                  </div>
                );
              }}
            />
            <Area type="monotone" dataKey="collections" stroke="#22c55e" strokeWidth={2} fill="url(#gradCollections)" name="Collections" />
            <Area type="monotone" dataKey="disbursements" stroke="#ef4444" strokeWidth={2} fill="url(#gradDisbursements)" name="Disbursements" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Commission Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">
            Commissions
            {commissionData ? ` · Total ${money(commissionData.total_commissions)}` : ''}
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-4 py-3">Broker</th>
              <th className="px-4 py-3">Policies</th>
              <th className="px-4 py-3">Premium</th>
              <th className="px-4 py-3">Rate</th>
              <th className="px-4 py-3">Commission</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {commissions.map(c => (
              <tr key={c.broker} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-900">{c.broker}</td>
                <td className="px-4 py-3 text-slate-600">{c.policies}</td>
                <td className="px-4 py-3 font-mono text-xs">{money(c.premium)}</td>
                <td className="px-4 py-3 text-slate-600">{pct(c.commission_rate)}</td>
                <td className="px-4 py-3 font-mono text-xs font-semibold">{money(c.commission_amount)}</td>
                <td className="px-4 py-3">{statusBadge(c.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Reconciliation Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-800">Reconciliation Status</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-4 py-3">Item</th>
              <th className="px-4 py-3">Expected</th>
              <th className="px-4 py-3">Actual</th>
              <th className="px-4 py-3">Variance</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {reconciliation.map(r => (
              <tr key={r.item} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-medium text-slate-900">{r.item}</td>
                <td className="px-4 py-3 font-mono text-xs">{money(r.expected)}</td>
                <td className="px-4 py-3 font-mono text-xs">{money(r.actual)}</td>
                <td className="px-4 py-3 font-mono text-xs">
                  <span className={r.variance < 0 ? 'text-red-600 font-semibold' : 'text-green-600'}>
                    {r.variance !== 0 ? money(r.variance) : '—'}
                  </span>
                </td>
                <td className="px-4 py-3">{statusBadge(r.status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Billing Account Lookup */}
      <BillingLookup />
    </div>
  );
};

/* ---- Billing Account Lookup Panel ---- */

function BillingLookup() {
  const [accountId, setAccountId] = useState('');
  const [queryId, setQueryId] = useState<string | null>(null);

  const { data: account, isLoading, isError } = useQuery<BillingAccount>({
    queryKey: ['billing-account', queryId],
    queryFn: () => getBillingAccount(queryId!),
    enabled: !!queryId,
  });

  const money = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

  const invoiceStatusColor: Record<string, string> = {
    issued: 'bg-blue-100 text-blue-700',
    paid: 'bg-green-100 text-green-700',
    past_due: 'bg-red-100 text-red-700',
    void: 'bg-slate-100 text-slate-500',
    draft: 'bg-amber-100 text-amber-700',
  };

  return (
    <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
      <div className="px-5 py-4 border-b border-slate-100">
        <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <FileText size={16} /> Billing Account Lookup
        </h2>
      </div>
      <div className="px-5 py-4">
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={accountId}
            onChange={e => setAccountId(e.target.value)}
            placeholder="Enter billing account ID…"
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <button
            onClick={() => setQueryId(accountId)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
          >
            Lookup
          </button>
        </div>

        {isLoading && <p className="text-sm text-slate-400">Loading…</p>}
        {isError && <p className="text-sm text-red-500">Account not found or API unavailable.</p>}

        {account && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <div>
                <p className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Status</p>
                <p className="mt-0.5 font-semibold text-slate-800 capitalize">{account.status.replace('_', ' ')}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Total Premium</p>
                <p className="mt-0.5 font-semibold text-slate-800">{money(account.total_premium)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Total Paid</p>
                <p className="mt-0.5 font-semibold text-green-700">{money(account.total_paid)}</p>
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">Balance Due</p>
                <p className={`mt-0.5 font-semibold ${account.balance_due > 0 ? 'text-red-600' : 'text-green-700'}`}>{money(account.balance_due)}</p>
              </div>
            </div>

            {account.invoices.length > 0 && (
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Invoices</h3>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50/80 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Description</th>
                      <th className="px-3 py-2">Amount</th>
                      <th className="px-3 py-2">Due Date</th>
                      <th className="px-3 py-2">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {(account.invoices as Invoice[]).map((inv) => (
                      <tr key={inv.invoice_id} className="hover:bg-slate-50/50">
                        <td className="px-3 py-2 text-slate-800">{inv.description}</td>
                        <td className="px-3 py-2 font-mono text-xs">{money(inv.amount)}</td>
                        <td className="px-3 py-2 text-slate-600">{inv.due_date}</td>
                        <td className="px-3 py-2">
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${invoiceStatusColor[inv.status] ?? 'bg-slate-100 text-slate-600'}`}>
                            {inv.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default FinanceDashboard;
