import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import StatusBadge from '../components/StatusBadge';
import { getBrokerSubmissions, getBrokerPolicies, getBrokerClaims } from '../api/workbench';
import { createSubmission } from '../api/submissions';
import { createClaim } from '../api/claims';
import type { LOB, SubmissionStatus, ClaimStatus, BrokerSubmission, BrokerPolicy } from '../types';

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

const lifecycleSteps: { key: SubmissionStatus; label: string }[] = [
  { key: 'received', label: 'Received' },
  { key: 'triaging', label: 'Triaging' },
  { key: 'underwriting', label: 'Underwriting' },
  { key: 'quoted', label: 'Quoted' },
  { key: 'bound', label: 'Bound' },
];

const industries = ['Technology', 'Healthcare', 'Financial Services', 'Retail', 'Manufacturing', 'Education', 'Energy', 'Media', 'Legal', 'Logistics'] as const;

const lobOptions: { value: LOB; label: string }[] = [
  { value: 'cyber', label: 'Cyber' },
  { value: 'professional_liability', label: 'Professional Liability' },
  { value: 'dnol', label: 'D&O' },
  { value: 'epli', label: 'EPLI' },
  { value: 'general_liability', label: 'General Liability' },
];

const lossTypes = ['Data Breach', 'Ransomware', 'Business Interruption', 'Third Party Liability', 'Social Engineering', 'Other'] as const;

const BrokerPortal: React.FC = () => {
  const { data: submissions = [] } = useQuery({ queryKey: ['broker-submissions'], queryFn: getBrokerSubmissions });
  const { data: policies = [] } = useQuery({ queryKey: ['broker-policies'], queryFn: getBrokerPolicies });
  const { data: claims = [] } = useQuery({ queryKey: ['broker-claims'], queryFn: getBrokerClaims });

  const [activeTab, setActiveTab] = useState<PortalTab>('submissions');
  const [selectedSubmission, setSelectedSubmission] = useState<BrokerSubmission | null>(null);
  const [showNewSubmission, setShowNewSubmission] = useState(false);
  const [showFNOL, setShowFNOL] = useState(false);
  const [fnolSuccess, setFnolSuccess] = useState(false);
  const [acceptedQuotes, setAcceptedQuotes] = useState<Set<string>>(new Set());

  const [newSub, setNewSub] = useState({
    applicant_name: '',
    industry: 'Technology',
    annual_revenue: '',
    employee_count: '',
    lob: 'cyber' as LOB,
    mfa_enabled: false,
    encryption_at_rest: false,
    incident_response_plan: false,
  });

  const [fnolForm, setFnolForm] = useState({
    policy_id: '',
    loss_type: 'Data Breach',
    loss_date: '',
    description: '',
  });

  const queryClient = useQueryClient();

  const submitMutation = useMutation({
    mutationFn: createSubmission,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['broker-submissions'] });
      setShowNewSubmission(false);
      setNewSub({
        applicant_name: '', industry: 'Technology', annual_revenue: '', employee_count: '',
        lob: 'cyber', mfa_enabled: false, encryption_at_rest: false, incident_response_plan: false,
      });
    },
  });

  const claimMutation = useMutation({
    mutationFn: createClaim,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['broker-claims'] });
      setShowFNOL(false);
      setFnolSuccess(true);
      setTimeout(() => setFnolSuccess(false), 4000);
      setFnolForm({ policy_id: '', loss_type: 'Data Breach', loss_date: '', description: '' });
    },
  });

  const handleSubmitNew = () => {
    submitMutation.mutate({
      applicant_name: newSub.applicant_name,
      industry: newSub.industry,
      annual_revenue: Number(newSub.annual_revenue),
      employee_count: Number(newSub.employee_count),
      lob: newSub.lob,
      mfa_enabled: newSub.mfa_enabled,
      encryption_at_rest: newSub.encryption_at_rest,
      incident_response_plan: newSub.incident_response_plan,
    });
  };

  const handleSubmitFNOL = () => {
    const policy = policies.find((p: BrokerPolicy) => p.id === fnolForm.policy_id);
    claimMutation.mutate({
      policy_id: fnolForm.policy_id,
      policy_number: policy?.policy_number ?? '',
      loss_type: fnolForm.loss_type,
      loss_date: fnolForm.loss_date,
      description: fnolForm.description,
    });
  };

  const effectiveStatus: SubmissionStatus = selectedSubmission
    ? (acceptedQuotes.has(selectedSubmission.id) ? 'bound' : selectedSubmission.status)
    : 'received';
  const currentStepIndex = lifecycleSteps.findIndex(s => s.key === effectiveStatus);

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      {/* ── Tab Nav (branding handled by Layout header) ── */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-white px-6">
        <nav className="flex gap-1 py-2">
          <StatusBadge label="Broker Portal" variant="blue" />
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

      {/* ── Content ── */}
      <div className="flex-1 overflow-y-auto p-6">
        {/* ── My Submissions ── */}
        {activeTab === 'submissions' && !selectedSubmission && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold text-slate-900">My Submissions</h2>
              <button onClick={() => setShowNewSubmission(true)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
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

        {/* ── Submission Detail ── */}
        {activeTab === 'submissions' && selectedSubmission && (
          <div className="space-y-4">
            <button onClick={() => setSelectedSubmission(null)} className="text-sm text-indigo-600 hover:text-indigo-800">← Back to submissions</button>
            <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
              <h2 className="text-xl font-bold text-slate-900">{selectedSubmission.applicant_name}</h2>
              <p className="text-sm text-slate-500">{formatSubId(selectedSubmission)} · {lobLabels[selectedSubmission.lob] ?? selectedSubmission.lob}</p>
              <div className="mt-2">
                <StatusBadge label={effectiveStatus} variant={statusVariant[effectiveStatus]} />
              </div>

              {/* ── Lifecycle Progress Bar ── */}
              <div className="mt-6 mb-6">
                <div className="flex items-center justify-between">
                  {lifecycleSteps.map((step, i) => (
                    <React.Fragment key={step.key}>
                      <div className="flex flex-col items-center gap-1">
                        <div className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-colors ${
                          currentStepIndex >= 0 && i < currentStepIndex
                            ? 'border-indigo-600 bg-indigo-600 text-white'
                            : currentStepIndex >= 0 && i === currentStepIndex
                            ? 'border-indigo-600 bg-indigo-50 text-indigo-600'
                            : 'border-slate-300 bg-white text-slate-400'
                        }`}>
                          {currentStepIndex >= 0 && i < currentStepIndex ? (
                            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            <span className={`h-2.5 w-2.5 rounded-full ${
                              currentStepIndex >= 0 && i === currentStepIndex ? 'bg-indigo-600' : 'bg-slate-300'
                            }`} />
                          )}
                        </div>
                        <span className={`text-xs font-medium ${
                          currentStepIndex >= 0 && i <= currentStepIndex ? 'text-indigo-600' : 'text-slate-400'
                        }`}>{step.label}</span>
                      </div>
                      {i < lifecycleSteps.length - 1 && (
                        <div className={`mx-1 h-0.5 flex-1 ${
                          currentStepIndex >= 0 && i < currentStepIndex ? 'bg-indigo-600' : 'bg-slate-200'
                        }`} />
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {/* ── Quote Card ── */}
              {effectiveStatus === 'quoted' && (
                <div className="mb-6 rounded-xl border border-green-200 bg-green-50 p-5">
                  <h3 className="text-sm font-semibold text-green-800">Quote Available</h3>
                  <p className="mt-2 text-2xl font-bold text-green-900">
                    {money(12500)}
                    <span className="ml-1 text-sm font-normal text-green-700">annual premium</span>
                  </p>
                  <div className="mt-4 flex gap-3">
                    <button
                      onClick={() => setAcceptedQuotes(prev => new Set(prev).add(selectedSubmission.id))}
                      className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 active:scale-[0.98] transition-all"
                    >
                      Accept Quote
                    </button>
                    <button className="rounded-lg border border-green-300 bg-white px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-50 active:scale-[0.98] transition-all">
                      Download Quote PDF
                    </button>
                  </div>
                </div>
              )}

              {effectiveStatus === 'bound' && acceptedQuotes.has(selectedSubmission.id) && (
                <div className="mb-6 rounded-xl border border-purple-200 bg-purple-50 p-5">
                  <h3 className="text-sm font-semibold text-purple-800">Quote Accepted</h3>
                  <p className="mt-1 text-sm text-purple-700">This submission has been bound. A policy document will be issued shortly.</p>
                </div>
              )}

              <h3 className="mt-2 mb-3 text-sm font-semibold text-slate-800">Timeline Events</h3>
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
                  <p>Current status: <StatusBadge label={effectiveStatus} variant={statusVariant[effectiveStatus]} /></p>
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
              <button onClick={() => setShowFNOL(true)} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] transition-all">
                File FNOL
              </button>
            </div>
            {fnolSuccess && (
              <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-800">
                ✓ FNOL submitted successfully. Your claim is being processed.
              </div>
            )}
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

      {/* ── New Submission Modal ── */}
      {showNewSubmission && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">New Submission</h2>
              <button onClick={() => setShowNewSubmission(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
            </div>
            <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Applicant Name</label>
                <input type="text" value={newSub.applicant_name} onChange={e => setNewSub(s => ({ ...s, applicant_name: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="Company name" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Industry</label>
                <select value={newSub.industry} onChange={e => setNewSub(s => ({ ...s, industry: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {industries.map(ind => <option key={ind} value={ind}>{ind}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Annual Revenue ($)</label>
                  <input type="number" value={newSub.annual_revenue} onChange={e => setNewSub(s => ({ ...s, annual_revenue: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="1000000" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Employee Count</label>
                  <input type="number" value={newSub.employee_count} onChange={e => setNewSub(s => ({ ...s, employee_count: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="50" />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Line of Business</label>
                <select value={newSub.lob} onChange={e => setNewSub(s => ({ ...s, lob: e.target.value as LOB }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {lobOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <fieldset>
                <legend className="text-sm font-medium text-slate-700 mb-2">Security Details</legend>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={newSub.mfa_enabled} onChange={e => setNewSub(s => ({ ...s, mfa_enabled: e.target.checked }))} className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    MFA Enabled
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={newSub.encryption_at_rest} onChange={e => setNewSub(s => ({ ...s, encryption_at_rest: e.target.checked }))} className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    Encryption at Rest
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="checkbox" checked={newSub.incident_response_plan} onChange={e => setNewSub(s => ({ ...s, incident_response_plan: e.target.checked }))} className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500" />
                    Incident Response Plan
                  </label>
                </div>
              </fieldset>
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setShowNewSubmission(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button onClick={handleSubmitNew} disabled={submitMutation.isPending || !newSub.applicant_name} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 disabled:opacity-50 active:scale-[0.98] transition-all">
                {submitMutation.isPending ? 'Submitting\u2026' : 'Submit'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── FNOL Modal ── */}
      {showFNOL && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-slate-900">File FNOL — First Notice of Loss</h2>
              <button onClick={() => setShowFNOL(false)} className="text-slate-400 hover:text-slate-600 text-xl leading-none">&times;</button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Policy</label>
                <select value={fnolForm.policy_id} onChange={e => setFnolForm(s => ({ ...s, policy_id: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  <option value="">Select a policy…</option>
                  {policies.map((p: BrokerPolicy) => <option key={p.id} value={p.id}>{p.policy_number} — {p.insured_name}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Loss Type</label>
                <select value={fnolForm.loss_type} onChange={e => setFnolForm(s => ({ ...s, loss_type: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500">
                  {lossTypes.map(lt => <option key={lt} value={lt}>{lt}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Date of Loss</label>
                <input type="date" value={fnolForm.loss_date} onChange={e => setFnolForm(s => ({ ...s, loss_date: e.target.value }))} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Description</label>
                <textarea value={fnolForm.description} onChange={e => setFnolForm(s => ({ ...s, description: e.target.value }))} rows={4} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="Describe the loss event…" />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={() => setShowFNOL(false)} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">Cancel</button>
              <button onClick={handleSubmitFNOL} disabled={claimMutation.isPending || !fnolForm.policy_id || !fnolForm.loss_date} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 disabled:opacity-50 active:scale-[0.98] transition-all">
                {claimMutation.isPending ? 'Submitting\u2026' : 'Submit FNOL'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};

export default BrokerPortal;
