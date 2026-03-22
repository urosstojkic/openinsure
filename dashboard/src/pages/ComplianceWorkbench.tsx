import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from 'recharts';
import StatusBadge from '../components/StatusBadge';
import ConfidenceBar from '../components/ConfidenceBar';
import EmptyState from '../components/EmptyState';
import { getDecisionAudit, getOverrideLog, getBiasChartData, getComplianceWorkbenchData, getBiasReport } from '../api/workbench';
import type { BiasAnalysis } from '../types';
import { Server, ClipboardList, BarChart3, RotateCcw } from 'lucide-react';

const ComplianceWorkbench: React.FC = () => {
  const { data: compliance } = useQuery({ queryKey: ['compliance-wb'], queryFn: getComplianceWorkbenchData });
  const { data: auditItems = [] } = useQuery({ queryKey: ['decision-audit'], queryFn: getDecisionAudit });
  const { data: overrides = [] } = useQuery({ queryKey: ['override-log'], queryFn: getOverrideLog });
  const { data: biasData } = useQuery({ queryKey: ['bias-charts'], queryFn: getBiasChartData });
  const queryClient = useQueryClient();
  const { data: biasReport, isLoading: biasReportLoading } = useQuery({ queryKey: ['bias-report'], queryFn: getBiasReport, retry: false });
  const generateReport = useMutation({
    mutationFn: getBiasReport,
    onSuccess: (data) => queryClient.setQueryData(['bias-report'], data),
  });

  const [auditState, setAuditState] = useState<Record<string, { reviewed: boolean; flagged: boolean }>>({});

  const getAuditState = (id: string) => auditState[id] ?? { reviewed: false, flagged: false };

  const markReviewed = (id: string) => {
    setAuditState((prev) => ({ ...prev, [id]: { ...getAuditState(id), reviewed: true } }));
  };

  const flagIssue = (id: string) => {
    setAuditState((prev) => ({ ...prev, [id]: { ...getAuditState(id), flagged: true } }));
  };

  const aiSystems = compliance?.ai_systems ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900">Compliance Workbench</h1>
        <p className="text-sm text-slate-500">AI governance, decision auditing, and bias monitoring</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Panel 1: AI System Inventory ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">AI System Inventory</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Name</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Version</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Risk Class</th>
                  <th className="px-3 py-2 text-left text-xs font-semibold text-slate-600">Status</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Decisions</th>
                  <th className="px-3 py-2 text-right text-xs font-semibold text-slate-600">Avg Conf</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {aiSystems.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                      <EmptyState
                        icon={Server}
                        title="No AI systems registered"
                        description="AI systems will appear here once they are configured and deployed."
                      />
                    </td>
                  </tr>
                ) : aiSystems.map((sys) => (
                  <tr key={sys.id}>
                    <td className="px-3 py-2 font-medium text-slate-900">{sys.name}</td>
                    <td className="px-3 py-2 font-mono text-xs text-slate-500">v{sys.version}</td>
                    <td className="px-3 py-2">
                      <StatusBadge
                        label={sys.risk_category === 'high' ? 'High (EU AI Act)' : sys.risk_category}
                        variant={sys.risk_category === 'high' ? 'red' : sys.risk_category === 'limited' ? 'yellow' : 'green'}
                      />
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge label={sys.status} variant={sys.status === 'active' ? 'green' : sys.status === 'testing' ? 'yellow' : 'gray'} />
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-slate-700">{sys.decisions_count}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-700">
                      {compliance ? `${Math.round(compliance.avg_confidence * 100)}%` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>            </table>
          </div>
        </div>

        {/* ── Panel 2: Decision Audit ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Decision Audit — Random Sample</h2>
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {auditItems.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No audit items"
                description="Decision audit entries will appear once AI agents process submissions or claims."
                action={{ label: "View Agent Decisions", href: "/agent-decisions" }}
              />
            ) : auditItems.map((item) => {
              const state = getAuditState(item.id);
              return (
                <div key={item.id} className={`rounded-lg border p-3 ${state.flagged ? 'border-red-200 bg-red-50' : state.reviewed ? 'border-green-200 bg-green-50' : 'border-slate-200'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-slate-900">{item.agent}</span>
                      <StatusBadge label={item.decision_type} variant="blue" />
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-20"><ConfidenceBar value={item.confidence} /></div>
                      <span className="text-xs text-slate-400">{new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-500 mb-1"><strong>Input:</strong> {item.input_summary}</p>
                  <p className="text-xs text-slate-700 mb-1"><strong>Output:</strong> {item.output}</p>
                  <details className="text-xs text-slate-500">
                    <summary className="cursor-pointer text-blue-600 hover:text-blue-800">Reasoning chain</summary>
                    <ol className="mt-1 ml-4 list-decimal space-y-0.5">
                      {item.reasoning_chain.map((step, i) => <li key={i}>{step}</li>)}
                    </ol>
                  </details>
                  <div className="mt-2 flex gap-2">
                    <button
                      onClick={() => markReviewed(item.id)}
                      disabled={state.reviewed}
                      className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700 disabled:opacity-50"
                    >
                      {state.reviewed ? '✓ Reviewed' : 'Mark Reviewed'}
                    </button>
                    <button
                      onClick={() => flagIssue(item.id)}
                      disabled={state.flagged}
                      className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {state.flagged ? '⚑ Flagged' : 'Flag Issue'}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Panel 3: Bias Monitoring ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-700">Bias Monitoring</h2>
            <div className="flex items-center gap-3">
              {biasReport && (
                <StatusBadge
                  label={biasReport.overall_status === 'compliant' ? 'Compliant' : 'Flagged'}
                  variant={biasReport.overall_status === 'compliant' ? 'green' : 'red'}
                />
              )}
              <button
                onClick={() => generateReport.mutate()}
                disabled={generateReport.isPending}
                className="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700 disabled:opacity-50"
              >
                {generateReport.isPending ? 'Generating…' : 'Generate Report'}
              </button>
            </div>
          </div>

          {/* Real bias report results */}
          {biasReport && (
            <div className="space-y-5">
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div className="rounded bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Submissions Analyzed</span>
                  <p className="text-lg font-semibold text-slate-900">{biasReport.total_submissions_analyzed.toLocaleString()}</p>
                </div>
                <div className="rounded bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">EU AI Act</span>
                  <p className="text-xs font-medium text-slate-700 mt-1">{biasReport.eu_ai_act_reference}</p>
                </div>
                <div className="rounded bg-slate-50 px-3 py-2">
                  <span className="text-slate-500">Recommendation</span>
                  <p className="text-xs font-medium text-slate-700 mt-1">{biasReport.recommendation}</p>
                </div>
              </div>

              {biasReport.analyses.map((analysis: BiasAnalysis, idx: number) => {
                const chartData = Object.entries(analysis.groups).map(([name, g]) => ({
                  name,
                  rate: g.rate,
                  total: g.total,
                  flagged: analysis.flagged_groups.includes(name),
                }));
                return (
                  <div key={idx} className="rounded border border-slate-100 p-3">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-semibold text-slate-600">{analysis.metric}</h3>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-slate-500">4/5ths ratio:</span>
                        <span className={`text-xs font-mono font-bold ${analysis.passes_threshold ? 'text-green-600' : 'text-red-600'}`}>
                          {analysis.four_fifths_ratio.toFixed(4)}
                        </span>
                        <StatusBadge
                          label={analysis.passes_threshold ? 'PASS' : 'FAIL'}
                          variant={analysis.passes_threshold ? 'green' : 'red'}
                        />
                      </div>
                    </div>
                    <ResponsiveContainer width="100%" height={180}>
                      <BarChart data={chartData}>
                        <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                        <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                        <Tooltip
                          formatter={(v) => [
                            `${Math.round(Number(v) * 100)}%`,
                            'Approval Rate',
                          ]}
                        />
                        <Bar dataKey="rate" radius={[3, 3, 0, 0]}>
                          {chartData.map((entry, i) => (
                            <Cell key={i} fill={entry.flagged ? '#ef4444' : '#3b82f6'} />
                          ))}
                        </Bar>
                        <ReferenceLine y={0.8} stroke="#ef4444" strokeDasharray="4 4" label={{ value: '4/5ths', fill: '#ef4444', fontSize: 10 }} />
                      </BarChart>
                    </ResponsiveContainer>
                    {analysis.flagged_groups.length > 0 && (
                      <div className="mt-2 rounded bg-red-50 px-3 py-2 text-xs text-red-700">
                        <strong>⚠ Flagged groups:</strong> {analysis.flagged_groups.join(', ')}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Fallback: static mock charts when no report loaded yet */}
          {!biasReport && biasData && (
            <div className="space-y-5">
              {/* Approval rates by sector */}
              <div>
                <h3 className="mb-2 text-xs font-semibold text-slate-600">Approval Rates by Industry Sector</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={biasData.approval_by_sector}>
                    <XAxis dataKey="sector" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
                    <Tooltip formatter={(v) => `${Math.round(Number(v) * 100)}%`} />
                    <Bar dataKey="rate" fill="#3b82f6" radius={[3, 3, 0, 0]} />
                    <ReferenceLine y={0.8} stroke="#ef4444" strokeDasharray="4 4" label={{ value: '4/5ths', fill: '#ef4444', fontSize: 10 }} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Premium distribution by company size */}
              <div>
                <h3 className="mb-2 text-xs font-semibold text-slate-600">Premium Distribution by Company Size</h3>
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={biasData.premium_by_size}>
                    <XAxis dataKey="size" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`} />
                    <Tooltip formatter={(v) => `$${Number(v).toLocaleString()}`} />
                    <Bar dataKey="median" fill="#8b5cf6" radius={[3, 3, 0, 0]} name="Median Premium" />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Disparate Impact Ratios */}
              <div>
                <h3 className="mb-2 text-xs font-semibold text-slate-600">Disparate Impact Ratios</h3>
                <div className="space-y-2">
                  {biasData.disparate_impact.map((di, i) => (
                    <div key={i} className="flex items-center gap-3">
                      <span className="w-32 text-xs text-slate-600">{di.category}</span>
                      <div className="flex-1">
                        <div className="relative h-4 w-full overflow-hidden rounded-full bg-slate-200">
                          <div
                            className={`h-4 rounded-full ${di.ratio >= di.threshold ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${di.ratio * 100}%` }}
                          />
                          <div
                            className="absolute top-0 h-4 w-0.5 bg-red-600"
                            style={{ left: `${di.threshold * 100}%` }}
                            title={`Threshold: ${di.threshold}`}
                          />
                        </div>
                      </div>
                      <span className="w-12 text-right text-xs font-mono text-slate-700">{di.ratio.toFixed(2)}</span>
                      {di.ratio < di.threshold && (
                        <StatusBadge label="ALERT" variant="red" />
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {biasReportLoading && (
            <p className="text-xs text-slate-400 text-center py-8">Loading bias report…</p>
          )}

          {!biasReportLoading && !biasReport && !biasData && (
            <EmptyState
              icon={BarChart3}
              title="No bias data available"
              description="Generate a bias report to monitor fairness metrics across AI decisions."
            />
          )}
        </div>

        {/* ── Panel 4: Override Log ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Override Log</h2>
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {overrides.length === 0 ? (
              <EmptyState
                icon={RotateCcw}
                title="No overrides recorded"
                description="Override entries appear when a human overrides an AI agent recommendation."
              />
            ) : overrides.map((ov) => (
              <div key={ov.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-slate-900">{ov.who}</span>
                  <span className="text-xs text-slate-400">{new Date(ov.timestamp).toLocaleString()}</span>
                </div>
                <p className="text-xs text-slate-500 mb-1"><strong>Decision Type:</strong> {ov.decision_type}</p>
                <div className="grid grid-cols-2 gap-2 mb-1">
                  <div className="rounded bg-red-50 px-2 py-1 text-xs text-red-700">
                    <strong>Original:</strong> {ov.original_recommendation}
                  </div>
                  <div className="rounded bg-green-50 px-2 py-1 text-xs text-green-700">
                    <strong>Override:</strong> {ov.override_to}
                  </div>
                </div>
                <p className="text-xs text-slate-600"><strong>Reason:</strong> {ov.reason}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ComplianceWorkbench;
