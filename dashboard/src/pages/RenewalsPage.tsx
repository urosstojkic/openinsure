import React, { useState } from 'react';
import {
  RefreshCw, Clock, AlertCircle, CheckCircle2,
} from 'lucide-react';
import StatCard from '../components/StatCard';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

// ── Mock renewal candidates ──
const renewalCandidates = [
  { id: 'pol-001', policy_number: 'POL-7A3B2C1D', policyholder_name: 'TechCorp Inc.', status: 'active', effective_date: '2025-01-15', expiration_date: '2026-01-15', premium: 45_000, days_to_expiry: 22, lob: 'Cyber' },
  { id: 'pol-002', policy_number: 'POL-8E4F5G6H', policyholder_name: 'Global Logistics LLC', status: 'active', effective_date: '2025-02-01', expiration_date: '2026-02-01', premium: 72_000, days_to_expiry: 38, lob: 'GL' },
  { id: 'pol-003', policy_number: 'POL-9I0J1K2L', policyholder_name: 'Apex Financial Group', status: 'active', effective_date: '2025-03-01', expiration_date: '2026-03-01', premium: 120_000, days_to_expiry: 66, lob: 'D&O' },
  { id: 'pol-004', policy_number: 'POL-3M4N5O6P', policyholder_name: 'Sunrise Healthcare', status: 'active', effective_date: '2025-04-15', expiration_date: '2026-04-15', premium: 95_000, days_to_expiry: 111, lob: 'Prof Liability' },
  { id: 'pol-005', policy_number: 'POL-7Q8R9S0T', policyholder_name: 'Metro Construction', status: 'active', effective_date: '2024-12-01', expiration_date: '2025-12-01', premium: 58_000, days_to_expiry: -24, lob: 'GL' },
];

const urgencyBadge = (days: number) => {
  if (days <= 0) return <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">Expired</span>;
  if (days <= 30) return <span className="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">≤30 days</span>;
  if (days <= 60) return <span className="inline-flex items-center rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">≤60 days</span>;
  if (days <= 90) return <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">≤90 days</span>;
  return <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">{days} days</span>;
};

const RenewalsPage: React.FC = () => {
  const [filter, setFilter] = useState<'all' | '30' | '60' | '90'>('all');

  const filtered = renewalCandidates.filter(r => {
    if (filter === '30') return r.days_to_expiry <= 30;
    if (filter === '60') return r.days_to_expiry <= 60;
    if (filter === '90') return r.days_to_expiry <= 90;
    return true;
  });

  const within30 = renewalCandidates.filter(r => r.days_to_expiry <= 30).length;
  const within60 = renewalCandidates.filter(r => r.days_to_expiry <= 60).length;
  const within90 = renewalCandidates.filter(r => r.days_to_expiry <= 90).length;
  const totalPremium = renewalCandidates.reduce((s, r) => s + r.premium, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Renewal Workflow</h1>
        <p className="text-sm text-slate-500">Policies approaching renewal — identify, quote, and process</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Candidates" value={renewalCandidates.length} icon={<RefreshCw size={20} />} subtitle={`${money(totalPremium)} premium at risk`} />
        <StatCard title="Within 30 Days" value={within30} icon={<AlertCircle size={20} />} subtitle="Urgent attention" />
        <StatCard title="Within 60 Days" value={within60} icon={<Clock size={20} />} subtitle="Action needed" />
        <StatCard title="Within 90 Days" value={within90} icon={<CheckCircle2 size={20} />} subtitle="Planning window" />
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
      <div className="rounded-lg border border-slate-200 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
            <tr>
              <th className="px-4 py-3">Policy #</th>
              <th className="px-4 py-3">Policyholder</th>
              <th className="px-4 py-3">LOB</th>
              <th className="px-4 py-3">Expiration</th>
              <th className="px-4 py-3">Urgency</th>
              <th className="px-4 py-3">Current Premium</th>
              <th className="px-4 py-3">Projected Renewal</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.map(r => (
              <tr key={r.id} className="hover:bg-slate-50 transition">
                <td className="px-4 py-3 font-mono text-xs font-medium text-slate-900">{r.policy_number}</td>
                <td className="px-4 py-3 font-medium text-slate-900">{r.policyholder_name}</td>
                <td className="px-4 py-3 text-slate-600">{r.lob}</td>
                <td className="px-4 py-3 text-slate-600">{r.expiration_date}</td>
                <td className="px-4 py-3">{urgencyBadge(r.days_to_expiry)}</td>
                <td className="px-4 py-3 font-mono text-xs">{money(r.premium)}</td>
                <td className="px-4 py-3 font-mono text-xs text-blue-600">{money(Math.round(r.premium * 1.05))}</td>
                <td className="px-4 py-3">
                  <button className="rounded-md bg-indigo-50 px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-100 transition">
                    Generate Terms
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
    </div>
  );
};

export default RenewalsPage;
