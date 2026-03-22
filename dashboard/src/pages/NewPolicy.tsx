import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle, Plus, Trash2 } from 'lucide-react';
import FormField from '../components/FormField';
import { createPolicy } from '../api/policies';
import { getProducts } from '../api/products';

const COVERAGE_CODE_OPTIONS = [
  { value: 'BREACH-RESP', label: 'Breach Response' },
  { value: 'THIRD-PARTY', label: 'Third Party Liability' },
  { value: 'REG-DEFENSE', label: 'Regulatory Defense' },
  { value: 'BUS-INTERRUPT', label: 'Business Interruption' },
  { value: 'RANSOMWARE', label: 'Ransomware' },
];

interface Coverage {
  code: string;
  limit: number | '';
  deductible: number | '';
  premium: number | '';
}

interface FormData {
  policyNumber: string;
  product: string;
  insuredName: string;
  effectiveDate: string;
  expirationDate: string;
  totalPremium: number | '';
}

const emptyRow = (): Coverage => ({ code: '', limit: '', deductible: '', premium: '' });

const initial: FormData = {
  policyNumber: '',
  product: '',
  insuredName: '',
  effectiveDate: '',
  expirationDate: '',
  totalPremium: '',
};

const NewPolicy: React.FC = () => {
  const navigate = useNavigate();
  const { data: products = [] } = useQuery({ queryKey: ['products'], queryFn: getProducts });

  const [form, setForm] = useState<FormData>(initial);
  const [coverages, setCoverages] = useState<Coverage[]>([emptyRow()]);
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const set = <K extends keyof FormData>(key: K, value: FormData[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const setCov = (idx: number, field: keyof Coverage, value: Coverage[keyof Coverage]) =>
    setCoverages((prev) => prev.map((c, i) => (i === idx ? { ...c, [field]: value } : c)));

  const addCoverage = () => setCoverages((prev) => [...prev, emptyRow()]);
  const removeCoverage = (idx: number) => setCoverages((prev) => prev.filter((_, i) => i !== idx));

  const productOptions = products.map((p) => ({ value: p.id, label: p.name }));

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string>> = {};
    if (!form.insuredName.trim()) e.insuredName = 'Insured company name is required';
    if (!form.effectiveDate) e.effectiveDate = 'Effective date is required';
    if (!form.expirationDate) e.expirationDate = 'Expiration date is required';
    if (form.totalPremium === '' || form.totalPremium <= 0) e.totalPremium = 'Total premium is required';
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
        policy_number: form.policyNumber || undefined,
        product_id: form.product || undefined,
        insured_name: form.insuredName,
        effective_date: form.effectiveDate,
        expiration_date: form.expirationDate,
        premium: form.totalPremium as number,
        coverages: coverages
          .filter((c) => c.code)
          .map((c) => ({
            code: c.code,
            limit: c.limit || 0,
            deductible: c.deductible || 0,
            premium: c.premium || 0,
          })),
      };
      await createPolicy(payload);
      setToast({ type: 'success', message: 'Policy created successfully!' });
      setTimeout(() => navigate('/policies'), 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create policy';
      setToast({ type: 'error', message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/policies')} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">New Policy</h1>
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
        {/* Policy Details */}
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Policy Details</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="text" label="Policy Number" name="policyNumber" value={form.policyNumber} onChange={(v) => set('policyNumber', v)} placeholder="Auto-generated if blank" />
            <FormField type="select" label="Product" name="product" value={form.product} onChange={(v) => set('product', v)} options={productOptions} placeholder="Select product…" />
            <FormField type="text" label="Insured Company Name" name="insuredName" value={form.insuredName} onChange={(v) => set('insuredName', v)} error={errors.insuredName} required />
            <FormField type="currency" label="Total Premium" name="totalPremium" value={form.totalPremium} onChange={(v) => set('totalPremium', v)} error={errors.totalPremium} required />
            <FormField type="date" label="Effective Date" name="effectiveDate" value={form.effectiveDate} onChange={(v) => set('effectiveDate', v)} error={errors.effectiveDate} required />
            <FormField type="date" label="Expiration Date" name="expirationDate" value={form.expirationDate} onChange={(v) => set('expirationDate', v)} error={errors.expirationDate} required />
          </div>
        </section>

        {/* Coverages */}
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-800">Coverages</h2>
            <button type="button" onClick={addCoverage} className="inline-flex items-center gap-1 rounded-lg border border-slate-200/60 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition-all">
              <Plus size={14} /> Add Coverage
            </button>
          </div>

          <div className="space-y-4">
            {coverages.map((cov, idx) => (
              <div key={idx} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">Coverage #{idx + 1}</span>
                  {coverages.length > 1 && (
                    <button type="button" onClick={() => removeCoverage(idx)} className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700">
                      <Trash2 size={12} /> Remove
                    </button>
                  )}
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <FormField type="select" label="Coverage Code" name={`cov-code-${idx}`} value={cov.code} onChange={(v) => setCov(idx, 'code', v)} options={COVERAGE_CODE_OPTIONS} placeholder="Select…" />
                  <FormField type="currency" label="Limit" name={`cov-limit-${idx}`} value={cov.limit} onChange={(v) => setCov(idx, 'limit', v)} />
                  <FormField type="currency" label="Deductible" name={`cov-ded-${idx}`} value={cov.deductible} onChange={(v) => setCov(idx, 'deductible', v)} />
                  <FormField type="currency" label="Premium" name={`cov-prem-${idx}`} value={cov.premium} onChange={(v) => setCov(idx, 'premium', v)} />
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={() => navigate('/policies')} className="rounded-lg border border-slate-200/60 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50 transition-all"
          >
            {submitting && <Loader2 size={16} className="animate-spin" />}
            {submitting ? 'Creating…' : 'Create Policy'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NewPolicy;
