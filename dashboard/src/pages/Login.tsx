import { useAuth, ROLE_PROFILES, type UserRole } from '../context/AuthContext';

const ROLE_COLORS: Record<UserRole, string> = {
  ceo: 'bg-gradient-to-br from-amber-400 to-amber-500',
  cuo: 'bg-gradient-to-br from-indigo-500 to-indigo-600',
  senior_uw: 'bg-gradient-to-br from-blue-500 to-blue-600',
  uw_analyst: 'bg-gradient-to-br from-sky-400 to-sky-500',
  claims_manager: 'bg-gradient-to-br from-orange-400 to-orange-500',
  adjuster: 'bg-gradient-to-br from-yellow-400 to-yellow-500',
  cfo: 'bg-gradient-to-br from-emerald-500 to-emerald-600',
  compliance: 'bg-gradient-to-br from-red-400 to-red-500',
  product_mgr: 'bg-gradient-to-br from-purple-500 to-purple-600',
  operations: 'bg-gradient-to-br from-teal-400 to-teal-500',
  broker: 'bg-gradient-to-br from-pink-400 to-pink-500',
};

const ROLE_DESCRIPTIONS: Record<UserRole, string> = {
  ceo: 'Executive overview & strategic KPIs',
  cuo: 'Underwriting oversight & AI governance',
  senior_uw: 'Review and bind complex risks',
  uw_analyst: 'Analyze submissions & risk data',
  claims_manager: 'Oversee claims operations',
  adjuster: 'Process and adjudicate claims',
  cfo: 'Financial reporting & loss ratios',
  compliance: 'Regulatory monitoring & audits',
  product_mgr: 'Product analytics & AI performance',
  operations: 'Operational metrics & workflows',
  broker: 'External submission portal',
};

interface PersonaGroup {
  label: string;
  roles: UserRole[];
}

const PERSONA_GROUPS: PersonaGroup[] = [
  { label: 'Leadership',          roles: ['ceo', 'cuo'] },
  { label: 'Underwriting',        roles: ['senior_uw', 'uw_analyst'] },
  { label: 'Claims',              roles: ['claims_manager', 'adjuster'] },
  { label: 'Finance & Compliance', roles: ['cfo', 'compliance'] },
  { label: 'Product & Ops',       roles: ['product_mgr', 'operations'] },
  { label: 'External',            roles: ['broker'] },
];

const Login: React.FC = () => {
  const { login } = useAuth();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/30 flex flex-col">
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-3xl">
          {/* Logo + Header */}
          <div className="text-center mb-10">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-600 text-lg font-bold text-white shadow-lg shadow-indigo-500/25 mb-4">
              OI
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">OpenInsure</h1>
            <p className="text-sm text-slate-500 mt-1">AI-Native Insurance Platform</p>
          </div>

          {/* Sign-in card */}
          <div className="bg-white rounded-2xl shadow-[var(--shadow-md)] border border-slate-200/60 px-8 py-8">
            <h2 className="text-lg font-semibold text-slate-800 text-center mb-6">Sign in to OpenInsure</h2>

            <div className="space-y-6">
              {PERSONA_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">{group.label}</span>
                    <div className="h-px flex-1 bg-slate-100" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                    {group.roles.map((role) => {
                      const profile = ROLE_PROFILES[role];
                      return (
                        <button
                          key={role}
                          onClick={() => login(role)}
                          className="group flex items-center gap-3 rounded-xl border border-slate-200/60 bg-white px-4 py-3 text-left transition-all duration-150 hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-100/50 hover:scale-[1.01] active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-indigo-500 focus-visible:outline-offset-2"
                        >
                          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white shadow-sm ${ROLE_COLORS[role]}`}>
                            {profile.avatar}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-[13px] font-semibold text-slate-800 truncate">{profile.name}</p>
                            <p className="text-[11px] text-slate-500 truncate">{profile.displayRole}</p>
                            <p className="text-[10px] text-slate-400 truncate mt-0.5">{ROLE_DESCRIPTIONS[role]}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="text-center text-[11px] text-slate-400 mt-6">
            Production: Microsoft Entra ID SSO · Demo: Select a persona
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
