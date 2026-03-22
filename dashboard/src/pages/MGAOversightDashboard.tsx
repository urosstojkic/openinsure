import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts';
import {
  Building2, ShieldCheck, AlertTriangle, TrendingUp,
} from 'lucide-react';
import StatCard from '../components/StatCard';
import {
  getMGAPerformance,
  getMGABordereaux,
  type MGAPerformance,
  type MGABordereau,
} from '../api/mga';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

// Audit findings remain static until audit module is built
const auditFindings = [
  { id: 1, mga: 'Summit Delegated Authority', date: '2025-04-10', severity: 'high', finding: 'Premium authority exceeded by 96.7% — near breach of limit', status: 'open' },
  { id: 2, mga: 'Coastal Risk Partners', date: '2025-07-20', severity: 'medium', finding: 'Late bordereau submissions for 2 consecutive quarters', status: 'remediated' },
  { id: 3, mga: 'Pacific Specialty MGA', date: '2025-09-15', severity: 'low', finding: 'Minor documentation gaps in 3 cyber policies', status: 'closed' },
  { id: 4, mga: 'Summit Delegated Authority', date: '2025-04-10', severity: 'high', finding: 'Loss ratio exceeds 70% threshold — corrective action required', status: 'open' },
];

const statusBadge = (s: string) => {
  const colors: Record<string, string> = {
    active: 'bg-green-100 text-green-700',
    suspended: 'bg-red-100 text-red-700',
    expired: 'bg-slate-100 text-slate-600',
    validated: 'bg-green-100 text-green-700',
    exceptions: 'bg-amber-100 text-amber-700',
    pending: 'bg-blue-100 text-blue-700',
    accepted: 'bg-green-100 text-green-700',
    open: 'bg-red-100 text-red-700',
    remediated: 'bg-amber-100 text-amber-700',
    closed: 'bg-slate-100 text-slate-600',
    high: 'bg-red-100 text-red-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-green-100 text-green-700',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors[s] ?? 'bg-slate-100 text-slate-600'}`}>
      {s}
    </span>
  );
};

const MGAOversightDashboard: React.FC = () => {
  const [tab, setTab] = useState<'scorecard' | 'bordereaux' | 'audit'>('scorecard');

  const { data: perfData, isLoading: perfLoading } = useQuery<MGAPerformance>({
    queryKey: ['mga-performance'],
    queryFn: getMGAPerformance,
  });

  const { data: bxData, isLoading: bxLoading } = useQuery<MGABordereau[]>({
    queryKey: ['mga-bordereaux'],
    queryFn: () => getMGABordereaux(),
  });

  if (perfLoading || bxLoading || !perfData) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-7 w-44 rounded-lg bg-slate-200 animate-pulse" />
          <div className="mt-2 h-4 w-72 rounded bg-slate-100 animate-pulse" />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
          <StatCardSkeleton />
        </div>
        <ChartSkeleton />
      </div>
    );
  }

  const mgaAuthorities = perfData.authorities;
  const bordereaux = bxData ?? [];

  const totalWritten = perfData.total_premium_written;
  const totalAuthority = mgaAuthorities.reduce((s, a) => s + a.premium_authority, 0);
  const activeMgas = mgaAuthorities.filter(a => a.status === 'active').length;
  const avgCompliance = Math.round(mgaAuthorities.reduce((s, a) => s + a.compliance_score, 0) / mgaAuthorities.length);

  const utilizationData = mgaAuthorities.map(a => ({
    name: a.mga_name.split(' ')[0],
    utilization: Math.round((a.premium_written / a.premium_authority) * 100),
    written: a.premium_written,
    authority: a.premium_authority,
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">MGA Oversight</h1>
        <p className="text-sm text-slate-500 mt-0.5">Delegated authority monitoring — Carrier view</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Active MGAs" value={activeMgas} icon={<Building2 size={20} />} subtitle={`${mgaAuthorities.length} total`} />
        <StatCard title="Total Premium Written" value={money(totalWritten)} icon={<TrendingUp size={20} />} subtitle={`of ${money(totalAuthority)} authority`} />
        <StatCard title="Avg Compliance Score" value={avgCompliance} icon={<ShieldCheck size={20} />} subtitle="Target: >85" />
        <StatCard title="Open Audit Findings" value={auditFindings.filter(f => f.status === 'open').length} icon={<AlertTriangle size={20} />} subtitle={`${auditFindings.length} total findings`} />
      </div>

      {/* Authority Utilization Chart */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <h2 className="mb-4 text-sm font-semibold text-slate-800">Authority Utilization</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={utilizationData} barCategoryGap="20%" maxBarSize={40}>
            <CartesianGrid stroke="#f1f5f9" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={(v: number) => `${v}%`} axisLine={false} tickLine={false} />
            <Tooltip
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
                    <p className="text-[11px] font-medium text-slate-400">{label}</p>
                    <p className="text-sm font-bold text-slate-800">{payload[0].value}%</p>
                  </div>
                );
              }}
            />
            <Bar dataKey="utilization" radius={[6, 6, 0, 0]}>
              {utilizationData.map((entry, i) => (
                <Cell key={i} fill={entry.utilization > 90 ? '#ef4444' : entry.utilization > 70 ? '#f59e0b' : '#22c55e'} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
        {(['scorecard', 'bordereaux', 'audit'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 rounded-md px-4 py-2 text-sm font-medium transition ${
              tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {t === 'scorecard' ? 'MGA Scorecard' : t === 'bordereaux' ? 'Bordereaux' : 'Audit Findings'}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {tab === 'scorecard' && (
        <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">MGA Name</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Premium Written / Authority</th>
                <th className="px-4 py-3">Loss Ratio</th>
                <th className="px-4 py-3">Compliance Score</th>
                <th className="px-4 py-3">LOBs</th>
                <th className="px-4 py-3">Last Audit</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {mgaAuthorities.map(a => (
                <tr key={a.mga_id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-900">{a.mga_name}</td>
                  <td className="px-4 py-3">{statusBadge(a.status)}</td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {money(a.premium_written)} / {money(a.premium_authority)}
                    <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                      <div
                        className={`h-1.5 rounded-full ${a.premium_written / a.premium_authority > 0.9 ? 'bg-red-500' : 'bg-blue-500'}`}
                        style={{ width: `${Math.min((a.premium_written / a.premium_authority) * 100, 100)}%` }}
                      />
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={a.loss_ratio > 0.65 ? 'text-red-600 font-semibold' : a.loss_ratio > 0.5 ? 'text-amber-600' : 'text-green-600'}>
                      {pct(a.loss_ratio)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={a.compliance_score < 70 ? 'text-red-600 font-semibold' : a.compliance_score < 85 ? 'text-amber-600' : 'text-green-600'}>
                      {a.compliance_score}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">{a.lines_of_business.join(', ')}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{a.last_audit_date}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'bordereaux' && (
        <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">MGA</th>
                <th className="px-4 py-3">Period</th>
                <th className="px-4 py-3">Premium</th>
                <th className="px-4 py-3">Claims</th>
                <th className="px-4 py-3">Loss Ratio</th>
                <th className="px-4 py-3">Policies</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Exceptions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {bordereaux.map(b => (
                <tr key={b.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-900">{mgaAuthorities.find(a => a.mga_id === b.mga_id)?.mga_name ?? b.mga_id}</td>
                  <td className="px-4 py-3 text-slate-600">{b.period}</td>
                  <td className="px-4 py-3 font-mono text-xs">{money(b.premium_reported)}</td>
                  <td className="px-4 py-3 font-mono text-xs">{money(b.claims_reported)}</td>
                  <td className="px-4 py-3">
                    <span className={b.loss_ratio > 0.65 ? 'text-red-600 font-semibold' : 'text-slate-700'}>
                      {pct(b.loss_ratio)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{b.policy_count}</td>
                  <td className="px-4 py-3">{statusBadge(b.status)}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    {b.exceptions.length > 0 ? b.exceptions.join('; ') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'audit' && (
        <div className="rounded-xl border border-slate-200/60 bg-white overflow-hidden shadow-[var(--shadow-xs)]">
          <table className="w-full text-sm">
            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">MGA</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Finding</th>
                <th className="px-4 py-3">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {auditFindings.map(f => (
                <tr key={f.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-900">{f.mga}</td>
                  <td className="px-4 py-3 text-slate-600">{f.date}</td>
                  <td className="px-4 py-3">{statusBadge(f.severity)}</td>
                  <td className="px-4 py-3 text-slate-700">{f.finding}</td>
                  <td className="px-4 py-3">{statusBadge(f.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default MGAOversightDashboard;
