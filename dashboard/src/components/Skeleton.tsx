import React from 'react';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circle' | 'rect';
  width?: string | number;
  height?: string | number;
  count?: number;
}

const Skeleton: React.FC<SkeletonProps> = ({
  className = '',
  variant = 'rect',
  width,
  height,
  count = 1,
}) => {
  const baseClass =
    variant === 'circle' ? 'skeleton-circle' :
    variant === 'text' ? 'skeleton-text' :
    'skeleton';

  const style: React.CSSProperties = {
    width: width ?? (variant === 'text' ? '100%' : undefined),
    height: height ?? (variant === 'text' ? '0.875rem' : undefined),
  };

  if (count > 1) {
    return (
      <div className="space-y-2">
        {Array.from({ length: count }).map((_, i) => (
          <div
            key={i}
            className={`${baseClass} ${className}`}
            style={{ ...style, width: i === count - 1 ? '60%' : style.width }}
          />
        ))}
      </div>
    );
  }

  return <div className={`${baseClass} ${className}`} style={style} />;
};

/* Pre-built skeleton layouts */

export const StatCardSkeleton: React.FC = () => (
  <div className="rounded-2xl border border-slate-100 bg-white p-5">
    <div className="flex items-start justify-between">
      <div className="flex-1">
        <Skeleton variant="text" width="60%" height={12} />
        <div className="mt-3">
          <Skeleton variant="rect" width={100} height={28} />
        </div>
        <div className="mt-2">
          <Skeleton variant="text" width="40%" height={10} />
        </div>
      </div>
      <Skeleton variant="rect" width={42} height={42} className="rounded-xl" />
    </div>
  </div>
);

export const TableRowSkeleton: React.FC<{ columns?: number }> = ({ columns = 6 }) => (
  <tr>
    {Array.from({ length: columns }).map((_, i) => (
      <td key={i} className="px-4 py-3.5">
        <Skeleton
          variant="text"
          width={i === 0 ? '70%' : i === columns - 1 ? '50%' : '80%'}
          height={14}
        />
      </td>
    ))}
  </tr>
);

export const TableSkeleton: React.FC<{ rows?: number; columns?: number }> = ({ rows = 5, columns = 6 }) => (
  <div className="overflow-hidden rounded-xl border border-slate-200/60 bg-white">
    <table className="min-w-full">
      <thead>
        <tr className="border-b border-slate-100 bg-slate-50/50">
          {Array.from({ length: columns }).map((_, i) => (
            <th key={i} className="px-4 py-3">
              <Skeleton variant="text" width="60%" height={10} />
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-50">
        {Array.from({ length: rows }).map((_, i) => (
          <TableRowSkeleton key={i} columns={columns} />
        ))}
      </tbody>
    </table>
  </div>
);

export const ChartSkeleton: React.FC<{ height?: number }> = ({ height = 220 }) => (
  <div className="rounded-xl border border-slate-200/60 bg-white p-5">
    <Skeleton variant="text" width="40%" height={14} />
    <div className="mt-4">
      <Skeleton variant="rect" width="100%" height={height} className="rounded-lg" />
    </div>
  </div>
);

export default Skeleton;
