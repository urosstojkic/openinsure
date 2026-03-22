import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import FormField from '../components/FormField';
import { createSubmission } from '../api/submissions';

const US_STATES = [
  'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ',
  'NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT',
  'VA','WA','WV','WI','WY','DC',
];

const LOB_OPTIONS = [
  { value: 'cyber', label: 'Cyber' },
  { value: 'professional_liability', label: 'Professional Liability' },
  { value: 'dnol', label: 'D&O' },
  { value: 'epli', label: 'EPLI' },
  { value: 'general_liability', label: 'General Liability' },
];

const CHANNEL_OPTIONS = [
  { value: 'email', label: 'Email' },
  { value: 'api', label: 'API' },
  { value: 'portal', label: 'Portal' },
  { value: 'broker_platform', label: 'Broker Platform' },
];

interface FormData {
  companyName: string;
  contactName: string;
  contactEmail: string;
  contactPhone: string;
  street: string;
  city: string;
  state: string;
  zip: string;
  lob: string;
  channel: string;
  effectiveDate: string;
  expirationDate: string;
  annualRevenue: number | '';
  employeeCount: number | '';
  industrySic: string;
  securityMaturity: number;
  hasMfa: boolean;
  hasEndpointProtection: boolean;
  hasBackupStrategy: boolean;
  hasIncidentResponsePlan: boolean;
  priorCyberIncidents: number | '';
}

const initial: FormData = {
  companyName: '',
  contactName: '',
  contactEmail: '',
  contactPhone: '',
  street: '',
  city: '',
  state: '',
  zip: '',
  lob: '',
  channel: '',
  effectiveDate: '',
  expirationDate: '',
  annualRevenue: '',
  employeeCount: '',
  industrySic: '',
  securityMaturity: 5,
  hasMfa: false,
  hasEndpointProtection: false,
  hasBackupStrategy: false,
  hasIncidentResponsePlan: false,
  priorCyberIncidents: '',
};

const NewSubmission: React.FC = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState<FormData>(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof FormData, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const set = <K extends keyof FormData>(key: K, value: FormData[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const validate = (): boolean => {
    const e: Partial<Record<keyof FormData, string>> = {};
    if (!form.companyName.trim()) e.companyName = 'Company name is required';
    if (!form.contactName.trim()) e.contactName = 'Contact name is required';
    if (!form.contactEmail.trim()) e.contactEmail = 'Email is required';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.contactEmail)) e.contactEmail = 'Invalid email';
    if (!form.lob) e.lob = 'Line of business is required';
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
        company_name: form.companyName,
        applicant_name: form.contactName,
        contact_email: form.contactEmail,
        contact_phone: form.contactPhone || undefined,
        address: {
          street: form.street || undefined,
          city: form.city || undefined,
          state: form.state || undefined,
          zip: form.zip || undefined,
        },
        lob: form.lob,
        channel: form.channel || undefined,
        requested_effective_date: form.effectiveDate || undefined,
        requested_expiration_date: form.expirationDate || undefined,
        annual_revenue: form.annualRevenue || undefined,
        employee_count: form.employeeCount || undefined,
        industry: form.industrySic || undefined,
        ...(form.lob === 'cyber' && {
          cyber_risk_data: {
            security_rating: form.securityMaturity * 10,
            mfa_enabled: form.hasMfa,
            endpoint_protection: form.hasEndpointProtection,
            backup_strategy: form.hasBackupStrategy,
            incident_response_plan: form.hasIncidentResponsePlan,
            prior_incidents: form.priorCyberIncidents || 0,
          },
        }),
      };
      const created = await createSubmission(payload);
      setToast({ type: 'success', message: 'Submission created successfully!' });
      setTimeout(() => navigate(`/submissions/${created.id}`), 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create submission';
      setToast({ type: 'error', message: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const isCyber = form.lob === 'cyber';

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button onClick={() => navigate('/submissions')} className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:bg-slate-50 hover:text-slate-700 hover:border-slate-300">
          <ArrowLeft size={18} />
        </button>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">New Submission</h1>
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
        {/* Applicant Information */}
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Applicant Information</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="text" label="Company Name" name="companyName" value={form.companyName} onChange={(v) => set('companyName', v)} error={errors.companyName} required />
            <FormField type="text" label="Contact Name" name="contactName" value={form.contactName} onChange={(v) => set('contactName', v)} error={errors.contactName} required />
            <FormField type="email" label="Contact Email" name="contactEmail" value={form.contactEmail} onChange={(v) => set('contactEmail', v)} error={errors.contactEmail} required />
            <FormField type="tel" label="Contact Phone" name="contactPhone" value={form.contactPhone} onChange={(v) => set('contactPhone', v)} />
            <FormField type="text" label="Street Address" name="street" value={form.street} onChange={(v) => set('street', v)} className="sm:col-span-2" />
            <FormField type="text" label="City" name="city" value={form.city} onChange={(v) => set('city', v)} />
            <div className="grid grid-cols-2 gap-4">
              <FormField type="select" label="State" name="state" value={form.state} onChange={(v) => set('state', v)} options={US_STATES.map((s) => ({ value: s, label: s }))} placeholder="Select…" />
              <FormField type="text" label="Zip Code" name="zip" value={form.zip} onChange={(v) => set('zip', v)} />
            </div>
          </div>
        </section>

        {/* Submission Details */}
        <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <h2 className="mb-4 text-sm font-semibold text-slate-800">Submission Details</h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField type="select" label="Line of Business" name="lob" value={form.lob} onChange={(v) => set('lob', v)} options={LOB_OPTIONS} placeholder="Select LOB…" error={errors.lob} required />
            <FormField type="select" label="Channel" name="channel" value={form.channel} onChange={(v) => set('channel', v)} options={CHANNEL_OPTIONS} placeholder="Select channel…" />
            <FormField type="date" label="Requested Effective Date" name="effectiveDate" value={form.effectiveDate} onChange={(v) => set('effectiveDate', v)} />
            <FormField type="date" label="Requested Expiration Date" name="expirationDate" value={form.expirationDate} onChange={(v) => set('expirationDate', v)} />
          </div>
        </section>

        {/* Cyber Risk Data */}
        {isCyber && (
          <section className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
            <h2 className="mb-4 text-sm font-semibold text-slate-800">Cyber Risk Data</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FormField type="currency" label="Annual Revenue" name="annualRevenue" value={form.annualRevenue} onChange={(v) => set('annualRevenue', v)} placeholder="0" />
              <FormField type="number" label="Employee Count" name="employeeCount" value={form.employeeCount} onChange={(v) => set('employeeCount', v)} min={0} />
              <FormField type="text" label="Industry SIC Code" name="industrySic" value={form.industrySic} onChange={(v) => set('industrySic', v)} />
              <FormField type="slider" label="Security Maturity Score" name="securityMaturity" value={form.securityMaturity} onChange={(v) => set('securityMaturity', v)} min={1} max={10} />
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <FormField type="checkbox" label="Has MFA" name="hasMfa" checked={form.hasMfa} onChange={(v) => set('hasMfa', v)} />
              <FormField type="checkbox" label="Endpoint Protection" name="hasEndpointProtection" checked={form.hasEndpointProtection} onChange={(v) => set('hasEndpointProtection', v)} />
              <FormField type="checkbox" label="Backup Strategy" name="hasBackupStrategy" checked={form.hasBackupStrategy} onChange={(v) => set('hasBackupStrategy', v)} />
              <FormField type="checkbox" label="Incident Response Plan" name="hasIncidentResponsePlan" checked={form.hasIncidentResponsePlan} onChange={(v) => set('hasIncidentResponsePlan', v)} />
            </div>
            <div className="mt-4 max-w-xs">
              <FormField type="number" label="Prior Cyber Incidents" name="priorCyberIncidents" value={form.priorCyberIncidents} onChange={(v) => set('priorCyberIncidents', v)} min={0} />
            </div>
          </section>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-3">
          <button type="button" onClick={() => navigate('/submissions')} className="rounded-lg border border-slate-200/60 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-all">
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 active:scale-[0.98] disabled:opacity-50 transition-all"
          >
            {submitting && <Loader2 size={16} className="animate-spin" />}
            {submitting ? 'Submitting…' : 'Submit'}
          </button>
        </div>
      </form>
    </div>
  );
};

export default NewSubmission;
