import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import StatusBadge from '../components/StatusBadge';
import { getBrokerSubmissions, getBrokerPolicies, getBrokerClaims } from '../api/workbench';
import type { LOB, SubmissionStatus, ClaimStatus, BrokerSubmission } from '../types';

const lobLabels: Record<LOB, string> = {
  cyber: 'Cyber',
  professional_liability: 'Prof Liability',
  dnol: 'D&O',
  epli: 'EPLI',
  general_liability: 'General Liability',
};

const statusVariant: Record<SubmissionStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'purple' | 'red' | 'cyan'> = {
  received: 'blue',
  triaging: 'yellow',
  underwriting: 'orange',
  quoted: 'green',
  bound: 'purple',
  declined: 'red',
  referred: 'cyan',
};

const claimStatusVariant: Record<ClaimStatus, 'blue' | 'yellow' | 'orange' | 'green' | 'red' | 'purple' | 'cyan'> = {
  reported: 'cyan',
  open: 'blue',
  investigating: 'yellow',
  reserved: 'orange',
  closed: 'green',
  denied: 'red',
  litigation: 'purple',
};

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const formatSubId = (sub: BrokerSubmission) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sn = (sub as any).submission_number;
  if (sn && typeof sn === 'string') return sn;
  if (sub.id.startsWith('SUB-')) return sub.id;
  return `SUB-${sub.id.substring(0, 8).toUpperCase()}`;
};

const formatDate = (dateStr: string) => {
  if (!dateStr) return '—';
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
};

type PortalTab = 'submissions' | 'policies' | 'claims' | 'documents';

const BrokerPortal: React.FC = () => {
  const { data: submissions = [] } = useQuery({ queryKey: ['broker-submissions'], queryFn: getBrokerSubmissions });
  const { data: policies = [] } = useQuery({ queryKey: ['broker-policies'], queryFn: getBrokerPolicies });
  const { data: claims = [] } = useQuery({ queryKey: ['broker-claims'], queryFn: getBrokerClaims });

  const [activeTab, setActiveTab] = useState<PortalTab>('submissions');
  const [selectedSubmission, setSelectedSubmission] = useState<BrokerSubmission | null>(null);

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      {/* ── Top Nav Bar (replaces sidebar for broker view) ── */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">OI</div>
            <span className="text-lg font-bold text-slate-900">OpenInsure</span>
            <StatusBadge label="Broker Portal" variant="blue" />
          </div>
          <nav className="flex gap-1">
            {([['submissions', 'My Submissions'], ['policies', 'My Policies'], ['claims', 'My Claims'], ['documents', 'Documents']] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => { setActiveTab(key); setSelectedSubmission(null); }}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${activeTab === key ? 'bg-indigo-50 text-indigo-600' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'}`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">Broker</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">BR</div>
        </div>
      </div>

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ── My Submissions ── */}
        {activeTab === 'submissions' && !selectedSubmission && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">My Submissions</h2>
              <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
                New Submission
              </button>
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">ID</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Applicant</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">LOB</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Status</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Submitted</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Last Update</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {submissions.map((sub) => (
                    <tr key={sub.id} className="cursor-pointer hover:bg-slate-50/50 transition-colors" onClick={() => setSelectedSubmission(sub)}>
                      <td className="px-4 py-3 font-mono text-xs text-slate-700">{formatSubId(sub)}</td>
                      <td className="px-4 py-3 text-sm text-slate-900">{sub.applicant_name}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{lobLabels[sub.lob] ?? sub.lob}</td>
                      <td className="px-4 py-3"><StatusBadge label={sub.status} variant={statusVariant[sub.status]} /></td>
                      <td className="px-4 py-3 text-sm text-slate-600">{formatDate(sub.submitted_date)}</td>
                      <td className="px-4 py-3 text-sm text-slate-500">{formatDate(sub.last_update)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Submission Detail (simplified — no internal data) ── */}
        {activeTab === 'submissions' && selectedSubmission && (
          <div className="space-y-4">
            <button onClick={() => setSelectedSubmission(null)} className="text-sm text-indigo-600 hover:text-indigo-800">← Back to submissions</button>
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="text-xl font-bold text-slate-900">{selectedSubmission.applicant_name}</h2>
              <p className="text-sm text-slate-500">{formatSubId(selectedSubmission)} · {lobLabels[selectedSubmission.lob] ?? selectedSubmission.lob}</p>
              <div className="mt-2">
                <StatusBadge label={selectedSubmission.status} variant={statusVariant[selectedSubmission.status]} />
              </div>

              <h3 className="mt-6 mb-3 text-sm font-semibold text-slate-800">Status Timeline</h3>
              {selectedSubmission.status_timeline.length > 0 ? (
                <div className="space-y-3">
                  {selectedSubmission.status_timeline.map((ev, i) => (
                    <div key={i} className="relative flex gap-4 pb-4">
                      {i < selectedSubmission.status_timeline.length - 1 && (
                        <div className="absolute left-[11px] top-7 bottom-0 w-px bg-slate-200" />
                      )}
                      <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100">
                        <span className="h-2.5 w-2.5 rounded-full bg-indigo-500" />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-slate-900">{ev.status}</p>
                        <p className="text-xs text-slate-500">{ev.description}</p>
                        <p className="text-xs text-slate-400">{formatDate(ev.timestamp)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border border-slate-200/60 p-4 text-center text-sm text-slate-400 shadow-[var(--shadow-xs)]">
                  <p>Current status: <StatusBadge label={selectedSubmission.status} variant={statusVariant[selectedSubmission.status]} /></p>
                  <p className="mt-1 text-xs">Submitted {formatDate(selectedSubmission.submitted_date)}</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── My Policies ── */}
        {activeTab === 'policies' && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900">My Policies</h2>
            <div className="overflow-x-auto rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Policy #</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Insured</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">LOB</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Effective</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Expiry</th>
                    <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-400">Premium</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {policies.map((pol) => (
                    <tr key={pol.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-slate-700">{pol.policy_number}</td>
                      <td className="px-4 py-3 text-sm text-slate-900">{pol.insured_name}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{lobLabels[pol.lob] ?? pol.lob}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{formatDate(pol.effective_date)}</td>
                      <td className="px-4 py-3 text-sm text-slate-600">{formatDate(pol.expiry_date)}</td>
                      <td className="px-4 py-3 text-right font-mono text-sm text-slate-700">{money(pol.premium)}</td>
                      <td className="px-4 py-3">
                        <div className="flex gap-2">
                          <button className="text-xs text-indigo-600 hover:text-indigo-800">Download</button>
                          <button className="text-xs text-indigo-600 hover:text-indigo-800">Certificate</button>
                          <button className="text-xs text-indigo-600 hover:text-indigo-800">Endorsement</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── My Claims ── */}
        {activeTab === 'claims' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">My Claims</h2>
              <button className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
                File FNOL
              </button>
            </div>
            <div className="overflow-x-auto rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
              <table className="min-w-full divide-y divide-slate-200">
                <thead className="sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm">
                  <tr>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Claim #</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Policy</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Status</th>
                    <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-slate-400">Loss Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {claims.map((clm) => (
                    <tr key={clm.id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-slate-700">{clm.claim_number}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{clm.policy_number}</td>
                      <td className="px-4 py-3"><StatusBadge label={clm.status} variant={claimStatusVariant[clm.status]} /></td>
                      <td className="px-4 py-3 text-sm text-slate-600">{formatDate(clm.loss_date)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ── Documents ── */}
        {activeTab === 'documents' && (
          <div className="space-y-4">
            <h2 className="text-xl font-bold text-slate-900">Documents</h2>
            <div className="rounded-xl border border-slate-200/60 bg-white p-8 text-center text-slate-400 shadow-[var(--shadow-xs)]">
              <p className="text-lg font-medium">Document Center</p>
              <p className="text-sm">Access policy documents, certificates, and endorsements from your policies above.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BrokerPortal;
