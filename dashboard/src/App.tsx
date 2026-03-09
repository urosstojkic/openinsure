import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1 },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="submissions" element={<Submissions />} />
            <Route path="submissions/new" element={<NewSubmission />} />
            <Route path="submissions/:id" element={<SubmissionDetail />} />
            <Route path="policies" element={<Policies />} />
            <Route path="policies/new" element={<NewPolicy />} />
            <Route path="claims" element={<Claims />} />
            <Route path="claims/new" element={<NewClaim />} />
            <Route path="decisions" element={<AgentDecisions />} />
            <Route path="compliance" element={<Compliance />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
