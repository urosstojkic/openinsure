import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import DataTable, { type Column } from '../DataTable'

interface TestRow {
  id: string
  name: string
  value: number
}

const columns: Column<TestRow>[] = [
  { key: 'name', header: 'Name', render: (r) => r.name },
  { key: 'value', header: 'Value', render: (r) => r.value, sortable: true, sortValue: (r) => r.value },
]

const sampleData: TestRow[] = [
  { id: '1', name: 'Alpha', value: 30 },
  { id: '2', name: 'Beta', value: 10 },
  { id: '3', name: 'Gamma', value: 20 },
]

describe('DataTable', () => {
  it('renders column headers', () => {
    render(<DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Name')).toBeInTheDocument()
    expect(screen.getByText('Value')).toBeInTheDocument()
  })

  it('renders all data rows', () => {
    render(<DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('Beta')).toBeInTheDocument()
    expect(screen.getByText('Gamma')).toBeInTheDocument()
  })

  it('shows empty state when no data', () => {
    render(<DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('No data available')).toBeInTheDocument()
  })

  it('shows custom empty message', () => {
    render(<DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} emptyMessage="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
  })

  it('shows loading skeleton', () => {
    const { container } = render(<DataTable columns={columns} data={[]} keyExtractor={(r) => r.id} isLoading={true} />)
    // Loading state should not show the empty message
    expect(screen.queryByText('No data available')).not.toBeInTheDocument()
    // Should render skeleton table with skeleton elements
    const skeletonElements = container.querySelectorAll('.skeleton-text, .skeleton')
    expect(skeletonElements.length).toBeGreaterThan(0)
  })

  it('calls onRowClick when row is clicked', () => {
    const onClick = vi.fn()
    render(<DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} onRowClick={onClick} />)
    fireEvent.click(screen.getByText('Alpha'))
    expect(onClick).toHaveBeenCalledWith(sampleData[0])
  })

  it('sorts data ascending on column header click', () => {
    render(<DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />)
    fireEvent.click(screen.getByText('Value'))
    const rows = screen.getAllByRole('row')
    // Header row + 3 data rows; first data row should be Beta (10)
    const firstDataRow = rows[1]
    expect(firstDataRow).toHaveTextContent('Beta')
  })

  it('toggles sort direction on second click', () => {
    render(<DataTable columns={columns} data={sampleData} keyExtractor={(r) => r.id} />)
    const header = screen.getByText('Value')
    fireEvent.click(header) // asc
    fireEvent.click(header) // desc
    const rows = screen.getAllByRole('row')
    const firstDataRow = rows[1]
    expect(firstDataRow).toHaveTextContent('Alpha') // 30 is highest
  })

  it('renders expanded row content', () => {
    render(
      <DataTable
        columns={columns}
        data={sampleData}
        keyExtractor={(r) => r.id}
        expandedRowKey="1"
        expandedRowRender={(r) => <div>Expanded: {r.name}</div>}
      />
    )
    expect(screen.getByText('Expanded: Alpha')).toBeInTheDocument()
  })

  it('does not render expanded content for non-expanded rows', () => {
    render(
      <DataTable
        columns={columns}
        data={sampleData}
        keyExtractor={(r) => r.id}
        expandedRowKey="1"
        expandedRowRender={(r) => <div>Expanded: {r.name}</div>}
      />
    )
    expect(screen.queryByText('Expanded: Beta')).not.toBeInTheDocument()
  })

  it('handles single row data', () => {
    render(<DataTable columns={columns} data={[sampleData[0]]} keyExtractor={(r) => r.id} />)
    expect(screen.getByText('Alpha')).toBeInTheDocument()
  })
})
