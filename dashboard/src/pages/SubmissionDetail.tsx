import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Download, CheckCircle, XCircle, AlertTriangle, ArrowUpRight } from 'lucide-react';
import StatusBadge from '../components/StatusBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import ReasoningPanel from '../components/ReasoningPanel';
import TimelineEvent from '../components/TimelineEvent';
import { getSubmission } from '../api/submissions';
import type { SubmissionStatus } from '../types';

const statusVariant: Record<SubmissionStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'cyan'> = {
  received: 'blue', triaging: 'yellow', underwriting: 'orange', quoted: 'green', bound: 'purple', declined: 'red', referred: 'cyan',
};

const lobLabels: Record<string, string> = {
  cyber: 'Cyber Liability', professional_liability: 'Professional Liability', dnol: 'Directors & Officers',
  epli: 'Employment Practices', general_liability: 'General Liability',
};

const money = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const SubmissionDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: sub, isLoading } = useQuery({
    queryKey: ['submission', id],
    queryFn: () => getSubmission(id!),
    enabled: !!id,
  });

  if (isLoading) return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;
  if (!sub) return <div className="flex h-64 items-center justify-center text-slate-400">Submission not found</div>;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button onClick={() => navigate('/submissions')} className="rounded-lg p-1 hover:bg-slate-200">
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900">{sub.id}</h1>
            <StatusBadge label={sub.status} variant={statusVariant[sub.status]} />
          </div>
          <p className="text-sm text-slate-500">{sub.company_name} · {lobLabels[sub.lob]}</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* ── Left column: details ── */}
        <div className="lg:col-span-2 space-y-6">
          {/* Submission info */}
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Submission Details</h2>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <div><dt className="text-slate-400">Applicant</dt><dd className="font-medium text-slate-900">{sub.applicant_name}</dd></div>
              <div><dt className="text-slate-400">Company</dt><dd className="font-medium text-slate-900">{sub.company_name}</dd></div>
              <div><dt className="text-slate-400">Industry</dt><dd className="font-medium text-slate-900">{sub.industry}</dd></div>
              <div><dt className="text-slate-400">Line of Business</dt><dd className="font-medium text-slate-900">{lobLabels[sub.lob]}</dd></div>
              <div><dt className="text-slate-400">Annual Revenue</dt><dd className="font-medium text-slate-900">{money(sub.annual_revenue)}</dd></div>
              <div><dt className="text-slate-400">Employee Count</dt><dd className="font-medium text-slate-900">{sub.employee_count.toLocaleString()}</dd></div>
              <div><dt className="text-slate-400">Requested Coverage</dt><dd className="font-medium text-slate-900">{money(sub.requested_coverage)}</dd></div>
              <div><dt className="text-slate-400">Received Date</dt><dd className="font-medium text-slate-900">{new Date(sub.received_date).toLocaleDateString()}</dd></div>
            </dl>
          </div>

          {/* Cyber risk panel */}
          {sub.cyber_risk_data && (
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Cyber Risk Assessment</h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <div>
                  <dt className="text-slate-400">Security Rating</dt>
                  <dd className="font-medium text-slate-900">{sub.cyber_risk_data.security_rating}/100</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Open Vulnerabilities</dt>
                  <dd className={`font-medium ${sub.cyber_risk_data.open_vulnerabilities > 5 ? 'text-red-600' : 'text-slate-900'}`}>
                    {sub.cyber_risk_data.open_vulnerabilities}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-400">Last Breach</dt>
                  <dd className="font-medium text-slate-900">{sub.cyber_risk_data.last_breach ?? 'None reported'}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">3rd Party Risk Score</dt>
                  <dd className="font-medium text-slate-900">{sub.cyber_risk_data.third_party_risk_score}/100</dd>
                </div>
              </dl>
              <div className="mt-3 flex flex-wrap gap-2">
                {sub.cyber_risk_data.mfa_enabled && <StatusBadge label="MFA Enabled" variant="green" />}
                {sub.cyber_risk_data.encryption_at_rest && <StatusBadge label="Encryption at Rest" variant="green" />}
                {sub.cyber_risk_data.incident_response_plan && <StatusBadge label="IR Plan" variant="green" />}
                {sub.cyber_risk_data.employee_training && <StatusBadge label="Security Training" variant="green" />}
              </div>
            </div>
          )}

          {/* Documents */}
          {sub.documents.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Documents</h2>
              <div className="space-y-2">
                {sub.documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between rounded-lg border border-slate-100 p-3">
                    <div>
                      <p className="text-sm font-medium text-slate-900">{doc.name}</p>
                      <p className="text-xs text-slate-400">{(doc.size / 1000).toFixed(0)} KB · {new Date(doc.uploaded_at).toLocaleDateString()}</p>
                    </div>
                    <button className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
                      <Download size={16} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Triage result */}
          {sub.triage_result && (
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Triage Result</h2>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
                <div>
                  <dt className="text-slate-400">Appetite Match</dt>
                  <dd>{sub.triage_result.appetite_match ? <StatusBadge label="Yes" variant="green" /> : <StatusBadge label="No" variant="red" />}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Risk Score</dt>
                  <dd className="font-medium text-slate-900">{sub.triage_result.risk_score}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Priority</dt>
                  <dd className="font-medium text-slate-900 capitalize">{sub.triage_result.priority}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">Timestamp</dt>
                  <dd className="font-medium text-slate-900">{new Date(sub.triage_result.timestamp).toLocaleString()}</dd>
                </div>
              </dl>
              {sub.triage_result.flags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {sub.triage_result.flags.map((f, i) => (
                    <StatusBadge key={i} label={f} variant="blue" />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Agent recommendation */}
          {sub.agent_recommendation && (
            <div className="space-y-2">
              <h2 className="text-sm font-semibold text-slate-700">Agent Recommendation</h2>
              <ReasoningPanel
                agent={sub.agent_recommendation.agent}
                decision={sub.agent_recommendation.decision}
                confidence={sub.agent_recommendation.confidence}
                reasoning={sub.agent_recommendation.reasoning}
                timestamp={sub.agent_recommendation.timestamp}
                defaultOpen
              />
              {sub.agent_recommendation.recommended_premium && (
                <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                  <p className="text-sm font-semibold text-green-800">
                    Recommended Premium: {money(sub.agent_recommendation.recommended_premium)}
                  </p>
                  {sub.agent_recommendation.recommended_terms && (
                    <ul className="mt-2 list-inside list-disc text-sm text-green-700">
                      {sub.agent_recommendation.recommended_terms.map((t, i) => (
                        <li key={i}>{t}</li>
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
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Actions</h2>
            <div className="space-y-2">
              <button className="flex w-full items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700">
                <CheckCircle size={16} /> Approve Quote
              </button>
              <button className="flex w-full items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
                <AlertTriangle size={16} /> Modify Terms
              </button>
              <button className="flex w-full items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700">
                <XCircle size={16} /> Decline
              </button>
              <button className="flex w-full items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                <ArrowUpRight size={16} /> Escalate
              </button>
            </div>
          </div>

          {/* Confidence summary */}
          {sub.agent_recommendation && (
            <div className="rounded-lg border border-slate-200 bg-white p-5">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">AI Confidence</h2>
              <ConfidenceBar value={sub.agent_recommendation.confidence} height="h-3" />
              <p className="mt-2 text-xs text-slate-500">
                {sub.agent_recommendation.confidence >= 0.8
                  ? 'High confidence — automated processing eligible'
                  : sub.agent_recommendation.confidence >= 0.5
                  ? 'Medium confidence — human review recommended'
                  : 'Low confidence — human review required'}
              </p>
            </div>
          )}

          {/* Decision history */}
          <div className="rounded-lg border border-slate-200 bg-white p-5">
            <h2 className="mb-4 text-sm font-semibold text-slate-700">Decision History</h2>
            {sub.decision_history.map((ev, i) => (
              <TimelineEvent
                key={ev.id}
                timestamp={ev.timestamp}
                actor={ev.actor}
                action={ev.action}
                details={ev.details}
                isAgent={ev.is_agent}
                isLast={i === sub.decision_history.length - 1}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SubmissionDetail;
