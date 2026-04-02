import React, { useState, useMemo, useCallback, useRef } from 'react';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';
import { TableSkeleton } from './Skeleton';

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  render: (row: T) => React.ReactNode;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  align?: 'left' | 'center' | 'right';
  className?: string;
}

interface Props<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  keyExtractor: (row: T) => string;
  emptyMessage?: string;
  isLoading?: boolean;
  expandedRowKey?: string | null;
  expandedRowRender?: (row: T) => React.ReactNode;
}

function DataTable<T>({ columns, data, onRowClick, keyExtractor, emptyMessage = 'No data available', isLoading, expandedRowKey, expandedRowRender }: Props<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const tbodyRef = useRef<HTMLTableSectionElement>(null);

  const sorted = useMemo(() => {
    if (!sortKey) return data;
    const col = columns.find((c) => c.key === sortKey);
    if (!col?.sortValue) return data;
    const fn = col.sortValue;
    return [...data].sort((a, b) => {
      const va = fn(a);
      const vb = fn(b);
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortKey, sortDir, columns]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  // Keyboard navigation (#277)
  const handleRowKeyDown = useCallback((e: React.KeyboardEvent<HTMLTableRowElement>, row: T, rowIndex: number) => {
    const rows = tbodyRef.current?.querySelectorAll<HTMLTableRowElement>('tr[tabindex]');
    if (!rows) return;
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (onRowClick) onRowClick(row);
        break;
      case 'ArrowDown': {
        e.preventDefault();
        const next = Math.min(rowIndex + 1, rows.length - 1);
        rows[next]?.focus();
        break;
      }
      case 'ArrowUp': {
        e.preventDefault();
        const prev = Math.max(rowIndex - 1, 0);
        rows[prev]?.focus();
        break;
      }
      case 'Home':
        e.preventDefault();
        rows[0]?.focus();
        break;
      case 'End':
        e.preventDefault();
        rows[rows.length - 1]?.focus();
        break;
    }
  }, [onRowClick]);

  if (isLoading) {
    return <TableSkeleton rows={5} columns={columns.length || 6} />;
  }

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200/60 bg-white p-12 text-center" role="status">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-50 ring-1 ring-slate-200/60 text-slate-400">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
        </div>
        <p className="text-sm font-semibold text-slate-700">{emptyMessage}</p>
        <p className="mt-1.5 text-xs text-slate-400">Try adjusting your filters or search criteria, or create a new record to get started.</p>
      </div>
    );
  }

  const alignClass = (align?: string) =>
    align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)]">
      <table className="min-w-full">
        <thead>
          <tr className="border-b border-slate-100">
            {columns.map((col) => (
              <th
                key={col.key}
                className={`sticky top-0 z-10 bg-slate-50/80 backdrop-blur-sm px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-400 ${alignClass(col.align)} ${
                  col.sortable ? 'cursor-pointer select-none transition-colors hover:text-slate-600' : ''
                } ${col.className ?? ''}`}
                onClick={col.sortable ? () => handleSort(col.key) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && (
                    sortKey === col.key
                      ? (sortDir === 'asc' ? <ChevronUp size={12} className="text-indigo-500" /> : <ChevronDown size={12} className="text-indigo-500" />)
                      : <ChevronsUpDown size={12} className="text-slate-300" />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody ref={tbodyRef} className="divide-y divide-slate-100/80">
          {sorted.map((row, rowIndex) => {
            const rowKey = keyExtractor(row);
            const isExpanded = expandedRowKey === rowKey;
            return (
              <React.Fragment key={rowKey}>
                <tr
                  tabIndex={0}
                  role="row"
                  aria-rowindex={rowIndex + 2}
                  className={`transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-400 ${
                    isExpanded ? 'bg-indigo-50/50' : rowIndex % 2 === 0 ? '' : 'bg-slate-50/40'
                  } ${
                    onRowClick
                      ? 'cursor-pointer hover:bg-indigo-50/40 active:bg-indigo-50/60'
                      : 'hover:bg-slate-50/60'
                  }`}
                  onClick={onRowClick ? () => onRowClick(row) : undefined}
                  onKeyDown={(e) => handleRowKeyDown(e, row, rowIndex)}
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className={`whitespace-nowrap px-4 py-3 text-sm text-slate-600 ${alignClass(col.align)} ${col.className ?? ''}`}
                    >
                      {col.render(row)}
                    </td>
                  ))}
                </tr>
                {isExpanded && expandedRowRender && (
                  <tr>
                    <td colSpan={columns.length} className="p-0">
                      {expandedRowRender(row)}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
