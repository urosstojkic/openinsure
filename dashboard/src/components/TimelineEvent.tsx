import React from 'react';
import { Bot, User } from 'lucide-react';

interface Props {
  timestamp: string;
  actor: string;
  action: string;
  details: string;
  isAgent: boolean;
  isLast?: boolean;
}

const TimelineEvent: React.FC<Props> = ({ timestamp, actor, action, details, isAgent, isLast }) => (
  <div className="relative flex gap-4 pb-6 group">
    {/* Vertical connector line */}
    {!isLast && (
      <div className="absolute left-[17px] top-9 bottom-0 w-px bg-gradient-to-b from-slate-200 to-slate-100" />
    )}

    {/* Icon node */}
    <div
      className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ring-4 ring-white transition-shadow ${
        isAgent
          ? 'bg-gradient-to-br from-indigo-500 to-indigo-600 text-white shadow-sm shadow-indigo-500/20'
          : 'bg-slate-100 text-slate-500'
      }`}
    >
      {isAgent ? <Bot size={14} /> : <User size={14} />}
    </div>

    {/* Content */}
    <div className="min-w-0 flex-1 pt-0.5">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-semibold text-slate-800">{actor}</span>
        <span className="text-[11px] text-slate-400">
          {new Date(timestamp).toLocaleString()}
        </span>
      </div>
      <p className="mt-0.5 text-sm font-medium text-slate-700">{action}</p>
      {details && (
        <p className="mt-0.5 text-sm leading-relaxed text-slate-500">{details}</p>
      )}
    </div>
  </div>
);

export default TimelineEvent;
