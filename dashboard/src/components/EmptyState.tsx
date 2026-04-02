import React from 'react';
import { Link } from 'react-router-dom';

interface EmptyStateProps {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description?: string;
  action?: { label: string; href: string };
  secondaryAction?: { label: string; href: string };
  tips?: string[];
}

export default function EmptyState({ icon: Icon, title, description, action, secondaryAction, tips }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      {/* Decorative illustration */}
      <div className="relative mb-6">
        <div className="absolute -inset-4 rounded-full bg-gradient-to-br from-indigo-50 via-slate-50 to-purple-50 opacity-60 blur-xl" />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-slate-100 to-slate-50 ring-1 ring-slate-200/60 shadow-sm">
          <Icon size={32} className="text-slate-400" />
        </div>
        {/* Floating dots decoration */}
        <div className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-indigo-200 opacity-60" />
        <div className="absolute -bottom-2 -left-2 h-2 w-2 rounded-full bg-purple-200 opacity-50" />
      </div>
      <h3 className="text-lg font-semibold text-slate-800">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-500">{description}</p>
      )}
      {tips && tips.length > 0 && (
        <div className="mt-[var(--spacing-md)] max-w-sm rounded-[var(--radius-default)] bg-indigo-50/50 border border-indigo-100 p-[var(--spacing-md)] text-left">
          <p className="text-xs font-semibold text-indigo-600 mb-2">💡 Getting Started</p>
          <ul className="space-y-1.5">
            {tips.map((tip, i) => (
              <li key={i} className="flex items-start gap-2 text-xs text-indigo-700/80">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-indigo-200/60 text-[10px] font-bold text-indigo-600">{i + 1}</span>
                {tip}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="mt-6 flex items-center gap-3">
        {action && (
          <Link
            to={action.href}
            className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2.5 text-sm font-medium text-white shadow-sm shadow-indigo-500/20 transition-all hover:bg-indigo-700 hover:shadow-md hover:shadow-indigo-500/25 active:scale-[0.98]"
          >
            {action.label}
          </Link>
        )}
        {secondaryAction && (
          <Link
            to={secondaryAction.href}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 px-5 py-2.5 text-sm font-medium text-slate-600 transition-all hover:bg-slate-50 hover:border-slate-300"
          >
            {secondaryAction.label}
          </Link>
        )}
      </div>
    </div>
  );
}
