import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import DataTable, { type Column } from '../components/DataTable';
import TrafficLight from '../components/TrafficLight';
import ConfidenceBar from '../components/ConfidenceBar';
import ReasoningPanel from '../components/ReasoningPanel';
import StatusBadge from '../components/StatusBadge';
import EmptyState from '../components/EmptyState';
import { TableSkeleton } from '../components/Skeleton';
import { getDecisions } from '../api/compliance';
import { formatTimestamp } from '../utils/formatDate';
import type { AgentDecision, AgentName, OversightLevel } from '../types';
import { Bot, ChevronDown, Cpu, ExternalLink, Eye, EyeOff, ShieldCheck, Timer, X } from 'lucide-react';

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

const oversightIcon: Record<OversightLevel, React.ReactNode> = {
  none: <EyeOff size={14} className="text-green-600" />,
  recommended: <Eye size={14} className="text-amber-600" />,
  required: <ShieldCheck size={14} className="text-red-600" />,
};

function confidenceBadge(value: number) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.8
      ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
      : value >= 0.6
        ? 'bg-amber-50 text-amber-700 ring-amber-200'
        : 'bg-red-50 text-red-700 ring-red-200';
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1 ring-inset ${color}`}>
      {pct}%
    </span>
  );
}

function linkedEntityLink(dec: AgentDecision) {
  if (dec.submission_id) {
    return (
      <Link to={`/submissions/${dec.submission_id}`} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline text-sm font-mono">
        Submission {dec.submission_id.slice(0, 8)}… <ExternalLink size={12} />
      </Link>
    );
  }
  if (dec.claim_id) {
    return (
      <Link to={`/claims/${dec.claim_id}`} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline text-sm font-mono">
        Claim {dec.claim_id.slice(0, 8)}… <ExternalLink size={12} />
      </Link>
    );
  }
  if (dec.policy_id) {
    return (
      <Link to={`/policies/${dec.policy_id}`} className="inline-flex items-center gap-1 text-indigo-600 hover:text-indigo-800 hover:underline text-sm font-mono">
        Policy {dec.policy_id.slice(0, 8)}… <ExternalLink size={12} />
      </Link>
    );
  }
  if (dec.entity_id) {
    return <span className="text-sm font-mono text-slate-500">{dec.entity_type}: {dec.entity_id.slice(0, 8)}…</span>;
  }
  return <span className="text-sm text-slate-400">—</span>;
}

function renderOutputSummary(output: Record<string, unknown> | undefined) {
  if (!output || Object.keys(output).length === 0) return <span className="text-slate-400 text-sm">No output data</span>;

  return (
    <div className="space-y-1.5">
      {Object.entries(output).map(([key, value]) => {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        if (Array.isArray(value)) {
          return (
            <div key={key}>
              <span className="text-xs font-medium text-slate-500">{label}:</span>
              <ul className="ml-4 mt-0.5 list-disc space-y-0.5">
                {value.slice(0, 8).map((item, i) => (
                  <li key={i} className="text-sm text-slate-600">
                    {typeof item === 'object' ? JSON.stringify(item) : String(item)}
                  </li>
                ))}
                {value.length > 8 && (
                  <li className="text-xs text-slate-400">+ {value.length - 8} more</li>
                )}
              </ul>
            </div>
          );
        }
        if (typeof value === 'object' && value !== null) {
          return (
            <div key={key}>
              <span className="text-xs font-medium text-slate-500">{label}:</span>
              <pre className="mt-0.5 rounded-md bg-slate-50 px-2 py-1 text-xs text-slate-600 overflow-x-auto">{JSON.stringify(value, null, 2)}</pre>
            </div>
          );
        }
        return (
          <div key={key} className="flex items-baseline gap-2 text-sm">
            <span className="text-xs font-medium text-slate-500 shrink-0">{label}:</span>
            <span className="text-slate-700">{typeof value === 'boolean' ? (value ? '✓ Yes' : '✗ No') : String(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

function renderInputSummary(input: Record<string, unknown> | undefined) {
  if (!input || Object.keys(input).length === 0) return <span className="text-slate-400 text-sm">No input data</span>;
  return (
    <div className="flex flex-wrap gap-3">
      {Object.entries(input).map(([key, value]) => {
        const label = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        return (
          <div key={key} className="rounded-lg bg-slate-50 px-3 py-1.5 text-sm">
            <span className="text-xs font-medium text-slate-400">{label}</span>
            <div className="text-slate-700 font-mono text-xs mt-0.5">
              {typeof value === 'object' ? JSON.stringify(value) : String(value)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DecisionDetailPanel({ dec, onClose }: { dec: AgentDecision; onClose: () => void }) {
  return (
    <div className="border-t-2 border-indigo-200 bg-gradient-to-b from-indigo-50/40 to-white px-6 py-5">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu size={16} className="text-indigo-500" />
          <h3 className="text-sm font-bold text-slate-900">Decision Detail</h3>
          <span className="font-mono text-xs text-slate-400">{dec.id}</span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onClose(); }}
          className="rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          aria-label="Close detail panel"
        >
          <X size={16} />
        </button>
      </div>

      {/* Top metadata row */}
      <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Agent</span>
          <div className="mt-0.5 text-sm font-medium text-slate-800">{agentLabels[dec.agent] ?? dec.agent}</div>
          {dec.model_id && (
            <div className="text-xs text-slate-500 mt-0.5">{dec.model_id}{dec.model_version ? ` (${dec.model_version})` : ''}</div>
          )}
        </div>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Decision Type</span>
          <div className="mt-0.5 text-sm capitalize text-slate-800">{dec.decision_type.replace(/_/g, ' ')}</div>
        </div>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Confidence</span>
          <div className="mt-1 flex items-center gap-2">
            {confidenceBadge(dec.confidence)}
            <div className="w-20"><ConfidenceBar value={dec.confidence} showLabel={false} /></div>
          </div>
        </div>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Human Oversight</span>
          <div className="mt-1 flex items-center gap-1.5">
            {oversightIcon[dec.human_oversight]}
            <StatusBadge label={dec.human_oversight} variant={oversightVariant[dec.human_oversight]} />
          </div>
        </div>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Linked Entity</span>
          <div className="mt-1">{linkedEntityLink(dec)}</div>
        </div>
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Timestamp</span>
          <div className="mt-0.5 text-sm text-slate-700">{formatTimestamp(dec.timestamp || dec.created_at)}</div>
          {dec.processing_time_ms != null && (
            <div className="flex items-center gap-1 mt-0.5 text-xs text-slate-500">
              <Timer size={10} /> {dec.processing_time_ms}ms
            </div>
          )}
        </div>
      </div>

      {/* Reasoning */}
      <div className="mb-4">
        <ReasoningPanel
          agent={agentLabels[dec.agent] ?? dec.agent}
          decision={dec.outcome}
          confidence={dec.confidence}
          reasoning={dec.reasoning}
          timestamp={dec.timestamp || dec.created_at || ''}
          defaultOpen
        />
      </div>

      {/* Input + Output grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200/60 bg-white p-4">
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Input Summary</h4>
          {renderInputSummary(dec.input_summary)}
        </div>
        <div className="rounded-xl border border-slate-200/60 bg-white p-4">
          <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">Output</h4>
          <div className="max-h-64 overflow-y-auto">
            {renderOutputSummary(dec.output_summary)}
          </div>
        </div>
      </div>
    </div>
  );
}

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
      key: 'expand',
      header: '',
      render: (r) => (
        <ChevronDown
          size={14}
          className={`text-slate-400 transition-transform duration-200 ${expandedId === r.id ? 'rotate-180' : ''}`}
        />
      ),
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
      render: (r) => formatTimestamp(r.timestamp || r.created_at),
      sortable: true,
      sortValue: (r) => r.timestamp || r.created_at || '',
    },
  ];

  if (isLoading) return <div className="space-y-4"><TableSkeleton rows={6} columns={8} /></div>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Agent Decisions</h1>
        <p className="text-sm text-slate-500 mt-0.5">EU AI Act compliance view — human oversight of automated decisions</p>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 rounded-xl border border-slate-200/60 bg-white px-4 py-2.5 shadow-[var(--shadow-xs)]">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Traffic Light</span>
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
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
          value={agentFilter}
          onChange={(e) => setAgentFilter(e.target.value)}
        >
          <option value="all">All Agents</option>
          {Object.entries(agentLabels).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="all">All Types</option>
          {types.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select
          className="rounded-lg border border-slate-200/60 bg-white px-3 py-2 text-sm text-slate-600 focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
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

      {filtered.length === 0 ? (
        <EmptyState
          icon={Bot}
          title="No agent decisions yet"
          description="Process a submission to generate agent decisions. Decisions will appear here with confidence scores and oversight levels."
          action={{ label: "View Submissions", href: "/submissions" }}
        />
      ) : (
        <DataTable
          columns={columns}
          data={filtered}
          keyExtractor={(r) => r.id}
          onRowClick={(r) => setExpandedId(expandedId === r.id ? null : r.id)}
          expandedRowKey={expandedId}
          expandedRowRender={(dec) => (
            <DecisionDetailPanel dec={dec} onClose={() => setExpandedId(null)} />
          )}
        />
      )}
    </div>
  );
};

export default AgentDecisions;
