import React, { useState, useMemo, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus, Play, Sparkles, Eye, Loader2, Search, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { TableSkeleton } from '../components/Skeleton';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getSubmissions } from '../api/submissions';
import client from '../api/client';
import type { Submission, SubmissionStatus, LOB } from '../types';

const statusVariant: Record<SubmissionStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'cyan'> = {
  received: 'blue',
  triaging: 'yellow',
  underwriting: 'orange',
  quoted: 'green',
  bound: 'purple',
  declined: 'red',
  referred: 'cyan',
};

const priorityVariant = (p: string) =>
  p === 'urgent' ? 'red' : p === 'high' ? 'orange' : p === 'medium' ? 'yellow' : 'gray';

const lobLabels: Record<LOB, string> = {
  cyber: 'Cyber',
  professional_liability: 'Prof Liability',
  dnol: 'D&O',
  epli: 'EPLI',
  general_liability: 'General Liability',
};

const Submissions: React.FC = () => {
  const navigate = useNavigate();
  const { data: submissions = [], isLoading, refetch } = useQuery({ queryKey: ['submissions'], queryFn: getSubmissions });

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [lobFilter, setLobFilter] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { toasts, addToast, dismissToast } = useToast();

  const formatMoney = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

  const handleAction = useCallback(async (id: string, action: 'triage' | 'quote' | 'bind', e: React.MouseEvent) => {
    e.stopPropagation();
    setActionLoading(`${id}-${action}`);
    try {
      const { data } = await client.post(`/submissions/${id}/${action}`);
      await refetch();
      if (action === 'triage') {
        const score = data?.risk_score ?? data?.risk_data?.risk_score ?? '—';
        const rec = data?.recommendation ?? data?.risk_data?.recommendation ?? '';
        addToast('success', `Triaged! Risk score: ${score}${rec ? `, Recommendation: ${rec}` : ''}`);
      } else if (action === 'quote') {
        const premium = data?.premium ?? data?.quote?.premium;
        addToast('success', premium != null ? `Quoted! Premium: ${formatMoney(premium)}` : 'Quote generated successfully!');
      } else if (action === 'bind') {
        const policyId = data?.policy_id ?? data?.policy_number ?? '';
        addToast('success', policyId ? `Bound! Policy ID: ${policyId}` : 'Policy bound successfully!');
      }
    } catch (err: unknown) {
      // On timeout/network errors, check if the action actually succeeded server-side
      const isTimeout = (err as { code?: string })?.code === 'ECONNABORTED'
        || (err as { message?: string })?.message?.includes('timeout');
      if (isTimeout) {
        try {
          const { data: updated } = await client.get(`/submissions/${id}`);
          const expectedStatus = action === 'triage' ? 'underwriting' : action === 'quote' ? 'quoted' : 'bound';
          if (updated?.status === expectedStatus) {
            await refetch();
            addToast('success', `${action.charAt(0).toUpperCase() + action.slice(1)} completed (AI processing took longer than usual)`);
            return;
          }
        } catch { /* ignore verification errors */ }
      }
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      addToast('error', `Failed to ${action}: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  }, [refetch, addToast]);

  const filtered = useMemo(() => {
    let list = submissions;
    if (statusFilter !== 'all') list = list.filter((s) => s.status === statusFilter);
    if (lobFilter !== 'all') list = list.filter((s) => s.lob === lobFilter);
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((s) =>
        s.applicant_name?.toLowerCase().includes(q) ||
        s.company_name?.toLowerCase().includes(q) ||
        (s.submission_number || s.id)?.toLowerCase().includes(q)
      );
    }
    return list;
  }, [submissions, statusFilter, lobFilter, searchQuery]);

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
    const selected = submissions.filter((s) => selectedIds.has(s.id));
    const headers = ['ID', 'Applicant', 'Company', 'LOB', 'Status', 'Risk Score', 'Priority'];
    const rows = selected.map((s) => [s.submission_number || s.id, s.applicant_name, s.company_name, s.lob, s.status, s.risk_score, s.priority].join(','));
    const csv = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'submissions_export.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const columns: Column<Submission>[] = [
    { key: 'select', header: (
        <input type="checkbox" checked={allPageSelected} onChange={toggleSelectAll} className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
      ), render: (r) => (
        <input type="checkbox" checked={selectedIds.has(r.id)} onChange={() => toggleSelect(r.id)} onClick={(e) => e.stopPropagation()} className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500" />
      ),
    },
    { key: 'id', header: 'ID',render: (r) => <span className="font-mono text-xs">{r.submission_number || r.id}</span>, sortable: true, sortValue: (r) => r.submission_number || r.id },
    { key: 'applicant', header: 'Applicant', render: (r) => (
        <div>
          <p className="font-medium text-slate-900">{r.applicant_name}</p>
          <p className="text-xs text-slate-400">{r.company_name}</p>
        </div>
      ), sortable: true, sortValue: (r) => r.applicant_name },
    { key: 'lob', header: 'LOB', render: (r) => lobLabels[r.lob] ?? r.lob, sortable: true, sortValue: (r) => r.lob },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge label={r.status} variant={statusVariant[r.status] || 'gray'} /> },
    { key: 'risk', header: 'Risk Score', render: (r) => (
        <span className={`font-mono text-sm ${r.risk_score >= 70 ? 'text-red-600 font-semibold' : r.risk_score >= 40 ? 'text-amber-600' : 'text-slate-600'}`}>
          {r.risk_score || '—'}
        </span>
      ), sortable: true, sortValue: (r) => r.risk_score },
    { key: 'priority', header: 'Priority', render: (r) => <StatusBadge label={r.priority} variant={priorityVariant(r.priority)} /> },
    { key: 'assigned', header: 'Assigned To', render: (r) => r.assigned_to ?? <span className="text-slate-300">Unassigned</span> },
    { key: 'date', header: 'Received', render: (r) => r.received_date ? new Date(r.received_date).toLocaleDateString() : '—', sortable: true, sortValue: (r) => r.received_date },
    { key: 'actions', header: 'Actions', render: (r) => {
      const loading = actionLoading?.startsWith(r.id);
      return (
        <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
          {r.status === 'received' && (
            <button
              onClick={(e) => handleAction(r.id, 'triage', e)}
              disabled={!!loading}
              className="inline-flex items-center gap-1 rounded-md bg-blue-600 px-2.5 py-1 text-xs font-medium text-white shadow-sm hover:bg-blue-700 active:scale-[0.97] disabled:opacity-50 transition-all"
            >
              {actionLoading === `${r.id}-triage` ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />}
              Triage
            </button>
          )}
          {r.status === 'underwriting' && (
            <button
              onClick={(e) => handleAction(r.id, 'quote', e)}
              disabled={!!loading}
              className="inline-flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1 text-xs font-medium text-white shadow-sm hover:bg-green-700 active:scale-[0.97] disabled:opacity-50 transition-all"
            >
              {actionLoading === `${r.id}-quote` ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
              Quote
            </button>
          )}
          {r.status === 'quoted' && (
            <button
              onClick={(e) => handleAction(r.id, 'bind', e)}
              disabled={!!loading}
              className="inline-flex items-center gap-1 rounded-md bg-purple-600 px-2.5 py-1 text-xs font-medium text-white shadow-sm hover:bg-purple-700 active:scale-[0.97] disabled:opacity-50 transition-all"
            >
              {actionLoading === `${r.id}-bind` ? <Loader2 size={11} className="animate-spin" /> : null}
              Bind
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); navigate(`/submissions/${r.id}`); }}
            className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-all"
          >
            <Eye size={11} />
            View
          </button>
        </div>
      );
    }},
  ];

  if (isLoading) return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="skeleton-text" style={{ width: '160px', height: '28px' }} />
        <div className="skeleton" style={{ width: '140px', height: '36px', borderRadius: '0.5rem' }} />
      </div>
      <TableSkeleton rows={8} columns={8} />
    </div>
  );

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Submissions</h1>
          <p className="text-sm text-slate-500 mt-0.5">Manage and track insurance submissions</p>
        </div>
        <Link to="/submissions/new" className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
          <Plus size={16} /> New Submission
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search applicant, submission #…"
            value={searchQuery}
            onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
            className="rounded-lg border border-slate-200/60 bg-white pl-9 pr-3 py-2 text-sm text-slate-600 placeholder:text-slate-400 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition w-64"
          />
        </div>
        <select
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600"
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setCurrentPage(1); }}
        >
          <option value="all">All Statuses</option>
          {Object.keys(statusVariant).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600"
          value={lobFilter}
          onChange={(e) => { setLobFilter(e.target.value); setCurrentPage(1); }}
        >
          <option value="all">All LOBs</option>
          {Object.entries(lobLabels).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <span className="text-[11px] font-medium text-slate-400">{filtered.length} results</span>
        {selectedIds.size > 0 && (
          <div className="ml-auto flex items-center gap-2 rounded-lg border border-indigo-200/60 bg-indigo-50/50 px-3 py-1.5">
            <span className="text-sm font-medium text-indigo-700">Selected ({selectedIds.size})</span>
            <button onClick={handleExportSelected} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700">
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
        onRowClick={(r) => navigate(`/submissions/${r.id}`)}
      />

      {totalPages > 1 && (
        <div className="flex items-center justify-between rounded-xl border border-slate-200/60 bg-white px-4 py-3">
          <span className="text-xs text-slate-500">
            Showing {(currentPage - 1) * PAGE_SIZE + 1}–{Math.min(currentPage * PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-2">
            <button
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => p - 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft size={14} /> Previous
            </button>
            <span className="text-sm text-slate-700">Page {currentPage} of {totalPages}</span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => p + 1)}
              className="inline-flex items-center gap-1 rounded-md border border-slate-200/60 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Submissions;
