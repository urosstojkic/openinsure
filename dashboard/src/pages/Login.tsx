import { useAuth, ROLE_PROFILES, type UserRole } from '../context/AuthContext';

const ROLE_COLORS: Record<UserRole, string> = {
  ceo: 'bg-amber-500',
  cuo: 'bg-indigo-500',
  senior_uw: 'bg-blue-500',
  uw_analyst: 'bg-sky-500',
  claims_manager: 'bg-orange-500',
  adjuster: 'bg-yellow-500',
  cfo: 'bg-emerald-500',
  compliance: 'bg-red-500',
  product_mgr: 'bg-purple-500',
  operations: 'bg-teal-500',
  broker: 'bg-pink-500',
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
    <div className="min-h-screen bg-slate-50 flex flex-col">
      {/* Main content — vertically centered */}
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-3xl">
          {/* Logo + Header */}
          <div className="text-center mb-10">
            <div className="inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-indigo-700 text-lg font-bold text-white shadow-lg shadow-indigo-500/25 mb-4">
              OI
            </div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">OpenInsure</h1>
            <p className="text-sm text-slate-500 mt-1">AI-Native Insurance Platform</p>
          </div>

          {/* Sign-in card */}
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 px-8 py-8">
            <h2 className="text-lg font-semibold text-slate-800 text-center mb-6">Sign in to OpenInsure</h2>

            {/* Persona groups */}
            <div className="space-y-6">
              {PERSONA_GROUPS.map((group) => (
                <div key={group.label}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">{group.label}</span>
                    <div className="h-px flex-1 bg-slate-100" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                    {group.roles.map((role) => {
                      const profile = ROLE_PROFILES[role];
                      return (
                        <button
                          key={role}
                          onClick={() => login(role)}
                          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-left transition-all hover:border-indigo-300 hover:shadow-md hover:shadow-indigo-100/50 hover:scale-[1.02] active:scale-[0.98]"
                        >
                          <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${ROLE_COLORS[role]}`}>
                            {profile.avatar}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-slate-800 truncate">{profile.name}</p>
                            <p className="text-xs text-slate-500 truncate">{profile.displayRole}</p>
                            <p className="text-[11px] text-slate-400 truncate mt-0.5">{ROLE_DESCRIPTIONS[role]}</p>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <p className="text-center text-xs text-slate-400 mt-6">
            Production: Microsoft Entra ID SSO · Demo: Select a persona
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
