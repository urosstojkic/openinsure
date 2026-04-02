import React, { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth, NAV_ACCESS, DEFAULT_ROUTES } from './context/AuthContext';
import { MockProvider } from './context/MockContext';
import Layout from './components/Layout';
import Login from './pages/Login';

// Route-level code splitting (#275)
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Submissions = lazy(() => import('./pages/Submissions'));
const SubmissionDetail = lazy(() => import('./pages/SubmissionDetail'));
const NewSubmission = lazy(() => import('./pages/NewSubmission'));
const Policies = lazy(() => import('./pages/Policies'));
const PolicyDetail = lazy(() => import('./pages/PolicyDetail'));
const NewPolicy = lazy(() => import('./pages/NewPolicy'));
const Claims = lazy(() => import('./pages/Claims'));
const ClaimDetail = lazy(() => import('./pages/ClaimDetail'));
const NewClaim = lazy(() => import('./pages/NewClaim'));
const AgentDecisions = lazy(() => import('./pages/AgentDecisions'));
const Compliance = lazy(() => import('./pages/Compliance'));
const UnderwriterWorkbench = lazy(() => import('./pages/UnderwriterWorkbench'));
const ClaimsWorkbench = lazy(() => import('./pages/ClaimsWorkbench'));
const ComplianceWorkbench = lazy(() => import('./pages/ComplianceWorkbench'));
const ExecutiveDashboard = lazy(() => import('./pages/ExecutiveDashboard'));
const BrokerPortal = lazy(() => import('./pages/BrokerPortal'));
const ReinsuranceDashboard = lazy(() => import('./pages/ReinsuranceDashboard'));
const ActuarialWorkbench = lazy(() => import('./pages/ActuarialWorkbench'));
const Escalations = lazy(() => import('./pages/Escalations'));
const FinanceDashboard = lazy(() => import('./pages/FinanceDashboard'));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'));
const UWAnalytics = lazy(() => import('./pages/UWAnalytics'));
const ClaimsAnalytics = lazy(() => import('./pages/ClaimsAnalytics'));
const ProductManagement = lazy(() => import('./pages/ProductManagement'));

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
        <p className="text-sm text-slate-400">Loading…</p>
      </div>
    </div>
  );
}

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
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route element={<Layout />}>
        <Route index element={<RouteGuard path=""><Dashboard /></RouteGuard>} />
        <Route path="submissions" element={<RouteGuard path="submissions"><Submissions /></RouteGuard>} />
        <Route path="submissions/new" element={<SubRouteGuard parentPath="/submissions"><NewSubmission /></SubRouteGuard>} />
        <Route path="submissions/:id" element={<SubRouteGuard parentPath="/submissions"><SubmissionDetail /></SubRouteGuard>} />
        <Route path="policies" element={<RouteGuard path="policies"><Policies /></RouteGuard>} />
        <Route path="policies/new" element={<SubRouteGuard parentPath="/policies"><NewPolicy /></SubRouteGuard>} />
        <Route path="policies/:id" element={<SubRouteGuard parentPath="/policies"><PolicyDetail /></SubRouteGuard>} />
        <Route path="claims" element={<RouteGuard path="claims"><Claims /></RouteGuard>} />
        <Route path="claims/:id" element={<SubRouteGuard parentPath="/claims"><ClaimDetail /></SubRouteGuard>} />
        <Route path="claims/new" element={<SubRouteGuard parentPath="/claims"><NewClaim /></SubRouteGuard>} />
        <Route path="decisions" element={<RouteGuard path="decisions"><AgentDecisions /></RouteGuard>} />
        <Route path="escalations" element={<RouteGuard path="escalations"><Escalations /></RouteGuard>} />
        <Route path="finance" element={<RouteGuard path="finance"><FinanceDashboard /></RouteGuard>} />
        <Route path="compliance" element={<RouteGuard path="compliance"><Compliance /></RouteGuard>} />
        <Route path="workbench/underwriting" element={<RouteGuard path="workbench/underwriting"><UnderwriterWorkbench /></RouteGuard>} />
        <Route path="workbench/claims" element={<RouteGuard path="workbench/claims"><ClaimsWorkbench /></RouteGuard>} />
        <Route path="workbench/compliance" element={<RouteGuard path="workbench/compliance"><ComplianceWorkbench /></RouteGuard>} />
        <Route path="workbench/reinsurance" element={<RouteGuard path="workbench/reinsurance"><ReinsuranceDashboard /></RouteGuard>} />
        <Route path="workbench/actuarial" element={<RouteGuard path="workbench/actuarial"><ActuarialWorkbench /></RouteGuard>} />
        <Route path="executive" element={<RouteGuard path="executive"><ExecutiveDashboard /></RouteGuard>} />
        <Route path="knowledge" element={<RouteGuard path="knowledge"><KnowledgePage /></RouteGuard>} />
        <Route path="analytics/underwriting" element={<RouteGuard path="analytics/underwriting"><UWAnalytics /></RouteGuard>} />
        <Route path="analytics/claims" element={<RouteGuard path="analytics/claims"><ClaimsAnalytics /></RouteGuard>} />
        <Route path="products" element={<RouteGuard path="products"><ProductManagement /></RouteGuard>} />
        <Route path="portal/broker" element={<RouteGuard path="portal/broker"><BrokerPortal /></RouteGuard>} />
        <Route path="*" element={<DefaultRedirect />} />
      </Route>
    </Routes>
    </Suspense>
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
    <MockProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <AuthGate />
        </AuthProvider>
      </QueryClientProvider>
    </MockProvider>
  );
}

export default App;
