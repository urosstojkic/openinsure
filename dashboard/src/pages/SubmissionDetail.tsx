import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Download, CheckCircle, XCircle, AlertTriangle, ArrowUpRight, FileText, Shield, Clock, Loader2, ExternalLink, Sparkles, Play } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import ConfidenceBar from '../components/ConfidenceBar';
import ReasoningPanel from '../components/ReasoningPanel';
import RiskGauge from '../components/RiskGauge';
import JourneyTimeline from '../components/JourneyTimeline';
import type { JourneyStep } from '../components/JourneyTimeline';
import TimelineEvent from '../components/TimelineEvent';
import Skeleton from '../components/Skeleton';
import { ToastContainer } from '../components/Toast';
import { useToast } from '../components/useToast';
import { getSubmission, enrichSubmission, bindSubmission, declineSubmission, referSubmission } from '../api/submissions';
import client from '../api/client';
import type { SubmissionStatus } from '../types';
import { lobDisplayName } from '../utils/lobLabels';

const statusVariant: Record<SubmissionStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'cyan'> = {
  received: 'blue', triaging: 'yellow', underwriting: 'orange', quoted: 'green', bound: 'purple', declined: 'red', referred: 'cyan',
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

function Pipeline({ status, decisionHistory }: { status: SubmissionStatus; decisionHistory?: Array<{ timestamp: string; action: string }> }) {
  const currentStep = STATUS_ORDER[status] ?? -1;
  const isTerminal = status === 'declined' || status === 'referred';

  const steps: JourneyStep[] = PIPELINE_STEPS.map((step) => {
    const event = decisionHistory?.find(e => e.action?.toLowerCase().includes(step.key));
    return { ...step, timestamp: event?.timestamp };
  });

  return (
    <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
      <h2 className="mb-5 text-xs font-semibold uppercase tracking-wider text-slate-400">Submission Journey</h2>
      <JourneyTimeline
        steps={steps}
        currentStepIndex={currentStep}
        isTerminal={isTerminal}
        terminalLabel={status === 'declined' ? 'Submission declined' : status === 'referred' ? 'Referred for manual review' : undefined}
      />
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
  const queryClient = useQueryClient();
  const { toasts, addToast, dismissToast } = useToast();
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const { data: sub, isLoading } = useQuery({
    queryKey: ['submission', id],
    queryFn: () => getSubmission(id!),
    enabled: !!id,
  });

  const [bindConfirmOpen, setBindConfirmOpen] = useState(false);

  const handleAction = async (action: 'triage' | 'quote' | 'bind' | 'decline' | 'refer') => {
    if (!id) return;
    setActionLoading(action);
    try {
      if (action === 'triage' || action === 'quote') {
        const { data } = await client.post(`/submissions/${id}/${action}`);
        await queryClient.invalidateQueries({ queryKey: ['submission', id] });
        if (action === 'triage') {
          const score = data?.risk_score ?? data?.risk_data?.risk_score ?? '—';
          addToast('success', `Triaged! Risk score: ${score}`);
        } else {
          const premium = data?.premium ?? data?.quote?.premium;
          addToast('success', premium != null ? `Quoted! Premium: ${money(premium)}` : 'Quote generated successfully!');
        }
      } else {
        const fns = { bind: bindSubmission, decline: declineSubmission, refer: referSubmission };
        const data = await fns[action](id);
        await queryClient.invalidateQueries({ queryKey: ['submission', id] });
        if (action === 'bind') {
          const policyId = (data as Record<string, unknown>)?.policy_id ?? '';
          addToast('success', policyId ? `Bound! Policy created: ${policyId}` : 'Policy bound successfully!');
        } else if (action === 'decline') {
          addToast('success', 'Submission declined.');
        } else {
          addToast('success', 'Submission escalated for manual review.');
        }
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Unknown error';
      const labels: Record<string, string> = { triage: 'triage', quote: 'quote', bind: 'bind', decline: 'decline', refer: 'escalate' };
      addToast('error', `Failed to ${labels[action]}: ${msg}`);
    } finally {
      setActionLoading(null);
    }
  };

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
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      {/* Header — #126: show submission_number instead of raw UUID */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate('/submissions')}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300"
        >
          <ArrowLeft size={16} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">{sub.submission_number || sub.id}</h1>
            <StatusBadge label={sub.status} variant={statusVariant[sub.status]} />
          </div>
          <p className="mt-0.5 text-sm text-slate-500">
            {sub.company_name} · {lobDisplayName(sub.lob)}
            {sub.submission_number && (
              <span className="ml-2 text-xs text-slate-400">ID: {sub.id}</span>
            )}
          </p>
        </div>
      </div>

      {/* ── Pipeline ── */}
      <Pipeline status={sub.status} decisionHistory={sub.decision_history} />

      {/* ── #120: AI Triage & Underwriting Results ── */}
      {(sub.risk_score > 0 || sub.quoted_premium || sub.recommendation) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Risk Score with color coding */}
          {sub.risk_score > 0 && (
            <div className="rounded-2xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-card)] flex flex-col items-center">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-3">Risk Score</p>
              <RiskGauge value={sub.risk_score * 10} displayValue={sub.risk_score} size={110} label={sub.risk_score < 4 ? 'Low' : sub.risk_score < 7 ? 'Medium' : 'High'} thresholds={[40, 70]} />
              <p className="mt-2 text-xs text-slate-500">Scale: 0-10</p>
            </div>
          )}

          {/* Quoted Premium */}
          {sub.quoted_premium != null && sub.quoted_premium > 0 && (
            <div className="rounded-xl border border-indigo-200/60 bg-indigo-50/50 p-4 shadow-[var(--shadow-xs)]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Quoted Premium</p>
              <p className="mt-1 text-3xl font-bold text-indigo-700">{money(sub.quoted_premium)}</p>
              <p className="mt-0.5 text-xs text-slate-500">Annual premium</p>
            </div>
          )}

          {/* Recommendation */}
          {sub.recommendation && (
            <div className="rounded-xl border border-slate-200/60 bg-white p-4 shadow-[var(--shadow-xs)]">
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Recommendation</p>
              <p className={`mt-1 text-lg font-bold capitalize ${
                sub.recommendation.includes('proceed') || sub.recommendation.includes('approve')
                  ? 'text-emerald-700'
                  : sub.recommendation.includes('decline')
                  ? 'text-red-700'
                  : 'text-amber-700'
              }`}>
                {sub.recommendation.replace(/_/g, ' ')}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Rating Breakdown */}
      {sub.rating_breakdown && (
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Rating Breakdown</h2>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Base Premium</p>
              <p className="mt-0.5 text-lg font-bold text-slate-800">{sub.rating_breakdown.base_premium}</p>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Adjusted Premium</p>
              <p className="mt-0.5 text-lg font-bold text-slate-800">{sub.rating_breakdown.adjusted_premium}</p>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400">Final Premium</p>
              <p className="mt-0.5 text-lg font-bold text-emerald-700">{sub.rating_breakdown.final_premium}</p>
            </div>
          </div>
          {Object.keys(sub.rating_breakdown.factors_applied).length > 0 && (
            <div>
              <p className="text-[10px] font-medium uppercase tracking-wider text-slate-400 mb-3">Factors Applied</p>
              <div className="space-y-2.5">
                {Object.entries(sub.rating_breakdown.factors_applied).map(([key, value]) => {
                  const numVal = typeof value === 'number' ? value : parseFloat(String(value)) || 1;
                  const barWidth = Math.min(100, Math.max(10, (numVal / 2) * 100));
                  const barColor = numVal < 1 ? 'bg-emerald-400' : numVal <= 1.2 ? 'bg-amber-400' : 'bg-red-400';
                  return (
                    <div key={key}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs font-medium text-slate-600 capitalize">{key.replace(/_/g, ' ')}</span>
                        <span className={`text-xs font-bold tabular-nums ${numVal < 1 ? 'text-emerald-600' : numVal <= 1.2 ? 'text-amber-600' : 'text-red-600'}`}>{numVal.toFixed(2)}×</span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                        <div className={`h-2 rounded-full ${barColor} transition-all duration-500`} style={{ width: `${barWidth}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
          {sub.rating_breakdown.warnings.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {sub.rating_breakdown.warnings.map((w, i) => (
                <StatusBadge key={i} label={w} variant="yellow" size="sm" />
              ))}
            </div>
          )}
        </div>
      )}

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
              <div><dt className="text-[11px] font-medium uppercase tracking-wider text-slate-400">Line of Business</dt><dd className="mt-0.5 font-medium text-slate-800">{lobDisplayName(sub.lob)}</dd></div>
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
          {/* Action buttons — status-aware (#129) */}
          <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-400">Actions</h2>
            <div className="space-y-2">
              {/* received → Triage */}
              {sub.status === 'received' && (
                <button
                  onClick={() => handleAction('triage')}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-blue-500/20 transition-all hover:bg-blue-700 hover:shadow-md hover:shadow-blue-500/25 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'triage' ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
                  Triage
                </button>
              )}

              {/* underwriting → Quote */}
              {sub.status === 'underwriting' && (
                <button
                  onClick={() => handleAction('quote')}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-green-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-green-500/20 transition-all hover:bg-green-700 hover:shadow-md hover:shadow-green-500/25 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'quote' ? <Loader2 size={15} className="animate-spin" /> : <Play size={15} />}
                  Quote
                </button>
              )}

              {/* quoted → Bind (with confirmation) */}
              {sub.status === 'quoted' && (
                <button
                  onClick={() => setBindConfirmOpen(true)}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-purple-500/20 transition-all hover:bg-purple-700 hover:shadow-md hover:shadow-purple-500/25 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'bind' ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle size={15} />}
                  Bind Policy
                </button>
              )}

              {/* bound → View Policy */}
              {sub.status === 'bound' && sub.policy_id && (
                <Link
                  to={`/policies/${sub.policy_id}`}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-purple-500/20 transition-all hover:bg-purple-700 hover:shadow-md hover:shadow-purple-500/25 active:scale-[0.98]"
                >
                  <ExternalLink size={15} /> View Policy
                </Link>
              )}
              {sub.status === 'bound' && !sub.policy_id && (
                <p className="text-sm text-slate-400">Policy bound — no policy ID available yet.</p>
              )}

              {/* declined */}
              {sub.status === 'declined' && (
                <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2.5">
                  <XCircle size={15} className="text-red-500" />
                  <span className="text-sm font-medium text-red-700">Declined</span>
                </div>
              )}

              {/* Escalate available for received, underwriting, quoted */}
              {['received', 'underwriting', 'quoted'].includes(sub.status) && (
                <button
                  onClick={() => handleAction('refer')}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 hover:border-slate-300 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'refer' ? <Loader2 size={15} className="animate-spin" /> : <ArrowUpRight size={15} />}
                  Escalate
                </button>
              )}

              {/* Decline available for received, underwriting, quoted */}
              {['received', 'underwriting', 'quoted'].includes(sub.status) && (
                <button
                  onClick={() => handleAction('decline')}
                  disabled={!!actionLoading}
                  className="flex w-full items-center gap-2.5 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm shadow-red-500/20 transition-all hover:bg-red-700 hover:shadow-md hover:shadow-red-500/25 active:scale-[0.98] disabled:opacity-50"
                >
                  {actionLoading === 'decline' ? <Loader2 size={15} className="animate-spin" /> : <XCircle size={15} />}
                  Decline
                </button>
              )}
            </div>
          </div>

          {/* Bind confirmation dialog (#122) */}
          <ConfirmDialog
            open={bindConfirmOpen}
            title="Confirm Bind"
            message="Are you sure you want to bind this submission? This will create a policy."
            confirmLabel="Confirm Bind"
            cancelLabel="Cancel"
            variant="warning"
            onConfirm={() => {
              setBindConfirmOpen(false);
              handleAction('bind');
            }}
            onCancel={() => setBindConfirmOpen(false)}
          />

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
