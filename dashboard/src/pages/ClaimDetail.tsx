import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, DollarSign, XCircle } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import { StatCardSkeleton } from '../components/Skeleton';
import { getClaim, getSubrogation, createSubrogation } from '../api/claims';
import type { ClaimStatus, ClaimSeverity } from '../types';

const statusVariant: Record<ClaimStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'red' | 'purple' | 'cyan'> = {
  reported: 'cyan',
  open: 'blue',
  investigating: 'yellow',
  reserved: 'orange',
  closed: 'green',
  denied: 'red',
  litigation: 'purple',
};

const severityVariant: Record<ClaimSeverity, 'gray' | 'yellow' | 'orange' | 'red'> = {
  low: 'gray',
  medium: 'yellow',
  high: 'orange',
  critical: 'red',
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

function SubrogationSection({ claimId }: { claimId: string }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [liableParty, setLiableParty] = useState('');
  const [basis, setBasis] = useState('');
  const [estimatedRecovery, setEstimatedRecovery] = useState('');

  const { data: records = [], isLoading } = useQuery({
    queryKey: ['subrogation', claimId],
    queryFn: () => getSubrogation(claimId),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createSubrogation(claimId, {
        liable_party: liableParty,
        basis,
        estimated_recovery: parseFloat(estimatedRecovery) || 0,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['subrogation', claimId] });
      setShowForm(false);
      setLiableParty('');
      setBasis('');
      setEstimatedRecovery('');
    },
  });

  const statusColors: Record<string, string> = {
    identified: 'bg-blue-100 text-blue-700',
    referred: 'bg-indigo-100 text-indigo-700',
    demand_sent: 'bg-yellow-100 text-yellow-700',
    negotiating: 'bg-orange-100 text-orange-700',
    settled: 'bg-emerald-100 text-emerald-700',
    collected: 'bg-green-100 text-green-700',
    closed: 'bg-slate-100 text-slate-600',
  };

  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-slate-900">Subrogation</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 transition-colors"
        >
          {showForm ? 'Cancel' : '+ New Referral'}
        </button>
      </div>

      {showForm && (
        <div className="mb-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
          <div>
            <label className="text-xs font-medium text-slate-500">Liable Party</label>
            <input
              value={liableParty}
              onChange={(e) => setLiableParty(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="e.g., Vendor Inc."
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Basis</label>
            <input
              value={basis}
              onChange={(e) => setBasis(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="e.g., Vendor negligence caused data breach"
            />
          </div>
          <div>
            <label className="text-xs font-medium text-slate-500">Estimated Recovery ($)</label>
            <input
              value={estimatedRecovery}
              onChange={(e) => setEstimatedRecovery(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              type="number"
              placeholder="50000"
            />
          </div>
          <button
            onClick={() => createMutation.mutate()}
            disabled={!liableParty || createMutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Referral'}
          </button>
        </div>
      )}

      {isLoading ? (
        <div className="animate-pulse space-y-2">
          {[1, 2].map((i) => (
            <div key={i} className="h-16 rounded-lg bg-slate-100" />
          ))}
        </div>
      ) : records.length === 0 ? (
        <p className="text-sm text-slate-400">No subrogation records for this claim.</p>
      ) : (
        <div className="space-y-3">
          {records.map((r) => (
            <div key={r.id} className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-slate-800">{r.liable_party}</span>
                <span
                  className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    statusColors[r.status] || 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {r.status.replace(/_/g, ' ')}
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-2">{r.basis}</p>
              <div className="flex gap-4 text-xs">
                <span className="text-slate-400">
                  Est. Recovery:{' '}
                  <span className="font-semibold text-slate-700">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(r.estimated_recovery)}
                  </span>
                </span>
                <span className="text-slate-400">
                  Actual:{' '}
                  <span className="font-semibold text-emerald-600">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(r.actual_recovery)}
                  </span>
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const ClaimDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: claim, isLoading } = useQuery({
    queryKey: ['claim', id],
    queryFn: () => getClaim(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="grid grid-cols-1 gap-6 lg:grid-cols-3"><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /></div>;
  if (!claim) return <div className="flex h-64 items-center justify-center text-slate-400">Claim not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/claims')} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300">
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">{claim.claim_number}</h1>
            <StatusBadge label={claim.status} variant={statusVariant[claim.status] || 'gray'} />
            <StatusBadge label={claim.severity} variant={severityVariant[claim.severity] || 'gray'} />
          </div>
          <p className="text-sm text-slate-500 mt-0.5">{lobLabels[claim.lob] ?? claim.lob} · {claim.assigned_to}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Left column: details ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Claim Details */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Claim Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Claim Number</dt><dd className="mt-0.5 font-medium text-slate-800 font-mono">{claim.claim_number}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Policy</dt><dd className="mt-0.5 font-medium text-slate-800 font-mono">{claim.policy_number || '—'}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Type</dt><dd className="mt-0.5 font-medium text-slate-800">{lobLabels[claim.lob] ?? claim.lob}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Status</dt><dd className="mt-0.5"><StatusBadge label={claim.status} variant={statusVariant[claim.status] || 'gray'} /></dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Severity</dt><dd className="mt-0.5"><StatusBadge label={claim.severity} variant={severityVariant[claim.severity] || 'gray'} /></dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Assigned Adjuster</dt><dd className="mt-0.5 font-medium text-slate-800">{claim.assigned_to}</dd></div>
            </dl>
          </div>

          {/* Description */}
          {claim.description && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-3 text-sm font-semibold text-slate-800">Description</h2>
              <p className="text-sm text-slate-700 leading-relaxed">{claim.description}</p>
            </div>
          )}

          {/* Dates */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Key Dates</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Date of Loss</dt><dd className="mt-0.5 font-medium text-slate-800">{fmtDate(claim.loss_date)}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Reported Date</dt><dd className="mt-0.5 font-medium text-slate-800">{fmtDate(claim.reported_date)}</dd></div>
            </dl>
          </div>

          {/* Reserves / Financials */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Reserves & Financials</h2>
            <dl className="grid grid-cols-3 gap-x-6 gap-y-3 text-sm">
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Total Reserved</dt>
                <dd className="mt-0.5 text-lg font-bold text-slate-800">{money(claim.total_reserved)}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Total Paid</dt>
                <dd className="mt-0.5 text-lg font-bold text-slate-800">{money(claim.total_paid)}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Total Incurred</dt>
                <dd className="mt-0.5 text-lg font-bold text-indigo-700">{money(claim.total_incurred)}</dd>
              </div>
            </dl>
          </div>
        </div>

        {/* ── Right column: actions ── */}
        <div className="space-y-6">
          {/* Action buttons */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Actions</h2>
            <div className="space-y-2">
              <button className="flex w-full items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600">
                <DollarSign size={16} /> Set Reserve
              </button>
              <button className="flex w-full items-center gap-2 rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
                <XCircle size={16} /> Close Claim
              </button>
            </div>
          </div>

          {/* Claim summary card */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Summary</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Policy ID</dt>
                <dd className="mt-0.5 font-medium text-slate-800 font-mono text-xs">{claim.policy_id || '—'}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Line of Business</dt>
                <dd className="mt-0.5 font-medium text-slate-800">{lobLabels[claim.lob] ?? claim.lob}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Adjuster</dt>
                <dd className="mt-0.5 font-medium text-slate-800">{claim.assigned_to}</dd>
              </div>
            </dl>
          </div>
        </div>
      </div>

      {/* Subrogation (#79) */}
      <SubrogationSection claimId={claim.id} />
    </div>
  );
};

export default ClaimDetail;
