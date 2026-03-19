import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  DollarSign, TrendingDown, TrendingUp, CreditCard, PiggyBank, Receipt,
} from 'lucide-react';
import StatCard from '../components/StatCard';
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
    return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;
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
        <h1 className="text-2xl font-bold text-slate-900">Finance Dashboard</h1>
        <p className="text-sm text-slate-500">
          Financial overview — premium, claims, cash flow & commissions
          {summary ? ` · Loss ratio ${pct(summary.loss_ratio)} · Combined ratio ${pct(summary.combined_ratio)}` : ''}
        </p>
      </div>

      {/* Premium Cards */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Premium</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {premiumCards.map(c => (
            <StatCard key={c.title} title={c.title} value={money(c.value)} icon={c.icon} />
          ))}
        </div>
      </div>

      {/* Claims Cards */}
      <div>
        <h2 className="mb-3 text-sm font-semibold text-slate-700">Claims</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {claimsCards.map(c => (
            <StatCard key={c.title} title={c.title} value={money(c.value)} icon={c.icon} />
          ))}
        </div>
      </div>

      {/* Cash Flow Chart */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">
          Cash Flow (12 Months)
          {cashFlow ? ` · Net ${money(cashFlow.net_cash_flow)}` : ''}
        </h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={cashFlowChartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`} />
            <Tooltip formatter={(v) => money(Number(v))} />
            <Line type="monotone" dataKey="collections" stroke="#22c55e" strokeWidth={2} name="Collections" dot={{ r: 3 }} />
            <Line type="monotone" dataKey="disbursements" stroke="#ef4444" strokeWidth={2} name="Disbursements" dot={{ r: 3 }} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Commission Table */}
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">
            Commissions
            {commissionData ? ` · Total ${money(commissionData.total_commissions)}` : ''}
          </h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
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
              <tr key={c.broker} className="hover:bg-slate-50 transition">
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
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-100">
          <h2 className="text-sm font-semibold text-slate-700">Reconciliation Status</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
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
              <tr key={r.item} className="hover:bg-slate-50 transition">
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
    </div>
  );
};

export default FinanceDashboard;
