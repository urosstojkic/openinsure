import React, { useState, useMemo, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Play, Eye, Loader2, DollarSign, XCircle, Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getClaims } from '../api/claims';
import client from '../api/client';
import type { Claim, ClaimStatus, ClaimSeverity } from '../types';

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

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const Claims: React.FC = () => {
  const navigate = useNavigate();
  const { data: claims = [], isLoading, refetch } = useQuery({ queryKey: ['claims'], queryFn: getClaims });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const handleClaimAction = useCallback(async (id: string, action: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(`${id}-${action}`);
    try {
      const { data } = await client.post(`/claims/${id}/${action}`);
      await refetch();
      if (action === 'set-reserve') {
        const reserve = data?.reserve ?? data?.total_reserved;
        addToast('success', reserve != null ? `Reserve set: ${money(reserve)}` : 'Reserve updated successfully!');
      } else if (action === 'close') {
        addToast('success', 'Claim closed successfully!');
      } else if (action === 'process') {
        const status = data?.status ?? data?.new_status ?? '';
        addToast('success', status ? `Claim processed — status: ${status}` : 'Claim processed successfully!');
      } else {
        addToast('success', `${action} completed successfully!`);
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Failed to ${action} claim: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  }, [refetch, addToast]);

  const filtered = useMemo(() => {
    let list = claims;
    if (statusFilter !== 'all') list = list.filter((c) => c.status === statusFilter);
    if (severityFilter !== 'all') list = list.filter((c) => c.severity === severityFilter);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((c) =>
        c.claim_number?.toLowerCase().includes(q) ||
        c.policy_number?.toLowerCase().includes(q) ||
        c.assigned_to?.toLowerCase().includes(q) ||
        c.lob?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [claims, statusFilter, severityFilter, searchQuery]);

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
    const selected = claims.filter((c) => selectedIds.has(c.id));
    const headers = ['Claim Number', 'Policy', 'Type', 'Status', 'Severity', 'Reserved', 'Total Incurred'];
    const rows = selected.map((c) => [c.claim_number, c.policy_number, c.lob, c.status, c.severity, c.total_reserved, c.total_incurred].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'claims_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: Column<Claim>[] = [
    { key: 'select', header: (
        <input type="checkbox" checked={allPageSelected} onChange={toggleSelectAll} className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
      ), render: (r) => (
        <input type="checkbox" checked={selectedIds.has(r.id)} onChange={() => toggleSelect(r.id)} onClick={(e) => e.stopPropagation()} className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
      ),
    },
    { key: 'number', header: 'Claim Number',render: (r) => <span className="font-mono text-xs">{r.claim_number}</span>, sortable: true, sortValue: (r) => r.claim_number },
    { key: 'policy', header: 'Policy', render: (r) => <span className="font-mono text-xs">{r.policy_number || '—'}</span> },
    { key: 'lob', header: 'Type', render: (r) => <span className="text-sm text-slate-600">{r.lob?.replace(/_/g, ' ') || '—'}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge label={r.status} variant={statusVariant[r.status] || 'gray'} /> },
    { key: 'loss_date', header: 'Loss Date', render: (r) => r.loss_date ? new Date(r.loss_date).toLocaleDateString() : '—', sortable: true, sortValue: (r) => r.loss_date },
    { key: 'severity', header: 'Severity', render: (r) => <StatusBadge label={r.severity} variant={severityVariant[r.severity] || 'gray'} /> },
    { key: 'reserved', header: 'Reserved', render: (r) => <span className={r.total_reserved > 0 ? 'font-medium text-slate-900' : 'text-slate-400'}>{money(r.total_reserved)}</span>, sortable: true, sortValue: (r) => r.total_reserved },
    { key: 'incurred', header: 'Total Incurred', render: (r) => money(r.total_incurred), sortable: true, sortValue: (r) => r.total_incurred },
    { key: 'assigned', header: 'Assigned To', render: (r) => r.assigned_to || <span className="text-slate-300">Unassigned</span> },
    { key: 'actions', header: 'Actions', render: (r) => {
      const loading = actionLoading?.startsWith(r.id);
      return (
        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {(r.status === 'reported' || r.status === 'open') && (
            <>
              <button
                onClick={(e) => handleClaimAction(r.id, 'process', e)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-all"
              >
                {actionLoading === `${r.id}-process` ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                Process
              </button>
              <button
                onClick={(e) => handleClaimAction(r.id, 'set-reserve', e)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-amber-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-600 disabled:opacity-50 transition-all"
              >
                {actionLoading === `${r.id}-set-reserve` ? <Loader2 size={11} className="animate-spin" /> : <DollarSign size={11} />}
                Set Reserve
              </button>
            </>
          )}
          {r.status === 'investigating' && (
            <>
              <button
                onClick={(e) => handleClaimAction(r.id, 'process', e)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-all"
              >
                {actionLoading === `${r.id}-process` ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
                Process
              </button>
              <button
                onClick={(e) => handleClaimAction(r.id, 'close', e)}
                disabled={!!loading}
                className="inline-flex items-center gap-1 rounded-md bg-slate-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-700 disabled:opacity-50 transition-all"
              >
                {actionLoading === `${r.id}-close` ? <Loader2 size={11} className="animate-spin" /> : <XCircle size={11} />}
                Close
              </button>
            </>
          )}
          {r.status === 'reserved' && (
            <button
              onClick={(e) => handleClaimAction(r.id, 'process', e)}
              disabled={!!loading}
              className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-all"
            >
              {actionLoading === `${r.id}-process` ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
              Process
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/claims/${r.id}`); }}
            className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-all"
          >
            <Eye size={11} />
            View
          </button>
        </div>
      );
    }},
  ];

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Claims</h1>
        <Link to="/claims/new" className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus size={16} /> File Claim
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
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
          value={severityFilter}
          onChange={(e) => setSeverityFilter(e.target.value)}
        >
          <option value="all">All Severities</option>
          {Object.keys(severityVariant).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-slate-400">{filtered.length} claims</span>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyExtractor={(r) => r.id}
      />
    </div>
  );
};

export default Claims;
