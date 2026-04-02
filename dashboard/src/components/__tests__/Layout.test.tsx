import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock contexts and API
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    user: {
      id: 'u-cuo',
      name: 'Sarah Chen',
      email: 's.chen@openinsure.io',
      role: 'cuo',
      displayRole: 'Chief Underwriting Officer',
      avatar: 'SC',
    },
    isAuthenticated: true,
    login: vi.fn(),
    logout: vi.fn(),
    hasAccess: vi.fn(() => true),
  })),
  NAV_ACCESS: {
    '/': ['cuo', 'ceo'],
    '/submissions': ['cuo'],
    '/policies': ['cuo'],
    '/claims': ['cuo'],
    '/decisions': ['cuo'],
    '/escalations': ['cuo'],
    '/compliance': ['cuo'],
    '/finance': ['cfo'],
    '/knowledge': ['cuo'],
    '/products': ['cuo'],
    '/analytics/underwriting': ['cuo'],
    '/analytics/claims': ['cuo'],
    '/workbench/underwriting': ['cuo'],
    '/workbench/claims': ['claims_manager'],
    '/workbench/compliance': ['compliance'],
    '/workbench/reinsurance': ['cuo'],
    '/workbench/actuarial': ['cuo'],
    '/executive': ['ceo', 'cuo'],
    '/portal/broker': ['broker'],
  },
}))

vi.mock('../../context/MockContext', () => ({
  useMockMode: vi.fn(() => ({ useMock: false, toggleMock: vi.fn() })),
}))

vi.mock('../../api/escalations', () => ({
  getEscalationCount: vi.fn(() => Promise.resolve(3)),
}))

// Dynamically import Layout after mocks are set up
import Layout from '../Layout'
import { useAuth } from '../../context/AuthContext'

function renderLayout(initialRoute = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Layout />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset useAuth mock to cuo role
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'u-cuo',
        name: 'Sarah Chen',
        email: 's.chen@openinsure.io',
        role: 'cuo' as const,
        displayRole: 'Chief Underwriting Officer',
        avatar: 'SC',
      },
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      hasAccess: vi.fn(() => true),
    })
  })

  it('renders sidebar navigation', () => {
    renderLayout()
    const dashboards = screen.getAllByText('Dashboard')
    expect(dashboards.length).toBeGreaterThanOrEqual(1)
  })

  it('renders submissions nav item for cuo role', () => {
    renderLayout()
    const items = screen.getAllByText('Submissions')
    expect(items.length).toBeGreaterThanOrEqual(1)
  })

  it('renders policies nav item', () => {
    renderLayout()
    const items = screen.getAllByText('Policies')
    expect(items.length).toBeGreaterThanOrEqual(1)
  })

  it('renders claims nav item', () => {
    renderLayout()
    const items = screen.getAllByText('Claims')
    expect(items.length).toBeGreaterThanOrEqual(1)
  })

  it('shows user name', () => {
    renderLayout()
    // The user name may appear in multiple places (sidebar + dropdown)
    const names = screen.getAllByText('Sarah Chen')
    expect(names.length).toBeGreaterThanOrEqual(1)
  })

  it('renders OpenInsure branding', () => {
    renderLayout()
    const brands = screen.getAllByText('OpenInsure')
    expect(brands.length).toBeGreaterThanOrEqual(1)
  })

  it('redirects broker to portal', () => {
    vi.mocked(useAuth).mockReturnValue({
      user: {
        id: 'u-brk',
        name: 'Thomas Anderson',
        email: 't.anderson@broker.com',
        role: 'broker' as const,
        displayRole: 'Broker — Marsh & Co',
        avatar: 'TA',
      },
      isAuthenticated: true,
      login: vi.fn(),
      logout: vi.fn(),
      hasAccess: vi.fn(() => false),
    })
    // Broker on internal route should redirect
    renderLayout('/submissions')
    // Broker layout shows a simplified top-nav, not the full sidebar
    // Verify the full sidebar nav section is not rendered
    const nav = screen.queryByLabelText('Main navigation')
    expect(nav).not.toBeInTheDocument()
  })
})
