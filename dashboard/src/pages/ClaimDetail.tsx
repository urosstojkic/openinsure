import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, DollarSign, XCircle, Play, Loader2, Sparkles, RefreshCw, Shield, ExternalLink, FileText, Clock, CheckCircle } from 'lucide-react';
import RiskGauge from '../components/RiskGauge';
import StackedBar from '../components/StackedBar';
import JourneyTimeline from '../components/JourneyTimeline';
import type { JourneyStep } from '../components/JourneyTimeline';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import ConfidenceBar from '../components/ConfidenceBar';
import { StatCardSkeleton } from '../components/Skeleton';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getClaim, processClaim, setReserve, closeClaim, reopenClaim, getSubrogation, createSubrogation } from '../api/claims';
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

import { lobDisplayName } from '../utils/lobLabels';

const claimTypeLabels: Record<string, string> = {
  data_breach: 'Data Breach',
  ransomware: 'Ransomware',
  business_interruption: 'Business Interruption',
  third_party_liability: 'Third-Party Liability',
  regulatory_proceeding: 'Regulatory Proceeding',
  other: 'Other',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const fmtDate = (d: string) => {
  if (!d) return '—';
  const date = new Date(d);
  if (isNaN(date.getTime())) return d;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

/* ── Claims Pipeline Visualization ── */
const PIPELINE_STEPS = [
  { key: 'reported', label: 'Reported' },
  { key: 'investigating', label: 'Investigation' },
  { key: 'reserved', label: 'Reserved' },
  { key: 'closed', label: 'Closed' },
];

const STATUS_ORDER: Record<string, number> = {
  reported: 0, open: 0, investigating: 1, reserved: 2, closed: 3, denied: -1, litigation: -1,
};

const CLAIM_JOURNEY_ICONS: Record<string, React.ElementType> = {
  reported: FileText,
  investigating: Shield,
  reserved: DollarSign,
  closed: CheckCircle,
};

function ClaimPipeline({ status }: { status: ClaimStatus }) {
  const currentStep = STATUS_ORDER[status] ?? -1;
  const isTerminal = status === 'denied' || status === 'litigation';

  const steps: JourneyStep[] = PIPELINE_STEPS.map((step) => ({
    key: step.key,
    label: step.label,
    icon: CLAIM_JOURNEY_ICONS[step.key] || Clock,
  }));

  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
      <h2 className="mb-5 text-xs font-semibold uppercase tracking-wider text-slate-400">Claims Journey</h2>
      <JourneyTimeline
        steps={steps}
        currentStepIndex={currentStep}
        isTerminal={isTerminal}
        terminalLabel={status === 'denied' ? 'Claim denied' : status === 'litigation' ? 'In litigation' : undefined}
      />
    </div>
  );
}

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
                  Est. Recovery: <span className="font-semibold text-slate-700">{money(r.estimated_recovery)}</span>
                </span>
                <span className="text-slate-400">
                  Actual: <span className="font-semibold text-emerald-600">{money(r.actual_recovery)}</span>
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
  const queryClient = useQueryClient();
  const { toasts, addToast, dismissToast } = useToast();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [closeConfirmOpen, setCloseConfirmOpen] = useState(false);
  const [reserveDialogOpen, setReserveDialogOpen] = useState(false);
  const [reserveAmount, setReserveAmount] = useState('25000');
  const [reserveCategory, setReserveCategory] = useState('indemnity');

  const { data: claim, isLoading } = useQuery({
    queryKey: ['claim', id],
    queryFn: () => getClaim(id!),
    enabled: !!id,
  });

  const handleProcess = async () => {
    if (!id) return;
    setActionLoading('process');
    try {
      const result = await processClaim(id);
      await queryClient.invalidateQueries({ queryKey: ['claim', id] });
      const outcome = result?.outcome || 'completed';
      addToast('success', `AI Assessment complete — outcome: ${outcome}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Assessment failed: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleSetReserve = async () => {
    if (!id) return;
    setActionLoading('reserve');
    try {
      const result = await setReserve(id, {
        category: reserveCategory,
        amount: parseFloat(reserveAmount) || 25000,
        notes: 'Set via portal',
      });
      await queryClient.invalidateQueries({ queryKey: ['claim', id] });
      const total = (result as Record<string, unknown>)?.total_reserved;
      addToast('success', total != null ? `Reserve set: ${money(Number(total))}` : 'Reserve updated successfully!');
      setReserveDialogOpen(false);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Set reserve failed: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleClose = async () => {
    if (!id) return;
    setActionLoading('close');
    try {
      await closeClaim(id, { reason: 'Resolved', outcome: 'resolved' });
      await queryClient.invalidateQueries({ queryKey: ['claim', id] });
      addToast('success', 'Claim closed successfully!');
      setCloseConfirmOpen(false);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Close failed: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleReopen = async () => {
    if (!id) return;
    setActionLoading('reopen');
    try {
      await reopenClaim(id, { reason: 'Reopened for further investigation' });
      await queryClient.invalidateQueries({ queryKey: ['claim', id] });
      addToast('success', 'Claim reopened successfully!');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Reopen failed: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  };

  if (isLoading) return <div className="grid grid-cols-1 gap-6 lg:grid-cols-3"><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /><StatCardSkeleton /></div>;
  if (!claim) return <div className="flex h-64 items-center justify-center text-slate-400">Claim not found</div>;

  // Extract AI assessment data from metadata if available
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const meta = (claim as any).metadata || {};
  const riskData = (claim as any).risk_data || {};
  const assessment = (claim as any).assessment || {};
  const fraudScore = claim.fraud_score ?? meta.fraud_score ?? riskData.fraud_score ?? assessment.fraud_score ?? null;
  const hasAIData = fraudScore != null || claim.total_reserved > 0 || meta.coverage_confirmed != null;

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />

      {/* AI processing overlay (#152) */}
      {actionLoading === 'process' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-slate-200/60 bg-white px-10 py-8 shadow-xl animate-pulse">
            <Loader2 size={36} className="animate-spin text-indigo-600" />
            <div className="text-center">
              <p className="text-base font-semibold text-slate-900">AI agent processing…</p>
              <p className="mt-1 text-sm text-slate-500">This may take up to 30 seconds</p>
            </div>
          </div>
        </div>
      )}

      {/* Confirmation Dialogs */}
      <ConfirmDialog
        open={closeConfirmOpen}
        title="Close Claim"
        message="Are you sure you want to close this claim? This will finalize the settlement."
        confirmLabel="Close Claim"
        variant="warning"
        onConfirm={handleClose}
        onCancel={() => setCloseConfirmOpen(false)}
      />

      {/* Reserve Dialog */}
      {reserveDialogOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" onClick={() => setReserveDialogOpen(false)} />
          <div className="relative mx-4 w-full max-w-md rounded-2xl border border-slate-200/60 bg-white p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900">Set Reserve</h3>
            <p className="mt-1 text-sm text-slate-500">Set or update reserves for this claim.</p>
            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs font-medium text-slate-500">Category</label>
                <select
                  value={reserveCategory}
                  onChange={(e) => setReserveCategory(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                >
                  <option value="indemnity">Indemnity</option>
                  <option value="expense">Expense</option>
                  <option value="defense">Defense</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500">Amount ($)</label>
                <input
                  type="number"
                  value={reserveAmount}
                  onChange={(e) => setReserveAmount(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  placeholder="25000"
                />
              </div>
            </div>
            <div className="mt-6 flex items-center justify-end gap-3">
              <button onClick={() => setReserveDialogOpen(false)} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button
                onClick={handleSetReserve}
                disabled={actionLoading === 'reserve'}
                className="inline-flex items-center gap-2 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
              >
                {actionLoading === 'reserve' ? <Loader2 size={14} className="animate-spin" /> : <DollarSign size={14} />}
                Set Reserve
              </button>
            </div>
          </div>
        </div>
      )}

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
          <p className="text-sm text-slate-500 mt-0.5">
            {lobDisplayName(claim.lob)} · {claim.assigned_to}
            {claim.claim_type && <span className="ml-2 text-xs text-slate-400">({claimTypeLabels[claim.claim_type] ?? claim.claim_type})</span>}
          </p>
        </div>
      </div>

      {/* Pipeline */}
      <ClaimPipeline status={claim.status} />

      {/* Severity Indicator */}
      {claim.severity && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-5">
          <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-card)] flex flex-col items-center">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-2">Severity</p>
            <RiskGauge
              value={claim.severity === 'critical' ? 95 : claim.severity === 'high' ? 75 : claim.severity === 'medium' ? 45 : 20}
              size={90}
              strokeWidth={8}
              label={claim.severity.charAt(0).toUpperCase() + claim.severity.slice(1)}
              thresholds={[35, 65]}
            />
          </div>
          {fraudScore != null && (
            <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-card)] flex flex-col items-center">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-2">Fraud Risk</p>
              <RiskGauge
                value={fraudScore * 100}
                size={90}
                strokeWidth={8}
                label={fraudScore < 0.3 ? 'Low' : fraudScore < 0.6 ? 'Medium' : 'High'}
                thresholds={[30, 60]}
              />
            </div>
          )}
          {claim.total_reserved > 0 && (
            <div className="sm:col-span-3 rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-card)]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-3">Financial Summary</p>
              <StackedBar
                segments={[
                  { label: 'Outstanding Reserve', value: Math.max(0, claim.total_reserved - claim.total_paid), color: '#f59e0b', textColor: '#92400e' },
                  { label: 'Paid', value: claim.total_paid, color: '#6366f1', textColor: '#3730a3' },
                ]}
                height={28}
              />
              <div className="mt-3 flex items-center gap-6 text-xs">
                <span className="text-slate-400">Total Incurred: <span className="font-bold text-slate-700">${claim.total_incurred.toLocaleString()}</span></span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI Assessment Results */}
      {hasAIData && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
          {claim.total_reserved > 0 && (
            <div className="rounded-xl border border-amber-200/60 bg-amber-50/50 p-4 shadow-[var(--shadow-xs)]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Total Reserved</p>
              <p className="mt-1 text-3xl font-bold text-amber-700">{money(claim.total_reserved)}</p>
              <p className="mt-0.5 text-xs text-slate-500">Current reserve</p>
            </div>
          )}

          {claim.total_paid > 0 && (
            <div className="rounded-xl border border-indigo-200/60 bg-indigo-50/50 p-4 shadow-[var(--shadow-xs)]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Total Paid</p>
              <p className="mt-1 text-3xl font-bold text-indigo-700">{money(claim.total_paid)}</p>
              <p className="mt-0.5 text-xs text-slate-500">Paid to date</p>
            </div>
          )}

          <div className="rounded-xl border border-slate-200/60 bg-white p-4 shadow-[var(--shadow-xs)]">
            <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Total Incurred</p>
            <p className="mt-1 text-3xl font-bold text-slate-800">{money(claim.total_incurred)}</p>
            <p className="mt-0.5 text-xs text-slate-500">Reserved + Paid</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Left column: details ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Claim Details */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Claim Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Claim Number</dt><dd className="mt-0.5 font-medium text-slate-800 font-mono">{claim.claim_number}</dd></div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Policy</dt>
                <dd className="mt-0.5 font-medium text-slate-800 font-mono">
                  {claim.policy_id ? (
                    <Link to={`/policies/${claim.policy_id}`} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline">
                      {claim.policy_number || claim.policy_id}
                      <ExternalLink size={11} />
                    </Link>
                  ) : (
                    claim.policy_number || '—'
                  )}
                </dd>
              </div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Type</dt><dd className="mt-0.5 font-medium text-slate-800">{claimTypeLabels[claim.claim_type || ''] ?? claim.claim_type ?? lobDisplayName(claim.lob)}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Status</dt><dd className="mt-0.5"><StatusBadge label={claim.status} variant={statusVariant[claim.status] || 'gray'} /></dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Severity</dt><dd className="mt-0.5"><StatusBadge label={claim.severity} variant={severityVariant[claim.severity] || 'gray'} /></dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Assigned Adjuster</dt><dd className="mt-0.5 font-medium text-slate-800">{claim.assigned_to}</dd></div>
              {claim.reported_by && (
                <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Reported By</dt><dd className="mt-0.5 font-medium text-slate-800">{claim.reported_by}</dd></div>
              )}
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

          {/* Reserves & Financials */}
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

            {/* Reserve vs Paid visualization */}
            {(claim.total_reserved > 0 || claim.total_paid > 0) && (
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400 mb-3">Reserve vs Paid</p>
                <StackedBar
                  segments={[
                    { label: 'Reserved', value: claim.total_reserved, color: '#f59e0b', textColor: '#92400e' },
                    { label: 'Paid', value: claim.total_paid, color: '#6366f1', textColor: '#3730a3' },
                  ]}
                  height={24}
                />
              </div>
            )}

            {/* Reserve breakdown */}
            {claim.reserves && claim.reserves.length > 0 && (
              <div className="mt-4 border-t border-slate-100 pt-3">
                <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400 mb-2">Reserve Breakdown</p>
                <div className="space-y-1.5">
                  {claim.reserves.map((r, i) => (
                    <div key={i} className="flex items-center justify-between rounded-lg bg-slate-50/50 px-3 py-1.5 text-sm">
                      <span className="text-slate-600 capitalize">{String(r.type || r.category || 'Reserve')}</span>
                      <span className="font-medium text-slate-800">{money(Number(r.amount || 0))}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* AI Assessment — fraud score, confidence */}
          {fraudScore != null && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">AI Assessment</h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
                  <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Fraud Score</p>
                  <div className="mt-1 flex items-center gap-2">
                    <Shield size={16} className={fraudScore < 0.3 ? 'text-emerald-500' : fraudScore < 0.6 ? 'text-amber-500' : 'text-red-500'} />
                    <span className="text-xl font-bold text-slate-900">{(fraudScore * 100).toFixed(0)}%</span>
                  </div>
                  <div className="mt-2">
                    <ConfidenceBar value={1 - fraudScore} height="h-2" />
                  </div>
                </div>
                {meta.subrogation_score != null && (
                  <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Subrogation Potential</p>
                    <p className="mt-1 text-xl font-bold text-slate-900">{(meta.subrogation_score * 100).toFixed(0)}%</p>
                  </div>
                )}
                {meta.coverage_confirmed != null && (
                  <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
                    <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Coverage</p>
                    <p className="mt-1">
                      <StatusBadge
                        label={meta.coverage_confirmed ? 'Confirmed' : 'Denied'}
                        variant={meta.coverage_confirmed ? 'green' : 'red'}
                      />
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Right column: actions + summary ── */}
        <div className="space-y-6">
          {/* Action buttons — status-aware */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Actions</h2>
            <div className="space-y-2">
              {/* reported/open → Process (AI Assessment) */}
              {(claim.status === 'reported' || claim.status === 'open') && (
                <button
                  onClick={handleProcess}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 transition-all hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'process' ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                  AI Assessment
                </button>
              )}

              {/* reported/open/investigating → Set Reserve */}
              {(claim.status === 'reported' || claim.status === 'open' || claim.status === 'investigating') && (
                <button
                  onClick={() => setReserveDialogOpen(true)}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-amber-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-amber-500/20 transition-all hover:bg-amber-600 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'reserve' ? <Loader2 size={15} className="animate-spin" /> : <DollarSign size={15} />}
                  Set Reserve
                </button>
              )}

              {/* reserved → Process to advance */}
              {claim.status === 'reserved' && (
                <button
                  onClick={handleProcess}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 transition-all hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'process' ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                  Process Claim
                </button>
              )}

              {/* Any non-closed status → Close */}
              {claim.status !== 'closed' && claim.status !== 'denied' && (
                <button
                  onClick={() => setCloseConfirmOpen(true)}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-slate-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-slate-500/20 transition-all hover:bg-slate-700 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'close' ? <Loader2 size={15} className="animate-spin" /> : <XCircle size={15} />}
                  Close Claim
                </button>
              )}

              {/* Closed → Reopen */}
              {claim.status === 'closed' && (
                <button
                  onClick={handleReopen}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-blue-700 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'reopen' ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
                  Reopen Claim
                </button>
              )}
            </div>
          </div>

          {/* Claim summary card */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">Summary</h2>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Policy</dt>
                <dd className="mt-0.5 font-medium text-slate-800 font-mono text-xs">
                  {claim.policy_id ? (
                    <Link to={`/policies/${claim.policy_id}`} className="text-indigo-600 hover:text-indigo-800 hover:underline">
                      {claim.policy_number || claim.policy_id}
                    </Link>
                  ) : '—'}
                </dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Line of Business</dt>
                <dd className="mt-0.5 font-medium text-slate-800">{lobDisplayName(claim.lob)}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Adjuster</dt>
                <dd className="mt-0.5 font-medium text-slate-800">{claim.assigned_to}</dd>
              </div>
              {claim.reported_by && (
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Reported By</dt>
                  <dd className="mt-0.5 font-medium text-slate-800">{claim.reported_by}</dd>
                </div>
              )}
            </dl>
          </div>
        </div>
      </div>

      {/* Subrogation */}
      <SubrogationSection claimId={claim.id} />
    </div>
  );
};

export default ClaimDetail;
