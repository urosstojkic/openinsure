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
  <div className="relative flex gap-4 pb-6">
    {/* Vertical line */}
    {!isLast && (
      <div className="absolute left-[17px] top-9 bottom-0 w-px bg-slate-200" />
    )}

    {/* Icon */}
    <div
      className={`relative z-10 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
        isAgent ? 'bg-blue-100 text-blue-600' : 'bg-slate-100 text-slate-600'
      }`}
    >
      {isAgent ? <Bot size={16} /> : <User size={16} />}
    </div>

    {/* Content */}
    <div className="min-w-0 flex-1">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-medium text-slate-900">{actor}</span>
        <span className="text-xs text-slate-400">
          {new Date(timestamp).toLocaleString()}
        </span>
      </div>
      <p className="text-sm font-medium text-slate-700">{action}</p>
      <p className="text-sm text-slate-500">{details}</p>
    </div>
  </div>
);

export default TimelineEvent;
