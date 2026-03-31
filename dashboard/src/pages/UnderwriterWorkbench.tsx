import React, { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Sparkles } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import TrafficLight from '../components/TrafficLight';
import ConfidenceBar from '../components/ConfidenceBar';
import TimelineEvent from '../components/TimelineEvent';
import ProcessWorkflowModal from '../components/ProcessWorkflowModal';
import { getUnderwriterQueue } from '../api/workbench';
import { processSubmission } from '../api/submissions';
import { TableSkeleton } from '../components/Skeleton';
import { formatDate } from '../utils/formatDate';
import type { UnderwriterQueueItem } from '../types';
import { lobShortName, lobDisplayName } from '../utils/lobLabels';

const priorityVariant: Record<string, 'red' | 'orange' | 'yellow' | 'green'> = {
  urgent: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'green',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

/** Risk level badge based on risk score (0-10 scale) */
function riskBadge(score: number) {
  if (score > 7) return <StatusBadge label="High Risk" variant="red" />;
  if (score >= 4) return <StatusBadge label="Medium Risk" variant="yellow" />;
  return <StatusBadge label="Low Risk" variant="green" />;
}

/** Derive row color class based on confidence & recommendation */
function rowColorClass(item: UnderwriterQueueItem): string {
  const rec = (item.agent_recommendation || '').toLowerCase();
  const conf = item.confidence ?? 0;

  if (rec.includes('decline') || conf < 0.5) return 'bg-red-50/60 hover:bg-red-50';
  if (conf >= 0.7 && rec.includes('quote') && !rec.includes('refer')) return 'bg-emerald-50/50 hover:bg-emerald-50';
  if (rec.includes('refer') || (conf >= 0.5 && conf < 0.7)) return 'bg-amber-50/50 hover:bg-amber-50';
  return 'hover:bg-slate-50/50';
}

type Tab = 'analysis' | 'documents' | 'risk' | 'history';

const UnderwriterWorkbench: React.FC = () => {
  const queryClient = useQueryClient();
  const { data: queue = [], isLoading } = useQuery({ queryKey: ['uw-queue'], queryFn: getUnderwriterQueue });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('analysis');

  // "Process with AI" modal state (#71)
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [processingLabel, setProcessingLabel] = useState('');

  // Decision panel state
  const [showDecline, setShowDecline] = useState(false);
  const [showModify, setShowModify] = useState(false);
  const [actionReason, setActionReason] = useState('');
  const [modLimit, setModLimit] = useState(0);
  const [modDeductible, setModDeductible] = useState(0);
  const [modPremium, setModPremium] = useState(0);
  const [modConditions, setModConditions] = useState('');
  const [confirmAction, setConfirmAction] = useState<string | null>(null);

  const selected = queue.find((q) => q.id === selectedId) ?? null;

  const handleSelect = (item: UnderwriterQueueItem) => {
    setSelectedId(item.id);
    setTab('analysis');
    setShowDecline(false);
    setShowModify(false);
    setActionReason('');
    setConfirmAction(null);
    if (item.recommended_terms) {
      setModLimit(item.recommended_terms.limit);
      setModDeductible(item.recommended_terms.deductible);
      setModPremium(item.recommended_terms.premium);
    }
  };

  const resetActions = () => {
    setShowDecline(false);
    setShowModify(false);
    setActionReason('');
    setConfirmAction(null);
  };

  const handleConfirmAction = () => {
    alert(`Action "${confirmAction}" confirmed with reason: ${actionReason}`);
    resetActions();
  };

  const authorityLimit = 500_000;
  const needsEscalation = selected ? selected.recommended_terms.premium > authorityLimit : false;

  /** Can this item be processed with AI? */
  const canProcess = (item: UnderwriterQueueItem) =>
    ['received', 'triaging', 'underwriting', 'quoted'].includes(item.status);

  if (isLoading) return <div className="space-y-4"><TableSkeleton rows={6} columns={8} /></div>;

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* ── Left Panel: Queue ── */}
      <div className="w-[44%] shrink-0 overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
        <div className="border-b border-slate-200 px-4 py-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">Underwriter Workbench</h1>
          <p className="text-xs text-slate-500 mt-0.5">{queue.length} submissions assigned</p>
        </div>
        <div className="overflow-auto" style={{ maxHeight: 'calc(100% - 56px)' }}>
          <table className="min-w-full divide-y divide-slate-100">
            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
              <tr>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Pri</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Applicant</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">LOB</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Risk</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Conf</th>
                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {queue.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer transition-colors ${selectedId === item.id ? 'bg-indigo-50/60' : rowColorClass(item)}`}
                  onClick={() => handleSelect(item)}
                >
                  <td className="px-3 py-2"><StatusBadge label={item.priority} variant={priorityVariant[item.priority] ?? 'yellow'} /></td>
                  <td className="px-3 py-2">
                    <div className="text-xs font-medium text-slate-900 truncate max-w-[140px]">{item.applicant_name}</div>
                    <div className="text-[10px] text-slate-400 font-mono">{item.submission_number || item.id.substring(0, 8)}</div>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{lobShortName(item.lob)}</td>
                  <td className="px-3 py-2">
                    <span className={`font-mono text-xs ${item.risk_score >= 7 ? 'text-red-600 font-semibold' : item.risk_score >= 4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {item.risk_score ? `${item.risk_score}/10` : '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{item.confidence ? `${Math.round(item.confidence * 100)}%` : '—'}</td>
                  <td className="px-3 py-2 text-right whitespace-nowrap">
                    {canProcess(item) ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setProcessingId(item.id);
                          setProcessingLabel(item.submission_number || item.id.substring(0, 8));
                        }}
                        title="Process with AI"
                        className="inline-flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-500 px-3 py-1.5 text-[11px] font-semibold text-white shadow-sm shadow-indigo-500/20 hover:from-indigo-600 hover:to-purple-600 active:scale-[0.97] transition-all"
                      >
                        <Sparkles size={13} />
                        Process
                      </button>
                    ) : (
                      <span className="text-[10px] text-slate-400 capitalize">{item.status}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Right Panel: Detail ── */}
      <div className="flex-1 overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-slate-400">
            Select a submission from the queue
          </div>
        ) : (
          <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{selected.company_name}</h2>
                <p className="text-xs text-slate-500">
                  {selected.applicant_name} · {lobDisplayName(selected.lob)} · Received {formatDate(selected.received_date)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                {canProcess(selected) && (
                  <button
                    onClick={() => {
                      setProcessingId(selected.id);
                      setProcessingLabel(selected.submission_number || selected.id.substring(0, 8));
                    }}
                    className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 via-purple-500 to-violet-500 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-500/25 hover:from-indigo-600 hover:via-purple-600 hover:to-violet-600 active:scale-[0.97] transition-all"
                  >
                    <Sparkles size={16} />
                    Process with AI
                  </button>
                )}
                <TrafficLight confidence={selected.confidence} humanOversight={selected.confidence < 0.5 ? 'required' : selected.confidence < 0.8 ? 'recommended' : 'none'} />
                {selected.risk_score > 0 && riskBadge(selected.risk_score)}
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-slate-200 px-5">
              {([['analysis', 'Agent Analysis'], ['documents', 'Documents'], ['risk', 'Risk Data'], ['history', 'History']] as const).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${tab === key ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-slate-400 hover:text-slate-600'}`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-5">
              {tab === 'analysis' && (
                <div className="space-y-5">
                  {/* Applicant Info (#68) */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Applicant Information</h3>
                    <div className="grid grid-cols-2 gap-3">
                      {[
                        ['Name', selected.applicant_name],
                        ['Company', selected.company_name],
                        ['Industry', selected.industry || '—'],
                        ['Revenue', selected.annual_revenue ? money(selected.annual_revenue) : '—'],
                        ['Employees', selected.employee_count ? selected.employee_count.toLocaleString() : '—'],
                        ['Line of Business', lobDisplayName(selected.lob)],
                      ].map(([label, value]) => (
                        <div key={label} className="flex items-center justify-between rounded border border-slate-100 px-3 py-2">
                          <span className="text-xs text-slate-500">{label}</span>
                          <span className="text-sm font-medium text-slate-900">{value}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Cyber Risk Data (#68) */}
                  {selected.cyber_risk_data && (
                    <div>
                      <h3 className="mb-3 text-sm font-semibold text-slate-800">Cyber Risk Data</h3>
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          ['Security Posture', `${selected.cyber_risk_data.security_rating}/100`],
                          ['MFA Enabled', selected.cyber_risk_data.mfa_enabled ? '✓ Yes' : '✗ No'],
                          ['Endpoint Protection', selected.cyber_risk_data.encryption_at_rest ? '✓ Active' : '✗ Missing'],
                          ['Open Vulnerabilities', String(selected.cyber_risk_data.open_vulnerabilities)],
                          ['IR Plan', selected.cyber_risk_data.incident_response_plan ? '✓ Yes' : '✗ No'],
                          ['3rd-Party Risk', `${selected.cyber_risk_data.third_party_risk_score}/100`],
                        ].map(([label, value]) => (
                          <div key={label} className="flex items-center justify-between rounded border border-slate-100 px-3 py-2">
                            <span className="text-xs text-slate-500">{label}</span>
                            <span className="text-sm font-medium text-slate-900">{value}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Agent Risk Assessment — Factor Breakdown (#68) */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Agent Risk Assessment</h3>
                    <div className="flex items-center gap-4 mb-3">
                      <div className="rounded-lg border border-slate-200 px-3 py-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Risk Score</span>
                        <p className={`text-xl font-bold ${selected.risk_score >= 7 ? 'text-red-600' : selected.risk_score >= 4 ? 'text-amber-600' : 'text-emerald-600'}`}>
                          {selected.risk_score || '—'}<span className="text-sm text-slate-400">/10</span>
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200 px-3 py-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Confidence</span>
                        <div className="mt-1 w-28"><ConfidenceBar value={selected.confidence} /></div>
                      </div>
                      <div className="rounded-lg border border-slate-200 px-3 py-2">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">Recommendation</span>
                        <p className="text-sm font-semibold text-slate-800">{selected.agent_recommendation || '—'}</p>
                      </div>
                    </div>
                    {selected.risk_factors.length > 0 ? (
                      <div className="space-y-2">
                        {selected.risk_factors.map((rf, i) => (
                          <div key={i} className="flex items-center gap-3">
                            <span className={`h-2 w-2 rounded-full ${rf.impact === 'positive' ? 'bg-green-500' : rf.impact === 'negative' ? 'bg-red-500' : 'bg-amber-500'}`} />
                            <span className="w-36 text-sm font-medium text-slate-700">{rf.factor}</span>
                            <div className="w-24"><ConfidenceBar value={rf.score / 100} showLabel={false} /></div>
                            <span className="text-xs text-slate-500">{rf.description}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-400">No risk factor data available</p>
                    )}
                  </div>

                  {/* Comparable Accounts */}
                  {(() => {
                    const PLACEHOLDER_RE = /^(Industry\s+)?Peer\s+[A-Z]$/i;
                    const realAccounts = selected.comparable_accounts.filter((ca) => ca.company && !PLACEHOLDER_RE.test(ca.company));
                    if (realAccounts.length === 0) return (
                      <div>
                        <h3 className="mb-3 text-sm font-semibold text-slate-800">Comparable Accounts</h3>
                        <p className="text-sm text-slate-400">No comparable accounts available</p>
                      </div>
                    );
                    return (
                      <div>
                        <h3 className="mb-3 text-sm font-semibold text-slate-800">Comparable Accounts</h3>
                        <div className="overflow-x-auto rounded-xl border border-slate-200/60">
                          <table className="min-w-full text-sm">
                            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
                              <tr>
                                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Company</th>
                                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Industry</th>
                                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Premium</th>
                                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Limit</th>
                                <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Loss Ratio</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-50">
                              {realAccounts.map((ca, i) => (
                                <tr key={i}>
                                  <td className="px-3 py-2 text-slate-700">{ca.company}</td>
                                  <td className="px-3 py-2 text-slate-500">{ca.industry}</td>
                                  <td className="px-3 py-2 text-right font-mono text-slate-700">{money(ca.premium)}</td>
                                  <td className="px-3 py-2 text-right font-mono text-slate-700">{money(ca.limit)}</td>
                                  <td className="px-3 py-2 text-right font-mono text-slate-700">{Math.round(ca.loss_ratio * 100)}%</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })()}

                  {/* Recommended Terms */}
                  {selected.recommended_terms.premium > 0 && (
                    <div>
                      <h3 className="mb-3 text-sm font-semibold text-slate-800">Recommended Terms</h3>
                      <div className="grid grid-cols-3 gap-4">
                        <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Limit</p>
                          <p className="text-lg font-bold text-slate-900">{money(selected.recommended_terms.limit)}</p>
                        </div>
                        <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Deductible</p>
                          <p className="text-lg font-bold text-slate-900">{money(selected.recommended_terms.deductible)}</p>
                        </div>
                        <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Premium</p>
                          <p className="text-lg font-bold text-slate-900">{money(selected.recommended_terms.premium)}</p>
                        </div>
                      </div>
                      {selected.recommended_terms.conditions.length > 0 && (
                        <ul className="mt-2 list-inside list-disc text-xs text-slate-600">
                          {selected.recommended_terms.conditions.map((c, i) => <li key={i}>{c}</li>)}
                        </ul>
                      )}
                    </div>
                  )}

                  {/* Rating Breakdown */}
                  {selected.rating_breakdown && (
                    <div>
                      <h3 className="mb-3 text-sm font-semibold text-slate-800">Rating Breakdown</h3>
                      <div className="rounded-xl border border-slate-200/60 overflow-hidden">
                        <table className="min-w-full text-sm">
                          <thead className="bg-slate-50/80">
                            <tr>
                              <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Factor</th>
                              <th className="px-4 py-2 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Value</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-50">
                            <tr>
                              <td className="px-4 py-2 text-slate-700">Base Premium</td>
                              <td className="px-4 py-2 text-right font-mono text-slate-900">{money(Number(selected.rating_breakdown.base_premium))}</td>
                            </tr>
                            {Object.entries(selected.rating_breakdown.factors_applied || {}).map(([factor, value]) => (
                              <tr key={factor}>
                                <td className="px-4 py-2 text-slate-600 pl-8">
                                  {factor.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                                </td>
                                <td className="px-4 py-2 text-right font-mono text-slate-700">{String(value)}×</td>
                              </tr>
                            ))}
                            <tr className="bg-slate-50/60">
                              <td className="px-4 py-2 text-slate-700">Adjusted Premium</td>
                              <td className="px-4 py-2 text-right font-mono text-slate-900">{money(Number(selected.rating_breakdown.adjusted_premium))}</td>
                            </tr>
                            <tr className="bg-indigo-50/60 font-semibold">
                              <td className="px-4 py-2 text-indigo-900">Final Premium</td>
                              <td className="px-4 py-2 text-right font-mono text-indigo-900">{money(Number(selected.rating_breakdown.final_premium))}</td>
                            </tr>
                          </tbody>
                        </table>
                        {selected.rating_breakdown.explanation && (
                          <div className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
                            {selected.rating_breakdown.explanation}
                          </div>
                        )}
                        {(selected.rating_breakdown.warnings?.length ?? 0) > 0 && (
                          <div className="border-t border-amber-100 bg-amber-50 px-4 py-2 text-xs text-amber-700">
                            {selected.rating_breakdown.warnings.map((w: string, i: number) => <p key={i}>⚠ {w}</p>)}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Agent Recommendation & Reasoning Chain (#68) */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Agent Recommendation</h3>
                    {selected.agent_recommendation && (
                      <div className="mb-3 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5">
                        <p className="text-sm font-semibold text-indigo-800">{selected.agent_recommendation}</p>
                        <p className="text-xs text-indigo-600 mt-0.5">
                          Confidence: {Math.round(selected.confidence * 100)}% · Risk Score: {selected.risk_score}/10
                        </p>
                      </div>
                    )}
                    {selected.reasoning_chain.length > 0 ? (
                      <ol className="space-y-1">
                        {selected.reasoning_chain.map((step, i) => (
                          <li key={i} className="flex gap-2 text-sm text-slate-600">
                            <span className="shrink-0 font-mono text-xs text-slate-400">{i + 1}.</span>
                            {step}
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="text-sm text-slate-400">No reasoning data available</p>
                    )}
                    {/* Decision Record link */}
                    <div className="mt-3">
                      <a
                        href={`/decisions?submission=${selected.id}`}
                        className="text-xs font-medium text-indigo-600 hover:text-indigo-800 hover:underline"
                      >
                        View Decision Record →
                      </a>
                    </div>
                  </div>
                </div>
              )}

              {tab === 'documents' && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-800">Extracted Documents</h3>
                  {selected.documents.length === 0 ? (
                    <p className="text-sm text-slate-400">No documents uploaded</p>
                  ) : (
                    <div className="space-y-2">
                      {selected.documents.map((doc) => (
                        <div key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                          <div>
                            <p className="text-sm font-medium text-slate-900">{doc.name}</p>
                            <p className="text-xs text-slate-400">{doc.type} · {(doc.size / 1000).toFixed(0)} KB · Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}</p>
                          </div>
                           <button className="text-xs text-indigo-600 hover:text-indigo-800">View</button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === 'risk' && (
                <div className="space-y-5">
                  <h3 className="text-sm font-semibold text-slate-800">Cyber Risk Profile</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Annual Revenue</p>
                      <p className="text-lg font-bold text-slate-900">{money(selected.annual_revenue)}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Employees</p>
                      <p className="text-lg font-bold text-slate-900">{selected.employee_count.toLocaleString()}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Industry</p>
                      <p className="text-lg font-bold text-slate-900">{selected.industry}</p>
                    </div>
                    <div className="rounded-xl border border-slate-200/60 p-3 shadow-[var(--shadow-xs)]">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Requested Coverage</p>
                      <p className="text-lg font-bold text-slate-900">{money(selected.requested_coverage)}</p>
                    </div>
                  </div>
                  {selected.cyber_risk_data ? (
                    <>
                      <h3 className="text-sm font-semibold text-slate-800">Security Controls</h3>
                      <div className="grid grid-cols-2 gap-3">
                        {[
                          ['Security Rating', `${selected.cyber_risk_data.security_rating}/100`],
                          ['Open Vulnerabilities', String(selected.cyber_risk_data.open_vulnerabilities)],
                          ['Last Breach', selected.cyber_risk_data.last_breach ?? 'None'],
                          ['MFA Enabled', selected.cyber_risk_data.mfa_enabled ? '✓ Yes' : '✗ No'],
                          ['Encryption at Rest', selected.cyber_risk_data.encryption_at_rest ? '✓ Yes' : '✗ No'],
                          ['IR Plan', selected.cyber_risk_data.incident_response_plan ? '✓ Yes' : '✗ No'],
                          ['Employee Training', selected.cyber_risk_data.employee_training ? '✓ Yes' : '✗ No'],
                          ['3rd-Party Risk Score', `${selected.cyber_risk_data.third_party_risk_score}/100`],
                        ].map(([label, value]) => (
                          <div key={label} className="flex items-center justify-between rounded border border-slate-100 px-3 py-2">
                            <span className="text-sm text-slate-600">{label}</span>
                            <span className="text-sm font-medium text-slate-900">{value}</span>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-slate-400">No cyber risk data available</p>
                  )}
                </div>
              )}

              {tab === 'history' && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-800">Decision Timeline</h3>
                  {selected.decision_history.length > 0 ? (
                    selected.decision_history.map((ev, i) => (
                      <TimelineEvent
                        key={ev.id}
                        timestamp={ev.timestamp}
                        actor={ev.actor}
                        action={ev.action}
                        details={ev.details}
                        isAgent={ev.is_agent}
                        isLast={i === selected.decision_history.length - 1}
                      />
                    ))
                  ) : (
                    <p className="text-sm text-slate-400">No decisions recorded yet</p>
                  )}
                </div>
              )}
            </div>

            {/* ── Decision Panel ── */}
            <div className="border-t border-slate-200 bg-slate-50 px-5 py-3">
              {needsEscalation && (
                <div className="mb-2 rounded bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-800">
                  ⚠ Premium exceeds your authority limit ({money(authorityLimit)}). Approval requires escalation.
                </div>
              )}

              {confirmAction && (
                <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
                  <p className="text-sm font-medium text-slate-900">Confirm: {confirmAction}</p>
                  <textarea
                    className="mt-2 w-full rounded-lg border border-slate-200/60 px-3 py-2 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
                    placeholder="Reason (required for audit trail)…"
                    rows={2}
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={handleConfirmAction}
                      disabled={!actionReason.trim()}
                      className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50 transition-all"
                    >
                      Confirm
                    </button>
                    <button onClick={resetActions} className="rounded border border-slate-200/60 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 transition-all">
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {showModify && !confirmAction && (
                <div className="mb-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="mb-2 text-sm font-semibold text-slate-900">Modify Terms</p>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Limit</label>
                      <input type="number" className="mt-1 w-full rounded-lg border border-slate-200/60 px-2 py-1 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition" value={modLimit} onChange={(e) => setModLimit(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Deductible</label>
                      <input type="number" className="mt-1 w-full rounded-lg border border-slate-200/60 px-2 py-1 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition" value={modDeductible} onChange={(e) => setModDeductible(Number(e.target.value))} />
                    </div>
                    <div>
                      <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Premium</label>
                      <input type="number" className="mt-1 w-full rounded-lg border border-slate-200/60 px-2 py-1 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition" value={modPremium} onChange={(e) => setModPremium(Number(e.target.value))} />
                    </div>
                  </div>
                  <div className="mt-2">
                    <label className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Additional Conditions</label>
                    <input type="text" className="mt-1 w-full rounded-lg border border-slate-200/60 px-2 py-1 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition" placeholder="Add conditions…" value={modConditions} onChange={(e) => setModConditions(e.target.value)} />
                  </div>
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => setConfirmAction('Modify Terms')} className="rounded bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-700 transition-all">Submit Modified Terms</button>
                    <button onClick={resetActions} className="rounded border border-slate-200/60 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 transition-all">Cancel</button>
                  </div>
                </div>
              )}

              {showDecline && !confirmAction && (
                <div className="mb-3 rounded-xl border border-red-200 bg-red-50 p-3">
                  <p className="mb-2 text-sm font-semibold text-slate-900">Decline Reason</p>
                  <textarea
                    className="w-full rounded-lg border border-slate-200/60 px-3 py-2 text-sm focus:border-indigo-400 focus:ring-1 focus:ring-indigo-400 outline-none transition"
                    placeholder="Provide decline reason (required)…"
                    rows={2}
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                  />
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => setConfirmAction('Decline')}
                      disabled={!actionReason.trim()}
                      className="rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm shadow-red-500/20 hover:bg-red-700 active:scale-[0.98] disabled:opacity-50 transition-all"
                    >
                      Confirm Decline
                    </button>
                    <button onClick={resetActions} className="rounded border border-slate-200/60 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 transition-all">Cancel</button>
                  </div>
                </div>
              )}

              {!showModify && !showDecline && !confirmAction && (
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setConfirmAction('Approve Quote')}
                    className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
                  >
                    Approve Quote
                  </button>
                  <button
                    onClick={() => setShowModify(true)}
                    className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600"
                  >
                    Modify Terms
                  </button>
                  <button
                    onClick={() => setShowDecline(true)}
                    className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-red-500/20 hover:bg-red-700 active:scale-[0.98] transition-all"
                  >
                    Decline
                  </button>
                  <button
                    onClick={() => setConfirmAction('Refer')}
                    className="rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-100 transition-all"
                  >
                    Refer
                  </button>
                  {needsEscalation && (
                    <StatusBadge label="Needs Escalation" variant="orange" />
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* "Process with AI" workflow modal (#71) */}
      {processingId && (
        <ProcessWorkflowModal
          mode="submission"
          itemId={processingId}
          itemLabel={processingLabel}
          onClose={() => setProcessingId(null)}
          onComplete={() => {
            queryClient.invalidateQueries({ queryKey: ['uw-queue'] });
          }}
          processFunc={processSubmission}
        />
      )}
    </div>
  );
};

export default UnderwriterWorkbench;
