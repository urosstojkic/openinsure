import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import FormField from '../components/FormField';
import { createClaim } from '../api/claims';
import { getPolicies } from '../api/policies';

const CAUSE_OPTIONS = [
  { value: 'data_breach', label: 'Data Breach' },
  { value: 'ransomware', label: 'Ransomware' },
  { value: 'social_engineering', label: 'Social Engineering' },
  { value: 'system_failure', label: 'System Failure' },
  { value: 'unauthorized_access', label: 'Unauthorized Access' },
  { value: 'denial_of_service', label: 'Denial of Service' },
  { value: 'other', label: 'Other' },
];

const SEVERITY_OPTIONS = [
  { value: 'simple', label: 'Simple' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'complex', label: 'Complex' },
  { value: 'catastrophe', label: 'Catastrophe' },
];

interface FormData {
  policyNumber: string;
  lossDate: string;
  causeOfLoss: string;
  description: string;
  severityEstimate: string;
  claimantName: string;
  claimantEmail: string;
  claimantPhone: string;
}

const initial: FormData = {
  policyNumber: '',
  lossDate: '',
  causeOfLoss: '',
  description: '',
  severityEstimate: '',
  claimantName: '',
  claimantEmail: '',
  claimantPhone: '',
};

const NewClaim: React.FC = () => {
  const navigate = useNavigate();
  const { data: policies = [] } = useQuery({ queryKey: ['policies'], queryFn: getPolicies });

  const [form, setForm] = useState<FormData>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const set = <K extends keyof FormData>(key: K, value: FormData[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const policyOptions = policies.map((p) => ({
    value: p.policy_number,
    label: `${p.policy_number} — ${p.insured_name}`,
  }));

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string>> = {};
    if (!form.policyNumber) e.policyNumber = 'Policy number is required';
    if (!form.lossDate) e.lossDate = 'Loss date is required';
    if (!form.causeOfLoss) e.causeOfLoss = 'Cause of loss is required';
    if (!form.description.trim()) e.description = 'Description is required';
    else if (form.description.trim().length < 20) e.description = 'Description must be at least 20 characters';
    if (!form.claimantName.trim()) e.claimantName = 'Claimant name is required';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);
    try {
      const payload = {
        policy_number: form.policyNumber,
        loss_date: form.lossDate,
        cause_of_loss: form.causeOfLoss,
        description: form.description,
        severity_estimate: form.severityEstimate || undefined,
        claimant: {
          name: form.claimantName,
          email: form.claimantEmail || undefined,
          phone: form.claimantPhone || undefined,
        },
      };
      await createClaim(payload);
      setToast({ type: 'success', message: 'Claim filed successfully!' });
      setTimeout(() => navigate('/claims'), 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to file claim';
      setToast({ type: 'error', message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/claims')} className="rounded-lg p-1 hover:bg-slate-200">
          <ArrowLeft size={20} />
        </button>
        <h1 className="text-2xl font-bold text-slate-900">File a Claim</h1>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium ${
            toast.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {toast.type === 'success' ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
          {toast.message}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Claim Details */}
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Claim Details</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="select" label="Policy Number" name="policyNumber" value={form.policyNumber} onChange={(v) => set('policyNumber', v)} options={policyOptions} placeholder="Select policy…" error={errors.policyNumber} required />
            <FormField type="date" label="Loss Date" name="lossDate" value={form.lossDate} onChange={(v) => set('lossDate', v)} error={errors.lossDate} required />
            <FormField type="select" label="Cause of Loss" name="causeOfLoss" value={form.causeOfLoss} onChange={(v) => set('causeOfLoss', v)} options={CAUSE_OPTIONS} placeholder="Select cause…" error={errors.causeOfLoss} required />
            <FormField type="select" label="Severity Estimate" name="severityEstimate" value={form.severityEstimate} onChange={(v) => set('severityEstimate', v)} options={SEVERITY_OPTIONS} placeholder="Select severity…" />
          </div>
          <div className="mt-4">
            <FormField type="textarea" label="Description" name="description" value={form.description} onChange={(v) => set('description', v)} placeholder="Describe the loss event in detail…" rows={4} minLength={20} error={errors.description} required />
          </div>
        </section>

        {/* Claimant Information */}
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Claimant Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="text" label="Claimant Name" name="claimantName" value={form.claimantName} onChange={(v) => set('claimantName', v)} error={errors.claimantName} required />
            <FormField type="email" label="Claimant Email" name="claimantEmail" value={form.claimantEmail} onChange={(v) => set('claimantEmail', v)} />
            <FormField type="tel" label="Claimant Phone" name="claimantPhone" value={form.claimantPhone} onChange={(v) => set('claimantPhone', v)} />
          </div>
        </section>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={() => navigate('/claims')} className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {submitting && <Loader2 size={16} className="animate-spin" />}
            {submitting ? 'Filing…' : 'File Claim'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NewClaim;
