import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend,
} from 'recharts';
import { DollarSign, Calculator, AlertTriangle } from 'lucide-react';
import StatCard from '../components/StatCard';
import {
  getActuarialReserves,
  getTriangleData,
  getIBNR,
  getRateAdequacy,
} from '../api/workbench';
import type { ActuarialReserve, TriangleEntry, IBNRResult } from '../types';

const money = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

/** Group reserves into summary rows: one row per LOB + accident year. */
function buildReserveSummary(reserves: ActuarialReserve[]) {
  const map = new Map<string, { lob: string; ay: number; case_: number; ibnr: number; total: number; indicated: number }>();
  for (const r of reserves) {
    const key = `${r.line_of_business}|${r.accident_year}`;
    const row = map.get(key) ?? { lob: r.line_of_business, ay: r.accident_year, case_: 0, ibnr: 0, total: 0, indicated: 0 };
    if (r.reserve_type === 'case') {
      row.case_ = r.selected_amount;
      row.indicated += r.indicated_amount;
    } else if (r.reserve_type === 'ibnr') {
      row.ibnr = r.selected_amount;
      row.indicated += r.indicated_amount;
    }
    row.total = row.case_ + row.ibnr;
    map.set(key, row);
  }
  return [...map.values()].sort((a, b) => a.lob.localeCompare(b.lob) || a.ay - b.ay);
}

/** Build a 2D grid for the loss triangle display. */
function buildTriangleGrid(entries: TriangleEntry[], accidentYears: number[], devMonths: number[]): Record<string, number | null>[] {
  const lookup = new Map<string, number>();
  for (const e of entries) lookup.set(`${e.accident_year}-${e.development_month}`, e.incurred_amount);
  return accidentYears.map(ay => ({
    accident_year: ay,
    ...Object.fromEntries(devMonths.map(dm => [`m${dm}`, lookup.get(`${ay}-${dm}`) ?? null])),
  }));
}

/** IBNR trending chart data */
function buildIBNRTrend(ibnr: IBNRResult) {
  return Object.entries(ibnr.ibnr_by_year)
    .map(([year, val]) => ({ year, ibnr: parseFloat(String(val)) }))
    .sort((a, b) => a.year.localeCompare(b.year));
}

const ActuarialWorkbench: React.FC = () => {
  const { data: reserves, isLoading: loadingR } = useQuery({ queryKey: ['actuarial-reserves'], queryFn: getActuarialReserves });
  const { data: triangle, isLoading: loadingT } = useQuery({ queryKey: ['actuarial-triangle'], queryFn: () => getTriangleData('cyber') });
  const { data: ibnr, isLoading: loadingI } = useQuery({ queryKey: ['actuarial-ibnr'], queryFn: () => getIBNR('cyber') });
  const { data: rateAdequacy, isLoading: loadingRA } = useQuery({ queryKey: ['actuarial-rate-adequacy'], queryFn: getRateAdequacy });

  const loading = loadingR || loadingT || loadingI || loadingRA;

  if (loading || !reserves || !triangle || !ibnr || !rateAdequacy) {
    return <div className="flex h-64 items-center justify-center text-slate-400">Loading…</div>;
  }

  const summary = buildReserveSummary(reserves);
  const totalCarried = reserves.reduce((s, r) => s + r.carried_amount, 0);
  const totalSelected = reserves.reduce((s, r) => s + r.selected_amount, 0);
  const totalIBNR = parseFloat(ibnr.total_ibnr);
  const avgAdequacy = rateAdequacy.length > 0
    ? rateAdequacy.reduce((s, r) => s + parseFloat(r.adequacy_ratio), 0) / rateAdequacy.length
    : 0;

  const triangleGrid = buildTriangleGrid(triangle.entries, triangle.accident_years, triangle.development_months);
  const ibnrTrend = buildIBNRTrend(ibnr);

  // Rate adequacy chart data
  const rateChartData = rateAdequacy.map(r => ({
    segment: r.segment,
    current: parseFloat(r.current_rate),
    indicated: parseFloat(r.indicated_rate),
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Actuarial Workbench</h1>
        <p className="text-sm text-slate-500">Reserves, loss triangles, IBNR & rate adequacy — Carrier only</p>
      </div>

      {/* ── KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard title="Total Carried Reserves" value={money(totalCarried)} icon={<DollarSign size={20} />} />
        <StatCard title="Total Selected Reserves" value={money(totalSelected)} icon={<DollarSign size={20} />} />
        <StatCard title="Total IBNR (Cyber)" value={money(totalIBNR)} icon={<AlertTriangle size={20} />} />
        <StatCard title="Avg Rate Adequacy" value={pct(avgAdequacy)} icon={<Calculator size={20} />} subtitle={avgAdequacy >= 1 ? 'Rates adequate' : 'Rates deficient'} />
      </div>

      {/* ── Reserve Summary Table ── */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">Reserve Summary</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-2 pr-4">LOB</th>
                <th className="py-2 pr-4">Accident Year</th>
                <th className="py-2 pr-4 text-right">Case</th>
                <th className="py-2 pr-4 text-right">IBNR</th>
                <th className="py-2 pr-4 text-right">Total</th>
                <th className="py-2 pr-4 text-right">Indicated</th>
                <th className="py-2 text-right">Adequacy %</th>
              </tr>
            </thead>
            <tbody>
              {summary.map((row, i) => {
                const adequacy = row.indicated > 0 ? row.total / row.indicated : 0;
                return (
                  <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="py-2 pr-4 font-medium text-slate-700">{row.lob.replace(/_/g, ' ')}</td>
                    <td className="py-2 pr-4 text-slate-600">{row.ay}</td>
                    <td className="py-2 pr-4 text-right font-mono text-slate-700">{money(row.case_)}</td>
                    <td className="py-2 pr-4 text-right font-mono text-slate-700">{money(row.ibnr)}</td>
                    <td className="py-2 pr-4 text-right font-mono font-semibold text-slate-900">{money(row.total)}</td>
                    <td className="py-2 pr-4 text-right font-mono text-slate-600">{money(row.indicated)}</td>
                    <td className={`py-2 text-right font-mono font-semibold ${adequacy >= 0.95 ? 'text-green-600' : 'text-amber-600'}`}>
                      {pct(adequacy)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Loss Triangle ── */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">
          Loss Development Triangle — {triangle.line_of_business.replace(/_/g, ' ')}
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs font-semibold uppercase tracking-wider text-slate-500">
                <th className="py-2 pr-4">AY</th>
                {triangle.development_months.map((dm: number) => (
                  <th key={dm} className="py-2 pr-4 text-right">{dm}m</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {triangleGrid.map((row, i) => (
                <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                  <td className="py-2 pr-4 font-medium text-slate-700">{row.accident_year}</td>
                  {triangle.development_months.map((dm: number) => {
                    const val = (row as Record<string, unknown>)[`m${dm}`] as number | null;
                    return (
                      <td key={dm} className="py-2 pr-4 text-right font-mono text-slate-700">
                        {val != null ? money(val) : <span className="text-slate-300">—</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Charts Row ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Rate Adequacy Chart */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Rate Adequacy — Current vs Indicated</h2>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={rateChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="segment" tick={{ fontSize: 9 }} angle={-30} textAnchor="end" height={60} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend />
              <Bar dataKey="current" name="Current Rate" fill="#94a3b8" radius={[4, 4, 0, 0]} />
              <Bar dataKey="indicated" name="Indicated Rate" fill="#6366f1" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* IBNR Trending */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">IBNR by Accident Year — Cyber</h2>
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={ibnrTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="year" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${v.toLocaleString()}`} />
              <Tooltip formatter={(v) => money(Number(v))} />
              <Line type="monotone" dataKey="ibnr" name="IBNR" stroke="#ef4444" strokeWidth={2} dot={{ fill: '#ef4444', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Development Factors ── */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">Age-to-Age Development Factors (Chain Ladder)</h2>
        <div className="flex flex-wrap gap-4">
          {Object.entries(ibnr.factors).map(([period, factor]) => (
            <div key={period} className="flex flex-col items-center rounded-lg border border-slate-200 px-4 py-3">
              <span className="text-xs text-slate-500">{period}m → next</span>
              <span className="mt-1 text-lg font-bold text-indigo-700">{String(factor)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ActuarialWorkbench;
