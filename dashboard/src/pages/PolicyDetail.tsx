import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, FileText, Award, List } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { StatCardSkeleton } from '../components/Skeleton';
import { getPolicy } from '../api/policies';
import client from '../api/client';
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

      {/* Policy Documents */}
      <PolicyDocuments policyId={id!} />
    </div>
  );
};

/* ---- Policy Documents Panel (#78) ---- */

interface DocContent {
  title: string;
  document_type: string;
  policy_number: string;
  sections: { heading: string; content: string; data?: Record<string, unknown> }[];
  effective_date: string;
  summary: string;
  generated_at: string;
}

function PolicyDocuments({ policyId }: { policyId: string }) {
  const [activeDoc, setActiveDoc] = React.useState<DocContent | null>(null);
  const [loading, setLoading] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  const fetchDoc = async (docType: string) => {
    setLoading(docType);
    setError(null);
    try {
      const { data } = await client.get<DocContent>(`/policies/${policyId}/documents/${docType}`);
      setActiveDoc(data);
    } catch {
      setError(`Failed to generate ${docType} document. API may be unavailable.`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
      <h2 className="mb-4 text-sm font-semibold text-slate-800">Policy Documents</h2>
      <div className="flex flex-wrap gap-3 mb-4">
        <button
          onClick={() => fetchDoc('declaration')}
          disabled={loading === 'declaration'}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50"
        >
          <FileText size={16} />
          {loading === 'declaration' ? 'Generating…' : 'View Declaration'}
        </button>
        <button
          onClick={() => fetchDoc('certificate')}
          disabled={loading === 'certificate'}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50"
        >
          <Award size={16} />
          {loading === 'certificate' ? 'Generating…' : 'Download Certificate'}
        </button>
        <button
          onClick={() => fetchDoc('schedule')}
          disabled={loading === 'schedule'}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 disabled:opacity-50"
        >
          <List size={16} />
          {loading === 'schedule' ? 'Generating…' : 'Coverage Schedule'}
        </button>
      </div>

      {error && <p className="text-sm text-red-500 mb-3">{error}</p>}

      {activeDoc && (
        <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-4 space-y-3">
          <h3 className="text-base font-bold text-slate-900">{activeDoc.title}</h3>
          <p className="text-sm text-slate-600 italic">{activeDoc.summary}</p>
          {activeDoc.sections.map((section, i) => (
            <div key={i} className="border-t border-slate-200 pt-3">
              <h4 className="text-sm font-semibold text-slate-800">{section.heading}</h4>
              <p className="mt-1 text-sm text-slate-600 whitespace-pre-wrap">{section.content}</p>
            </div>
          ))}
          <p className="text-[11px] text-slate-400 mt-2">Generated at {activeDoc.generated_at}</p>
        </div>
      )}
    </div>
  );
}

export default PolicyDetail;
