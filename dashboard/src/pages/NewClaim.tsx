import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import FormField from '../components/FormField';
import { createClaim } from '../api/claims';
import { getPolicies } from '../api/policies';

const CLAIM_TYPE_OPTIONS = [
  { value: 'data_breach', label: 'Data Breach' },
  { value: 'ransomware', label: 'Ransomware' },
  { value: 'business_interruption', label: 'Business Interruption' },
  { value: 'third_party_liability', label: 'Third-Party Liability' },
  { value: 'regulatory_proceeding', label: 'Regulatory Proceeding' },
  { value: 'other', label: 'Other' },
];

interface FormData {
  policyId: string;
  lossDate: string;
  claimType: string;
  description: string;
  reportedBy: string;
  contactEmail: string;
  contactPhone: string;
}

const initial: FormData = {
  policyId: '',
  lossDate: '',
  claimType: '',
  description: '',
  reportedBy: '',
  contactEmail: '',
  contactPhone: '',
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
    value: p.id,
    label: `${p.policy_number} — ${p.insured_name}`,
  }));

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string>> = {};
    if (!form.policyId) e.policyId = 'Policy is required';
    if (!form.lossDate) e.lossDate = 'Loss date is required';
    if (!form.claimType) e.claimType = 'Claim type is required';
    if (!form.description.trim()) e.description = 'Description is required';
    else if (form.description.trim().length < 20) e.description = 'Description must be at least 20 characters';
    if (!form.reportedBy.trim()) e.reportedBy = 'Reported by is required';
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
        policy_id: form.policyId,
        date_of_loss: form.lossDate,
        claim_type: form.claimType,
        description: form.description,
        reported_by: form.reportedBy,
        contact_email: form.contactEmail || undefined,
        contact_phone: form.contactPhone || undefined,
      };
      const result = await createClaim(payload);
      const claimNum = result?.claim_number || '';
      setToast({ type: 'success', message: claimNum ? `Claim ${claimNum} filed successfully!` : 'Claim filed successfully!' });
      setTimeout(() => navigate('/claims'), 800);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
        ?? (err as { message?: string })?.message ?? 'Failed to file claim';
      setToast({ type: 'error', message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/claims')} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">File a Claim</h1>
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
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Claim Details</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="select" label="Policy" name="policyId" value={form.policyId} onChange={(v) => set('policyId', v)} options={policyOptions} placeholder="Select policy…" error={errors.policyId} required />
            <FormField type="date" label="Date of Loss" name="lossDate" value={form.lossDate} onChange={(v) => set('lossDate', v)} error={errors.lossDate} required />
            <FormField type="select" label="Claim Type" name="claimType" value={form.claimType} onChange={(v) => set('claimType', v)} options={CLAIM_TYPE_OPTIONS} placeholder="Select type…" error={errors.claimType} required />
          </div>
          <div className="mt-4">
            <FormField type="textarea" label="Description" name="description" value={form.description} onChange={(v) => set('description', v)} placeholder="Describe the loss event in detail…" rows={4} minLength={20} error={errors.description} required />
          </div>
        </section>

        {/* Reporter Information */}
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Reporter Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="text" label="Reported By" name="reportedBy" value={form.reportedBy} onChange={(v) => set('reportedBy', v)} error={errors.reportedBy} required />
            <FormField type="email" label="Contact Email" name="contactEmail" value={form.contactEmail} onChange={(v) => set('contactEmail', v)} />
            <FormField type="tel" label="Contact Phone" name="contactPhone" value={form.contactPhone} onChange={(v) => set('contactPhone', v)} />
          </div>
        </section>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={() => navigate('/claims')} className="rounded-lg border border-slate-200/60 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50 transition-all"
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
