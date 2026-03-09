import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import DataTable, { type Column } from '../components/DataTable';
import TrafficLight from '../components/TrafficLight';
import ConfidenceBar from '../components/ConfidenceBar';
import ReasoningPanel from '../components/ReasoningPanel';
import StatusBadge from '../components/StatusBadge';
import { getDecisions } from '../api/compliance';
import type { AgentDecision, AgentName, OversightLevel } from '../types';

const agentLabels: Record<AgentName, string> = {
  triage_agent: 'Triage Agent',
  underwriting_agent: 'Underwriting Agent',
  claims_agent: 'Claims Agent',
  compliance_agent: 'Compliance Agent',
  fraud_agent: 'Fraud Detection',
};

const oversightVariant: Record<OversightLevel, 'green' | 'yellow' | 'red'> = {
  none: 'green',
  recommended: 'yellow',
  required: 'red',
};

const AgentDecisions: React.FC = () => {
  const { data: decisions = [], isLoading } = useQuery({ queryKey: ['decisions'], queryFn: getDecisions });
  const [agentFilter, setAgentFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [oversightFilter, setOversightFilter] = useState<string>('all');
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const types = useMemo(() => [...new Set(decisions.map((d) => d.decision_type))], [decisions]);

  const filtered = useMemo(() => {
    let list = decisions;
    if (agentFilter !== 'all') list = list.filter((d) => d.agent === agentFilter);
    if (typeFilter !== 'all') list = list.filter((d) => d.decision_type === typeFilter);
    if (oversightFilter !== 'all') list = list.filter((d) => d.human_oversight === oversightFilter);
    return list;
  }, [decisions, agentFilter, typeFilter, oversightFilter]);

  const columns: Column<AgentDecision>[] = [
    {
      key: 'signal',
      header: '',
      render: (r) => <TrafficLight confidence={r.confidence} humanOversight={r.human_oversight} size="sm" />,
    },
    {
      key: 'id',
      header: 'Decision ID',
      render: (r) => <span className="font-mono text-xs">{r.id}</span>,
      sortable: true,
      sortValue: (r) => r.id,
    },
    {
      key: 'agent',
      header: 'Agent',
      render: (r) => agentLabels[r.agent] ?? r.agent,
      sortable: true,
      sortValue: (r) => r.agent,
    },
    {
      key: 'type',
      header: 'Type',
      render: (r) => <span className="capitalize">{r.decision_type.replace(/_/g, ' ')}</span>,
    },
    {
      key: 'confidence',
      header: 'Confidence',
      render: (r) => <div className="w-28"><ConfidenceBar value={r.confidence} /></div>,
      sortable: true,
      sortValue: (r) => r.confidence,
    },
    {
      key: 'oversight',
      header: 'Human Oversight',
      render: (r) => <StatusBadge label={r.human_oversight} variant={oversightVariant[r.human_oversight]} />,
    },
    {
      key: 'outcome',
      header: 'Outcome',
      render: (r) => <span className="max-w-[200px] truncate block">{r.outcome}</span>,
    },
    {
      key: 'timestamp',
      header: 'Timestamp',
      render: (r) => new Date(r.timestamp).toLocaleString(),
      sortable: true,
      sortValue: (r) => r.timestamp,
    },
  ];

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Agent Decisions</h1>
        <p className="text-sm text-slate-500">EU AI Act compliance view — human oversight of automated decisions</p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 rounded-lg border border-slate-200 bg-white px-4 py-2.5">
        <span className="text-xs font-semibold text-slate-500 uppercase">Traffic Light</span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
          <span className="h-3 w-3 rounded-full bg-green-500" /> Confidence ≥ 80%, no oversight needed
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
          <span className="h-3 w-3 rounded-full bg-amber-500" /> Confidence 50–80%, or oversight recommended
        </span>
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-600">
          <span className="h-3 w-3 rounded-full bg-red-500" /> Confidence &lt; 50%, or oversight required
        </span>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
        >
          <option value="all">All Agents</option>
          {Object.entries(agentLabels).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="all">All Types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700"
          value={oversightFilter}
          onChange={(e) => setOversightFilter(e.target.value)}
        >
          <option value="all">All Oversight Levels</option>
          <option value="none">None</option>
          <option value="recommended">Recommended</option>
          <option value="required">Required</option>
        </select>
        <span className="text-xs text-slate-400">{filtered.length} decisions</span>
      </div>

      <DataTable
        columns={columns}
        data={filtered}
        keyExtractor={(r) => r.id}
        onRowClick={(r) => setExpandedId(expandedId === r.id ? null : r.id)}
      />

      {/* Expanded reasoning panel */}
      {expandedId && (() => {
        const dec = decisions.find((d) => d.id === expandedId);
        if (!dec) return null;
        return (
          <div className="rounded-lg border-2 border-blue-200 bg-blue-50/30 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">Decision Detail — {dec.id}</h3>
              <button
                onClick={() => setExpandedId(null)}
                className="text-xs text-slate-400 hover:text-slate-600"
              >
                Close
              </button>
            </div>
            <ReasoningPanel
              agent={agentLabels[dec.agent] ?? dec.agent}
              decision={dec.outcome}
              confidence={dec.confidence}
              reasoning={dec.reasoning}
              timestamp={dec.timestamp}
              defaultOpen
            />
            <div className="mt-3 grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-slate-400">Oversight Level:</span>{' '}
                <StatusBadge label={dec.human_oversight} variant={oversightVariant[dec.human_oversight]} />
              </div>
              {dec.submission_id && (
                <div>
                  <span className="text-slate-400">Submission:</span>{' '}
                  <span className="font-mono text-xs">{dec.submission_id}</span>
                </div>
              )}
              {dec.claim_id && (
                <div>
                  <span className="text-slate-400">Claim:</span>{' '}
                  <span className="font-mono text-xs">{dec.claim_id}</span>
                </div>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default AgentDecisions;
