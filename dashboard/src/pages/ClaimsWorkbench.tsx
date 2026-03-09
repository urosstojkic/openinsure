import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import StatusBadge from '../components/StatusBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import TimelineEvent from '../components/TimelineEvent';
import { getClaimsQueue } from '../api/workbench';
import type { ClaimsQueueItem, ClaimStatus, ClaimSeverity } from '../types';

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

type Tab = 'assessment' | 'timeline' | 'documents' | 'financials';

const ClaimsWorkbench: React.FC = () => {
  const { data: queue = [], isLoading } = useQuery({ queryKey: ['claims-queue'], queryFn: getClaimsQueue });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('assessment');

  // Action state
  const [activeAction, setActiveAction] = useState<string | null>(null);
  const [actionAmount, setActionAmount] = useState('');
  const [actionPayee, setActionPayee] = useState('');
  const [actionReason, setActionReason] = useState('');
  const [closeReason, setCloseReason] = useState('settled');

  const selected = queue.find((q) => q.id === selectedId) ?? null;

  const handleSelect = (item: ClaimsQueueItem) => {
    setSelectedId(item.id);
    setTab('assessment');
    setActiveAction(null);
  };

  const settlementAuthority = 250_000;
  const needsEscalation = selected ? Number(actionAmount) > settlementAuthority : false;

  const handleSubmitAction = () => {
    alert(`Action "${activeAction}" submitted. Amount: ${actionAmount}, Reason: ${actionReason}`);
    setActiveAction(null);
    setActionAmount('');
    setActionPayee('');
    setActionReason('');
  };

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;

  return (
    <div className="flex h-[calc(100vh-7rem)] gap-4">
      {/* ── Left Panel: Claims Queue ── */}
      <div className="w-[40%] shrink-0 overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-3">
          <h1 className="text-lg font-bold text-slate-900">Claims Workbench</h1>
          <p className="text-xs text-slate-500">{queue.length} assigned claims</p>
        </div>
        <div className="overflow-y-auto" style={{ maxHeight: 'calc(100% - 56px)' }}>
          <table className="min-w-full divide-y divide-slate-100">
            <thead className="sticky top-0 bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Claim #</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Policy</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Status</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Severity</th>
                <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Loss Date</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Reserve</th>
                <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {queue.map((item) => (
                <tr
                  key={item.id}
                  className={`cursor-pointer transition-colors ${selectedId === item.id ? 'bg-blue-50' : 'hover:bg-slate-50'}`}
                  onClick={() => handleSelect(item)}
                >
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{item.claim_number}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-500">{item.policy_number}</td>
                  <td className="px-3 py-2"><StatusBadge label={item.status} variant={statusVariant[item.status]} /></td>
                  <td className="px-3 py-2"><StatusBadge label={item.severity} variant={severityVariant[item.severity]} /></td>
                  <td className="px-3 py-2 text-xs text-slate-600">{item.loss_date}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs text-slate-700">{money(item.reserve)}</td>
                  <td className="px-3 py-2 text-right text-xs text-slate-600">{item.days_open}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Right Panel: Detail ── */}
      <div className="flex-1 overflow-hidden rounded-lg border border-slate-200 bg-white">
        {!selected ? (
          <div className="flex h-full items-center justify-center text-slate-400">
            Select a claim from the queue
          </div>
        ) : (
          <div className="flex h-full flex-col">
            {/* Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-bold text-slate-900">{selected.claim_number}</h2>
                  <StatusBadge label={selected.severity} variant={severityVariant[selected.severity]} />
                </div>
                <p className="text-xs text-slate-500">
                  {selected.insured_name} · {selected.policy_number}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <p className="text-xs text-slate-500">Fraud Score</p>
                  <p className={`text-sm font-bold ${selected.fraud_score > 0.5 ? 'text-red-600' : selected.fraud_score > 0.2 ? 'text-amber-600' : 'text-green-600'}`}>
                    {Math.round(selected.fraud_score * 100)}%
                  </p>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex border-b border-slate-200 px-5">
              {([['assessment', 'Agent Assessment'], ['timeline', 'Timeline'], ['documents', 'Documents'], ['financials', 'Financials']] as const).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setTab(key)}
                  className={`border-b-2 px-4 py-2.5 text-sm font-medium transition-colors ${tab === key ? 'border-blue-600 text-blue-700' : 'border-transparent text-slate-500 hover:text-slate-700'}`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-y-auto p-5">
              {tab === 'assessment' && (
                <div className="space-y-5">
                  {/* Coverage Verification */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-700">Coverage Verification</h3>
                    <div className={`rounded-lg border p-4 ${selected.coverage_verification.status === 'verified' ? 'border-green-200 bg-green-50' : selected.coverage_verification.status === 'pending' ? 'border-amber-200 bg-amber-50' : 'border-red-200 bg-red-50'}`}>
                      <div className="flex items-center gap-2 mb-2">
                        <StatusBadge label={selected.coverage_verification.status} variant={selected.coverage_verification.status === 'verified' ? 'green' : selected.coverage_verification.status === 'pending' ? 'yellow' : 'red'} />
                        <span className="text-sm text-slate-700">
                          Policy {selected.coverage_verification.policy_active ? 'Active' : 'Inactive'} ·
                          {selected.coverage_verification.within_coverage ? ' Within coverage' : ' Coverage question'}
                        </span>
                      </div>
                      <p className="text-xs text-slate-600">{selected.coverage_verification.notes}</p>
                      <div className="mt-2 flex flex-wrap gap-1">
                        {selected.coverage_verification.exclusions_checked.map((ex, i) => (
                          <span key={i} className="rounded bg-white px-2 py-0.5 text-xs text-slate-500 border border-slate-200">{ex} ✓</span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Reserve Recommendation */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-700">Initial Reserve Recommendation</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-lg border border-slate-200 p-3">
                        <p className="text-xs text-slate-500">Indemnity</p>
                        <p className="text-lg font-bold text-slate-900">{money(selected.reserve_recommendation.recommended_indemnity)}</p>
                      </div>
                      <div className="rounded-lg border border-slate-200 p-3">
                        <p className="text-xs text-slate-500">Expense</p>
                        <p className="text-lg font-bold text-slate-900">{money(selected.reserve_recommendation.recommended_expense)}</p>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center gap-2">
                      <span className="text-xs text-slate-500">Confidence:</span>
                      <div className="w-32"><ConfidenceBar value={selected.reserve_recommendation.confidence} /></div>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">{selected.reserve_recommendation.basis}</p>
                  </div>

                  {/* Comparable Claims */}
                  <div>
                    <h3 className="mb-3 text-sm font-semibold text-slate-700">Comparable Claims</h3>
                    <div className="overflow-x-auto rounded border border-slate-100">
                      <table className="min-w-full text-sm">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Claim #</th>
                            <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Type</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Settled</th>
                            <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Duration</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                          {selected.comparable_claims.map((cc, i) => (
                            <tr key={i}>
                              <td className="px-3 py-2 font-mono text-xs text-slate-700">{cc.claim_number}</td>
                              <td className="px-3 py-2 text-slate-600">{cc.type}</td>
                              <td className="px-3 py-2 text-right font-mono text-slate-700">{money(cc.settled_amount)}</td>
                              <td className="px-3 py-2 text-right text-slate-600">{cc.duration_days} days</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Fraud Indicators */}
                  {selected.fraud_indicators.length > 0 && (
                    <div>
                      <h3 className="mb-3 text-sm font-semibold text-slate-700">Fraud Indicators</h3>
                      <div className="space-y-2">
                        {selected.fraud_indicators.map((fi, i) => (
                          <div key={i} className="flex items-center gap-3 rounded border border-slate-100 px-3 py-2">
                            <StatusBadge label={fi.severity} variant={fi.severity === 'high' ? 'red' : fi.severity === 'medium' ? 'yellow' : 'green'} />
                            <div>
                              <p className="text-sm font-medium text-slate-700">{fi.indicator}</p>
                              <p className="text-xs text-slate-500">{fi.description}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {tab === 'timeline' && (
                <div>
                  <h3 className="mb-3 text-sm font-semibold text-slate-700">Claim Timeline</h3>
                  {selected.timeline.map((ev, i) => (
                    <TimelineEvent
                      key={i}
                      timestamp={ev.timestamp}
                      actor={ev.actor}
                      action={ev.event}
                      details={ev.details}
                      isAgent={ev.is_agent}
                      isLast={i === selected.timeline.length - 1}
                    />
                  ))}
                </div>
              )}

              {tab === 'documents' && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-slate-700">Claim Documents</h3>
                  {selected.claim_documents.map((doc) => (
                    <div key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3">
                      <div>
                        <p className="text-sm font-medium text-slate-900">{doc.name}</p>
                        <p className="text-xs text-slate-400">
                          <StatusBadge label={doc.category.replace(/_/g, ' ')} variant="gray" className="mr-2" />
                          {new Date(doc.uploaded_at).toLocaleDateString()}
                        </p>
                      </div>
                      <button className="text-xs text-blue-600 hover:text-blue-800">View</button>
                    </div>
                  ))}
                </div>
              )}

              {tab === 'financials' && (
                <div className="space-y-5">
                  <h3 className="text-sm font-semibold text-slate-700">Financial Summary</h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="rounded-lg border border-slate-200 p-4">
                      <p className="text-xs text-slate-500">Indemnity Reserve</p>
                      <p className="text-xl font-bold text-slate-900">{money(selected.financials.indemnity_reserve)}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 p-4">
                      <p className="text-xs text-slate-500">Expense Reserve</p>
                      <p className="text-xl font-bold text-slate-900">{money(selected.financials.expense_reserve)}</p>
                    </div>
                    <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                      <p className="text-xs text-blue-600">Total Incurred</p>
                      <p className="text-xl font-bold text-blue-900">{money(selected.financials.total_incurred)}</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="rounded-lg border border-slate-200 p-4">
                      <p className="text-xs text-slate-500">Indemnity Paid</p>
                      <p className="text-xl font-bold text-slate-900">{money(selected.financials.indemnity_paid)}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 p-4">
                      <p className="text-xs text-slate-500">Expense Paid</p>
                      <p className="text-xl font-bold text-slate-900">{money(selected.financials.expense_paid)}</p>
                    </div>
                    <div className="rounded-lg border border-slate-200 p-4">
                      <p className="text-xs text-slate-500">Recovery</p>
                      <p className="text-xl font-bold text-slate-900">{money(selected.financials.recovery)}</p>
                    </div>
                  </div>

                  {/* Summary bar */}
                  <div className="rounded-lg border border-slate-200 p-4">
                    <h4 className="mb-2 text-xs font-semibold text-slate-600">Reserve Utilization</h4>
                    <div className="flex items-center gap-3">
                      <div className="flex-1">
                        <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-3 rounded-full bg-blue-500"
                            style={{ width: `${((selected.financials.indemnity_paid + selected.financials.expense_paid) / selected.financials.total_incurred) * 100}%` }}
                          />
                        </div>
                      </div>
                      <span className="text-xs text-slate-600">
                        {money(selected.financials.indemnity_paid + selected.financials.expense_paid)} paid of {money(selected.financials.total_incurred)}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* ── Action Panel ── */}
            <div className="border-t border-slate-200 bg-slate-50 px-5 py-3">
              {activeAction && (
                <div className="mb-3 rounded-lg border border-blue-200 bg-blue-50 p-3">
                  <p className="mb-2 text-sm font-semibold text-slate-900">{activeAction}</p>
                  {(activeAction === 'Update Reserve' || activeAction === 'Approve Settlement') && (
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-xs text-slate-500">Amount</label>
                        <input type="number" className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm" placeholder="$0" value={actionAmount} onChange={(e) => setActionAmount(e.target.value)} />
                      </div>
                      {activeAction === 'Approve Settlement' && (
                        <div>
                          <label className="text-xs text-slate-500">Payee</label>
                          <input type="text" className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm" value={actionPayee} onChange={(e) => setActionPayee(e.target.value)} />
                        </div>
                      )}
                    </div>
                  )}
                  {activeAction === 'Close Claim' && (
                    <div>
                      <label className="text-xs text-slate-500">Close Reason</label>
                      <select className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm" value={closeReason} onChange={(e) => setCloseReason(e.target.value)}>
                        <option value="settled">Settled</option>
                        <option value="withdrawn">Withdrawn</option>
                        <option value="denied">Denied</option>
                        <option value="subrogation">Subrogation Complete</option>
                      </select>
                    </div>
                  )}
                  <div className="mt-2">
                    <label className="text-xs text-slate-500">Reason / Notes</label>
                    <textarea className="mt-1 w-full rounded border border-slate-300 px-2 py-1 text-sm" rows={2} placeholder="Required for audit trail…" value={actionReason} onChange={(e) => setActionReason(e.target.value)} />
                  </div>
                  {needsEscalation && activeAction === 'Approve Settlement' && (
                    <div className="mt-2 rounded bg-amber-50 border border-amber-200 px-3 py-1.5 text-xs text-amber-800">
                      ⚠ Amount exceeds settlement authority ({money(settlementAuthority)}). Requires CCO approval.
                    </div>
                  )}
                  <div className="mt-2 flex gap-2">
                    <button onClick={handleSubmitAction} disabled={!actionReason.trim()} className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50">
                      Submit
                    </button>
                    <button onClick={() => setActiveAction(null)} className="rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">Cancel</button>
                  </div>
                </div>
              )}

              {!activeAction && (
                <div className="flex items-center gap-3">
                  <button onClick={() => setActiveAction('Update Reserve')} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                    Update Reserve
                  </button>
                  <button onClick={() => setActiveAction('Approve Settlement')} className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">
                    Approve Settlement
                  </button>
                  <button onClick={() => setActiveAction('Escalate to CCO')} className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600">
                    Escalate to CCO
                  </button>
                  <button onClick={() => setActiveAction('Close Claim')} className="rounded-lg bg-slate-600 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700">
                    Close Claim
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ClaimsWorkbench;
