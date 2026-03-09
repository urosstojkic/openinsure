import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Inbox,
  FileText,
  AlertTriangle,
  Brain,
  ShieldCheck,
} from 'lucide-react';

const navItems = [
  { to: '/',            label: 'Dashboard',       icon: LayoutDashboard },
  { to: '/submissions', label: 'Submissions',     icon: Inbox },
  { to: '/policies',    label: 'Policies',        icon: FileText },
  { to: '/claims',      label: 'Claims',          icon: AlertTriangle },
  { to: '/decisions',   label: 'Agent Decisions',  icon: Brain },
  { to: '/compliance',  label: 'Compliance',      icon: ShieldCheck },
];

const Layout: React.FC = () => (
  <div className="flex h-screen overflow-hidden bg-slate-100">
    {/* ── Sidebar ── */}
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
          OI
        </div>
        <span className="text-lg font-bold text-slate-900">OpenInsure</span>
      </div>

      {/* Nav */}
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-blue-50 text-blue-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-200 px-4 py-3 text-xs text-slate-400">
        v1.0.0 · AI Oversight Platform
      </div>
    </aside>

    {/* ── Main area ── */}
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Top bar */}
      <header className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-6">
        <div />
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">Underwriter</span>
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white">
            SC
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6">
        <Outlet />
      </main>
    </div>
  </div>
);

export default Layout;
