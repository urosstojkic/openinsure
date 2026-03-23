import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, FileText, ShieldCheck, Scale, Loader2 } from 'lucide-react';
import { getGuidelines, getProducts, getClaimsPrecedents, getComplianceRules } from '../api/knowledge';
import EmptyState from '../components/EmptyState';

type KnowledgeTab = 'guidelines' | 'rating' | 'claims' | 'compliance';

const TABS: { key: KnowledgeTab; label: string }[] = [
  { key: 'guidelines', label: 'Guidelines' },
  { key: 'rating', label: 'Rating Factors' },
  { key: 'claims', label: 'Claims Precedents' },
  { key: 'compliance', label: 'Compliance Rules' },
];

const LOBS = ['cyber', 'general_liability', 'property'] as const;

function formatLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)] ${className}`}>
      {children}
    </div>
  );
}

function LoadingState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <Loader2 size={28} className="animate-spin text-indigo-500 mb-3" />
      <p className="text-sm text-slate-500">Loading knowledge base…</p>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <p className="text-sm text-red-500">{message}</p>
    </div>
  );
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  if (value == null) return null;

  let display: React.ReactNode;
  if (Array.isArray(value)) {
    display = value.length > 0 ? value.join(', ') : '—';
  } else if (typeof value === 'object') {
    display = (
      <pre className="mt-1 whitespace-pre-wrap text-xs text-slate-600 bg-slate-50 rounded-lg p-2">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  } else {
    display = String(value);
  }

  return (
    <div className="py-1.5">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{formatLabel(label)}</span>
      <div className="text-sm text-slate-700 mt-0.5">{display}</div>
    </div>
  );
}

/* ── Guidelines Tab ── */
function GuidelinesTab() {
  const queries = LOBS.map((lob) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({
      queryKey: ['knowledge-guidelines', lob],
      queryFn: () => getGuidelines(lob),
      retry: 1,
    }),
  );

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.every((q) => q.isError);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load guidelines." />;

  const allEmpty = queries.every((q) => !q.data?.guidelines?.length);
  if (allEmpty) return <EmptyState icon={BookOpen} title="No guidelines found" description="Underwriting guidelines will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {queries.map((q, i) => {
        const lob = LOBS[i];
        const data = q.data;
        if (!data?.guidelines?.length) return null;

        return data.guidelines.map((g: Record<string, unknown>, gi: number) => (
          <Card key={`${lob}-${gi}`}>
            <h3 className="text-sm font-semibold text-slate-800 mb-3">{formatLabel(lob)}</h3>
            <div className="divide-y divide-slate-100">
              {['min_revenue', 'max_revenue', 'excluded_industries', 'required_controls', 'authority_tiers', 'minimum_premium'].map(
                (field) => <FieldRow key={field} label={field} value={g[field]} />,
              )}
            </div>
          </Card>
        ));
      })}
    </div>
  );
}

/* ── Rating Factors Tab ── */
function RatingFactorsTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-products'],
    queryFn: getProducts,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load products." />;
  if (!data?.products?.length) return <EmptyState icon={FileText} title="No products found" description="Rating factor products will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {data.products.map((p: Record<string, unknown>, i: number) => (
        <Card key={i}>
          <h3 className="text-sm font-semibold text-slate-800 mb-1">{String(p.name || p.product_name || `Product ${i + 1}`)}</h3>
          {p.code ? <p className="text-xs text-slate-400 mb-3">Code: {String(p.code)}</p> : null}
          <div className="divide-y divide-slate-100">
            <FieldRow label="Line of Business" value={p.line_of_business || p.lob} />
            <FieldRow label="Rating Rules" value={p.rating_rules} />
            <FieldRow label="Underwriting Rules" value={p.underwriting_rules} />
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── Claims Precedents Tab ── */
function ClaimsPrecedentsTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-claims-precedents'],
    queryFn: getClaimsPrecedents,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load claims precedents." />;
  if (!data?.precedents?.length) return <EmptyState icon={Scale} title="No claims precedents" description="Claims precedent data will appear here once available." />;

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {data.claim_type && (
        <div className="sm:col-span-2 lg:col-span-3 mb-1">
          <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 rounded-full px-3 py-1">
            {formatLabel(String(data.claim_type))}
          </span>
        </div>
      )}
      {data.precedents.map((p: Record<string, unknown>, i: number) => (
        <Card key={i}>
          <h3 className="text-sm font-semibold text-slate-800 mb-2">{String(p.title || p.name || `Precedent ${i + 1}`)}</h3>
          <div className="divide-y divide-slate-100">
            {Object.entries(p)
              .filter(([k]) => k !== 'title' && k !== 'name')
              .map(([k, v]) => (
                <FieldRow key={k} label={k} value={v} />
              ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── Compliance Rules Tab ── */
function ComplianceRulesTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-compliance-rules'],
    queryFn: getComplianceRules,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load compliance rules." />;
  if (!data?.rules?.length) return <EmptyState icon={ShieldCheck} title="No compliance rules" description="Compliance rules will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
      {data.framework && (
        <div className="sm:col-span-2 lg:col-span-3 mb-1">
          <span className="text-xs font-semibold text-indigo-600 bg-indigo-50 rounded-full px-3 py-1">
            {formatLabel(String(data.framework))}
          </span>
        </div>
      )}
      {data.rules.map((r: Record<string, unknown>, i: number) => (
        <Card key={i}>
          <h3 className="text-sm font-semibold text-slate-800 mb-2">{String(r.title || r.name || `Rule ${i + 1}`)}</h3>
          <div className="divide-y divide-slate-100">
            {Object.entries(r)
              .filter(([k]) => k !== 'title' && k !== 'name')
              .map(([k, v]) => (
                <FieldRow key={k} label={k} value={v} />
              ))}
          </div>
        </Card>
      ))}
    </div>
  );
}

/* ── Main Page ── */
export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<KnowledgeTab>('guidelines');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Knowledge Base</h1>
        <p className="mt-1 text-sm text-slate-500">Browse underwriting guidelines, rating factors, claims precedents, and compliance rules.</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-slate-100/60 p-1 w-fit">
        {TABS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === key
                ? 'bg-indigo-50 text-indigo-600'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'guidelines' && <GuidelinesTab />}
      {activeTab === 'rating' && <RatingFactorsTab />}
      {activeTab === 'claims' && <ClaimsPrecedentsTab />}
      {activeTab === 'compliance' && <ComplianceRulesTab />}
    </div>
  );
}
