import React, { useState, useRef, useEffect } from 'react';
import { NavLink, Outlet, useLocation, useSearchParams } from 'react-router-dom';
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
  ArrowLeftRight,
} from 'lucide-react';
import { useAuth, NAV_ACCESS, ALL_ROLES, type UserRole } from '../context/AuthContext';

const navItems = [
  { to: '/',            label: 'Dashboard',        icon: LayoutDashboard },
  { to: '/submissions', label: 'Submissions',      icon: Inbox },
  { to: '/policies',    label: 'Policies',         icon: FileText },
  { to: '/claims',      label: 'Claims',           icon: AlertTriangle },
  { to: '/decisions',   label: 'Agent Decisions',  icon: Brain },
  { to: '/compliance',  label: 'Compliance',       icon: ShieldCheck },
];

const workbenchItems = [
  { to: '/workbench/underwriting', label: 'Underwriter',  icon: Briefcase },
  { to: '/workbench/claims',      label: 'Claims',        icon: Scale },
  { to: '/workbench/compliance',  label: 'Compliance',    icon: ShieldAlert },
];

const extraItems = [
  { to: '/executive',     label: 'Executive',     icon: BarChart3 },
  { to: '/portal/broker', label: 'Broker Portal', icon: ExternalLink },
];

const ROLE_LABELS: Record<UserRole, string> = {
  ceo: 'CEO',
  cuo: 'CUO',
  senior_uw: 'Senior UW',
  uw_analyst: 'UW Analyst',
  claims_manager: 'Claims Mgr',
  adjuster: 'Adjuster',
  cfo: 'CFO',
  compliance: 'Compliance',
  product_mgr: 'Product Mgr',
  operations: 'Operations',
  broker: 'Broker',
};

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  ceo: 'Executive overview',
  cuo: 'Underwriting oversight',
  senior_uw: 'Senior underwriting',
  uw_analyst: 'Underwriting analysis',
  claims_manager: 'Claims oversight',
  adjuster: 'Claims processing',
  cfo: 'Financial oversight',
  compliance: 'Regulatory compliance',
  product_mgr: 'Product & data',
  operations: 'Operations management',
  broker: 'External portal',
};

const ROLE_COLORS: Record<UserRole, string> = {
  ceo: 'bg-amber-400',
  cuo: 'bg-indigo-400',
  senior_uw: 'bg-blue-400',
  uw_analyst: 'bg-sky-400',
  claims_manager: 'bg-orange-400',
  adjuster: 'bg-yellow-400',
  cfo: 'bg-emerald-400',
  compliance: 'bg-red-400',
  product_mgr: 'bg-purple-400',
  operations: 'bg-teal-400',
  broker: 'bg-pink-400',
};

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
    '/compliance': 'Compliance',
    '/workbench/underwriting': 'Underwriter Workbench',
    '/workbench/claims': 'Claims Workbench',
    '/workbench/compliance': 'Compliance Workbench',
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
  const { user, setRole } = useAuth();
  const location = useLocation();
  const [, setSearchParams] = useSearchParams();
  const isBroker = user.role === 'broker';

  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const bannerDropdownRef = useRef<HTMLDivElement>(null);

  /* URL sync: read ?role= on mount */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const roleParam = params.get('role');
    if (roleParam && ALL_ROLES.includes(roleParam as UserRole)) {
      setRole(roleParam as UserRole);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* URL sync: update URL when role changes */
  useEffect(() => {
    setSearchParams(prev => {
      const next = new URLSearchParams(prev);
      next.set('role', user.role);
      return next;
    }, { replace: true });
  }, [user.role, setSearchParams]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        (!dropdownRef.current || !dropdownRef.current.contains(target)) &&
        (!bannerDropdownRef.current || !bannerDropdownRef.current.contains(target))
      ) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleRoleSwitch = (role: UserRole) => {
    setRole(role);
    setDropdownOpen(false);
  };

  /* Shared dropdown panel */
  const roleDropdownContent = (
    <div className="w-72 rounded-xl border border-slate-200 bg-white py-2 shadow-xl shadow-slate-200/50 z-50">
      <div className="px-4 py-2 border-b border-slate-100">
        <p className="text-sm font-semibold text-slate-700">🔄 Switch Role</p>
        <p className="text-[11px] text-slate-400 mt-0.5">Select a persona to preview their view</p>
      </div>
      <div className="max-h-80 overflow-y-auto py-1">
        {ALL_ROLES.map((r) => (
          <button
            key={r}
            onClick={() => handleRoleSwitch(r)}
            className={`flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors ${
              r === user.role
                ? 'bg-violet-50 border-l-[3px] border-violet-500 pl-[13px]'
                : 'hover:bg-slate-50'
            }`}
          >
            <span className={`h-2.5 w-2.5 rounded-full shrink-0 ${ROLE_COLORS[r]} ${r === user.role ? 'ring-2 ring-violet-300 ring-offset-1' : ''}`} />
            <div className="min-w-0 flex-1">
              <p className={`text-sm ${r === user.role ? 'font-semibold text-violet-700' : 'font-medium text-slate-700'}`}>
                {ROLE_LABELS[r]}
              </p>
              <p className="text-[11px] text-slate-400 truncate">{ROLE_DESCRIPTIONS[r]}</p>
            </div>
            {r === user.role && (
              <span className="text-[10px] font-semibold text-violet-500 bg-violet-100 px-1.5 py-0.5 rounded shrink-0">Active</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );

  /* Demo-mode banner — visible on ALL pages */
  const demoBanner = (
    <div className="bg-violet-600 text-white text-center text-xs py-1.5 px-4 flex items-center justify-center gap-2 relative z-30">
      <span>🎭 Demo Mode — Switch roles to see different views.</span>
      <div ref={bannerDropdownRef} className="relative inline-block">
        <button
          onClick={() => setDropdownOpen(!dropdownOpen)}
          className="underline font-medium hover:text-violet-200 transition-colors"
        >
          Current: {user.displayRole}
        </button>
        {isBroker && dropdownOpen && (
          <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2">
            {roleDropdownContent}
          </div>
        )}
      </div>
    </div>
  );

  /* ── Broker gets a minimal top-nav layout ── */
  if (isBroker) {
    return (
      <div className="flex h-screen flex-col overflow-hidden" style={{ background: 'var(--color-surface)' }}>
        {demoBanner}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden" style={{ background: 'var(--color-surface)' }}>
      {demoBanner}
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

            {/* Right: role switcher + bell + avatar */}
            <div className="flex items-center gap-4">
              {/* Role switcher — prominent pill badge */}
              <div ref={dropdownRef} className="relative">
                <button
                  onClick={() => setDropdownOpen(!dropdownOpen)}
                  className="flex items-center gap-2 rounded-full border border-violet-300 bg-violet-50 px-4 py-1.5 text-sm font-semibold text-violet-700 shadow-sm ring-2 ring-violet-200 transition hover:bg-violet-100 hover:ring-violet-300"
                >
                  <ArrowLeftRight size={14} className="text-violet-500" />
                  <span>Demo:</span>
                  <span className="text-violet-900">{ROLE_LABELS[user.role]}</span>
                  <ChevronDown size={14} className={`text-violet-400 transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
                </button>
                {dropdownOpen && (
                  <div className="absolute right-0 top-full mt-2">
                    {roleDropdownContent}
                  </div>
                )}
              </div>

              {/* Notification bell */}
              <button className="relative rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
                <Bell size={18} />
                <span className="absolute -top-0.5 -right-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">
                  3
                </span>
              </button>

              {/* User */}
              <div className="flex items-center gap-2.5">
                <div className="text-right leading-tight">
                  <p className="text-sm font-medium text-slate-700">{user.name}</p>
                  <p className="text-[11px] text-slate-400">{user.displayRole}</p>
                </div>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-indigo-700 text-xs font-bold text-white shadow-md shadow-indigo-500/20">
                  {user.avatar}
                </div>
              </div>
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
