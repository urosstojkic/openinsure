import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  RefreshCw, Clock, AlertCircle, CheckCircle2, Timer, Play, Sparkles,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import { StatCardSkeleton } from '../components/Skeleton';
import {
  getUpcomingRenewals,
  processRenewal,
  getRenewalQueue,
  runRenewalScheduler,
  generateAITerms,
  type UpcomingRenewals,
  type RenewalCandidate,
  type RenewalQueueItem,
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

function CountdownTimer({ days }: { days: number }) {
  if (days <= 0) return <span className="text-red-600 font-bold text-lg">EXPIRED</span>;
  const displayDays = Math.floor(days);
  return (
    <div className="flex items-center gap-1.5">
      <Timer size={14} className={days <= 30 ? 'text-red-500' : days <= 60 ? 'text-amber-500' : 'text-blue-500'} />
      <span className={`text-lg font-bold tabular-nums ${days <= 30 ? 'text-red-600' : days <= 60 ? 'text-amber-600' : 'text-blue-600'}`}>
        {displayDays}
      </span>
      <span className="text-xs text-slate-400">days</span>
    </div>
  );
}

const RenewalsPage: React.FC = () => {
  const [filter, setFilter] = useState<'all' | '30' | '60' | '90'>('all');
  const [activeTab, setActiveTab] = useState<'upcoming' | 'queue'>('upcoming');
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<UpcomingRenewals>({
    queryKey: ['renewals-upcoming'],
    queryFn: () => getUpcomingRenewals(365),
  });

  const renewMutation = useMutation({
    mutationFn: (policyId: string) => processRenewal(policyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['renewals-upcoming'] }),
  });

  const { data: queueData = [], isLoading: queueLoading } = useQuery({
    queryKey: ['renewal-queue'],
    queryFn: () => getRenewalQueue(),
    enabled: activeTab === 'queue',
  });

  const schedulerMutation = useMutation({
    mutationFn: runRenewalScheduler,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['renewal-queue'] });
      queryClient.invalidateQueries({ queryKey: ['renewals-upcoming'] });
    },
  });

  const termsMutation = useMutation({
    mutationFn: (policyId: string) => generateAITerms(policyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['renewal-queue'] });
    },
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Renewal Workflow</h1>
          <p className="text-sm text-slate-500 mt-0.5">Policies approaching renewal — identify, quote, and process</p>
        </div>
        <button
          onClick={() => schedulerMutation.mutate()}
          disabled={schedulerMutation.isPending}
          className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition disabled:opacity-50"
        >
          <Play size={14} />
          {schedulerMutation.isPending ? 'Running…' : 'Run Scheduler'}
        </button>
      </div>

      {schedulerMutation.isSuccess && schedulerMutation.data && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          Scheduler completed — {Object.entries(schedulerMutation.data.stats).map(([k, v]) => `${k}: ${v}`).join(', ')}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Candidates" value={data.total} icon={<RefreshCw size={20} />} subtitle={`${money(totalPremium)} premium at risk`} />
        <StatCard title="Within 30 Days" value={data.within_30_days} icon={<AlertCircle size={20} />} subtitle="Urgent attention" />
        <StatCard title="Within 60 Days" value={data.within_60_days} icon={<Clock size={20} />} subtitle="Action needed" />
        <StatCard title="Within 90 Days" value={data.within_90_days} icon={<CheckCircle2 size={20} />} subtitle="Planning window" />
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        <button
          onClick={() => setActiveTab('upcoming')}
          className={`flex items-center gap-1.5 flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
            activeTab === 'upcoming' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Clock size={14} /> Upcoming
        </button>
        <button
          onClick={() => setActiveTab('queue')}
          className={`flex items-center gap-1.5 flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
            activeTab === 'queue' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <RefreshCw size={14} /> Queue
        </button>
      </div>

      {activeTab === 'upcoming' && (<>
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
              <th className="px-4 py-3">Countdown</th>
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
                <td className="px-4 py-3"><CountdownTimer days={r.days_to_expiry} /></td>
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
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                  No renewals in this window
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      </>)}

      {/* Queue Tab (#84) */}
      {activeTab === 'queue' && (
        <div className="space-y-4">
          {queueLoading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2"><StatCardSkeleton /><StatCardSkeleton /></div>
          ) : queueData.length === 0 ? (
            <div className="rounded-xl border border-slate-200/60 bg-white p-8 text-center shadow-[var(--shadow-xs)]">
              <RefreshCw size={32} className="mx-auto text-slate-300 mb-3" />
              <p className="text-sm text-slate-500">No items in the renewal queue.</p>
              <p className="text-xs text-slate-400 mt-1">Click "Run Scheduler" to scan for upcoming renewals.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {queueData.map((item: RenewalQueueItem) => (
                <div key={item.id} className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)] hover:shadow-md transition-shadow">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-mono text-xs font-medium text-slate-900">{item.policy_number}</span>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          item.badge === 'critical' ? 'bg-red-100 text-red-700' :
                          item.badge === 'warning' ? 'bg-amber-100 text-amber-700' :
                          item.badge === 'soon' ? 'bg-blue-100 text-blue-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {item.badge}
                        </span>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          item.status === 'pending' ? 'bg-slate-100 text-slate-600' :
                          item.status === 'quoted' ? 'bg-indigo-100 text-indigo-700' :
                          item.status === 'renewed' ? 'bg-emerald-100 text-emerald-700' :
                          'bg-slate-100 text-slate-600'
                        }`}>
                          {item.status}
                        </span>
                      </div>
                      <p className="font-medium text-slate-900">{item.policyholder_name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {item.effective_date} → {item.expiration_date} · Premium: {money(item.expiring_premium)}
                      </p>
                      {item.recommendation && (
                        <p className="text-xs text-slate-500 mt-1 italic">"{item.recommendation}"</p>
                      )}
                      {item.ai_terms && (
                        <div className="mt-2 rounded-lg border border-indigo-100 bg-indigo-50/50 p-3">
                          <div className="flex items-center gap-1.5 mb-1">
                            <Sparkles size={12} className="text-indigo-500" />
                            <span className="text-[10px] font-semibold text-indigo-600 uppercase tracking-wider">AI-Generated Terms</span>
                          </div>
                          <div className="text-xs text-slate-600 space-y-0.5">
                            {Object.entries(item.ai_terms).map(([k, v]) => (
                              <div key={k}><span className="font-medium text-slate-700">{k}:</span> {String(v)}</div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <CountdownTimer days={item.days_to_expiry} />
                      {!item.ai_terms && (
                        <button
                          onClick={() => termsMutation.mutate(item.policy_id)}
                          disabled={termsMutation.isPending}
                          className="flex items-center gap-1.5 rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition disabled:opacity-50"
                        >
                          <Sparkles size={12} />
                          {termsMutation.isPending ? 'Generating…' : 'Generate Terms'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RenewalsPage;
