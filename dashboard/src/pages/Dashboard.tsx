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
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import StatCard from '../components/StatCard';
import StatusBadge from '../components/StatusBadge';
import { getDashboardStats } from '../api/dashboard';
import type { AgentStatus } from '../types';

const agentStatusVariant = (s: AgentStatus['status']) =>
  s === 'active' ? 'green' : s === 'idle' ? 'yellow' : 'red';

const Dashboard: React.FC = () => {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboardStats,
  });

  if (isLoading || !stats) {
    return <div className="flex h-64 items-center justify-center text-slate-400">Loading dashboard…</div>;
  }

  const chartData = stats.agent_statuses.map((a) => ({
    name: a.display_name.replace(' Agent', ''),
    decisions: a.decisions_today,
  }));

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Total Submissions"
          value={stats.total_submissions.toLocaleString()}
          icon={<Inbox size={20} />}
          trend={{ value: 12, positive: true }}
        />
        <StatCard
          title="Active Policies"
          value={stats.active_policies.toLocaleString()}
          icon={<FileText size={20} />}
        />
        <StatCard
          title="Open Claims"
          value={stats.open_claims}
          icon={<AlertTriangle size={20} />}
        />
        <StatCard
          title="Pending Decisions"
          value={stats.pending_decisions}
          icon={<Clock size={20} />}
          subtitle="Awaiting human review"
        />
      </div>

      {/* ── Quick stats ── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard
          title="Approval Rate"
          value={`${Math.round(stats.approval_rate * 100)}%`}
          icon={<TrendingUp size={20} />}
        />
        <StatCard
          title="Avg Processing Time"
          value={`${stats.avg_processing_time_hours}h`}
          icon={<Zap size={20} />}
        />
        <StatCard
          title="Escalation Rate"
          value={`${Math.round(stats.escalation_rate * 100)}%`}
          icon={<ArrowUpRight size={20} />}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ── Agent activity chart ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Agent Decisions Today</h2>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="decisions" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[220px] items-center justify-center text-sm text-slate-400">
              No agent activity data available yet
            </div>
          )}
        </div>

        {/* ── Agent status overview ── */}
        <div className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="mb-4 text-sm font-semibold text-slate-700">Agent Status</h2>
          {stats.agent_statuses.length > 0 ? (
            <div className="space-y-3">
              {stats.agent_statuses.map((a) => (
                <div key={a.name} className="flex items-center justify-between rounded-lg border border-slate-100 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{a.display_name}</p>
                    <p className="text-xs text-slate-400">{a.last_action}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">{a.decisions_today} today</span>
                    <StatusBadge label={a.status} variant={agentStatusVariant(a.status)} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex h-40 items-center justify-center text-sm text-slate-400">
              Agent status data is populated when agents process submissions
            </div>
          )}
        </div>
      </div>

      {/* ── Recent activity ── */}
      <div className="rounded-lg border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">Recent Activity</h2>
        {stats.recent_activity.length > 0 ? (
          <div className="divide-y divide-slate-100">
            {stats.recent_activity.map((ev) => (
              <div key={ev.id} className="flex items-center gap-3 py-2.5">
                <div
                  className={`h-2 w-2 shrink-0 rounded-full ${
                    ev.is_agent ? 'bg-blue-500' : 'bg-slate-400'
                  }`}
                />
                <span className="flex-1 text-sm text-slate-700">{ev.description}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-4 text-center text-sm text-slate-400">
            Activity feed will populate as submissions and claims are processed
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
