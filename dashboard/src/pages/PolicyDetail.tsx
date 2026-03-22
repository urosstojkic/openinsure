import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { StatCardSkeleton } from '../components/Skeleton';
import { getPolicy } from '../api/policies';
import type { PolicyStatus } from '../types';

const statusVariant: Record<PolicyStatus, 'green' | 'gray' | 'red' | 'yellow'> = {
  active: 'green',
  expired: 'gray',
  cancelled: 'red',
  pending: 'yellow',
};

const lobLabels: Record<string, string> = {
  cyber: 'Cyber Liability',
  professional_liability: 'Professional Liability',
  dnol: 'Directors & Officers',
  epli: 'Employment Practices',
  general_liability: 'General Liability',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const fmtDate = (d: string) => {
  if (!d) return '—';
  const date = new Date(d);
  if (isNaN(date.getTime())) return d;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const PolicyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: policy, isLoading } = useQuery({
    queryKey: ['policy', id],
    queryFn: () => getPolicy(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="grid grid-cols-1 gap-6 lg:grid-cols-2"><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /></div>;
  if (!policy) return <div className="flex h-64 items-center justify-center text-slate-400">Policy not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/policies')} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{policy.policy_number}</h1>
            <StatusBadge label={policy.status} variant={statusVariant[policy.status]} />
          </div>
          <p className="text-sm text-slate-500 mt-0.5">{policy.insured_name} · {lobLabels[policy.lob] ?? policy.lob}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Policy Details */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">Policy Details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Policy Number</dt><dd className="mt-0.5 font-medium text-slate-800 font-mono">{policy.policy_number}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Insured</dt><dd className="mt-0.5 font-medium text-slate-800">{policy.insured_name}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Line of Business</dt><dd className="mt-0.5 font-medium text-slate-800">{lobLabels[policy.lob] ?? policy.lob}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Status</dt><dd className="mt-0.5"><StatusBadge label={policy.status} variant={statusVariant[policy.status]} /></dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Effective Date</dt><dd className="mt-0.5 font-medium text-slate-800">{fmtDate(policy.effective_date)}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Expiration Date</dt><dd className="mt-0.5 font-medium text-slate-800">{fmtDate(policy.expiration_date)}</dd></div>
          </dl>
        </div>

        {/* Financial Details */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">Financial Details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Premium</dt><dd className="mt-0.5 text-lg font-bold text-slate-800">{money(policy.premium)}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Coverage Limit</dt><dd className="mt-0.5 text-lg font-bold text-slate-800">{money(policy.coverage_limit)}</dd></div>
            <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Deductible</dt><dd className="mt-0.5 font-medium text-slate-800">{money(policy.deductible)}</dd></div>
            {policy.submission_id && (
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Submission ID</dt>
                <dd className="mt-0.5 font-medium text-indigo-600 hover:text-indigo-800 cursor-pointer font-mono text-xs" onClick={() => navigate(`/submissions/${policy.submission_id}`)}>
                  {policy.submission_id}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>
    </div>
  );
};

export default PolicyDetail;
