import React, { createContext, useContext, useState, useCallback, type ReactNode } from 'react';

export type UserRole =
  | 'cuo'
  | 'senior_uw'
  | 'uw_analyst'
  | 'claims_manager'
  | 'adjuster'
  | 'cfo'
  | 'compliance'
  | 'product_mgr'
  | 'operations'
  | 'broker'
  | 'ceo';

interface User {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  displayRole: string;
  avatar: string;
}

interface AuthContextType {
  user: User;
  isAuthenticated: boolean;
  login: (role: UserRole) => void;
  logout: () => void;
  hasAccess: (requiredRoles: UserRole[]) => boolean;
}

const ROLE_PROFILES: Record<UserRole, Omit<User, 'role'>> = {
  ceo:            { id: 'u-ceo', name: 'Alexandra Reed',   email: 'a.reed@openinsure.io',     displayRole: 'Chief Executive Officer',    avatar: 'AR' },
  cuo:            { id: 'u-cuo', name: 'Sarah Chen',       email: 's.chen@openinsure.io',     displayRole: 'Chief Underwriting Officer', avatar: 'SC' },
  senior_uw:      { id: 'u-suw', name: 'James Wright',     email: 'j.wright@openinsure.io',   displayRole: 'Senior Underwriter',         avatar: 'JW' },
  uw_analyst:     { id: 'u-uwa', name: 'Maria Lopez',      email: 'm.lopez@openinsure.io',    displayRole: 'Underwriting Analyst',       avatar: 'ML' },
  claims_manager: { id: 'u-ccm', name: 'David Park',       email: 'd.park@openinsure.io',     displayRole: 'Chief Claims Officer',       avatar: 'DP' },
  adjuster:       { id: 'u-adj', name: 'Lisa Martinez',    email: 'l.martinez@openinsure.io', displayRole: 'Claims Adjuster',            avatar: 'LM' },
  cfo:            { id: 'u-cfo', name: 'Michael Torres',   email: 'm.torres@openinsure.io',   displayRole: 'Chief Financial Officer',    avatar: 'MT' },
  compliance:     { id: 'u-cro', name: 'Anna Kowalski',    email: 'a.kowalski@openinsure.io', displayRole: 'Compliance Officer',         avatar: 'AK' },
  product_mgr:    { id: 'u-pm',  name: 'Robert Chen',      email: 'r.chen@openinsure.io',     displayRole: 'Head of Product & Data',     avatar: 'RC' },
  operations:     { id: 'u-ops', name: 'Emily Davis',      email: 'e.davis@openinsure.io',    displayRole: 'Operations Lead',            avatar: 'ED' },
  broker:         { id: 'u-brk', name: 'Thomas Anderson',  email: 't.anderson@broker.com',    displayRole: 'Broker — Marsh & Co',        avatar: 'TA' },
};

export const DEFAULT_ROUTES: Record<UserRole, string> = {
  ceo: '/executive',
  cuo: '/',
  senior_uw: '/workbench/underwriting',
  uw_analyst: '/workbench/underwriting',
  claims_manager: '/workbench/claims',
  adjuster: '/workbench/claims',
  cfo: '/executive',
  compliance: '/workbench/compliance',
  product_mgr: '/',
  operations: '/',
  broker: '/portal/broker',
};

export const NAV_ACCESS: Record<string, UserRole[]> = {
  '/':                       ['ceo', 'cuo', 'senior_uw', 'uw_analyst', 'claims_manager', 'adjuster', 'cfo', 'compliance', 'product_mgr', 'operations'],
  '/submissions':            ['cuo', 'senior_uw', 'uw_analyst', 'product_mgr', 'operations'],
  '/policies':               ['cuo', 'senior_uw', 'uw_analyst', 'claims_manager', 'cfo', 'compliance'],
  '/claims':                 ['cuo', 'claims_manager', 'adjuster', 'compliance'],
  '/decisions':              ['cuo', 'compliance', 'product_mgr', 'ceo'],
  '/compliance':             ['compliance', 'cuo', 'ceo'],
  '/workbench/underwriting': ['cuo', 'senior_uw', 'uw_analyst'],
  '/workbench/claims':       ['claims_manager', 'adjuster'],
  '/workbench/compliance':   ['compliance'],
  '/workbench/reinsurance':  ['cuo', 'cfo'],
  '/workbench/actuarial':    ['cuo', 'cfo', 'ceo'],
  '/executive':              ['ceo', 'cuo', 'cfo'],
  '/portal/broker':          ['broker'],
};

export const ALL_ROLES: UserRole[] = [
  'ceo', 'cuo', 'senior_uw', 'uw_analyst', 'claims_manager',
  'adjuster', 'cfo', 'compliance', 'product_mgr', 'operations', 'broker',
];

const STORAGE_KEY = 'openinsure_role';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function buildUser(role: UserRole): User {
  return { ...ROLE_PROFILES[role], role };
}

function getSavedRole(): UserRole | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && ALL_ROLES.includes(saved as UserRole)) return saved as UserRole;
  } catch { /* localStorage unavailable */ }
  return null;
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const savedRole = getSavedRole();
  const [role, setRoleState] = useState<UserRole>(savedRole ?? 'cuo');
  const [isAuthenticated, setIsAuthenticated] = useState(savedRole !== null);

  const user = buildUser(role);

  const login = useCallback((newRole: UserRole) => {
    setRoleState(newRole);
    setIsAuthenticated(true);
    try { localStorage.setItem(STORAGE_KEY, newRole); } catch { /* noop */ }
  }, []);

  const logout = useCallback(() => {
    setIsAuthenticated(false);
    setRoleState('cuo');
    try { localStorage.removeItem(STORAGE_KEY); } catch { /* noop */ }
  }, []);

  const hasAccess = useCallback((requiredRoles: UserRole[]) => requiredRoles.includes(role), [role]);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, logout, hasAccess }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export { ROLE_PROFILES };
