import React from 'react';

export interface BarSegment {
  label: string;
  value: number;
  color: string;
  /** Text color for the legend item */
  textColor?: string;
}

interface Props {
  segments: BarSegment[];
  height?: number;
  formatter?: (v: number) => string;
  showLegend?: boolean;
}

const defaultFormatter = (v: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(v);

/**
 * Horizontal stacked bar with legend — for reserve vs paid, premium breakdown, etc.
 */
const StackedBar: React.FC<Props> = ({
  segments,
  height = 28,
  formatter = defaultFormatter,
  showLegend = true,
}) => {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  if (total === 0) return null;

  return (
    <div className="space-y-3">
      {/* Bar */}
      <div
        className="flex w-full overflow-hidden rounded-full"
        style={{ height }}
      >
        {segments.map((seg, i) => {
          const pct = (seg.value / total) * 100;
          if (pct <= 0) return null;
          return (
            <div
              key={i}
              className="relative group transition-all duration-500"
              style={{
                width: `${pct}%`,
                backgroundColor: seg.color,
              }}
            >
              {/* Tooltip on hover */}
              <div className="absolute -top-10 left-1/2 -translate-x-1/2 hidden group-hover:flex items-center rounded-lg bg-slate-900 px-2.5 py-1 text-[10px] font-medium text-white shadow-lg whitespace-nowrap z-10">
                {seg.label}: {formatter(seg.value)} ({pct.toFixed(0)}%)
              </div>
            </div>
          );
        })}
      </div>
      {/* Legend */}
      {showLegend && (
        <div className="flex flex-wrap gap-4">
          {segments.map((seg, i) => (
            <div key={i} className="flex items-center gap-2">
              <div
                className="h-3 w-3 rounded-sm"
                style={{ backgroundColor: seg.color }}
              />
              <span className="text-xs text-slate-600">{seg.label}</span>
              <span
                className="text-xs font-semibold"
                style={{ color: seg.textColor || seg.color }}
              >
                {formatter(seg.value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default StackedBar;
