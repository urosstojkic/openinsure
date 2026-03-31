import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Inbox,
  FileText,
  AlertTriangle,
  Clock,
  TrendingUp,
  Zap,
  ArrowUpRight,
  Bot,
  Activity,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { StatCardSkeleton, ChartSkeleton } from '../components/Skeleton';
import { getDashboardStats } from '../api/dashboard';
import type { AgentStatus } from '../types';

const agentStatusVariant = (s: AgentStatus['status']) =>
  s === 'active' ? 'green' : s === 'idle' ? 'yellow' : 'red';

/* Custom chart tooltip */
const ChartTooltip = ({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200/60 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-sm">
      <p className="text-[11px] font-medium text-slate-500">{label}</p>
      <p className="text-sm font-bold text-slate-800">{payload[0].value} decisions</p>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardStats,
  });

  if (isLoading || !stats) {
    return (
      <div className="space-y-6">
        <div>
          <div className="skeleton-text mb-2" style={{ width: '180px', height: '28px' }} />
          <div className="skeleton-text" style={{ width: '260px', height: '14px' }} />
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[1,2,3,4].map(i => <StatCardSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {[1,2,3].map(i => <StatCardSkeleton key={i} />)}
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ChartSkeleton />
          <ChartSkeleton />
        </div>
      </div>
    );
  }

  const chartData = stats.agent_statuses.map((a) => ({
    name: a.display_name.replace(' Agent', ''),
    decisions: a.decisions_today,
  }));

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Dashboard</h1>
        <p className="mt-0.5 text-sm text-slate-500">Overview of your insurance operations</p>
      </div>

      {/* ── Hero KPI Cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Submissions"
          value={stats.total_submissions.toLocaleString()}
          icon={<Inbox size={18} />}
          trend={{ value: 12, positive: true }}
          subtitle="vs last month"
          sparklineData={[4, 6, 5, 8, 7, 10, 12]}
        />
        <StatCard
          title="Active Policies"
          value={stats.active_policies.toLocaleString()}
          icon={<FileText size={18} />}
          sparklineData={[20, 22, 21, 24, 23, 25, 27]}
          trend={{ value: 8, positive: true }}
          subtitle="vs last month"
        />
        <StatCard
          title="Open Claims"
          value={stats.open_claims}
          icon={<AlertTriangle size={18} />}
          sparklineData={[5, 7, 6, 4, 5, 3, 4]}
          trend={{ value: 5, positive: false }}
          subtitle="vs last month"
        />
        <StatCard
          title="Pending Decisions"
          value={stats.pending_decisions}
          icon={<Clock size={18} />}
          subtitle="Awaiting human review"
        />
      </div>

      {/* ── Quick Metrics ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Approval Rate"
          value={`${Math.round(stats.approval_rate * 100)}%`}
          icon={<TrendingUp size={18} />}
          trend={{ value: 3, positive: true }}
          subtitle="30-day average"
        />
        <StatCard
          title="Avg Processing Time"
          value={`${stats.avg_processing_time_hours}h`}
          icon={<Zap size={18} />}
          trend={{ value: 15, positive: true }}
          subtitle="vs manual: 72h"
        />
        <StatCard
          title="Escalation Rate"
          value={`${Math.round(stats.escalation_rate * 100)}%`}
          icon={<ArrowUpRight size={18} />}
          trend={{ value: 2, positive: false }}
          subtitle="Target: < 15%"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Agent Activity Chart ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Agent Decisions Today</h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Automated decisions by AI agent</p>
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-indigo-50 px-2.5 py-1">
              <Activity size={12} className="text-indigo-500" />
              <span className="text-[11px] font-medium text-indigo-600">Live</span>
            </div>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} barCategoryGap="25%">
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={50} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(99, 102, 241, 0.04)' }} />
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#6366f1" />
                    <stop offset="100%" stopColor="#818cf8" />
                  </linearGradient>
                </defs>
                <Bar dataKey="decisions" fill="url(#barGradient)" radius={[6, 6, 0, 0]} maxBarSize={48} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[220px] flex-col items-center justify-center gap-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
                <Activity size={20} className="text-slate-400" />
              </div>
              <p className="text-sm text-slate-400">No agent activity data yet</p>
            </div>
          )}
        </div>

        {/* ── Agent Status Panel ── */}
        <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-slate-800">Agent Status</h2>
              <p className="text-[11px] text-slate-400 mt-0.5">Real-time AI agent health</p>
            </div>
            <div className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1">
              <Bot size={12} className="text-emerald-500" />
              <span className="text-[11px] font-medium text-emerald-600">{stats.agent_statuses.filter(a => a.status === 'active').length} active</span>
            </div>
          </div>
          {stats.agent_statuses.length > 0 ? (
            <div className="space-y-2">
              {stats.agent_statuses.map((a) => (
                <div key={a.name} className="flex items-center justify-between rounded-lg border border-slate-100 p-3 transition-colors hover:bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                      a.status === 'active' ? 'bg-emerald-50 text-emerald-600' : a.status === 'idle' ? 'bg-amber-50 text-amber-600' : 'bg-slate-100 text-slate-400'
                    }`}>
                      <Bot size={14} />
                    </div>
                    <div>
                      <p className="text-[13px] font-semibold text-slate-800">{a.display_name}</p>
                      <p className="text-[11px] text-slate-400">{a.last_action}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[11px] font-medium tabular-nums text-slate-500">{a.decisions_today} today</span>
                    <StatusBadge label={a.status} variant={agentStatusVariant(a.status)} size="sm" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-40 flex-col items-center justify-center gap-2">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
                <Bot size={20} className="text-slate-400" />
              </div>
              <p className="text-sm text-slate-400">Agent statuses appear after processing</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Recent Activity Feed ── */}
      <div className="rounded-xl border border-slate-200/60 bg-white p-5 shadow-[var(--shadow-xs)]">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-800">Recent Activity</h2>
            <p className="text-[11px] text-slate-400 mt-0.5">Latest operations and decisions</p>
          </div>
        </div>
        {stats.recent_activity.length > 0 ? (
          <div className="space-y-1">
            {stats.recent_activity.map((ev) => (
              <div key={ev.id} className="flex items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-slate-50/50">
                <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
                  ev.is_agent ? 'bg-indigo-50' : 'bg-slate-100'
                }`}>
                  {ev.is_agent
                    ? <Bot size={12} className="text-indigo-500" />
                    : <Activity size={12} className="text-slate-400" />}
                </div>
                <span className="flex-1 text-[13px] text-slate-600">{ev.description}</span>
                <span className="shrink-0 text-[11px] font-medium tabular-nums text-slate-400">
                  {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
              <Activity size={20} className="text-slate-400" />
            </div>
            <p className="text-sm text-slate-400">Activity will appear as submissions and claims are processed</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
