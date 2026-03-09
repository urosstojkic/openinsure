import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import Submissions from './pages/Submissions';
import SubmissionDetail from './pages/SubmissionDetail';
import Policies from './pages/Policies';
import Claims from './pages/Claims';
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
            <Route path="submissions/:id" element={<SubmissionDetail />} />
            <Route path="policies" element={<Policies />} />
            <Route path="claims" element={<Claims />} />
            <Route path="decisions" element={<AgentDecisions />} />
            <Route path="compliance" element={<Compliance />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
