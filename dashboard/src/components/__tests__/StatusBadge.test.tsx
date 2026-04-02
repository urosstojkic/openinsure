import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StatusBadge from '../StatusBadge'

describe('StatusBadge', () => {
  it('renders label text', () => {
    render(<StatusBadge label="active" variant="green" />)
    expect(screen.getByText('Active')).toBeInTheDocument()
  })

  it('converts underscores to spaces and title-cases', () => {
    render(<StatusBadge label="under_review" variant="yellow" />)
    expect(screen.getByText('Under Review')).toBeInTheDocument()
  })

  it('renders with blue variant', () => {
    const { container } = render(<StatusBadge label="new" variant="blue" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('bg-blue-50')
  })

  it('renders with red variant', () => {
    const { container } = render(<StatusBadge label="declined" variant="red" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('bg-red-50')
  })

  it('renders with green variant', () => {
    const { container } = render(<StatusBadge label="bound" variant="green" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('bg-emerald-50')
  })

  it('shows dot by default', () => {
    const { container } = render(<StatusBadge label="test" variant="gray" />)
    const dot = container.querySelector('.rounded-full.bg-slate-400')
    expect(dot).toBeInTheDocument()
  })

  it('hides dot when showDot is false', () => {
    const { container } = render(<StatusBadge label="test" variant="gray" showDot={false} />)
    const dots = container.querySelectorAll('.h-1\\.5.w-1\\.5.rounded-full')
    expect(dots.length).toBe(0)
  })

  it('renders small size', () => {
    const { container } = render(<StatusBadge label="sm" variant="purple" size="sm" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('text-[10px]')
  })

  it('renders medium size by default', () => {
    const { container } = render(<StatusBadge label="md" variant="purple" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('text-xs')
  })

  it('applies additional className', () => {
    const { container } = render(<StatusBadge label="test" variant="cyan" className="ml-2" />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('ml-2')
  })

  it('falls back to gray for unknown variant', () => {
    const { container } = render(<StatusBadge label="test" variant={'unknown' as any} />)
    const badge = container.querySelector('span')
    expect(badge?.className).toContain('bg-slate-50')
  })
})
