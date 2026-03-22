import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw, Clock, AlertCircle, CheckCircle2,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton } from '../components/Skeleton';
import {
  getUpcomingRenewals,
  processRenewal,
  type UpcomingRenewals,
  type RenewalCandidate,
} from '../api/renewals';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const urgencyBadge = (days: number) => {
  if (days <= 0) return <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">Expired</span>;
  if (days <= 30) return <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">≤30 days</span>;
  if (days <= 60) return <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">≤60 days</span>;
  if (days <= 90) return <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">≤90 days</span>;
  return <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{days} days</span>;
};

const RenewalsPage: React.FC = () => {
  const [filter, setFilter] = useState<'all' | '30' | '60' | '90'>('all');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<UpcomingRenewals>({
    queryKey: ['renewals-upcoming'],
    queryFn: () => getUpcomingRenewals(365),
  });

  const renewMutation = useMutation({
    mutationFn: (policyId: string) => processRenewal(policyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['renewals-upcoming'] }),
  });

  if (isLoading || !data) {
    return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /></div>;
  }

  const renewals = data.renewals;
  const filtered = renewals.filter((r: RenewalCandidate) => {
    if (filter === '30') return r.days_to_expiry <= 30;
    if (filter === '60') return r.days_to_expiry <= 60;
    if (filter === '90') return r.days_to_expiry <= 90;
    return true;
  });

  const totalPremium = renewals.reduce((s: number, r: RenewalCandidate) => s + r.premium, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Renewal Workflow</h1>
        <p className="text-sm text-slate-500 mt-0.5">Policies approaching renewal — identify, quote, and process</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Candidates" value={data.total} icon={<RefreshCw size={20} />} subtitle={`${money(totalPremium)} premium at risk`} />
        <StatCard title="Within 30 Days" value={data.within_30_days} icon={<AlertCircle size={20} />} subtitle="Urgent attention" />
        <StatCard title="Within 60 Days" value={data.within_60_days} icon={<Clock size={20} />} subtitle="Action needed" />
        <StatCard title="Within 90 Days" value={data.within_90_days} icon={<CheckCircle2 size={20} />} subtitle="Planning window" />
      </div>

      {/* Filter buttons */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {([['all', 'All'], ['30', '≤30 Days'], ['60', '≤60 Days'], ['90', '≤90 Days']] as const).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setFilter(key as typeof filter)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
              filter === key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Renewals Table */}
      <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-4 py-3">Policy #</th>
              <th className="px-4 py-3">Policyholder</th>
              <th className="px-4 py-3">Expiration</th>
              <th className="px-4 py-3">Urgency</th>
              <th className="px-4 py-3">Current Premium</th>
              <th className="px-4 py-3">Projected Renewal</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map((r: RenewalCandidate) => (
              <tr key={r.id} className="hover:bg-slate-50/50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs font-medium text-slate-900">{r.policy_number}</td>
                <td className="px-4 py-3 font-medium text-slate-900">{r.policyholder_name}</td>
                <td className="px-4 py-3 text-slate-600">{r.expiration_date}</td>
                <td className="px-4 py-3">{urgencyBadge(r.days_to_expiry)}</td>
                <td className="px-4 py-3 font-mono text-xs">{money(r.premium)}</td>
                <td className="px-4 py-3 font-mono text-xs text-indigo-600">{money(Math.round(r.premium * 1.05))}</td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => renewMutation.mutate(r.id)}
                    disabled={renewMutation.isPending}
                    className="rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition disabled:opacity-50"
                  >
                    {renewMutation.isPending ? 'Processing…' : 'Process Renewal'}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  No renewals in this window
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default RenewalsPage;
