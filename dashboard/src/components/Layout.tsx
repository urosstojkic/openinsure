import React, { useState, useRef, useEffect } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
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
  Banknote,
  BookOpen,
  PanelLeftClose,
  PanelLeftOpen,
  Menu,
  X,
  Search,
  Command,
  Package,
} from 'lucide-react';
import { useAuth, NAV_ACCESS, type UserRole } from '../context/AuthContext';
import { useMockMode } from '../context/MockContext';
import { getEscalationCount } from '../api/escalations';

const SIDEBAR_COLLAPSED_KEY = 'openinsure_sidebar_collapsed';

const navItems = [
  { to: '/',            label: 'Dashboard',        icon: LayoutDashboard },
  { to: '/submissions', label: 'Submissions',      icon: Inbox },
  { to: '/policies',    label: 'Policies',         icon: FileText },
  { to: '/claims',      label: 'Claims',           icon: AlertTriangle },
  { to: '/decisions',    label: 'Agent Decisions',  icon: Brain },
  { to: '/escalations', label: 'Escalations',      icon: ArrowUpFromLine },
  { to: '/finance',     label: 'Finance',          icon: Banknote },
  { to: '/compliance',  label: 'Compliance',       icon: ShieldCheck },
  { to: '/knowledge',   label: 'Knowledge',        icon: BookOpen },
  { to: '/products',    label: 'Products',         icon: Package },
  { to: '/analytics/underwriting', label: 'UW Analytics',     icon: BarChart3 },
  { to: '/analytics/claims',       label: 'Claims Analytics', icon: BarChart3 },
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
    '/finance': 'Finance Dashboard',
    '/compliance': 'Compliance',
    '/workbench/underwriting': 'Underwriter Workbench',
    '/workbench/claims': 'Claims Workbench',
    '/workbench/compliance': 'Compliance Workbench',
    '/workbench/reinsurance': 'Reinsurance Dashboard',
    '/workbench/actuarial': 'Actuarial Workbench',
    '/knowledge': 'Knowledge Base',
    '/products': 'Product Management',
    '/analytics/underwriting': 'UW Performance Analytics',
    '/analytics/claims': 'Claims Analytics',
    '/executive': 'Executive Dashboard',
    '/portal/broker': 'Broker Portal',
  };
  if (map[pathname]) return map[pathname];
  // Detail pages: show parent label
  const detailPatterns: Record<string, string> = {
    '/submissions/': 'Submissions',
    '/policies/': 'Policies',
    '/claims/': 'Claims',
  };
  for (const [prefix, label] of Object.entries(detailPatterns)) {
    if (pathname.startsWith(prefix)) {
      const id = pathname.slice(prefix.length);
      if (id === 'new') return label;
      return label;
    }
  }
  return pathname.split('/').filter(Boolean).pop() ?? 'Home';
}

const NavSection: React.FC<{
  items: typeof navItems;
  role: UserRole;
  sectionLabel?: string;
  collapsed?: boolean;
  escalationCount?: number;
}> = ({ items, role, sectionLabel, collapsed, escalationCount }) => {
  const visible = filterItems(items, role);
  if (visible.length === 0) return null;
  return (
    <>
      {sectionLabel && !collapsed && (
        <div className="pt-6 pb-1.5 px-3">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400/80">{sectionLabel}</span>
            <div className="h-px flex-1 bg-slate-200/50" />
          </div>
        </div>
      )}
      {sectionLabel && collapsed && (
        <div className="pt-4 pb-1 px-2">
          <div className="h-px bg-slate-200/50" />
        </div>
      )}
      {visible.map(({ to, label, icon: Icon }) => {
        const showBadge = to === '/escalations' && escalationCount != null && escalationCount > 0;
        return (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={collapsed ? label : undefined}
            className={({ isActive }) =>
              `group relative flex items-center ${collapsed ? 'justify-center' : 'gap-2.5'} rounded-lg ${collapsed ? 'px-2 py-2 mx-1' : 'px-3 py-[7px]'} text-[13px] font-medium transition-all duration-150 ${
                isActive
                  ? 'bg-indigo-50/80 text-indigo-700'
                  : 'text-slate-500 hover:bg-slate-100/80 hover:text-slate-800'
              }`
            }
          >
            {({ isActive }) => (
              <>
                {isActive && !collapsed && (
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-[3px] rounded-r-full bg-indigo-500" />
                )}
                <Icon size={17} className={`shrink-0 ${isActive ? 'text-indigo-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                {!collapsed && (
                  <span className="flex-1">{label}</span>
                )}
                {showBadge && !collapsed && (
                  <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1.5 text-[10px] font-bold text-white">
                    {escalationCount}
                  </span>
                )}
                {showBadge && collapsed && (
                  <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white ring-2 ring-white">
                    {escalationCount}
                  </span>
                )}
              </>
            )}
          </NavLink>
        );
      })}
    </>
  );
};

const Layout: React.FC = () => {
  const { user, logout } = useAuth();
  const { useMock, toggleMock } = useMockMode();
  const location = useLocation();
  const isBroker = user.role === 'broker';

  // Escalation badge count (#76)
  const { data: escalationCount = 0 } = useQuery({
    queryKey: ['escalation-count'],
    queryFn: async () => {
      try { return await getEscalationCount(); }
      catch { return 0; }
    },
    refetchInterval: 30_000,
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Sidebar collapse state (persisted in localStorage)
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'; }
    catch { return false; }
  });
  // Mobile sidebar open state
  const [mobileOpen, setMobileOpen] = useState(false);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    try { localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next)); }
    catch { /* localStorage unavailable */ }
  };

  // Close mobile sidebar on route change
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

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
        className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 transition-all hover:bg-slate-100/80"
      >
        <div className="text-right leading-tight hidden sm:block">
          <p className="text-[13px] font-semibold text-slate-700">{user.name}</p>
          <p className="text-[10px] text-slate-400">{user.displayRole}</p>
        </div>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-600 text-[11px] font-bold text-white shadow-sm shadow-indigo-500/20">
          {user.avatar}
        </div>
        <ChevronDown size={12} className={`text-slate-400 transition-transform duration-200 ${menuOpen ? 'rotate-180' : ''}`} />
      </button>

      {menuOpen && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-slate-200/60 bg-white/95 py-1 shadow-xl shadow-slate-200/40 backdrop-blur-sm z-50">
          <div className="px-4 py-2.5 border-b border-slate-100">
            <p className="text-sm font-semibold text-slate-700">{user.name}</p>
            <p className="text-[11px] text-slate-400">{user.email}</p>
          </div>
          <button
            onClick={() => { setMenuOpen(false); logout(); }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-slate-600 hover:bg-slate-50 transition-colors"
          >
            <ArrowLeftRight size={14} className="text-slate-400" />
            Switch Account
          </button>
          <button
            onClick={() => { setMenuOpen(false); logout(); }}
            className="flex w-full items-center gap-2.5 px-4 py-2.5 text-[13px] text-red-600 hover:bg-red-50 transition-colors"
          >
            <LogOut size={14} className="text-red-400" />
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
          <div className="page-enter">
            <Outlet />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      <div className="flex flex-1 overflow-hidden">
        {/* ── Mobile overlay ── */}
        {mobileOpen && (
          <div
            className="fixed inset-0 z-30 bg-black/20 backdrop-blur-sm md:hidden"
            onClick={() => setMobileOpen(false)}
          />
        )}

        {/* ── Sidebar ── */}
        <aside className={`
          ${collapsed ? 'w-[60px]' : 'w-[240px]'} shrink-0 flex-col border-r border-slate-200/60 bg-white transition-all duration-200
          fixed inset-y-0 left-0 z-40 md:static
          ${mobileOpen ? 'flex' : 'hidden md:flex'}
        `}>
          {/* Logo */}
          <div className={`flex h-14 items-center ${collapsed ? 'justify-center' : 'gap-2.5'} border-b border-slate-100 px-3`}>
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-indigo-600 text-[11px] font-bold text-white shadow-sm shadow-indigo-500/20">
              OI
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span className="text-[13px] font-bold tracking-tight text-slate-900">OpenInsure</span>
                <span className="text-[9px] font-medium uppercase tracking-wider text-slate-400">AI Platform</span>
              </div>
            )}
            {/* Close button on mobile */}
            <button
              onClick={() => setMobileOpen(false)}
              className="ml-auto rounded-lg p-1 text-slate-400 hover:bg-slate-100 md:hidden"
            >
              <X size={16} />
            </button>
          </div>

          {/* Quick search hint (expanded only) */}
          {!collapsed && (
            <div className="px-3 pt-3 pb-1">
              <div className="flex items-center gap-2 rounded-lg border border-slate-200/60 bg-slate-50/50 px-3 py-[6px] text-slate-400">
                <Search size={13} />
                <span className="flex-1 text-[12px]">Search…</span>
                <kbd className="hidden sm:inline-flex items-center gap-0.5 rounded border border-slate-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                  <Command size={9} />K
                </kbd>
              </div>
            </div>
          )}

          {/* Nav */}
          <nav className="flex-1 space-y-0.5 overflow-y-auto custom-scrollbar px-2 py-2">
            <NavSection items={navItems} role={user.role} collapsed={collapsed} escalationCount={escalationCount} />
            <NavSection items={workbenchItems} role={user.role} sectionLabel="Workbenches" collapsed={collapsed} />
            <NavSection items={extraItems} role={user.role} sectionLabel="Views" collapsed={collapsed} />
          </nav>

          {/* Footer */}
          <div className="border-t border-slate-100 px-3 py-2.5">
            {!collapsed && (
              <>
                {/* User mini-card */}
                <div className="mb-2 flex items-center gap-2.5 rounded-lg bg-slate-50/80 px-2.5 py-2">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-600 text-[10px] font-bold text-white">
                    {user.avatar}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-[12px] font-semibold text-slate-700 truncate">{user.name}</p>
                    <p className="text-[10px] text-slate-400 truncate">{user.displayRole}</p>
                  </div>
                </div>
                <button
                  onClick={toggleMock}
                  className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-[11px] text-slate-400 hover:bg-slate-50 transition-colors"
                >
                  <span>Demo Mode</span>
                  <span className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${useMock ? 'bg-indigo-500' : 'bg-slate-300'}`}>
                    <span className={`inline-block h-3 w-3 transform rounded-full bg-white shadow-sm transition-transform ${useMock ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
                  </span>
                </button>
                <p className="mt-1 px-2.5 text-[9px] text-slate-400/70">v1.0.0 · AI Oversight Platform</p>
              </>
            )}
            {/* Collapse toggle (hidden on mobile) */}
            <button
              onClick={toggleCollapsed}
              className="mt-1 hidden w-full items-center justify-center rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 transition-colors md:flex"
              title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {collapsed ? <PanelLeftOpen size={15} /> : <PanelLeftClose size={15} />}
            </button>
          </div>
        </aside>

        {/* ── Main area ── */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top bar — frosted glass */}
          <header className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-slate-200/60 bg-white/80 px-6 backdrop-blur-sm">
            {/* Mobile hamburger + Breadcrumb */}
            <div className="flex items-center gap-2 text-sm">
              <button
                onClick={() => setMobileOpen(true)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 md:hidden"
              >
                <Menu size={18} />
              </button>
              <span className="text-slate-400/80 text-[13px]">OpenInsure</span>
              <span className="text-slate-200">/</span>
              <span className="font-semibold text-slate-700 text-[13px]">{getBreadcrumb(location.pathname)}</span>
            </div>

            {/* Right: bell + user menu */}
            <div className="flex items-center gap-2">
              {/* Notification bell */}
              <button className="relative rounded-lg p-1.5 text-slate-400 transition-all hover:bg-slate-100 hover:text-slate-600">
                <Bell size={17} />
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white ring-2 ring-white">
                  3
                </span>
              </button>

              {/* Separator */}
              <div className="hidden sm:block h-6 w-px bg-slate-200/60" />

              {/* User menu */}
              {userMenu}
            </div>
          </header>

          {/* Content */}
          <main className="flex-1 overflow-y-auto custom-scrollbar p-6">
            <div className="page-enter">
              <Outlet />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};

export default Layout;
