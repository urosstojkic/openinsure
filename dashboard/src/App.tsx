import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth, NAV_ACCESS, DEFAULT_ROUTES } from './context/AuthContext';
import Layout from './components/Layout';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Submissions from './pages/Submissions';
import SubmissionDetail from './pages/SubmissionDetail';
import NewSubmission from './pages/NewSubmission';
import Policies from './pages/Policies';
import NewPolicy from './pages/NewPolicy';
import Claims from './pages/Claims';
import NewClaim from './pages/NewClaim';
import AgentDecisions from './pages/AgentDecisions';
import Compliance from './pages/Compliance';
import UnderwriterWorkbench from './pages/UnderwriterWorkbench';
import ClaimsWorkbench from './pages/ClaimsWorkbench';
import ComplianceWorkbench from './pages/ComplianceWorkbench';
import ExecutiveDashboard from './pages/ExecutiveDashboard';
import BrokerPortal from './pages/BrokerPortal';
import ReinsuranceDashboard from './pages/ReinsuranceDashboard';
import ActuarialWorkbench from './pages/ActuarialWorkbench';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

/** Redirects users away from routes they cannot access */
function RouteGuard({ children, path }: { children: React.ReactNode; path: string }) {
  const { user } = useAuth();

  // Normalise: strip trailing slashes
  const normPath = path === '' ? '/' : `/${path}`;

  const access = NAV_ACCESS[normPath];
  if (access && !access.includes(user.role)) {
    return <Navigate to={DEFAULT_ROUTES[user.role]} replace />;
  }
  return <>{children}</>;
}

/** Sub-routes under /submissions and /claims are governed by parent access */
function SubRouteGuard({ children, parentPath }: { children: React.ReactNode; parentPath: string }) {
  const { user } = useAuth();
  const access = NAV_ACCESS[parentPath];
  if (access && !access.includes(user.role)) {
    return <Navigate to={DEFAULT_ROUTES[user.role]} replace />;
  }
  return <>{children}</>;
}

/** Sends each role to their default landing page */
function DefaultRedirect() {
  const { user } = useAuth();
  const location = useLocation();
  const target = DEFAULT_ROUTES[user.role];
  if (location.pathname !== target) {
    return <Navigate to={target} replace />;
  }
  return null;
}

function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<RouteGuard path=""><Dashboard /></RouteGuard>} />
        <Route path="submissions" element={<RouteGuard path="submissions"><Submissions /></RouteGuard>} />
        <Route path="submissions/new" element={<SubRouteGuard parentPath="/submissions"><NewSubmission /></SubRouteGuard>} />
        <Route path="submissions/:id" element={<SubRouteGuard parentPath="/submissions"><SubmissionDetail /></SubRouteGuard>} />
        <Route path="policies" element={<RouteGuard path="policies"><Policies /></RouteGuard>} />
        <Route path="policies/new" element={<SubRouteGuard parentPath="/policies"><NewPolicy /></SubRouteGuard>} />
        <Route path="claims" element={<RouteGuard path="claims"><Claims /></RouteGuard>} />
        <Route path="claims/new" element={<SubRouteGuard parentPath="/claims"><NewClaim /></SubRouteGuard>} />
        <Route path="decisions" element={<RouteGuard path="decisions"><AgentDecisions /></RouteGuard>} />
        <Route path="compliance" element={<RouteGuard path="compliance"><Compliance /></RouteGuard>} />
        <Route path="workbench/underwriting" element={<RouteGuard path="workbench/underwriting"><UnderwriterWorkbench /></RouteGuard>} />
        <Route path="workbench/claims" element={<RouteGuard path="workbench/claims"><ClaimsWorkbench /></RouteGuard>} />
        <Route path="workbench/compliance" element={<RouteGuard path="workbench/compliance"><ComplianceWorkbench /></RouteGuard>} />
        <Route path="workbench/reinsurance" element={<RouteGuard path="workbench/reinsurance"><ReinsuranceDashboard /></RouteGuard>} />
        <Route path="workbench/actuarial" element={<RouteGuard path="workbench/actuarial"><ActuarialWorkbench /></RouteGuard>} />
        <Route path="executive" element={<RouteGuard path="executive"><ExecutiveDashboard /></RouteGuard>} />
        <Route path="portal/broker" element={<RouteGuard path="portal/broker"><BrokerPortal /></RouteGuard>} />
        <Route path="*" element={<DefaultRedirect />} />
      </Route>
    </Routes>
  );
}

function AuthGate() {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Login />;
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGate />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
