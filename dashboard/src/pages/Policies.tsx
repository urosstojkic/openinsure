import React, { useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Eye, RefreshCw, FileText, Loader2, Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { TableSkeleton } from '../components/Skeleton';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getPolicies } from '../api/policies';
import { generateRenewalTerms } from '../api/renewals';
import type { Policy, PolicyStatus } from '../types';
import { lobShortName } from '../utils/lobLabels';

const statusVariant: Record<PolicyStatus, 'green' | 'gray' | 'red' | 'yellow'> = {
  active: 'green',
  expired: 'gray',
  cancelled: 'red',
  pending: 'yellow',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const fmtDate = (d: string) => {
  if (!d) return '—';
  const date = new Date(d);
  if (isNaN(date.getTime())) return d;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

const Policies: React.FC = () => {
  const navigate = useNavigate();
  const { data: policies = [], isLoading, refetch } = useQuery({ queryKey: ['policies'], queryFn: getPolicies });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
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
    let list = policies;
    if (statusFilter !== 'all') list = list.filter((p) => p.status === statusFilter);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((p) =>
        p.policy_number?.toLowerCase().includes(q) ||
        p.insured_name?.toLowerCase().includes(q) ||
        p.lob?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [policies, statusFilter, searchQuery]);

  const PAGE_SIZE = 25;
  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paginated = filtered.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);
  const pageIds = paginated.map((r) => r.id);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));

  const toggleSelectAll = () => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allPageSelected) pageIds.forEach((id) => next.delete(id));
      else pageIds.forEach((id) => next.add(id));
      return next;
    });
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleExportSelected = () => {
    const selected = policies.filter((p) => selectedIds.has(p.id));
    const headers = ['Policy Number', 'Insured', 'LOB', 'Status', 'Effective', 'Expiration', 'Premium'];
    const rows = selected.map((p) => [p.policy_number, p.insured_name, p.lob, p.status, p.effective_date, p.expiration_date, p.premium].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'policies_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: Column<Policy>[] = [
    { key: 'select', header: (
        <input type="checkbox" checked={allPageSelected} onChange={toggleSelectAll} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
      ), render: (r) => (
        <input type="checkbox" checked={selectedIds.has(r.id)} onChange={() => toggleSelect(r.id)} onClick={(e) => e.stopPropagation()} className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
      ),
    },
    { key: 'number', header: 'Policy Number',render: (r) => <span className="font-mono text-xs">{r.policy_number}</span>, sortable: true, sortValue: (r) => r.policy_number },
    { key: 'insured', header: 'Insured', render: (r) => <span className="font-medium text-slate-900">{r.insured_name}</span>, sortable: true, sortValue: (r) => r.insured_name },
    { key: 'lob', header: 'LOB', render: (r) => lobShortName(r.lob) },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge label={r.status} variant={statusVariant[r.status]} /> },
    { key: 'effective', header: 'Effective', render: (r) => fmtDate(r.effective_date), sortable: true, sortValue: (r) => r.effective_date },
    { key: 'expiration', header: 'Expiration', render: (r) => fmtDate(r.expiration_date), sortable: true, sortValue: (r) => r.expiration_date },
    { key: 'premium', header: 'Premium', render: (r) => money(r.premium), sortable: true, sortValue: (r) => r.premium },
    { key: 'actions', header: 'Actions', render: (r) => {
      const loading = actionLoading?.startsWith(r.id);
      return (
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => navigate(`/policies/${r.id}`)}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-all"
          >
            <Eye size={11} />
            View
          </button>
          {r.status === 'active' && (
            <>
              <button
                onClick={() => handleRenew(r.id)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 shadow-sm shadow-indigo-500/20 active:scale-[0.98] disabled:opacity-50 transition-all"
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

  if (isLoading) return <div className="space-y-4"><TableSkeleton rows={8} columns={8} /></div>;

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Policies</h1>
        <Link to="/policies/new" className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
          <Plus size={16} /> New Policy
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search policy #, insured…"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            className="rounded-lg border border-slate-200/60 bg-white pl-9 pr-3 py-2 text-sm text-slate-600 placeholder:text-slate-400 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition w-64"
          />
        </div>
        <select
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
        >
          <option value="all">All Statuses</option>
          {Object.keys(statusVariant).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-slate-400">{filtered.length} policies</span>
        {selectedIds.size > 0 && (
          <div className="ml-auto flex items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-1.5">
            <span className="text-sm font-medium text-indigo-700">Selected ({selectedIds.size})</span>
            <button onClick={handleExportSelected} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
              <Download size={12} /> Export
            </button>
            <button onClick={() => setSelectedIds(new Set())} className="text-xs text-indigo-600 hover:text-indigo-800">Clear</button>
          </div>
        )}
      </div>

      <DataTable
        columns={columns}
        data={paginated}
        keyExtractor={(r) => r.id}
      />

      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-slate-200/60 bg-white px-4 py-3 shadow-[var(--shadow-xs)]">
          <span className="text-xs text-slate-500">
            Showing {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => p - 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span className="text-sm text-slate-700">Page {currentPage} of {totalPages}</span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => p + 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Policies;
