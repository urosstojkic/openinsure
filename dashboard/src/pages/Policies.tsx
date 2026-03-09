import React, { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import DataTable, { type Column } from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import { getPolicies } from '../api/policies';
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
  const { data: policies = [], isLoading } = useQuery({ queryKey: ['policies'], queryFn: getPolicies });
  const [statusFilter, setStatusFilter] = useState<string>('all');

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
  ];

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
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
