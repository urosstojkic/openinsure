import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Download, CheckCircle, XCircle, AlertTriangle, ArrowUpRight, FileText, Shield, Clock } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import ReasoningPanel from '../components/ReasoningPanel';
import TimelineEvent from '../components/TimelineEvent';
import Skeleton from '../components/Skeleton';
import { getSubmission, enrichSubmission } from '../api/submissions';
import type { SubmissionStatus } from '../types';

const statusVariant: Record<SubmissionStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'cyan'> = {
  received: 'blue', triaging: 'yellow', underwriting: 'orange', quoted: 'green', bound: 'purple', declined: 'red', referred: 'cyan',
};

const lobLabels: Record<string, string> = {
  cyber: 'Cyber Liability', professional_liability: 'Professional Liability', dnol: 'Directors & Officers',
  epli: 'Employment Practices', general_liability: 'General Liability',
};

const money = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

/* ── Submission Pipeline Visualization ── */
const PIPELINE_STEPS = [
  { key: 'received', label: 'Received', icon: FileText },
  { key: 'triaging', label: 'Triage', icon: Shield },
  { key: 'underwriting', label: 'Underwriting', icon: AlertTriangle },
  { key: 'quoted', label: 'Quote', icon: Clock },
  { key: 'bound', label: 'Bind', icon: CheckCircle },
];

const STATUS_ORDER: Record<string, number> = {
  received: 0, triaging: 1, underwriting: 2, quoted: 3, bound: 4, declined: -1, referred: -1,
};

function Pipeline({ status }: { status: SubmissionStatus }) {
  const currentStep = STATUS_ORDER[status] ?? -1;
  const isTerminal = status === 'declined' || status === 'referred';

  return (
    <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Submission Pipeline</h2>
      <div className="flex items-center">
        {PIPELINE_STEPS.map((step, i) => {
          const Icon = step.icon;
          const isDone = !isTerminal && currentStep > i;
          const isActive = !isTerminal && currentStep === i;
          // isPending derived from isTerminal/currentStep (available if needed)

          return (
            <React.Fragment key={step.key}>
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full transition-all ${
                    isDone
                      ? 'bg-emerald-500 text-white shadow-sm shadow-emerald-500/20'
                      : isActive
                      ? 'bg-indigo-500 text-white shadow-sm shadow-indigo-500/20 ring-4 ring-indigo-100'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isDone ? <CheckCircle size={16} /> : <Icon size={16} />}
                </div>
                <span className={`text-[11px] font-medium ${
                  isDone ? 'text-emerald-600' : isActive ? 'text-indigo-600' : 'text-slate-400'
                }`}>
                  {step.label}
                </span>
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`mx-1.5 h-0.5 flex-1 rounded-full ${
                  !isTerminal && currentStep > i ? 'bg-emerald-300' : 'bg-slate-200'
                }`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      {isTerminal && (
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-red-50 px-3 py-2">
          <XCircle size={14} className="text-red-500" />
          <span className="text-xs font-medium text-red-700">
            Submission {status === 'declined' ? 'declined' : 'referred for manual review'}
          </span>
        </div>
      )}
    </div>
  );
}

function EnrichmentSection({ submissionId, metadata }: { submissionId: string; metadata: Record<string, unknown> }) {
  const queryClient = useQueryClient();
  const riskSummary = metadata?.risk_summary as { composite_risk_score?: number; security_grade?: string; breach_count?: number; credit_rating?: string; enriched_at?: string } | undefined;

  const enrichMutation = useMutation({
    mutationFn: () => enrichSubmission(submissionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['submission', submissionId] });
    },
  });

  const gradeColor = (grade: string) => {
    if (grade === 'A') return 'text-emerald-600 bg-emerald-50';
    if (grade === 'B') return 'text-blue-600 bg-blue-50';
    if (grade === 'C') return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-bold text-slate-900">Data Enrichment</h2>
        <button
          onClick={() => enrichMutation.mutate()}
          disabled={enrichMutation.isPending}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {enrichMutation.isPending ? 'Enriching...' : riskSummary ? 'Re-Enrich' : 'Enrich Now'}
        </button>
      </div>

      {enrichMutation.isError && (
        <p className="text-sm text-red-500 mb-3">Enrichment failed. Please try again.</p>
      )}

      {riskSummary ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Risk Score</p>
              <p className="mt-1 text-xl font-bold text-slate-900">
                {typeof riskSummary.composite_risk_score === 'number'
                  ? (riskSummary.composite_risk_score * 100).toFixed(0)
                  : '—'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Security Grade</p>
              <p className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-lg font-bold ${gradeColor(riskSummary.security_grade || 'N/A')}`}>
                {riskSummary.security_grade || 'N/A'}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Breach Count</p>
              <p className="mt-1 text-xl font-bold text-slate-900">{riskSummary.breach_count ?? '—'}</p>
            </div>
            <div className="rounded-xl border border-slate-200/60 bg-slate-50/30 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Credit Rating</p>
              <p className="mt-1 text-xl font-bold text-slate-900">{riskSummary.credit_rating || '—'}</p>
            </div>
          </div>
          {riskSummary.enriched_at && (
            <p className="text-[11px] text-slate-400">
              Last enriched: {new Date(riskSummary.enriched_at).toLocaleString()}
            </p>
          )}
        </div>
      ) : (
        <p className="text-sm text-slate-400">
          No enrichment data available. Click &quot;Enrich Now&quot; to query external data sources.
        </p>
      )}
    </div>
  );
}

const SubmissionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: sub, isLoading } = useQuery({
    queryKey: ['submission', id],
    queryFn: () => getSubmission(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton variant="rect" width={36} height={36} className="rounded-lg" />
          <div className="flex-1 space-y-2">
            <Skeleton variant="text" width="200px" height={24} />
            <Skeleton variant="text" width="300px" height={14} />
          </div>
        </div>
        <Skeleton variant="rect" width="100%" height={80} className="rounded-xl" />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2 space-y-6">
            <Skeleton variant="rect" width="100%" height={200} className="rounded-xl" />
            <Skeleton variant="rect" width="100%" height={160} className="rounded-xl" />
          </div>
          <div className="space-y-6">
            <Skeleton variant="rect" width="100%" height={180} className="rounded-xl" />
            <Skeleton variant="rect" width="100%" height={240} className="rounded-xl" />
          </div>
        </div>
      </div>
    );
  }
  if (!sub) return (
    <div className="flex h-64 flex-col items-center justify-center gap-2">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
        <FileText size={24} className="text-slate-400" />
      </div>
      <p className="text-sm text-slate-400">Submission not found</p>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/submissions')}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">{sub.id}</h1>
            <StatusBadge label={sub.status} variant={statusVariant[sub.status]} />
          </div>
          <p className="mt-0.5 text-sm text-slate-500">{sub.company_name} · {lobLabels[sub.lob]}</p>
        </div>
      </div>

      {/* ── Pipeline ── */}
      <Pipeline status={sub.status} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Left column: details ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Submission info */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Submission Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Applicant</dt><dd className="mt-0.5 font-medium text-slate-800">{sub.applicant_name}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Company</dt><dd className="mt-0.5 font-medium text-slate-800">{sub.company_name}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Industry</dt><dd className="mt-0.5 font-medium text-slate-800">{sub.industry}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Line of Business</dt><dd className="mt-0.5 font-medium text-slate-800">{lobLabels[sub.lob]}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Annual Revenue</dt><dd className="mt-0.5 font-semibold text-slate-800">{money(sub.annual_revenue)}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Employee Count</dt><dd className="mt-0.5 font-medium text-slate-800">{sub.employee_count.toLocaleString()}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Requested Coverage</dt><dd className="mt-0.5 font-semibold text-slate-800">{money(sub.requested_coverage)}</dd></div>
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Received Date</dt><dd className="mt-0.5 font-medium text-slate-800">{new Date(sub.received_date).toLocaleDateString()}</dd></div>
            </dl>
          </div>

          {/* Cyber risk panel */}
          {sub.cyber_risk_data && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Cyber Risk Assessment</h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Security Rating</dt>
                  <dd className="mt-0.5 flex items-center gap-2">
                    <span className="text-lg font-bold text-slate-800">{sub.cyber_risk_data.security_rating}</span>
                    <span className="text-xs text-slate-400">/ 100</span>
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Open Vulnerabilities</dt>
                  <dd className={`mt-0.5 text-lg font-bold ${sub.cyber_risk_data.open_vulnerabilities > 5 ? 'text-red-600' : 'text-slate-800'}`}>
                    {sub.cyber_risk_data.open_vulnerabilities}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Last Breach</dt>
                  <dd className="mt-0.5 font-medium text-slate-800">{sub.cyber_risk_data.last_breach ?? 'None reported'}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">3rd Party Risk Score</dt>
                  <dd className="mt-0.5 flex items-center gap-2">
                    <span className="text-lg font-bold text-slate-800">{sub.cyber_risk_data.third_party_risk_score}</span>
                    <span className="text-xs text-slate-400">/ 100</span>
                  </dd>
                </div>
              </dl>
              <div className="mt-4 flex flex-wrap gap-2">
                {sub.cyber_risk_data.mfa_enabled && <StatusBadge label="MFA Enabled" variant="green" />}
                {sub.cyber_risk_data.encryption_at_rest && <StatusBadge label="Encryption at Rest" variant="green" />}
                {sub.cyber_risk_data.incident_response_plan && <StatusBadge label="IR Plan" variant="green" />}
                {sub.cyber_risk_data.employee_training && <StatusBadge label="Security Training" variant="green" />}
              </div>
            </div>
          )}

          {/* Documents */}
          {sub.documents.length > 0 && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Documents</h2>
              <div className="space-y-2">
                {sub.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50/30 p-3 transition-colors hover:bg-slate-50">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-50 text-indigo-500">
                        <FileText size={14} />
                      </div>
                      <div>
                        <p className="text-[13px] font-medium text-slate-800">{doc.name}</p>
                        <p className="text-[11px] text-slate-400">{(doc.size / 1000).toFixed(0)} KB · {new Date(doc.uploaded_at).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <button className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white hover:text-slate-600">
                      <Download size={14} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Triage result */}
          {sub.triage_result && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Triage Result</h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm">
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Appetite Match</dt>
                  <dd className="mt-1">{sub.triage_result.appetite_match ? <StatusBadge label="Yes" variant="green" /> : <StatusBadge label="No" variant="red" />}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Risk Score</dt>
                  <dd className="mt-0.5 text-lg font-bold text-slate-800">{sub.triage_result.risk_score}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Priority</dt>
                  <dd className="mt-0.5 font-medium text-slate-800 capitalize">{sub.triage_result.priority}</dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Timestamp</dt>
                  <dd className="mt-0.5 font-medium text-slate-800">{new Date(sub.triage_result.timestamp).toLocaleString()}</dd>
                </div>
              </dl>
              {sub.triage_result.flags.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-1.5">
                  {sub.triage_result.flags.map((f, i) => (
                    <StatusBadge key={i} label={f} variant="blue" size="sm" />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Agent recommendation */}
          {sub.agent_recommendation && (
            <div className="space-y-3">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-slate-400">Agent Recommendation</h2>
              <ReasoningPanel
                agent={sub.agent_recommendation.agent}
                decision={sub.agent_recommendation.decision}
                confidence={sub.agent_recommendation.confidence}
                reasoning={sub.agent_recommendation.reasoning}
                timestamp={sub.agent_recommendation.timestamp}
                defaultOpen
              />
              {sub.agent_recommendation.recommended_premium && (
                <div className="rounded-xl border border-emerald-200/60 bg-emerald-50/50 p-4">
                  <p className="text-sm font-semibold text-emerald-800">
                    Recommended Premium: {money(sub.agent_recommendation.recommended_premium)}
                  </p>
                  {sub.agent_recommendation.recommended_terms && (
                    <ul className="mt-2 space-y-1">
                      {sub.agent_recommendation.recommended_terms.map((t, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-emerald-700">
                          <CheckCircle size={12} className="mt-1 shrink-0 text-emerald-500" />
                          {t}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* ── Right column: actions + timeline ── */}
        <div className="space-y-6">
          {/* Action buttons */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Actions</h2>
            <div className="space-y-2">
              <button className="flex w-full items-center gap-2.5 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-700 hover:shadow-md hover:shadow-emerald-500/25 active:scale-[0.98]">
                <CheckCircle size={15} /> Approve Quote
              </button>
              <button className="flex w-full items-center gap-2.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 transition-all hover:bg-indigo-700 hover:shadow-md hover:shadow-indigo-500/25 active:scale-[0.98]">
                <AlertTriangle size={15} /> Modify Terms
              </button>
              <button className="flex w-full items-center gap-2.5 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-red-500/20 transition-all hover:bg-red-700 hover:shadow-md hover:shadow-red-500/25 active:scale-[0.98]">
                <XCircle size={15} /> Decline
              </button>
              <button className="flex w-full items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98]">
                <ArrowUpRight size={15} /> Escalate
              </button>
            </div>
          </div>

          {/* Confidence summary */}
          {sub.agent_recommendation && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">AI Confidence</h2>
              <ConfidenceBar value={sub.agent_recommendation.confidence} height="h-3" />
              <p className="mt-2.5 text-[11px] leading-relaxed text-slate-500">
                {sub.agent_recommendation.confidence >= 0.8
                  ? 'High confidence — automated processing eligible'
                  : sub.agent_recommendation.confidence >= 0.5
                  ? 'Medium confidence — human review recommended'
                  : 'Low confidence — human review required'}
              </p>
            </div>
          )}

          {/* Decision history */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Decision History</h2>
            {sub.decision_history && sub.decision_history.length > 0 ? (
              sub.decision_history.map((ev, i) => (
                <TimelineEvent
                  key={ev.id}
                  timestamp={ev.timestamp}
                  actor={ev.actor}
                  action={ev.action}
                  details={ev.details}
                  isAgent={ev.is_agent}
                  isLast={i === sub.decision_history.length - 1}
                />
              ))
            ) : (
              <p className="text-sm text-slate-400">No decisions recorded yet</p>
            )}
          </div>
        </div>
      </div>

      {/* Data Enrichment (#80) */}
      <EnrichmentSection submissionId={sub.id} metadata={(sub as any).metadata || {}} />
    </div>
  );
};

export default SubmissionDetail;
