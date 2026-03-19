import React, { useState, useRef, useEffect } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Inbox,
  FileText,
  AlertTriangle,
  Brain,
  ShieldCheck,
  Briefcase,
  Scale,
  ShieldAlert,
  BarChart3,
  ExternalLink,
  Bell,
  ChevronDown,
  LogOut,
  ArrowLeftRight,
  ArrowUpFromLine,
  Calculator,
  Repeat2,
} from 'lucide-react';
import { useAuth, NAV_ACCESS, type UserRole } from '../context/AuthContext';

const navItems = [
  { to: '/',            label: 'Dashboard',        icon: LayoutDashboard },
  { to: '/submissions', label: 'Submissions',      icon: Inbox },
  { to: '/policies',    label: 'Policies',         icon: FileText },
  { to: '/claims',      label: 'Claims',           icon: AlertTriangle },
  { to: '/decisions',    label: 'Agent Decisions',  icon: Brain },
  { to: '/escalations', label: 'Escalations',      icon: ArrowUpFromLine },
  { to: '/compliance',  label: 'Compliance',       icon: ShieldCheck },
];

const workbenchItems = [
  { to: '/workbench/underwriting', label: 'Underwriter',  icon: Briefcase },
  { to: '/workbench/claims',      label: 'Claims',        icon: Scale },
  { to: '/workbench/compliance',  label: 'Compliance',    icon: ShieldAlert },
  { to: '/workbench/actuarial',   label: 'Actuarial',     icon: Calculator },
  { to: '/workbench/reinsurance', label: 'Reinsurance',   icon: Repeat2 },
];

const extraItems = [
  { to: '/executive',     label: 'Executive',     icon: BarChart3 },
  { to: '/portal/broker', label: 'Broker Portal', icon: ExternalLink },
];

function filterItems(items: typeof navItems, role: UserRole) {
  return items.filter(({ to }) => {
    const access = NAV_ACCESS[to];
    return access ? access.includes(role) : false;
  });
}

/* Breadcrumb helper */
function getBreadcrumb(pathname: string): string {
  const map: Record<string, string> = {
    '/': 'Dashboard',
    '/submissions': 'Submissions',
    '/policies': 'Policies',
    '/claims': 'Claims',
    '/decisions': 'Agent Decisions',
    '/escalations': 'Escalation Queue',
    '/compliance': 'Compliance',
    '/workbench/underwriting': 'Underwriter Workbench',
    '/workbench/claims': 'Claims Workbench',
    '/workbench/compliance': 'Compliance Workbench',
    '/workbench/reinsurance': 'Reinsurance Dashboard',
    '/workbench/actuarial': 'Actuarial Workbench',
    '/executive': 'Executive Dashboard',
    '/portal/broker': 'Broker Portal',
  };
  return map[pathname] ?? pathname.split('/').filter(Boolean).pop() ?? 'Home';
}

const NavSection: React.FC<{
  items: typeof navItems;
  role: UserRole;
  sectionLabel?: string;
}> = ({ items, role, sectionLabel }) => {
  const visible = filterItems(items, role);
  if (visible.length === 0) return null;
  return (
    <>
      {sectionLabel && (
        <div className="pt-5 pb-1.5 px-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">{sectionLabel}</span>
            <div className="h-px flex-1 bg-slate-200/70" />
          </div>
        </div>
      )}
      {visible.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className={({ isActive }) =>
            `group flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-all duration-150 ${
              isActive
                ? 'bg-indigo-50 text-indigo-700 border-l-[3px] border-indigo-500 pl-[9px]'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900 hover:scale-[1.01]'
            }`
          }
        >
          <Icon size={18} className="shrink-0" />
          {label}
        </NavLink>
      ))}
    </>
  );
};

const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const location = useLocation();
  const isBroker = user.role === 'broker';

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  /* User menu dropdown */
  const userMenu = (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition hover:bg-slate-100"
      >
        <div className="text-right leading-tight">
          <p className="text-sm font-medium text-slate-700">{user.name}</p>
          <p className="text-[11px] text-slate-400">{user.displayRole}</p>
        </div>
        <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 text-xs font-bold text-white shadow-md shadow-indigo-500/20">
          {user.avatar}
        </div>
        <ChevronDown size={14} className={`text-slate-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-slate-200 bg-white py-1 shadow-xl shadow-slate-200/50 z-50">
          <div className="px-4 py-2.5 border-b border-slate-100">
            <p className="text-sm font-semibold text-slate-700">{user.name}</p>
            <p className="text-xs text-slate-400">{user.email}</p>
          </div>
          <button
            onClick={() => { setMenuOpen(false); logout(); }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <ArrowLeftRight size={15} className="text-slate-400" />
            Switch Account
          </button>
          <button
            onClick={() => { setMenuOpen(false); logout(); }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut size={15} className="text-red-400" />
            Sign Out
          </button>
        </div>
      )}
    </div>
  );

  /* ── Broker gets a minimal top-nav layout ── */
  if (isBroker) {
    return (
      <div className="flex h-screen flex-col overflow-hidden" style={{ background: 'var(--color-surface)' }}>
        <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200/60 bg-white/80 px-6 backdrop-blur-sm">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-700 text-xs font-bold text-white">
              OI
            </div>
            <span className="text-sm font-bold text-slate-900">OpenInsure</span>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
              <Bell size={18} />
              <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                3
              </span>
            </button>
            {userMenu}
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar ── */}
        <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200/60 bg-gradient-to-b from-white to-slate-50">
          {/* Logo */}
          <div className="flex h-16 items-center gap-2.5 border-b border-slate-200/60 px-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-sm font-bold text-white shadow-lg shadow-indigo-500/20">
              OI
            </div>
            <div className="flex flex-col">
              <span className="text-base font-bold tracking-tight text-slate-900">OpenInsure</span>
              <span className="text-[10px] text-slate-400">AI Oversight Platform</span>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
            <NavSection items={navItems} role={user.role} />
            <NavSection items={workbenchItems} role={user.role} sectionLabel="Workbenches" />
            <NavSection items={extraItems} role={user.role} sectionLabel="Views" />
          </nav>

          {/* Footer */}
          <div className="border-t border-slate-200/60 px-4 py-3 text-[11px] text-slate-400">
            v1.0.0 · AI Oversight Platform
          </div>
        </aside>

        {/* ── Main area ── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top bar — frosted glass */}
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200/60 bg-white/80 px-6 backdrop-blur-sm">
            {/* Breadcrumb */}
            <div className="flex items-center gap-2 text-sm">
              <span className="text-slate-400">OpenInsure</span>
              <span className="text-slate-300">/</span>
              <span className="font-medium text-slate-700">{getBreadcrumb(location.pathname)}</span>
            </div>

            {/* Right: bell + user menu */}
            <div className="flex items-center gap-3">
              {/* Notification bell */}
              <button className="relative rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
                <Bell size={18} />
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                  3
                </span>
              </button>

              {/* User menu */}
              {userMenu}
            </div>
          </header>

          {/* Content */}
          <main className="flex-1 overflow-y-auto p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
};

export default Layout;
