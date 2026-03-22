import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getReinsuranceDashboard } from '../api/reinsurance';
import { StatCardSkeleton } from '../components/Skeleton';
import type { ReinsuranceTreaty } from '../types';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${Math.round(n)}%`;

const treatyTypeLabels: Record<string, string> = {
  quota_share: 'Quota Share',
  excess_of_loss: 'Excess of Loss',
  surplus: 'Surplus',
  facultative: 'Facultative',
};

const statusColors: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  expired: 'bg-slate-100 text-slate-500',
  pending: 'bg-amber-100 text-amber-700',
};

const recoveryStatusColors: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700',
  billed: 'bg-blue-100 text-blue-700',
  collected: 'bg-emerald-100 text-emerald-700',
};

function CapacityBar({ treaty }: { treaty: ReinsuranceTreaty }) {
  const usedPct = treaty.capacity_total > 0
    ? Math.min(100, (treaty.capacity_used / treaty.capacity_total) * 100)
    : 0;
  const barColor = usedPct > 85 ? 'bg-red-500' : usedPct > 60 ? 'bg-amber-500' : 'bg-indigo-500';

  return (
    <div className="w-full">
      <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
        <span>{money(treaty.capacity_used)} used</span>
        <span>{pct(usedPct)}</span>
      </div>
      <div className="h-2.5 w-full rounded-full bg-slate-100">
        <div className={`h-2.5 rounded-full transition-all ${barColor}`} style={{ width: `${usedPct}%` }} />
      </div>
      <div className="mt-0.5 text-right text-[10px] text-slate-400">
        {money(treaty.capacity_total)} total
      </div>
    </div>
  );
}

const ReinsuranceDashboard: React.FC = () => {
  const { data, isLoading } = useQuery({ queryKey: ['reinsurance'], queryFn: getReinsuranceDashboard });

  if (isLoading || !data) {
    return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /></div>;
  }

  const { treaties, cessions, recoveries } = data;
  const activeTreaties = treaties.filter(t => t.status === 'active');

  const totalCapacity = activeTreaties.reduce((s, t) => s + t.capacity_total, 0);
  const totalUsed = activeTreaties.reduce((s, t) => s + t.capacity_used, 0);
  const totalCeded = cessions.reduce((s, c) => s + c.ceded_premium, 0);
  const totalRecoveries = recoveries.reduce((s, r) => s + r.recovery_amount, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Reinsurance Dashboard</h1>
        <p className="text-sm text-slate-500 mt-0.5">Treaty management, cessions & recovery tracking — Carrier view</p>
      </div>

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Treaties</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{activeTreaties.length}</p>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Total Capacity</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">{money(totalCapacity)}</p>
          <p className="text-xs text-slate-400">{pct(totalCapacity > 0 ? (totalUsed / totalCapacity) * 100 : 0)} utilized</p>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Ceded Premium (YTD)</p>
          <p className="mt-1 text-2xl font-bold text-indigo-600">{money(totalCeded)}</p>
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recoveries (YTD)</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{money(totalRecoveries)}</p>
        </div>
      </div>

      {/* ── Treaty Summary Table ── */}
      <div className="rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
        <div className="border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-800">Treaty Summary</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                <th className="px-5 py-3">Treaty #</th>
                <th className="px-5 py-3">Type</th>
                <th className="px-5 py-3">Reinsurer</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Capacity</th>
                <th className="px-5 py-3">Used %</th>
                <th className="px-5 py-3">Expiry</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {treaties.map(t => {
                const usedPct = t.capacity_total > 0 ? (t.capacity_used / t.capacity_total) * 100 : 0;
                return (
                  <tr key={t.id} className="transition-colors hover:bg-slate-50/50">
                    <td className="px-5 py-3 font-mono text-xs font-medium text-indigo-600">{t.treaty_number}</td>
                    <td className="px-5 py-3">{treatyTypeLabels[t.treaty_type] ?? t.treaty_type}</td>
                    <td className="px-5 py-3 font-medium text-slate-700">{t.reinsurer_name}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${statusColors[t.status] ?? ''}`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">{money(t.capacity_total)}</td>
                    <td className="px-5 py-3">
                      <span className={`font-medium ${usedPct > 85 ? 'text-red-600' : usedPct > 60 ? 'text-amber-600' : 'text-slate-700'}`}>
                        {pct(usedPct)}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-500">{t.expiration_date}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Capacity Utilization Bars ── */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">Capacity Utilization</h2>
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {activeTreaties.map(t => (
            <div key={t.id} className="rounded-lg border border-slate-100 p-4">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-sm font-medium text-slate-700">{t.treaty_number}</span>
                <span className="text-xs text-slate-400">{t.reinsurer_name}</span>
              </div>
              <CapacityBar treaty={t} />
            </div>
          ))}
        </div>
      </div>

      {/* ── Bottom: Cessions + Recoveries side by side ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Cessions */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-800">Recent Cessions</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <th className="px-5 py-3">Policy</th>
                  <th className="px-5 py-3">Ceded Premium</th>
                  <th className="px-5 py-3">Ceded Limit</th>
                  <th className="px-5 py-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cessions.map(c => (
                  <tr key={c.id} className="transition-colors hover:bg-slate-50/50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-600">{c.policy_number}</td>
                    <td className="px-5 py-3 font-medium text-slate-700">{money(c.ceded_premium)}</td>
                    <td className="px-5 py-3">{money(c.ceded_limit)}</td>
                    <td className="px-5 py-3 text-slate-500">{c.cession_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recovery Tracking */}
        <div className="rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
          <div className="border-b border-slate-200 px-5 py-4">
            <h2 className="text-sm font-semibold text-slate-800">Recovery Tracking</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  <th className="px-5 py-3">Claim</th>
                  <th className="px-5 py-3">Amount</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {recoveries.map(r => (
                  <tr key={r.id} className="transition-colors hover:bg-slate-50/50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-600">{r.claim_number}</td>
                    <td className="px-5 py-3 font-medium text-slate-700">{money(r.recovery_amount)}</td>
                    <td className="px-5 py-3">
                      <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${recoveryStatusColors[r.status] ?? ''}`}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-slate-500">{r.recovery_date}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReinsuranceDashboard;
