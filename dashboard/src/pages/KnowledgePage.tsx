import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { BookOpen, FileText, ShieldCheck, Scale, Shield, Loader2, Search, Pencil, X, Check, Globe, Building2, RefreshCw } from 'lucide-react';
import { getGuidelines, getRatingFactors, getCoverageOptions, getClaimsPrecedents, getComplianceRules, searchKnowledge, updateGuidelines, getIndustryProfiles, getJurisdictionRules, getSyncStatus } from '../api/knowledge';
import EmptyState from '../components/EmptyState';

type KnowledgeTab = 'guidelines' | 'rating' | 'coverage' | 'claims' | 'compliance' | 'industry' | 'jurisdiction';

const TABS: { key: KnowledgeTab; label: string; icon: typeof BookOpen }[] = [
  { key: 'guidelines', label: 'Guidelines', icon: BookOpen },
  { key: 'rating', label: 'Rating Factors', icon: FileText },
  { key: 'coverage', label: 'Coverage Options', icon: Shield },
  { key: 'claims', label: 'Claims Precedents', icon: Scale },
  { key: 'compliance', label: 'Compliance Rules', icon: ShieldCheck },
  { key: 'industry', label: 'Industry Profiles', icon: Building2 },
  { key: 'jurisdiction', label: 'Jurisdiction Rules', icon: Globe },
];

const LOBS = ['cyber', 'general_liability', 'property'] as const;

function formatLabel(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
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

function Badge({ children, color = 'indigo' }: { children: React.ReactNode; color?: string }) {
  const colors: Record<string, string> = {
    indigo: 'bg-indigo-50 text-indigo-600',
    green: 'bg-emerald-50 text-emerald-600',
    amber: 'bg-amber-50 text-amber-700',
    red: 'bg-red-50 text-red-600',
  };
  return (
    <span className={`text-xs font-semibold rounded-full px-2.5 py-0.5 ${colors[color] || colors.indigo}`}>
      {children}
    </span>
  );
}

/* ── Search Bar ── */
function SearchBar({ onSearch }: { onSearch: (q: string) => void }) {
  const [query, setQuery] = useState('');
  return (
    <div className="relative w-full max-w-md">
      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
      <input
        type="text"
        placeholder="Search knowledge base…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && query.trim()) onSearch(query.trim()); }}
        className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
      />
    </div>
  );
}

/* ── Search Results ── */
function SearchResults({ query, onClose }: { query: string; onClose: () => void }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-search', query],
    queryFn: () => searchKnowledge(query),
    enabled: !!query,
  });

  return (
    <Card className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-800">
          Search results for &ldquo;{query}&rdquo;
        </h3>
        <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg">
          <X size={16} className="text-slate-400" />
        </button>
      </div>
      {isLoading && <LoadingState />}
      {isError && <ErrorState message="Search failed." />}
      {data && data.results?.length === 0 && <p className="text-sm text-slate-500">No results found.</p>}
      {data && data.results?.length > 0 && (
        <div className="space-y-3">
          {data.results.map((r: Record<string, unknown>, i: number) => (
            <div key={i} className="border-l-2 border-indigo-200 pl-3 py-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge>{String(r.category || r.entityType || 'unknown')}</Badge>
                <span className="text-xs text-slate-400">{String(r.id)}</span>
              </div>
              <p className="text-sm text-slate-700">{String(r.content || '')}</p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ── Guidelines Tab ── */
function GuidelinesTab() {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<string | null>(null);
  const [editJson, setEditJson] = useState('');

  const queries = LOBS.map((lob) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({
      queryKey: ['knowledge-guidelines', lob],
      queryFn: () => getGuidelines(lob),
      retry: 1,
    }),
  );

  const mutation = useMutation({
    mutationFn: ({ lob, data }: { lob: string; data: Record<string, unknown> }) => updateGuidelines(lob, data),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['knowledge-guidelines', vars.lob] });
      setEditing(null);
    },
  });

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.every((q) => q.isError);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load guidelines." />;

  const allEmpty = queries.every((q) => !q.data?.guidelines?.length);
  if (allEmpty) return <EmptyState icon={BookOpen} title="No guidelines found" description="Underwriting guidelines will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
      {queries.map((q, i) => {
        const lob = LOBS[i];
        const data = q.data;
        if (!data?.guidelines?.length) return null;

        return data.guidelines.map((g: Record<string, unknown>, gi: number) => {
          const isEditing = editing === lob;
          const appetite = g.appetite as Record<string, unknown> | undefined;
          const secReq = appetite?.security_requirements as Record<string, unknown> | undefined;

          return (
            <Card key={`${lob}-${gi}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-slate-800">{formatLabel(lob)}</h3>
                {!isEditing ? (
                  <button
                    onClick={() => { setEditing(lob); setEditJson(JSON.stringify(g, null, 2)); }}
                    className="p-1.5 hover:bg-slate-100 rounded-lg"
                    title="Edit guidelines"
                  >
                    <Pencil size={14} className="text-slate-400" />
                  </button>
                ) : (
                  <div className="flex gap-1">
                    <button
                      onClick={() => {
                        try { mutation.mutate({ lob, data: JSON.parse(editJson) }); } catch { /* ignore parse errors */ }
                      }}
                      className="p-1.5 hover:bg-emerald-50 rounded-lg"
                      title="Save"
                    >
                      <Check size={14} className="text-emerald-600" />
                    </button>
                    <button onClick={() => setEditing(null)} className="p-1.5 hover:bg-slate-100 rounded-lg" title="Cancel">
                      <X size={14} className="text-slate-400" />
                    </button>
                  </div>
                )}
              </div>
              {isEditing ? (
                <textarea
                  value={editJson}
                  onChange={(e) => setEditJson(e.target.value)}
                  className="w-full h-64 text-xs font-mono border border-slate-200 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                />
              ) : (
                <div className="divide-y divide-slate-100">
                  {appetite && (
                    <>
                      <FieldRow label="target_industries" value={(appetite.target_industries as string[])?.join(', ')} />
                      <FieldRow label="revenue_range" value={
                        appetite.revenue_range
                          ? `${formatCurrency((appetite.revenue_range as Record<string, number>).min)} - ${formatCurrency((appetite.revenue_range as Record<string, number>).max)}`
                          : undefined
                      } />
                      <FieldRow label="employee_range" value={appetite.employee_range} />
                      <FieldRow label="sic_codes" value={appetite.sic_codes} />
                      {secReq && (
                        <>
                          <FieldRow label="min_security_score" value={secReq.minimum_score} />
                          <FieldRow label="required_controls" value={secReq.required_controls} />
                          <FieldRow label="preferred_controls" value={secReq.preferred_controls} />
                        </>
                      )}
                      <FieldRow label="max_prior_incidents" value={appetite.max_prior_incidents} />
                    </>
                  )}
                  <FieldRow label="exclusions" value={g.exclusions} />
                  <FieldRow label="subjectivities" value={g.subjectivities} />
                </div>
              )}
            </Card>
          );
        });
      })}
    </div>
  );
}

/* ── Rating Factors Tab ── */
function RatingFactorsTab() {
  const queries = LOBS.map((lob) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({
      queryKey: ['knowledge-rating-factors', lob],
      queryFn: () => getRatingFactors(lob),
      retry: 1,
    }),
  );

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.every((q) => q.isError);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load rating factors." />;

  return (
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
      {queries.map((q, i) => {
        const lob = LOBS[i];
        const data = q.data;
        if (!data?.rating_factors) return null;
        const rf = data.rating_factors as Record<string, unknown>;

        return (
          <Card key={lob}>
            <h3 className="text-sm font-semibold text-slate-800 mb-3">{formatLabel(lob)}</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Base Rate</span>
                <Badge color="green">${String(rf.base_rate_per_1000 || rf.base_rate_per_1000)}/1K revenue</Badge>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Min Premium</span>
                <Badge color="amber">{formatCurrency(rf.minimum_premium as number)}</Badge>
              </div>
              {Object.entries(rf).filter(([k]) => k.endsWith('_factors')).map(([key, factors]) => (
                <div key={key}>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1">{formatLabel(key)}</p>
                  <div className="bg-slate-50 rounded-lg p-2">
                    <table className="w-full text-xs">
                      <tbody>
                        {Object.entries(factors as Record<string, number>).map(([fk, fv]) => (
                          <tr key={fk} className="border-b border-slate-100 last:border-0">
                            <td className="py-1 text-slate-600">{formatLabel(fk)}</td>
                            <td className="py-1 text-right font-mono">
                              <span className={fv < 1 ? 'text-emerald-600' : fv > 1 ? 'text-red-600' : 'text-slate-600'}>
                                {fv}x
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        );
      })}
    </div>
  );
}

/* ── Coverage Options Tab ── */
function CoverageOptionsTab() {
  const queries = LOBS.map((lob) =>
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useQuery({
      queryKey: ['knowledge-coverage-options', lob],
      queryFn: () => getCoverageOptions(lob),
      retry: 1,
    }),
  );

  const isLoading = queries.some((q) => q.isLoading);
  const isError = queries.every((q) => q.isError);

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load coverage options." />;

  return (
    <div className="space-y-6">
      {queries.map((q, i) => {
        const lob = LOBS[i];
        const data = q.data;
        if (!data?.coverage_options?.length) return null;

        return (
          <div key={lob}>
            <h3 className="text-sm font-semibold text-slate-800 mb-3">{formatLabel(lob)}</h3>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {data.coverage_options.map((cov: Record<string, unknown>, ci: number) => (
                <Card key={ci} className="flex flex-col">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="text-sm font-medium text-slate-800">{String(cov.name)}</h4>
                    <Badge color="green">{formatCurrency(cov.default_limit as number)}</Badge>
                  </div>
                  <p className="text-xs text-slate-500 flex-1">{String(cov.description)}</p>
                </Card>
              ))}
            </div>
          </div>
        );
      })}
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
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2">
      {data.precedents.map((p: Record<string, unknown>, i: number) => {
        const reserveRange = p.typical_reserve_range as number[] | undefined;
        const cases = p.case_examples as Record<string, unknown>[] | undefined;

        return (
          <Card key={i}>
            <div className="flex items-center gap-2 mb-3">
              <h3 className="text-sm font-semibold text-slate-800">{formatLabel(String(Object.keys(data.precedents.length > 1 ? {} : p)[0] || `Type ${i + 1}`))}</h3>
              {p.average_resolution_days != null && (
                <Badge color="amber">{String(p.average_resolution_days)} days avg</Badge>
              )}
            </div>
            {reserveRange && (
              <div className="mb-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Reserve Range</span>
                <p className="text-sm text-slate-700">
                  {formatCurrency(reserveRange[0])} – {formatCurrency(reserveRange[1])}
                </p>
              </div>
            )}
            <FieldRow label="common_costs" value={p.common_costs} />
            <FieldRow label="red_flags" value={p.red_flags} />
            {p.common_patterns != null ? <FieldRow label="common_patterns" value={p.common_patterns} /> : null}
            {p.recovery_rate != null && <FieldRow label="recovery_rate" value={`${(p.recovery_rate as number) * 100}%`} />}
            {p.notification_deadlines != null ? <FieldRow label="notification_deadlines" value={p.notification_deadlines} /> : null}
            {cases && cases.length > 0 && (
              <div className="mt-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Case Examples</span>
                <div className="mt-1 space-y-2">
                  {cases.map((ex, ci) => (
                    <div key={ci} className="bg-slate-50 rounded-lg p-2 text-xs">
                      <p className="text-slate-700 mb-1">{String(ex.description)}</p>
                      <div className="flex gap-3 text-slate-500">
                        <span>Reserve: {formatCurrency(ex.reserve as number)}</span>
                        <span>Settlement: {formatCurrency(ex.settlement as number)}</span>
                        <span>{String(ex.duration_days)} days</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        );
      })}
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
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
      {data.rules.map((r: Record<string, unknown>, i: number) => {
        const articles = r.articles as Record<string, Record<string, string>> | undefined;

        return (
          <Card key={i}>
            <h3 className="text-sm font-semibold text-slate-800 mb-3">{formatLabel(String(Object.keys(r)[0] || `Framework ${i + 1}`))}</h3>
            {articles && (
              <div className="space-y-2 mb-3">
                {Object.entries(articles).map(([key, art]) => (
                  <div key={key} className="bg-slate-50 rounded-lg p-2">
                    <div className="flex items-center gap-2 mb-1">
                      <Badge>{key.replace('_', ' ').toUpperCase()}</Badge>
                      <span className="text-xs font-medium text-slate-700">{art.title}</span>
                    </div>
                    <p className="text-xs text-slate-500">{art.requirement}</p>
                    {art.implementation && (
                      <p className="text-xs text-emerald-600 mt-1">✓ {art.implementation}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
            {r.requirement != null ? <FieldRow label="requirement" value={r.requirement} /> : null}
            {r.key_provisions != null ? <FieldRow label="key_provisions" value={r.key_provisions} /> : null}
            {r.penalties != null ? <FieldRow label="penalties" value={r.penalties} /> : null}
            {r.data_retention_days != null ? <FieldRow label="data_retention" value={`${Math.round((r.data_retention_days as number) / 365)} years`} /> : null}
            {r.right_to_explanation != null && <FieldRow label="right_to_explanation" value={r.right_to_explanation ? 'Yes' : 'No'} />}
          </Card>
        );
      })}
    </div>
  );
}

/* ── Industry Profiles Tab ── */
function IndustryProfilesTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-industry-profiles'],
    queryFn: getIndustryProfiles,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load industry profiles." />;
  if (!data?.profiles?.length) return <EmptyState icon={Building2} title="No industry profiles" description="Industry-specific risk profiles will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
      {data.profiles.map((p: Record<string, unknown>, i: number) => (
        <Card key={i}>
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-sm font-semibold text-slate-800">{formatLabel(String(p.industry || `Industry ${i + 1}`))}</h3>
            {p.premium_adjustment != null && (
              <Badge color={(p.premium_adjustment as number) > 1 ? 'red' : 'green'}>
                {(p.premium_adjustment as number)}x premium
              </Badge>
            )}
          </div>
          <FieldRow label="regulatory_frameworks" value={p.regulatory_frameworks} />
          <FieldRow label="key_risks" value={p.key_risks} />
          <FieldRow label="required_controls" value={p.required_controls} />
          <FieldRow label="typical_claim_types" value={p.typical_claim_types} />
          {p.avg_breach_cost_per_record != null && (
            <FieldRow label="avg_breach_cost_per_record" value={`$${String(p.avg_breach_cost_per_record)}`} />
          )}
          <FieldRow label="regulatory_fine_exposure" value={p.regulatory_fine_exposure} />
        </Card>
      ))}
    </div>
  );
}

/* ── Jurisdiction Rules Tab ── */
function JurisdictionRulesTab() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['knowledge-jurisdiction-rules'],
    queryFn: getJurisdictionRules,
    retry: 1,
  });

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message="Failed to load jurisdiction rules." />;
  if (!data?.rules?.length) return <EmptyState icon={Globe} title="No jurisdiction rules" description="Jurisdiction-specific compliance rules will appear here once configured." />;

  return (
    <div className="grid gap-5 sm:grid-cols-1 lg:grid-cols-2 xl:grid-cols-3">
      {data.rules.map((r: Record<string, unknown>, i: number) => (
        <Card key={i}>
          <div className="flex items-center gap-2 mb-3">
            <h3 className="text-sm font-semibold text-slate-800">{String(r.territory || `Territory ${i + 1}`)}</h3>
            <Badge>{String(r.framework || 'Unknown')}</Badge>
          </div>
          <FieldRow label="requirements" value={r.requirements} />
          <FieldRow label="notification_deadline" value={r.notification_deadline} />
          <FieldRow label="key_regulations" value={r.key_regulations} />
        </Card>
      ))}
    </div>
  );
}

/* ── Sync Status Badge ── */
function SyncStatusBadge() {
  const { data, isLoading } = useQuery({
    queryKey: ['knowledge-sync-status'],
    queryFn: getSyncStatus,
    refetchInterval: 30_000,
    retry: 1,
  });

  if (isLoading) return null;

  const source = data?.source || 'unknown';
  const cosmosAvailable = data?.cosmos_available || false;

  return (
    <div className="flex items-center gap-2 text-xs">
      <RefreshCw size={12} className={cosmosAvailable ? 'text-emerald-500' : 'text-amber-500'} />
      <span className={cosmosAvailable ? 'text-emerald-600 font-medium' : 'text-amber-600 font-medium'}>
        {cosmosAvailable ? 'Cosmos DB synced' : 'In-memory fallback'}
      </span>
      <span className="text-slate-400">Source: {source}</span>
    </div>
  );
}

/* ── Main Page ── */
export default function KnowledgePage() {
  const [activeTab, setActiveTab] = useState<KnowledgeTab>('guidelines');
  const [searchQuery, setSearchQuery] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Knowledge Base</h1>
          <p className="mt-1 text-sm text-slate-500">Browse underwriting guidelines, rating factors, coverage options, claims precedents, compliance rules, industry profiles, and jurisdiction rules.</p>
          <div className="mt-2">
            <SyncStatusBadge />
          </div>
        </div>
        <SearchBar onSearch={(q) => setSearchQuery(q)} />
      </div>

      {/* Search results */}
      {searchQuery && <SearchResults query={searchQuery} onClose={() => setSearchQuery(null)} />}

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl bg-slate-100/60 p-1 w-fit flex-wrap">
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
      {activeTab === 'coverage' && <CoverageOptionsTab />}
      {activeTab === 'claims' && <ClaimsPrecedentsTab />}
      {activeTab === 'compliance' && <ComplianceRulesTab />}
      {activeTab === 'industry' && <IndustryProfilesTab />}
      {activeTab === 'jurisdiction' && <JurisdictionRulesTab />}
    </div>
  );
}
