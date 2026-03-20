import React, { useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Eye, RefreshCw, FileText, Loader2 } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getPolicies } from '../api/policies';
import { generateRenewalTerms } from '../api/renewals';
import type { Policy, PolicyStatus } from '../types';

const statusVariant: Record<PolicyStatus, 'green' | 'gray' | 'red' | 'yellow'> = {
  active: 'green',
  expired: 'gray',
  cancelled: 'red',
  pending: 'yellow',
};

const lobLabels: Record<string, string> = {
  cyber: 'Cyber', professional_liability: 'Prof Liability', dnol: 'D&O',
  epli: 'EPLI', general_liability: 'General Liability',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const Policies: React.FC = () => {
  const navigate = useNavigate();
  const { data: policies = [], isLoading, refetch } = useQuery({ queryKey: ['policies'], queryFn: getPolicies });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const handleRenew = useCallback(async (policyId: string) => {
    setActionLoading(`${policyId}-renew`);
    try {
      const data = await generateRenewalTerms(policyId);
      await refetch();
      const premium = Number(data?.renewal_premium ?? data?.premium ?? 0);
      addToast('success', premium > 0 ? `Renewal generated! New premium: ${money(premium)}` : 'Renewal generated successfully!');
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Failed to generate renewal: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  }, [refetch, addToast]);

  const filtered = useMemo(() => {
    if (statusFilter === 'all') return policies;
    return policies.filter((p) => p.status === statusFilter);
  }, [policies, statusFilter]);

  const columns: Column<Policy>[] = [
    { key: 'number', header: 'Policy Number', render: (r) => <span className="font-mono text-xs">{r.policy_number}</span>, sortable: true, sortValue: (r) => r.policy_number },
    { key: 'insured', header: 'Insured', render: (r) => <span className="font-medium text-slate-900">{r.insured_name}</span>, sortable: true, sortValue: (r) => r.insured_name },
    { key: 'lob', header: 'LOB', render: (r) => lobLabels[r.lob] ?? r.lob },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge label={r.status} variant={statusVariant[r.status]} /> },
    { key: 'effective', header: 'Effective', render: (r) => r.effective_date, sortable: true, sortValue: (r) => r.effective_date },
    { key: 'expiration', header: 'Expiration', render: (r) => r.expiration_date, sortable: true, sortValue: (r) => r.expiration_date },
    { key: 'premium', header: 'Premium', render: (r) => money(r.premium), sortable: true, sortValue: (r) => r.premium },
    { key: 'actions', header: 'Actions', render: (r) => {
      const loading = actionLoading?.startsWith(r.id);
      return (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => navigate(`/policies/${r.id}`)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-all"
          >
            <Eye size={11} />
            View
          </button>
          {r.status === 'active' && (
            <>
              <button
                onClick={() => handleRenew(r.id)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-all"
              >
                {actionLoading === `${r.id}-renew` ? <Loader2 size={11} className="animate-spin" /> : <RefreshCw size={11} />}
                Renew
              </button>
              <button
                onClick={() => alert('Endorsement coming soon — this feature is under development.')}
                className="inline-flex items-center gap-1 rounded-md bg-purple-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-purple-700 transition-all"
              >
                <FileText size={11} />
                Endorse
              </button>
            </>
          )}
        </div>
      );
    }},
  ];

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Policies</h1>
        <Link to="/policies/new" className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus size={16} /> New Policy
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="all">All Statuses</option>
          {Object.keys(statusVariant).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-slate-400">{filtered.length} policies</span>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyExtractor={(r) => r.id}
      />
    </div>
  );
};

export default Policies;
