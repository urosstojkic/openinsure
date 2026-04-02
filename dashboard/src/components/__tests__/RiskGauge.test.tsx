import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import RiskGauge from '../RiskGauge'

describe('RiskGauge', () => {
  it('renders with default props', () => {
    const { container } = render(<RiskGauge value={50} />)
    expect(container.querySelector('svg')).toBeInTheDocument()
    expect(screen.getByText('50')).toBeInTheDocument()
  })

  it('renders display value override', () => {
    render(<RiskGauge value={75} displayValue="7.5" />)
    expect(screen.getByText('7.5')).toBeInTheDocument()
  })

  it('renders label below value', () => {
    render(<RiskGauge value={30} label="Risk Score" />)
    expect(screen.getByText('Risk Score')).toBeInTheDocument()
  })

  it('applies green color for low values', () => {
    const { container } = render(<RiskGauge value={20} />)
    const circle = container.querySelectorAll('circle')[1]
    expect(circle?.getAttribute('stroke')).toBe('#10b981')
  })

  it('applies yellow color for medium values', () => {
    const { container } = render(<RiskGauge value={55} />)
    const circle = container.querySelectorAll('circle')[1]
    expect(circle?.getAttribute('stroke')).toBe('#f59e0b')
  })

  it('applies red color for high values', () => {
    const { container } = render(<RiskGauge value={85} />)
    const circle = container.querySelectorAll('circle')[1]
    expect(circle?.getAttribute('stroke')).toBe('#ef4444')
  })

  it('clamps value at 0', () => {
    render(<RiskGauge value={-10} />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('clamps value at 100', () => {
    render(<RiskGauge value={150} />)
    expect(screen.getByText('100')).toBeInTheDocument()
  })

  it('handles custom thresholds', () => {
    const { container } = render(<RiskGauge value={30} thresholds={[20, 50]} />)
    // 30 is above first threshold (20) but below second (50) → yellow
    const circle = container.querySelectorAll('circle')[1]
    expect(circle?.getAttribute('stroke')).toBe('#f59e0b')
  })

  it('renders with custom size', () => {
    const { container } = render(<RiskGauge value={50} size={200} />)
    const svg = container.querySelector('svg')
    expect(svg?.getAttribute('width')).toBe('200')
    expect(svg?.getAttribute('height')).toBe('200')
  })

  it('renders exact boundary values correctly', () => {
    // At threshold[0] = 40, should be yellow
    const { container: c1 } = render(<RiskGauge value={40} />)
    const circle1 = c1.querySelectorAll('circle')[1]
    expect(circle1?.getAttribute('stroke')).toBe('#f59e0b')

    // At threshold[1] = 70, should be red
    const { container: c2 } = render(<RiskGauge value={70} />)
    const circle2 = c2.querySelectorAll('circle')[1]
    expect(circle2?.getAttribute('stroke')).toBe('#ef4444')
  })

  it('renders zero value', () => {
    render(<RiskGauge value={0} />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })
})
