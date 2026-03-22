import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import StatusBadge from '../components/StatusBadge';
import TrafficLight from '../components/TrafficLight';
import ConfidenceBar from '../components/ConfidenceBar';
import TimelineEvent from '../components/TimelineEvent';
import { getUnderwriterQueue } from '../api/workbench';
import { TableSkeleton } from '../components/Skeleton';
import { formatDate } from '../utils/formatDate';
import type { UnderwriterQueueItem, LOB } from '../types';

const priorityVariant: Record<string, 'red' | 'orange' | 'yellow' | 'green'> = {
  urgent: 'red',
  high: 'orange',
  medium: 'yellow',
  low: 'green',
};

const lobLabels: Record<LOB, string> = {
  cyber: 'Cyber',
  professional_liability: 'Prof Liability',
  dnol: 'D&O',
  epli: 'EPLI',
  general_liability: 'General Liability',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

type Tab = 'analysis' | 'documents' | 'risk' | 'history';

const UnderwriterWorkbench: React.FC = () => {
  const { data: queue = [], isLoading } = useQuery({ queryKey: ['uw-queue'], queryFn: getUnderwriterQueue });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('analysis');

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
    // In a real app, this would call an API
    alert(`Action "${confirmAction}" confirmed with reason: ${actionReason}`);
    resetActions();
  };

  const authorityLimit = 500_000; // Example: underwriter's authority limit for premium
  const needsEscalation = selected ? selected.recommended_terms.premium > authorityLimit : false;

  if (isLoading) return <div className="space-y-4"><TableSkeleton rows={6} columns={8} /></div>;

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* ── Left Panel: Queue ── */}
      <div className="w-[40%] shrink-0 overflow-hidden rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
        <div className="border-b border-slate-200 px-4 py-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">Underwriter Workbench</h1>
          <p className="text-xs text-slate-500 mt-0.5">{queue.length} submissions assigned</p>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: 'calc(100% - 56px)' }}>
          <table className="min-w-full divide-y divide-slate-100">
            <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
              <tr>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Pri</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">ID</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Applicant</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">LOB</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Risk</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Conf</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Recommendation</th>
                <th className="px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Due</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {queue.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer transition-colors ${selectedId === item.id ? 'bg-indigo-50/60' : 'hover:bg-slate-50/50'}`}
                  onClick={() => handleSelect(item)}
                >
                  <td className="px-3 py-2"><StatusBadge label={item.priority} variant={priorityVariant[item.priority] ?? 'yellow'} /></td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700 max-w-[120px] truncate" title={item.id}>{item.submission_number || item.id.substring(0, 8) + '…'}</td>
                  <td className="px-3 py-2 text-xs text-slate-900">{item.applicant_name}</td>
                  <td className="px-3 py-2 text-xs text-slate-600">{lobLabels[item.lob]}</td>
                  <td className="px-3 py-2">
                    <span className={`font-mono text-xs ${item.risk_score >= 70 ? 'text-red-600 font-semibold' : item.risk_score >= 40 ? 'text-amber-600' : 'text-slate-500'}`}>
                      {item.risk_score || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">{item.confidence ? `${Math.round(item.confidence * 100)}%` : '—'}</td>
                  <td className="px-3 py-2 text-xs text-slate-600 max-w-[120px] truncate">{item.agent_recommendation}</td>
                  <td className="px-3 py-2 text-xs text-slate-500">{formatDate(item.due_date || item.received_date)}</td>
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
                  {selected.applicant_name} · {lobLabels[selected.lob]} · Received {formatDate(selected.received_date)}
                </p>
              </div>
              <TrafficLight confidence={selected.confidence} humanOversight={selected.confidence < 0.5 ? 'required' : selected.confidence < 0.8 ? 'recommended' : 'none'} />
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
                  {/* Risk Score Breakdown */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Risk Score Breakdown</h3>
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
                  {selected.comparable_accounts.length > 0 && (
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
                            {selected.comparable_accounts.map((ca, i) => (
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
                  )}

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

                  {/* Reasoning Chain */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-800">Reasoning Chain</h3>
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
                  {needsEscalation && (
                    <StatusBadge label="Needs Escalation" variant="orange" />
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UnderwriterWorkbench;
