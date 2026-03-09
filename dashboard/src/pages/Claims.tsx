import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { getClaims } from '../api/claims';
import type { Claim, ClaimStatus, ClaimSeverity } from '../types';

const statusVariant: Record<ClaimStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'red' | 'purple'> = {
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
  const { data: claims = [], isLoading } = useQuery({ queryKey: ['claims'], queryFn: getClaims });
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');

  const filtered = useMemo(() => {
    let list = claims;
    if (statusFilter !== 'all') list = list.filter((c) => c.status === statusFilter);
    if (severityFilter !== 'all') list = list.filter((c) => c.severity === severityFilter);
    return list;
  }, [claims, statusFilter, severityFilter]);

  const columns: Column<Claim>[] = [
    { key: 'number', header: 'Claim Number', render: (r) => <span className="font-mono text-xs">{r.claim_number}</span>, sortable: true, sortValue: (r) => r.claim_number },
    { key: 'policy', header: 'Policy', render: (r) => <span className="font-mono text-xs">{r.policy_number}</span> },
    { key: 'status', header: 'Status', render: (r) => <StatusBadge label={r.status} variant={statusVariant[r.status]} /> },
    { key: 'loss_date', header: 'Loss Date', render: (r) => r.loss_date, sortable: true, sortValue: (r) => r.loss_date },
    { key: 'severity', header: 'Severity', render: (r) => <StatusBadge label={r.severity} variant={severityVariant[r.severity]} /> },
    { key: 'incurred', header: 'Total Incurred', render: (r) => money(r.total_incurred), sortable: true, sortValue: (r) => r.total_incurred },
    { key: 'assigned', header: 'Assigned To', render: (r) => r.assigned_to },
  ];

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
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
