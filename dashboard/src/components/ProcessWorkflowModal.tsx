import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, CheckCircle2, Loader2, AlertCircle, ChevronDown, ChevronRight,
  Shield, Brain, Scale, Sparkles, Zap,
} from 'lucide-react';
import ConfidenceBar from './ConfidenceBar';

/* ── Types ─────────────────────────────────────────────────────────── */

interface WorkflowStepResponse {
  response: Record<string, unknown>;
  source: string;
}

interface WorkflowResult {
  submission_id?: string;
  claim_id?: string;
  workflow?: string;
  outcome?: string;
  policy_id?: string;
  policy_number?: string;
  premium?: number;
  steps?: Record<string, WorkflowStepResponse>;
  authority?: { decision: string; reason: string };
  [key: string]: unknown;
}

interface StepConfig {
  key: string;
  label: string;
  agent: string;
  model: string;
  icon: React.ReactNode;
  description: string;
}

type StepStatus = 'pending' | 'running' | 'complete' | 'error';

interface Props {
  mode: 'submission' | 'claim';
  itemId: string;
  itemLabel: string;
  onClose: () => void;
  onComplete: () => void;
  processFunc: (id: string) => Promise<WorkflowResult>;
}

/* ── Constants ─────────────────────────────────────────────────────── */

const SUBMISSION_STEPS: StepConfig[] = [
  { key: 'triage', label: 'Triage Agent', agent: 'triage_agent', model: 'GPT-5.1', icon: <Zap size={18} />, description: 'Analyzing risk appetite & submission quality' },
  { key: 'underwriting', label: 'Underwriting Agent', agent: 'underwriting_agent', model: 'GPT-5.1', icon: <Brain size={18} />, description: 'Calculating premium & evaluating risk factors' },
  { key: 'compliance', label: 'Compliance Agent', agent: 'compliance_agent', model: 'GPT-5.1', icon: <Scale size={18} />, description: 'Reviewing regulatory requirements & guidelines' },
];

const CLAIM_STEPS: StepConfig[] = [
  { key: 'triage', label: 'Claims Triage Agent', agent: 'claims_triage_agent', model: 'GPT-5.1', icon: <Zap size={18} />, description: 'Initial claim assessment & classification' },
  { key: 'coverage', label: 'Coverage Verification', agent: 'coverage_agent', model: 'GPT-5.1', icon: <Shield size={18} />, description: 'Validating policy coverage & exclusions' },
  { key: 'reserve', label: 'Reserve Estimation', agent: 'reserve_agent', model: 'GPT-5.1', icon: <Brain size={18} />, description: 'Calculating reserves & exposure analysis' },
];

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const STEP_INTERVAL_MS = 1800;

/* ── Outcome badge ─────────────────────────────────────────────────── */

function OutcomeBadge({ outcome }: { outcome: string }) {
  const styles: Record<string, string> = {
    bound: 'bg-emerald-100 text-emerald-800 ring-emerald-500/20',
    quoted_pending_approval: 'bg-amber-100 text-amber-800 ring-amber-500/20',
    declined: 'bg-red-100 text-red-800 ring-red-500/20',
    approved: 'bg-emerald-100 text-emerald-800 ring-emerald-500/20',
    reserved: 'bg-blue-100 text-blue-800 ring-blue-500/20',
    investigating: 'bg-amber-100 text-amber-800 ring-amber-500/20',
  };
  const labels: Record<string, string> = {
    bound: 'Bound',
    quoted_pending_approval: 'Quoted — Pending Approval',
    declined: 'Declined',
    approved: 'Approved',
    reserved: 'Reserved',
    investigating: 'Under Investigation',
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-semibold ring-1 ${styles[outcome] ?? 'bg-slate-100 text-slate-800 ring-slate-500/20'}`}>
      {outcome === 'bound' || outcome === 'approved' ? <CheckCircle2 size={15} /> : null}
      {labels[outcome] ?? outcome.replace(/_/g, ' ')}
    </span>
  );
}

/* ── Authority badge ───────────────────────────────────────────────── */

function AuthorityBadge({ decision, reason }: { decision: string; reason: string }) {
  const auto = decision === 'auto_execute';
  return (
    <div className={`flex items-start gap-3 rounded-lg px-4 py-3 ${auto ? 'bg-emerald-50 border border-emerald-200' : 'bg-amber-50 border border-amber-200'}`}>
      <div className={`mt-0.5 rounded-full p-1 ${auto ? 'bg-emerald-200 text-emerald-700' : 'bg-amber-200 text-amber-700'}`}>
        {auto ? <CheckCircle2 size={16} /> : <Shield size={16} />}
      </div>
      <div>
        <p className={`text-sm font-semibold ${auto ? 'text-emerald-800' : 'text-amber-800'}`}>
          {auto ? 'Auto-Executed — Within Authority' : 'Requires Human Approval'}
        </p>
        <p className={`text-xs ${auto ? 'text-emerald-600' : 'text-amber-600'}`}>
          {reason.replace(/_/g, ' ')}
        </p>
      </div>
    </div>
  );
}

/* ── Expandable reasoning ──────────────────────────────────────────── */

function ReasoningChain({ stepKey, data }: { stepKey: string; data: WorkflowStepResponse }) {
  const [open, setOpen] = useState(false);
  const resp = data.response || {};
  const reasoning: string[] = (resp.reasoning as string[]) || (resp.reasoning_chain as string[]) || [];
  const allEntries = Object.entries(resp).filter(
    ([k]) => !['reasoning', 'reasoning_chain'].includes(k),
  );

  return (
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          {open ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
          <span className="text-sm font-medium text-slate-700 capitalize">{stepKey.replace(/_/g, ' ')} Agent</span>
          <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 ring-1 ring-indigo-500/20">
            {data.source === 'foundry' ? 'Foundry AI' : data.source || 'AI'}
          </span>
        </div>
        {typeof (resp as Record<string, unknown>).confidence === 'number' && (
          <div className="w-28">
            <ConfidenceBar value={(resp as Record<string, unknown>).confidence as number} />
          </div>
        )}
      </button>
      {open && (
        <div className="border-t border-slate-100 px-4 py-3 space-y-3">
          {reasoning.length > 0 && (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Reasoning Chain</h4>
              <ol className="list-inside list-decimal space-y-1">
                {reasoning.map((step, i) => (
                  <li key={i} className="text-sm text-slate-700">{step}</li>
                ))}
              </ol>
            </div>
          )}
          {allEntries.length > 0 && (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">Agent Output</h4>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                {allEntries.map(([k, v]) => (
                  <div key={k} className="flex items-baseline gap-1.5">
                    <span className="text-xs text-slate-400 capitalize">{k.replace(/_/g, ' ')}:</span>
                    <span className="text-xs font-medium text-slate-700 truncate">
                      {typeof v === 'number' ? (k.includes('premium') || k.includes('reserve') || k.includes('amount') ? money(v) : v.toLocaleString())
                        : typeof v === 'boolean' ? (v ? 'Yes' : 'No')
                        : typeof v === 'object' ? JSON.stringify(v)
                        : String(v ?? '—')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ── Main Modal ────────────────────────────────────────────────────── */

const ProcessWorkflowModal: React.FC<Props> = ({
  mode, itemId, itemLabel, onClose, onComplete, processFunc,
}) => {
  const stepConfigs = mode === 'submission' ? SUBMISSION_STEPS : CLAIM_STEPS;

  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>(stepConfigs.map(() => 'pending'));
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<'running' | 'complete' | 'error'>('running');
  const [elapsedMs, setElapsedMs] = useState(0);

  const apiDone = useRef(false);
  const apiResult = useRef<WorkflowResult | null>(null);
  const apiError = useRef<string | null>(null);
  const startTime = useRef(Date.now());

  // Elapsed timer
  useEffect(() => {
    if (phase !== 'running') return;
    const id = setInterval(() => setElapsedMs(Date.now() - startTime.current), 100);
    return () => clearInterval(id);
  }, [phase]);

  // Fire API call once
  useEffect(() => {
    let cancelled = false;
    processFunc(itemId)
      .then((res) => {
        if (cancelled) return;
        apiDone.current = true;
        apiResult.current = res;
      })
      .catch((err) => {
        if (cancelled) return;
        apiDone.current = true;
        apiError.current = err instanceof Error ? err.message : 'Processing failed';
      });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Animate steps
  useEffect(() => {
    let currentStep = 0;
    // Start first step immediately
    setStepStatuses((prev) => { const n = [...prev]; n[0] = 'running'; return n; });

    const interval = setInterval(() => {
      // Complete current step
      setStepStatuses((prev) => {
        const n = [...prev];
        if (currentStep < n.length) n[currentStep] = 'complete';
        return n;
      });
      currentStep++;

      if (currentStep < stepConfigs.length) {
        // Start next step
        setStepStatuses((prev) => {
          const n = [...prev];
          n[currentStep] = 'running';
          return n;
        });
      }

      // All visual steps done — wait for API
      if (currentStep >= stepConfigs.length) {
        clearInterval(interval);
        const waitForApi = setInterval(() => {
          if (apiDone.current) {
            clearInterval(waitForApi);
            if (apiError.current) {
              setError(apiError.current);
              setPhase('error');
              setStepStatuses((prev) => {
                const n = [...prev];
                const lastRunning = n.lastIndexOf('running');
                if (lastRunning >= 0) n[lastRunning] = 'error';
                return n;
              });
            } else {
              setResult(apiResult.current);
              setPhase('complete');
            }
          }
        }, 200);
        return () => clearInterval(waitForApi);
      }
    }, STEP_INTERVAL_MS);

    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Handle completion
  const handleClose = useCallback(() => {
    if (phase === 'complete') onComplete();
    onClose();
  }, [phase, onComplete, onClose]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') handleClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [handleClose]);

  /* ── Derived data ── */
  const steps = result?.steps ?? {};
  const uwStep = (steps.underwriting as WorkflowStepResponse | undefined);
  const uwResp = (uwStep?.response ?? {}) as Record<string, unknown>;
  const confidence = (uwResp.confidence as number) ?? null;
  const riskScore = (uwResp.risk_score as number) ?? null;
  const recommendedPremium = (uwResp.recommended_premium as number) ?? result?.premium ?? null;
  const completedCount = stepStatuses.filter((s) => s === 'complete').length;
  const progressPct = phase === 'complete' ? 100 : Math.round((completedCount / stepConfigs.length) * 90);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={handleClose} />

      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto rounded-2xl bg-white shadow-2xl animate-in fade-in zoom-in-95">
        {/* ── Gradient header ── */}
        <div className="relative overflow-hidden rounded-t-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-violet-600 px-6 py-5">
          <div className="absolute -right-6 -top-6 h-32 w-32 rounded-full bg-white/10 blur-2xl" />
          <div className="absolute -left-4 bottom-0 h-24 w-24 rounded-full bg-white/5 blur-xl" />

          <div className="relative flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2 mb-1.5">
                <Sparkles size={20} className="text-amber-300" />
                <span className="text-xs font-semibold uppercase tracking-widest text-white/80">
                  Microsoft Foundry AI Pipeline
                </span>
              </div>
              <h2 className="text-lg font-bold text-white">
                {mode === 'submission' ? 'Processing Submission' : 'Processing Claim'}
              </h2>
              <p className="mt-0.5 text-sm text-white/70 font-mono">{itemLabel}</p>
            </div>
            <button
              onClick={handleClose}
              className="rounded-lg p-1.5 text-white/60 hover:bg-white/10 hover:text-white transition-colors"
            >
              <X size={20} />
            </button>
          </div>

          {/* Overall progress bar */}
          <div className="mt-4 flex items-center gap-3">
            <div className="flex-1 h-1.5 rounded-full bg-white/20 overflow-hidden">
              <div
                className="h-full rounded-full bg-white/90 transition-all duration-700 ease-out"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="text-xs font-mono text-white/70">
              {(elapsedMs / 1000).toFixed(1)}s
            </span>
          </div>
        </div>

        {/* ── Step tracker ── */}
        <div className="px-6 py-5 space-y-3">
          {stepConfigs.map((step, idx) => {
            const status = stepStatuses[idx];
            const isActive = status === 'running';
            const isDone = status === 'complete';
            const isErr = status === 'error';
            return (
              <div
                key={step.key}
                className={`flex items-center gap-4 rounded-xl border px-4 py-3 transition-all duration-500 ${
                  isActive ? 'border-indigo-300 bg-indigo-50 shadow-sm shadow-indigo-100' :
                  isDone ? 'border-emerald-200 bg-emerald-50/50' :
                  isErr ? 'border-red-200 bg-red-50/50' :
                  'border-slate-200 bg-slate-50/30'
                }`}
              >
                {/* Status icon */}
                <div className={`flex-shrink-0 flex items-center justify-center w-9 h-9 rounded-full ${
                  isActive ? 'bg-indigo-100 text-indigo-600' :
                  isDone ? 'bg-emerald-100 text-emerald-600' :
                  isErr ? 'bg-red-100 text-red-600' :
                  'bg-slate-100 text-slate-400'
                }`}>
                  {isActive ? <Loader2 size={18} className="animate-spin" /> :
                   isDone ? <CheckCircle2 size={18} /> :
                   isErr ? <AlertCircle size={18} /> :
                   step.icon}
                </div>

                {/* Label */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-sm font-semibold ${isActive ? 'text-indigo-900' : isDone ? 'text-emerald-900' : isErr ? 'text-red-900' : 'text-slate-500'}`}>
                      Step {idx + 1}: {step.label}
                    </span>
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wide ${
                      isActive ? 'bg-indigo-200/60 text-indigo-700' :
                      isDone ? 'bg-emerald-200/60 text-emerald-700' :
                      'bg-slate-200/60 text-slate-500'
                    }`}>
                      {step.model}
                    </span>
                  </div>
                  <p className={`text-xs mt-0.5 ${isActive ? 'text-indigo-600' : isDone ? 'text-emerald-600' : 'text-slate-400'}`}>
                    {isActive ? step.description + '…' : isDone ? 'Complete' : isErr ? 'Failed' : 'Waiting'}
                  </p>
                </div>

                {/* Source badge */}
                {(isActive || isDone) && (
                  <span className="flex-shrink-0 flex items-center gap-1 rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 px-2.5 py-1 text-[10px] font-bold text-white shadow-sm">
                    <Sparkles size={10} /> Foundry
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Error state ── */}
        {phase === 'error' && error && (
          <div className="mx-6 mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle size={18} className="mt-0.5 text-red-500 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-800">Pipeline Error</p>
              <p className="text-xs text-red-600 mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {phase === 'complete' && result && (
          <div className="border-t border-slate-200 px-6 py-5 space-y-5">
            {/* Outcome header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Pipeline Result</h3>
                <div className="mt-1.5">
                  <OutcomeBadge outcome={result.outcome ?? 'unknown'} />
                </div>
              </div>
              {result.policy_number && (
                <div className="text-right">
                  <p className="text-xs text-slate-400">Policy Created</p>
                  <p className="font-mono text-sm font-bold text-indigo-700">{result.policy_number}</p>
                </div>
              )}
            </div>

            {/* KPI cards */}
            <div className="grid grid-cols-3 gap-3">
              {recommendedPremium != null && (
                <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Premium</p>
                  <p className="mt-1 text-xl font-bold text-slate-900">{money(recommendedPremium)}</p>
                </div>
              )}
              {riskScore != null && (
                <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Risk Score</p>
                  <p className={`mt-1 text-xl font-bold ${riskScore >= 70 ? 'text-red-600' : riskScore >= 40 ? 'text-amber-600' : 'text-emerald-600'}`}>
                    {riskScore}
                  </p>
                </div>
              )}
              {confidence != null && (
                <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Confidence</p>
                  <div className="mt-2">
                    <ConfidenceBar value={confidence} height="h-2.5" />
                  </div>
                </div>
              )}
              {recommendedPremium == null && riskScore == null && confidence == null && (
                <div className="col-span-3 rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3.5">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Workflow</p>
                  <p className="mt-1 text-sm font-medium text-slate-700 capitalize">{(result.workflow ?? mode).replace(/_/g, ' ')}</p>
                </div>
              )}
            </div>

            {/* Authority decision */}
            {result.authority && (
              <AuthorityBadge decision={result.authority.decision} reason={result.authority.reason} />
            )}

            {/* Expandable reasoning per step */}
            {Object.keys(steps).length > 0 && (
              <div>
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Agent Reasoning</h3>
                <div className="space-y-2">
                  {Object.entries(steps).map(([key, data]) => (
                    <ReasoningChain key={key} stepKey={key} data={data as WorkflowStepResponse} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Footer ── */}
        <div className="flex items-center justify-between rounded-b-2xl border-t border-slate-200 bg-slate-50 px-6 py-3.5">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <svg className="h-4 w-4" viewBox="0 0 23 23" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M11 0H0v11h11V0Z" fill="#F25022"/>
              <path d="M23 0H12v11h11V0Z" fill="#7FBA00"/>
              <path d="M11 12H0v11h11V12Z" fill="#00A4EF"/>
              <path d="M23 12H12v11h11V12Z" fill="#FFB900"/>
            </svg>
            <span>Powered by <strong className="text-slate-500">Microsoft Foundry</strong></span>
          </div>
          <button
            onClick={handleClose}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              phase === 'complete'
                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                : phase === 'error'
                ? 'bg-slate-200 text-slate-700 hover:bg-slate-300'
                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
            }`}
            disabled={phase === 'running'}
          >
            {phase === 'complete' ? 'Done' : phase === 'error' ? 'Close' : 'Processing…'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProcessWorkflowModal;
