import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getEscalations, approveEscalation, rejectEscalation, type Escalation } from '../api/escalations';
import { useAuth } from '../context/AuthContext';
import EmptyState from '../components/EmptyState';
import { TableSkeleton } from '../components/Skeleton';
import { AlertTriangle } from 'lucide-react';

const ACTION_LABELS: Record<string, string> = {
  bind: 'Bind Policy',
  quote: 'Issue Quote',
  settle: 'Settle Claim',
  reserve: 'Set Reserve',
};

const Escalations: React.FC = () => {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('pending');
  const [modalItem, setModalItem] = useState<Escalation | null>(null);
  const [modalAction, setModalAction] = useState<'approve' | 'reject'>('approve');
  const [reason, setReason] = useState('');

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['escalations', statusFilter],
    queryFn: () => getEscalations(statusFilter || undefined),
  });

  const mutation = useMutation({
    mutationFn: (vars: { id: string; action: 'approve' | 'reject'; reason: string }) =>
      vars.action === 'approve'
        ? approveEscalation(vars.id, user.name, vars.reason)
        : rejectEscalation(vars.id, user.name, vars.reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['escalations'] });
      queryClient.invalidateQueries({ queryKey: ['escalation-count'] });
      setModalItem(null);
      setReason('');
    },
  });

  const openModal = (item: Escalation, action: 'approve' | 'reject') => {
    setModalItem(item);
    setModalAction(action);
    setReason('');
  };

  const handleSubmit = () => {
    if (!modalItem || !reason.trim()) return;
    mutation.mutate({ id: modalItem.id, action: modalAction, reason: reason.trim() });
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

  const fmtDate = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Escalation Queue</h1>
          <p className="text-sm text-slate-500 mt-0.5">Actions awaiting authority approval</p>
        </div>
        <div className="flex gap-2">
          {['pending', 'approved', 'rejected', ''].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                statusFilter === s
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-slate-500 hover:bg-slate-100'
              }`}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 border-b border-slate-100 bg-slate-50/80 backdrop-blur-sm">
            <tr>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Action</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Source Agent</th>
              <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Amount</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Reason</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Required Role</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Status</th>
              <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Created</th>
              <th className="px-4 py-3 text-center text-[11px] font-semibold uppercase tracking-wider text-slate-400">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="px-4 py-6">
                  <TableSkeleton rows={4} columns={8} />
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={8}>
                  <EmptyState
                    icon={AlertTriangle}
                    title="No escalations pending"
                    description="Escalations appear when agent actions exceed authority limits or require human approval."
                    action={{ label: "View Submissions", href: "/submissions" }}
                  />
                </td>
              </tr>
            ) : (
              items.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/50 transition-colors">
                  <td className="px-4 py-3 font-medium text-slate-800">
                    {ACTION_LABELS[item.action] ?? item.action}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    <span className="text-sm">{item.requested_by}</span>
                    <span className="ml-1 text-xs text-slate-400 font-mono">({item.entity_type} {item.entity_id.slice(0, 8)}…)</span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-slate-800">{fmt(item.amount)}</td>
                  <td className="px-4 py-3 text-xs text-slate-600 max-w-[200px] truncate" title={item.reason}>{item.reason || '—'}</td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-amber-200">
                      {item.required_role.replace('openinsure-', '')}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${
                      item.status === 'pending'
                        ? 'bg-amber-50 text-amber-700 ring-1 ring-amber-600/10'
                        : item.status === 'approved'
                        ? 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/10'
                        : 'bg-red-50 text-red-700 ring-1 ring-red-600/10'
                    }`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(item.created_at)}</td>
                  <td className="px-4 py-3 text-center">
                    {item.status === 'pending' ? (
                      <div className="flex items-center justify-center gap-1.5">
                        <button
                          onClick={() => openModal(item, 'approve')}
                          className="rounded-lg bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => openModal(item, 'reject')}
                          className="rounded-lg bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100 transition"
                        >
                          Reject
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400">
                        {item.resolved_by && `by ${item.resolved_by}`}
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {modalItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
            <h2 className="text-lg font-bold text-slate-900">
              {modalAction === 'approve' ? 'Approve' : 'Reject'} Escalation
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {ACTION_LABELS[modalItem.action] ?? modalItem.action} — {fmt(modalItem.amount)}
            </p>
            <textarea
              className="mt-4 w-full rounded-lg border border-slate-200/60 px-3 py-2 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
              rows={3}
              placeholder="Reason for decision…"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setModalItem(null)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 transition"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmit}
                disabled={!reason.trim() || mutation.isPending}
                className={`rounded-lg px-4 py-2 text-sm font-medium text-white transition ${
                  modalAction === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300'
                    : 'bg-red-600 hover:bg-red-700 disabled:bg-red-300'
                }`}
              >
                {mutation.isPending ? 'Saving…' : modalAction === 'approve' ? 'Approve' : 'Reject'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Escalations;
