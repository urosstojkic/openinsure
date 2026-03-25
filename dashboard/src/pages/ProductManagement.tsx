import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Package, Plus, ChevronRight, ArrowLeft, Save, Rocket, GitBranch,
  Shield, BarChart3, FileText, Settings, History, Globe, AlertTriangle,
  Pencil, Check, X, GripVertical, Trash2,
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts';
import StatusBadge from '../components/StatusBadge';
import StatCard from '../components/StatCard';
import { useToast } from '../components/useToast';
import Toast from '../components/Toast';
import {
  getProducts, getProduct, updateProduct, publishProduct,
  createProductVersion, getProductPerformance, createProduct,
} from '../api/products';
import type {
  ProductDetail, CoverageDefinition, RatingFactorTable,
  AppetiteRule, AuthorityLimit, ProductPerformance,
} from '../api/products';

/* ── Helpers ── */

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);
const pct = (n: number) => `${Math.round(n * 100)}%`;
const statusVariant = (s: string) =>
  ({ active: 'green', draft: 'yellow', retired: 'gray', sunset: 'orange' }[s] ?? 'gray') as
    'green' | 'yellow' | 'gray' | 'orange';
const lobLabel = (l: string) =>
  ({ cyber: 'Cyber', tech_eo: 'Tech E&O', mpl: 'MPL' }[l] ?? l);

type Tab = 'overview' | 'coverages' | 'rating' | 'appetite' | 'authority' | 'performance' | 'history';

/* ── Main Component ── */

const ProductManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const { toasts, addToast, removeToast } = useToast();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showCreate, setShowCreate] = useState(false);

  /* ── Queries ── */
  const { data: products = [], isLoading } = useQuery({
    queryKey: ['products'],
    queryFn: getProducts,
  });

  const { data: detail } = useQuery({
    queryKey: ['product', selectedId],
    queryFn: () => getProduct(selectedId!),
    enabled: !!selectedId,
  });

  const { data: perf } = useQuery<ProductPerformance>({
    queryKey: ['product-performance', selectedId],
    queryFn: () => getProductPerformance(selectedId!),
    enabled: !!selectedId && activeTab === 'performance',
  });

  /* ── Mutations ── */
  const saveMutation = useMutation({
    mutationFn: (p: { id: string; body: Partial<ProductDetail> }) => updateProduct(p.id, p.body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', selectedId] });
      addToast('success', 'Product saved');
    },
    onError: () => addToast('error', 'Failed to save product'),
  });

  const publishMutation = useMutation({
    mutationFn: (id: string) => publishProduct(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', selectedId] });
      addToast('success', 'Product published — now active');
    },
    onError: (e: Error) => addToast('error', e.message || 'Publish failed'),
  });

  const versionMutation = useMutation({
    mutationFn: (id: string) => createProductVersion(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', selectedId] });
      addToast('success', 'New version created');
    },
    onError: () => addToast('error', 'Version creation failed'),
  });

  const createMutation = useMutation({
    mutationFn: (body: Partial<ProductDetail>) => createProduct(body),
    onSuccess: (p) => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      setSelectedId(p.id);
      setShowCreate(false);
      addToast('success', 'Product created');
    },
    onError: () => addToast('error', 'Failed to create product'),
  });

  const filtered = useMemo(() => {
    if (statusFilter === 'all') return products;
    return products.filter((p) => p.status === statusFilter);
  }, [products, statusFilter]);

  /* ── Sub-views ── */

  if (showCreate) {
    return (
      <>
        <CreateProductView
          onCancel={() => setShowCreate(false)}
          onCreate={(body) => createMutation.mutate(body)}
          isLoading={createMutation.isPending}
        />
        {toasts.map((t) => <Toast key={t.id} type={t.type} message={t.message} onClose={() => removeToast(t.id)} />)}
      </>
    );
  }

  if (selectedId && detail) {
    return (
      <>
        <ProductDetailView
          product={detail}
          performance={perf ?? null}
          activeTab={activeTab}
          onTabChange={setActiveTab}
          onBack={() => { setSelectedId(null); setActiveTab('overview'); }}
          onSave={(body) => saveMutation.mutate({ id: detail.id, body })}
          onPublish={() => publishMutation.mutate(detail.id)}
          onNewVersion={() => versionMutation.mutate(detail.id)}
          isSaving={saveMutation.isPending}
        />
        {toasts.map((t) => <Toast key={t.id} type={t.type} message={t.message} onClose={() => removeToast(t.id)} />)}
      </>
    );
  }

  /* ── Product List ── */
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Product Management</h1>
          <p className="mt-1 text-sm text-slate-500">Configure, version, and publish insurance products</p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm shadow-indigo-500/20 transition-all hover:bg-indigo-700 active:scale-[0.98]"
        >
          <Plus size={16} />
          Create Product
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2">
        {['all', 'active', 'draft', 'retired', 'sunset'].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
              statusFilter === s
                ? 'bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200'
                : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </div>

      {/* Product Cards */}
      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-2xl border border-slate-200/60 bg-white" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <Package size={40} className="text-slate-300" />
          <p className="mt-3 text-sm font-medium text-slate-500">No products found</p>
          <p className="mt-1 text-xs text-slate-400">Create your first product to get started</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p) => (
            <button
              key={p.id}
              onClick={() => setSelectedId(p.id)}
              className="group relative flex flex-col rounded-2xl border border-slate-200/60 bg-white p-5 text-left shadow-[var(--shadow-card)] transition-all duration-200 hover:shadow-[var(--shadow-md)] hover:border-slate-200 active:scale-[0.99]"
            >
              <div className="flex items-start justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-50 to-indigo-100/60 text-indigo-600 ring-1 ring-indigo-100">
                  <Package size={18} />
                </div>
                <StatusBadge label={p.status} variant={statusVariant(p.status)} size="sm" />
              </div>
              <h3 className="mt-3 text-sm font-semibold text-slate-900">{p.name}</h3>
              <p className="mt-1 text-xs text-slate-500 line-clamp-2">{p.description}</p>
              <div className="mt-auto flex items-center gap-3 pt-4 border-t border-slate-100">
                <span className="text-[10px] font-medium uppercase tracking-wider text-slate-400">
                  {lobLabel(p.product_line)}
                </span>
                <span className="text-[10px] text-slate-300">•</span>
                <span className="text-[10px] text-slate-400">v{p.version}</span>
                <span className="text-[10px] text-slate-300">•</span>
                <span className="text-[10px] text-slate-400">{p.coverages?.length ?? 0} coverages</span>
              </div>
              <ChevronRight
                size={16}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300 opacity-0 transition-opacity group-hover:opacity-100"
              />
            </button>
          ))}
        </div>
      )}

      {toasts.map((t) => <Toast key={t.id} type={t.type} message={t.message} onClose={() => removeToast(t.id)} />)}
    </div>
  );
};

/* ════════════════════════════════════════════════════════════════════════════
   Product Detail / Editor View
   ════════════════════════════════════════════════════════════════════════════ */

interface DetailProps {
  product: ProductDetail;
  performance: ProductPerformance | null;
  activeTab: Tab;
  onTabChange: (t: Tab) => void;
  onBack: () => void;
  onSave: (body: Partial<ProductDetail>) => void;
  onPublish: () => void;
  onNewVersion: () => void;
  isSaving: boolean;
}

const TABS: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: 'overview',    label: 'Overview',       icon: FileText },
  { key: 'coverages',   label: 'Coverages',      icon: Shield },
  { key: 'rating',      label: 'Rating Factors',  icon: Settings },
  { key: 'appetite',    label: 'Appetite Rules',  icon: AlertTriangle },
  { key: 'authority',   label: 'Authority',        icon: Shield },
  { key: 'performance', label: 'Performance',      icon: BarChart3 },
  { key: 'history',     label: 'History',          icon: History },
];

const ProductDetailView: React.FC<DetailProps> = ({
  product, performance, activeTab, onTabChange, onBack, onSave, onPublish, onNewVersion, isSaving,
}) => {
  const [editName, setEditName] = useState(product.name);
  const [editDesc, setEditDesc] = useState(product.description);
  const [editCoverages, setEditCoverages] = useState<CoverageDefinition[]>(product.coverages ?? []);
  const [editFactors, setEditFactors] = useState<RatingFactorTable[]>(product.rating_factor_tables ?? []);
  const [editAppetite, setEditAppetite] = useState<AppetiteRule[]>(product.appetite_rules ?? []);
  const [editAuthority, setEditAuthority] = useState<AuthorityLimit>(
    product.authority_limits ?? { max_auto_bind_premium: 0, max_auto_bind_limit: 0, requires_senior_review_above: 0, requires_cuo_review_above: 0 },
  );
  const [editTerritories, setEditTerritories] = useState<string[]>(product.territories ?? []);
  const [dirty, setDirty] = useState(false);

  const markDirty = () => { if (!dirty) setDirty(true); };

  const handleSave = () => {
    onSave({
      name: editName,
      description: editDesc,
      coverages: editCoverages as unknown as CoverageDefinition[],
      rating_factor_tables: editFactors as unknown as RatingFactorTable[],
      appetite_rules: editAppetite as unknown as AppetiteRule[],
      authority_limits: editAuthority as unknown as AuthorityLimit,
      territories: editTerritories,
    });
    setDirty(false);
  };

  return (
    <div className="space-y-6">
      {/* Top bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 transition-colors">
            <ArrowLeft size={18} />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl font-bold tracking-tight text-slate-900">{product.name}</h1>
              <StatusBadge label={product.status} variant={statusVariant(product.status)} size="sm" />
            </div>
            <p className="text-xs text-slate-400">
              {lobLabel(product.product_line)} · v{product.version} · {product.coverages.length} coverage{product.coverages.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {dirty && (
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition-all hover:bg-slate-50 disabled:opacity-50"
            >
              <Save size={14} />
              {isSaving ? 'Saving…' : 'Save Draft'}
            </button>
          )}
          {product.status === 'active' && (
            <button
              onClick={onNewVersion}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition-all hover:bg-slate-50"
            >
              <GitBranch size={14} />
              New Version
            </button>
          )}
          {product.status === 'draft' && (
            <button
              onClick={onPublish}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm shadow-emerald-500/20 transition-all hover:bg-emerald-700 active:scale-[0.98]"
            >
              <Rocket size={14} />
              Publish
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-1 overflow-x-auto rounded-xl border border-slate-200/60 bg-white p-1 shadow-[var(--shadow-xs)]">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => onTabChange(key)}
            className={`flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-medium transition-all ${
              activeTab === key
                ? 'bg-indigo-50 text-indigo-700'
                : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'
            }`}
          >
            <Icon size={14} />
            {label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)]">
        {activeTab === 'overview' && (
          <OverviewTab
            product={product}
            editName={editName} setEditName={(v) => { setEditName(v); markDirty(); }}
            editDesc={editDesc} setEditDesc={(v) => { setEditDesc(v); markDirty(); }}
            editTerritories={editTerritories} setEditTerritories={(v) => { setEditTerritories(v); markDirty(); }}
          />
        )}
        {activeTab === 'coverages' && (
          <CoveragesTab
            coverages={editCoverages}
            onChange={(c) => { setEditCoverages(c); markDirty(); }}
          />
        )}
        {activeTab === 'rating' && (
          <RatingFactorsTab
            tables={editFactors}
            baseRate={product.rating_rules?.base_rate as number | undefined}
            onChange={(t) => { setEditFactors(t); markDirty(); }}
          />
        )}
        {activeTab === 'appetite' && (
          <AppetiteTab
            rules={editAppetite}
            onChange={(r) => { setEditAppetite(r); markDirty(); }}
          />
        )}
        {activeTab === 'authority' && (
          <AuthorityTab
            limits={editAuthority}
            onChange={(l) => { setEditAuthority(l); markDirty(); }}
          />
        )}
        {activeTab === 'performance' && (
          <PerformanceTab performance={performance} />
        )}
        {activeTab === 'history' && (
          <HistoryTab history={product.version_history ?? []} currentVersion={product.version} />
        )}
      </div>
    </div>
  );
};

/* ── Overview Tab ── */

const OverviewTab: React.FC<{
  product: ProductDetail;
  editName: string; setEditName: (v: string) => void;
  editDesc: string; setEditDesc: (v: string) => void;
  editTerritories: string[]; setEditTerritories: (v: string[]) => void;
}> = ({ product, editName, setEditName, editDesc, setEditDesc, editTerritories, setEditTerritories }) => (
  <div className="space-y-6">
    <div className="grid gap-6 sm:grid-cols-2">
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Product Name</label>
        <input
          value={editName}
          onChange={(e) => setEditName(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 outline-none transition-all"
        />
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Product Line</label>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {lobLabel(product.product_line)}
        </div>
      </div>
    </div>
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1.5">Description</label>
      <textarea
        value={editDesc}
        onChange={(e) => setEditDesc(e.target.value)}
        rows={3}
        className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100 outline-none transition-all resize-none"
      />
    </div>
    <div className="grid gap-6 sm:grid-cols-3">
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Version</label>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{product.version}</div>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Effective Date</label>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {product.effective_date ? new Date(product.effective_date).toLocaleDateString() : '—'}
        </div>
      </div>
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Expiration Date</label>
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
          {product.expiration_date ? new Date(product.expiration_date).toLocaleDateString() : '—'}
        </div>
      </div>
    </div>
    <div>
      <label className="block text-xs font-medium text-slate-500 mb-1.5">Territories</label>
      <div className="flex flex-wrap gap-2">
        {editTerritories.map((t) => (
          <span key={t} className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 ring-1 ring-indigo-100">
            <Globe size={11} />
            {t}
            <button onClick={() => setEditTerritories(editTerritories.filter((x) => x !== t))} className="ml-0.5 text-indigo-400 hover:text-indigo-600">
              <X size={11} />
            </button>
          </span>
        ))}
        <TerritoryAdder current={editTerritories} onAdd={(t) => setEditTerritories([...editTerritories, t])} />
      </div>
    </div>
    {product.forms && product.forms.length > 0 && (
      <div>
        <label className="block text-xs font-medium text-slate-500 mb-1.5">Required Forms</label>
        <ul className="space-y-1">
          {product.forms.map((f) => (
            <li key={f} className="flex items-center gap-2 text-sm text-slate-700">
              <FileText size={13} className="text-slate-400" />
              {f}
            </li>
          ))}
        </ul>
      </div>
    )}
  </div>
);

const TerritoryAdder: React.FC<{ current: string[]; onAdd: (t: string) => void }> = ({ current, onAdd }) => {
  const [adding, setAdding] = useState(false);
  const [val, setVal] = useState('');
  if (!adding) {
    return (
      <button onClick={() => setAdding(true)} className="inline-flex items-center gap-1 rounded-full border border-dashed border-slate-300 px-2.5 py-1 text-xs text-slate-400 hover:border-indigo-300 hover:text-indigo-600 transition-colors">
        <Plus size={11} /> Add
      </button>
    );
  }
  return (
    <span className="inline-flex items-center gap-1">
      <input
        autoFocus
        value={val}
        onChange={(e) => setVal(e.target.value.toUpperCase())}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && val && !current.includes(val)) { onAdd(val); setVal(''); setAdding(false); }
          if (e.key === 'Escape') { setAdding(false); setVal(''); }
        }}
        className="w-16 rounded border border-indigo-300 px-2 py-0.5 text-xs outline-none"
        placeholder="US"
      />
      <button onClick={() => { if (val && !current.includes(val)) { onAdd(val); } setVal(''); setAdding(false); }}>
        <Check size={13} className="text-emerald-500" />
      </button>
      <button onClick={() => { setAdding(false); setVal(''); }}>
        <X size={13} className="text-slate-400" />
      </button>
    </span>
  );
};

/* ── Coverages Tab ── */

const CoveragesTab: React.FC<{
  coverages: CoverageDefinition[];
  onChange: (c: CoverageDefinition[]) => void;
}> = ({ coverages, onChange }) => {
  const [editingIdx, setEditingIdx] = useState<number | null>(null);

  const handleAdd = () => {
    onChange([...coverages, {
      name: 'New Coverage', description: '', default_limit: 1_000_000,
      max_limit: 5_000_000, default_deductible: 10_000, is_optional: true,
    }]);
    setEditingIdx(coverages.length);
  };

  const handleUpdate = (idx: number, field: keyof CoverageDefinition, value: string | number | boolean) => {
    const updated = [...coverages];
    updated[idx] = { ...updated[idx], [field]: value };
    onChange(updated);
  };

  const handleRemove = (idx: number) => {
    onChange(coverages.filter((_, i) => i !== idx));
    setEditingIdx(null);
  };

  const handleDrag = (from: number, to: number) => {
    if (to < 0 || to >= coverages.length) return;
    const arr = [...coverages];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    onChange(arr);
    setEditingIdx(to);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Coverage Parts</h3>
        <button onClick={handleAdd} className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
          <Plus size={14} /> Add Coverage
        </button>
      </div>
      <div className="space-y-3">
        {coverages.map((c, i) => (
          <div key={i} className="rounded-xl border border-slate-200/60 bg-slate-50/50 p-4 transition-all hover:border-slate-200">
            <div className="flex items-start gap-3">
              <button className="mt-1 cursor-grab text-slate-300 hover:text-slate-400" title="Drag to reorder"
                onClick={() => { if (i > 0) handleDrag(i, i - 1); }}>
                <GripVertical size={16} />
              </button>
              <div className="flex-1 min-w-0">
                {editingIdx === i ? (
                  <div className="space-y-3">
                    <input value={c.name} onChange={(e) => handleUpdate(i, 'name', e.target.value)}
                      className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-sm font-medium outline-none focus:border-indigo-300" />
                    <textarea value={c.description} onChange={(e) => handleUpdate(i, 'description', e.target.value)}
                      rows={2} className="w-full rounded-lg border border-slate-200 px-3 py-1.5 text-xs outline-none focus:border-indigo-300 resize-none" />
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="text-[10px] font-medium text-slate-400 uppercase">Default Limit</label>
                        <input type="number" value={c.default_limit} onChange={(e) => handleUpdate(i, 'default_limit', Number(e.target.value))}
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none" />
                      </div>
                      <div>
                        <label className="text-[10px] font-medium text-slate-400 uppercase">Max Limit</label>
                        <input type="number" value={c.max_limit} onChange={(e) => handleUpdate(i, 'max_limit', Number(e.target.value))}
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none" />
                      </div>
                      <div>
                        <label className="text-[10px] font-medium text-slate-400 uppercase">Default Deductible</label>
                        <input type="number" value={c.default_deductible} onChange={(e) => handleUpdate(i, 'default_deductible', Number(e.target.value))}
                          className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none" />
                      </div>
                    </div>
                    <label className="flex items-center gap-2 text-xs text-slate-600">
                      <input type="checkbox" checked={c.is_optional} onChange={(e) => handleUpdate(i, 'is_optional', e.target.checked)}
                        className="rounded border-slate-300 text-indigo-600" />
                      Optional coverage
                    </label>
                    <div className="flex gap-2">
                      <button onClick={() => setEditingIdx(null)} className="text-xs text-indigo-600 font-medium hover:text-indigo-700">Done</button>
                      <button onClick={() => handleRemove(i)} className="text-xs text-red-500 font-medium hover:text-red-600">Remove</button>
                    </div>
                  </div>
                ) : (
                  <div className="cursor-pointer" onClick={() => setEditingIdx(i)}>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-900">{c.name}</span>
                      {c.is_optional && <StatusBadge label="Optional" variant="gray" size="sm" showDot={false} />}
                      <Pencil size={12} className="text-slate-300 ml-auto" />
                    </div>
                    {c.description && <p className="mt-0.5 text-xs text-slate-500">{c.description}</p>}
                    <div className="mt-2 flex gap-4 text-xs text-slate-400">
                      <span>Limit: {money(c.default_limit)}</span>
                      <span>Max: {money(c.max_limit)}</span>
                      <span>Deductible: {money(c.default_deductible)}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── Rating Factors Tab ── */

const RatingFactorsTab: React.FC<{
  tables: RatingFactorTable[];
  baseRate: number | undefined;
  onChange: (t: RatingFactorTable[]) => void;
}> = ({ tables, baseRate, onChange }) => {
  const [editCell, setEditCell] = useState<{ table: number; row: number; field: string } | null>(null);

  const handleCellChange = (tIdx: number, rIdx: number, field: string, value: string | number) => {
    const updated = tables.map((t, ti) => {
      if (ti !== tIdx) return t;
      return {
        ...t,
        entries: t.entries.map((e, ei) => ei === rIdx ? { ...e, [field]: value } : e),
      };
    });
    onChange(updated);
  };

  const handleAddEntry = (tIdx: number) => {
    const updated = tables.map((t, ti) =>
      ti === tIdx ? { ...t, entries: [...t.entries, { key: '', multiplier: 1.0, description: '' }] } : t,
    );
    onChange(updated);
  };

  const handleRemoveEntry = (tIdx: number, rIdx: number) => {
    const updated = tables.map((t, ti) =>
      ti === tIdx ? { ...t, entries: t.entries.filter((_, i) => i !== rIdx) } : t,
    );
    onChange(updated);
  };

  const handleAddTable = () => {
    onChange([...tables, { name: 'new_factor', description: 'New rating factor', entries: [] }]);
  };

  const handleRemoveTable = (tIdx: number) => {
    onChange(tables.filter((_, i) => i !== tIdx));
  };

  return (
    <div className="space-y-6">
      {baseRate != null && (
        <div className="rounded-xl bg-indigo-50/60 border border-indigo-100 p-4">
          <p className="text-xs font-medium text-indigo-600">Base Rate</p>
          <p className="text-2xl font-bold text-indigo-900">{money(baseRate)}</p>
          <p className="text-xs text-indigo-500 mt-1">Multiplied by factor tables below to calculate final premium</p>
        </div>
      )}

      {tables.map((table, tIdx) => (
        <div key={tIdx} className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-slate-900 capitalize">{table.name.replace(/_/g, ' ')}</h4>
              {table.description && <p className="text-xs text-slate-500">{table.description}</p>}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => handleAddEntry(tIdx)} className="text-xs text-indigo-600 hover:text-indigo-700 font-medium">
                <Plus size={13} className="inline mr-0.5" />Add Row
              </button>
              <button onClick={() => handleRemoveTable(tIdx)} className="text-xs text-red-400 hover:text-red-500">
                <Trash2 size={13} />
              </button>
            </div>
          </div>
          <div className="overflow-hidden rounded-xl border border-slate-200/60">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-slate-50 text-left">
                  <th className="px-3 py-2 font-semibold text-slate-600">Key</th>
                  <th className="px-3 py-2 font-semibold text-slate-600 w-28">Multiplier</th>
                  <th className="px-3 py-2 font-semibold text-slate-600">Description</th>
                  <th className="px-3 py-2 w-10" />
                </tr>
              </thead>
              <tbody>
                {table.entries.map((entry, rIdx) => (
                  <tr key={rIdx} className="border-t border-slate-100 hover:bg-slate-50/50">
                    <td className="px-3 py-2">
                      {editCell?.table === tIdx && editCell.row === rIdx && editCell.field === 'key' ? (
                        <input autoFocus value={entry.key}
                          onChange={(e) => handleCellChange(tIdx, rIdx, 'key', e.target.value)}
                          onBlur={() => setEditCell(null)} onKeyDown={(e) => e.key === 'Enter' && setEditCell(null)}
                          className="w-full rounded border border-indigo-300 px-1.5 py-0.5 text-xs outline-none" />
                      ) : (
                        <span className="cursor-pointer text-slate-700 hover:text-indigo-600" onClick={() => setEditCell({ table: tIdx, row: rIdx, field: 'key' })}>
                          {entry.key || <span className="text-slate-300 italic">click to edit</span>}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {editCell?.table === tIdx && editCell.row === rIdx && editCell.field === 'multiplier' ? (
                        <input autoFocus type="number" step="0.01" value={entry.multiplier}
                          onChange={(e) => handleCellChange(tIdx, rIdx, 'multiplier', parseFloat(e.target.value) || 1)}
                          onBlur={() => setEditCell(null)} onKeyDown={(e) => e.key === 'Enter' && setEditCell(null)}
                          className="w-full rounded border border-indigo-300 px-1.5 py-0.5 text-xs outline-none" />
                      ) : (
                        <span
                          className={`cursor-pointer font-mono font-medium ${
                            entry.multiplier < 1 ? 'text-emerald-600' : entry.multiplier > 1 ? 'text-red-600' : 'text-slate-600'
                          }`}
                          onClick={() => setEditCell({ table: tIdx, row: rIdx, field: 'multiplier' })}
                        >
                          {entry.multiplier.toFixed(2)}×
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {editCell?.table === tIdx && editCell.row === rIdx && editCell.field === 'description' ? (
                        <input autoFocus value={entry.description}
                          onChange={(e) => handleCellChange(tIdx, rIdx, 'description', e.target.value)}
                          onBlur={() => setEditCell(null)} onKeyDown={(e) => e.key === 'Enter' && setEditCell(null)}
                          className="w-full rounded border border-indigo-300 px-1.5 py-0.5 text-xs outline-none" />
                      ) : (
                        <span className="cursor-pointer text-slate-500 hover:text-indigo-600" onClick={() => setEditCell({ table: tIdx, row: rIdx, field: 'description' })}>
                          {entry.description || <span className="text-slate-300 italic">—</span>}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <button onClick={() => handleRemoveEntry(tIdx, rIdx)} className="text-slate-300 hover:text-red-500">
                        <X size={13} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      <button onClick={handleAddTable} className="inline-flex items-center gap-1.5 text-xs font-medium text-indigo-600 hover:text-indigo-700">
        <Plus size={14} /> Add Factor Table
      </button>
    </div>
  );
};

/* ── Appetite Rules Tab ── */

const AppetiteTab: React.FC<{
  rules: AppetiteRule[];
  onChange: (r: AppetiteRule[]) => void;
}> = ({ rules, onChange }) => {
  const handleUpdate = (idx: number, field: keyof AppetiteRule, value: unknown) => {
    const updated = rules.map((r, i) => i === idx ? { ...r, [field]: value } : r);
    onChange(updated);
  };

  const handleAdd = () => {
    onChange([...rules, { name: 'New Rule', field: '', operator: 'eq', value: '', description: '' }]);
  };

  const handleRemove = (idx: number) => {
    onChange(rules.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">Appetite Rules</h3>
          <p className="text-xs text-slate-500">Define which submissions qualify for this product</p>
        </div>
        <button onClick={handleAdd} className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700">
          <Plus size={14} /> Add Rule
        </button>
      </div>
      <div className="space-y-3">
        {rules.map((rule, i) => (
          <div key={i} className="rounded-xl border border-slate-200/60 bg-slate-50/50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <input value={rule.name} onChange={(e) => handleUpdate(i, 'name', e.target.value)}
                className="rounded border border-transparent bg-transparent px-1 py-0.5 text-sm font-medium text-slate-900 outline-none hover:border-slate-200 focus:border-indigo-300" />
              <button onClick={() => handleRemove(i)} className="text-slate-300 hover:text-red-500"><Trash2 size={14} /></button>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <label className="text-[10px] font-medium text-slate-400 uppercase">Field</label>
                <input value={rule.field} onChange={(e) => handleUpdate(i, 'field', e.target.value)}
                  className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none" placeholder="e.g. annual_revenue" />
              </div>
              <div>
                <label className="text-[10px] font-medium text-slate-400 uppercase">Operator</label>
                <select value={rule.operator} onChange={(e) => handleUpdate(i, 'operator', e.target.value)}
                  className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none bg-white">
                  <option value="in">in</option>
                  <option value="not_in">not in</option>
                  <option value="gte">≥</option>
                  <option value="lte">≤</option>
                  <option value="between">between</option>
                  <option value="eq">=</option>
                </select>
              </div>
              <div>
                <label className="text-[10px] font-medium text-slate-400 uppercase">Value</label>
                <input
                  value={typeof rule.value === 'string' ? rule.value : JSON.stringify(rule.value)}
                  onChange={(e) => {
                    try { handleUpdate(i, 'value', JSON.parse(e.target.value)); }
                    catch { handleUpdate(i, 'value', e.target.value); }
                  }}
                  className="w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none font-mono"
                />
              </div>
            </div>
            <input value={rule.description} onChange={(e) => handleUpdate(i, 'description', e.target.value)}
              placeholder="Rule description…"
              className="w-full rounded border border-transparent bg-transparent px-1 py-0.5 text-xs text-slate-500 outline-none hover:border-slate-200 focus:border-indigo-300" />
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── Authority Tab ── */

const AuthorityTab: React.FC<{
  limits: AuthorityLimit;
  onChange: (l: AuthorityLimit) => void;
}> = ({ limits, onChange }) => {
  const fields: { key: keyof AuthorityLimit; label: string; desc: string }[] = [
    { key: 'max_auto_bind_premium', label: 'Max Auto-Bind Premium', desc: 'Maximum premium for automatic binding without human review' },
    { key: 'max_auto_bind_limit', label: 'Max Auto-Bind Limit', desc: 'Maximum coverage limit for automatic binding' },
    { key: 'requires_senior_review_above', label: 'Senior UW Review Above', desc: 'Premium threshold requiring senior underwriter approval' },
    { key: 'requires_cuo_review_above', label: 'CUO Review Above', desc: 'Premium threshold requiring CUO sign-off' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-slate-900">Authority Limits</h3>
        <p className="text-xs text-slate-500">Define auto-bind thresholds and escalation triggers</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map(({ key, label, desc }) => (
          <div key={key} className="rounded-xl border border-slate-200/60 bg-slate-50/50 p-4">
            <label className="block text-xs font-medium text-slate-700 mb-1">{label}</label>
            <p className="text-[10px] text-slate-400 mb-2">{desc}</p>
            <div className="flex items-center gap-1">
              <span className="text-sm text-slate-400">$</span>
              <input
                type="number"
                value={limits[key]}
                onChange={(e) => onChange({ ...limits, [key]: Number(e.target.value) })}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100"
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* ── Performance Tab ── */

const CHART_COLORS = ['#6366f1', '#14b8a6', '#f59e0b', '#ef4444', '#8b5cf6'];

const PerformanceTab: React.FC<{ performance: ProductPerformance | null }> = ({ performance }) => {
  if (!performance) {
    return <div className="flex items-center justify-center py-12 text-sm text-slate-400">Loading performance data…</div>;
  }

  const bindData = [
    { name: 'Bound', value: performance.bound_count },
    { name: 'Declined', value: performance.declined_count },
    { name: 'Pending', value: Math.max(0, performance.submissions_count - performance.bound_count - performance.declined_count) },
  ];

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Policies in Force" value={performance.policies_in_force.toLocaleString()} icon={<FileText size={18} />} />
        <StatCard title="Gross Written Premium" value={money(performance.total_gwp)} icon={<BarChart3 size={18} />} />
        <StatCard title="Loss Ratio" value={pct(performance.loss_ratio)} icon={<AlertTriangle size={18} />}
          trend={{ value: Math.round(performance.loss_ratio * 100), positive: performance.loss_ratio < 0.6 }} />
        <StatCard title="Bind Rate" value={pct(performance.bind_rate)} icon={<Check size={18} />}
          trend={{ value: Math.round(performance.bind_rate * 100), positive: performance.bind_rate > 0.4 }} />
      </div>

      {/* Charts */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Premium Trend */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5">
          <h4 className="text-sm font-semibold text-slate-900 mb-4">Premium Trend</h4>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={performance.premium_trend}>
              <defs>
                <linearGradient id="premGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity={0.15} />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v: number) => [money(v), 'Premium']} />
              <Area type="monotone" dataKey="premium" stroke="#6366f1" fill="url(#premGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Submission Pipeline */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5">
          <h4 className="text-sm font-semibold text-slate-900 mb-4">Submission Pipeline</h4>
          <div className="flex items-center justify-center">
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={bindData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} paddingAngle={3} dataKey="value"
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                  {bindData.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl bg-indigo-50/60 border border-indigo-100 p-4 text-center">
          <p className="text-2xl font-bold text-indigo-900">{performance.submissions_count}</p>
          <p className="text-xs text-indigo-600 mt-1">Total Submissions</p>
        </div>
        <div className="rounded-xl bg-emerald-50/60 border border-emerald-100 p-4 text-center">
          <p className="text-2xl font-bold text-emerald-900">{money(performance.avg_premium)}</p>
          <p className="text-xs text-emerald-600 mt-1">Avg Premium</p>
        </div>
        <div className="rounded-xl bg-amber-50/60 border border-amber-100 p-4 text-center">
          <p className="text-2xl font-bold text-amber-900">{performance.bound_count}</p>
          <p className="text-xs text-amber-600 mt-1">Policies Bound</p>
        </div>
      </div>
    </div>
  );
};

/* ── History Tab ── */

const HistoryTab: React.FC<{ history: { version: string; created_at: string; created_by: string; change_summary: string }[]; currentVersion: string }> = ({ history, currentVersion }) => (
  <div className="space-y-4">
    <h3 className="text-sm font-semibold text-slate-900">Version History</h3>
    {(!history || history.length === 0) ? (
      <p className="text-xs text-slate-400">No version history yet. Publish the product to create the first snapshot.</p>
    ) : (
      <div className="relative border-l-2 border-indigo-100 ml-3 space-y-6 pl-6">
        {/* Current */}
        <div className="relative">
          <div className="absolute -left-[31px] top-0 flex h-5 w-5 items-center justify-center rounded-full bg-indigo-600 ring-4 ring-white">
            <div className="h-2 w-2 rounded-full bg-white" />
          </div>
          <p className="text-sm font-semibold text-slate-900">v{currentVersion} <span className="ml-1 text-xs font-normal text-indigo-600">(current)</span></p>
          <p className="text-xs text-slate-400">In progress</p>
        </div>
        {/* Past versions */}
        {[...history].reverse().map((v, i) => (
          <div key={i} className="relative">
            <div className="absolute -left-[31px] top-0 flex h-5 w-5 items-center justify-center rounded-full bg-slate-200 ring-4 ring-white">
              <div className="h-2 w-2 rounded-full bg-slate-400" />
            </div>
            <p className="text-sm font-medium text-slate-700">v{v.version}</p>
            <p className="text-xs text-slate-500 mt-0.5">{v.change_summary}</p>
            <p className="text-[10px] text-slate-400 mt-1">
              {v.created_by} · {new Date(v.created_at).toLocaleDateString()}
            </p>
          </div>
        ))}
      </div>
    )}
  </div>
);

/* ── Create Product View ── */

const CreateProductView: React.FC<{
  onCancel: () => void;
  onCreate: (body: Partial<ProductDetail>) => void;
  isLoading: boolean;
}> = ({ onCancel, onCreate, isLoading }) => {
  const [name, setName] = useState('');
  const [productLine, setProductLine] = useState<string>('cyber');
  const [description, setDescription] = useState('');

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={onCancel} className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100"><ArrowLeft size={18} /></button>
        <h1 className="text-xl font-bold tracking-tight text-slate-900">Create New Product</h1>
      </div>
      <div className="rounded-2xl border border-slate-200/60 bg-white p-6 shadow-[var(--shadow-card)] space-y-6">
        <div className="grid gap-6 sm:grid-cols-2">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Product Name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cyber Liability"
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-100" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1.5">Product Line</label>
            <select value={productLine} onChange={(e) => setProductLine(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-300">
              <option value="cyber">Cyber</option>
              <option value="tech_eo">Tech E&O</option>
              <option value="mpl">MPL</option>
            </select>
          </div>
        </div>
        <div>
          <label className="block text-xs font-medium text-slate-500 mb-1.5">Description</label>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
            placeholder="Describe the product coverage and target market…"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-indigo-300 resize-none" />
        </div>
        <div className="flex justify-end gap-3">
          <button onClick={onCancel} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50">Cancel</button>
          <button
            onClick={() => onCreate({ name, product_line: productLine, description })}
            disabled={!name || isLoading}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-indigo-500/20 hover:bg-indigo-700 disabled:opacity-50 active:scale-[0.98]"
          >
            {isLoading ? 'Creating…' : 'Create Product'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Skeleton components ── */

export const ProductCardSkeleton: React.FC = () => (
  <div className="h-48 animate-pulse rounded-2xl border border-slate-200/60 bg-white p-5">
    <div className="flex items-start justify-between">
      <div className="h-10 w-10 rounded-xl bg-slate-100" />
      <div className="h-5 w-16 rounded-full bg-slate-100" />
    </div>
    <div className="mt-3 h-4 w-3/4 rounded bg-slate-100" />
    <div className="mt-2 h-3 w-full rounded bg-slate-100" />
    <div className="mt-auto pt-8">
      <div className="h-3 w-1/2 rounded bg-slate-100" />
    </div>
  </div>
);

export default ProductManagement;
