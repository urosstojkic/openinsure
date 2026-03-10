import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import {
  DollarSign, TrendingDown, TrendingUp, CreditCard, PiggyBank, Receipt,
} from 'lucide-react';
import StatCard from '../components/StatCard';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

// ── Mock data ──

const premiumCards = [
  { title: 'Premium Written', value: 24_500_000, icon: <DollarSign size={20} /> },
  { title: 'Premium Earned', value: 18_200_000, icon: <TrendingUp size={20} /> },
  { title: 'Premium Unearned', value: 6_300_000, icon: <PiggyBank size={20} /> },
];

const claimsCards = [
  { title: 'Claims Paid', value: 8_100_000, icon: <CreditCard size={20} /> },
  { title: 'Claims Reserved', value: 4_600_000, icon: <Receipt size={20} /> },
  { title: 'Claims Incurred', value: 12_700_000, icon: <TrendingDown size={20} /> },
];

const cashFlowData = [
  { month: 'Jul', collections: 2_100_000, disbursements: 1_500_000 },
  { month: 'Aug', collections: 2_300_000, disbursements: 1_700_000 },
  { month: 'Sep', collections: 1_900_000, disbursements: 1_800_000 },
  { month: 'Oct', collections: 2_400_000, disbursements: 1_600_000 },
  { month: 'Nov', collections: 2_200_000, disbursements: 2_000_000 },
  { month: 'Dec', collections: 2_600_000, disbursements: 1_900_000 },
  { month: 'Jan', collections: 2_000_000, disbursements: 1_400_000 },
  { month: 'Feb', collections: 2_100_000, disbursements: 1_600_000 },
  { month: 'Mar', collections: 2_500_000, disbursements: 1_800_000 },
  { month: 'Apr', collections: 2_300_000, disbursements: 2_100_000 },
  { month: 'May', collections: 2_700_000, disbursements: 1_700_000 },
  { month: 'Jun', collections: 2_400_000, disbursements: 1_900_000 },
];

const commissions = [
  { broker: 'Marsh & Co', policies: 42, premium: 4_200_000, rate: 0.12, amount: 504_000, status: 'paid' },
  { broker: 'Aon Risk Solutions', policies: 35, premium: 3_600_000, rate: 0.10, amount: 360_000, status: 'paid' },
  { broker: 'Willis Towers Watson', policies: 28, premium: 2_900_000, rate: 0.11, amount: 319_000, status: 'pending' },
  { broker: 'Brown & Brown', policies: 18, premium: 1_800_000, rate: 0.10, amount: 180_000, status: 'pending' },
  { broker: 'Gallagher', policies: 22, premium: 2_200_000, rate: 0.09, amount: 198_000, status: 'overdue' },
];

const reconciliation = [
  { item: 'Premium receivables', expected: 6_300_000, actual: 6_100_000, variance: -200_000, status: 'warning' },
  { item: 'Claims payables', expected: 4_600_000, actual: 4_600_000, variance: 0, status: 'matched' },
  { item: 'Commission payables', expected: 1_561_000, actual: 1_561_000, variance: 0, status: 'matched' },
  { item: 'Reinsurance recoverables', expected: 2_100_000, actual: 1_950_000, variance: -150_000, status: 'warning' },
  { item: 'Tax reserves', expected: 780_000, actual: 780_000, variance: 0, status: 'matched' },
];

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
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Finance Dashboard</h1>
        <p className="text-sm text-slate-500">Financial overview — premium, claims, cash flow & commissions</p>
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
        <h2 className="mb-4 text-sm font-semibold text-slate-700">Cash Flow (12 Months)</h2>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={cashFlowData}>
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
          <h2 className="text-sm font-semibold text-slate-700">Commissions</h2>
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
                <td className="px-4 py-3 text-slate-600">{pct(c.rate)}</td>
                <td className="px-4 py-3 font-mono text-xs font-semibold">{money(c.amount)}</td>
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
