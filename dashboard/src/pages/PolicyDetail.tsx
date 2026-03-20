import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
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

const PolicyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: policy, isLoading } = useQuery({
    queryKey: ['policy', id],
    queryFn: () => getPolicy(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;
  if (!policy) return <div className="flex h-64 items-center justify-center text-slate-400">Policy not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/policies')} className="rounded-lg p-1 hover:bg-slate-200">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">{policy.policy_number}</h1>
            <StatusBadge label={policy.status} variant={statusVariant[policy.status]} />
          </div>
          <p className="text-sm text-slate-500">{policy.insured_name} · {lobLabels[policy.lob] ?? policy.lob}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Policy Details */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Policy Details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-slate-400">Policy Number</dt><dd className="font-medium text-slate-900 font-mono">{policy.policy_number}</dd></div>
            <div><dt className="text-slate-400">Insured</dt><dd className="font-medium text-slate-900">{policy.insured_name}</dd></div>
            <div><dt className="text-slate-400">Line of Business</dt><dd className="font-medium text-slate-900">{lobLabels[policy.lob] ?? policy.lob}</dd></div>
            <div><dt className="text-slate-400">Status</dt><dd><StatusBadge label={policy.status} variant={statusVariant[policy.status]} /></dd></div>
            <div><dt className="text-slate-400">Effective Date</dt><dd className="font-medium text-slate-900">{policy.effective_date}</dd></div>
            <div><dt className="text-slate-400">Expiration Date</dt><dd className="font-medium text-slate-900">{policy.expiration_date}</dd></div>
          </dl>
        </div>

        {/* Financial Details */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Financial Details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <div><dt className="text-slate-400">Premium</dt><dd className="text-lg font-bold text-slate-900">{money(policy.premium)}</dd></div>
            <div><dt className="text-slate-400">Coverage Limit</dt><dd className="text-lg font-bold text-slate-900">{money(policy.coverage_limit)}</dd></div>
            <div><dt className="text-slate-400">Deductible</dt><dd className="font-medium text-slate-900">{money(policy.deductible)}</dd></div>
            {policy.submission_id && (
              <div>
                <dt className="text-slate-400">Submission ID</dt>
                <dd className="font-medium text-blue-600 hover:text-blue-800 cursor-pointer font-mono text-xs" onClick={() => navigate(`/submissions/${policy.submission_id}`)}>
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
