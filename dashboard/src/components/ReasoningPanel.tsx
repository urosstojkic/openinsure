import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Brain } from 'lucide-react';
import ConfidenceBar from './ConfidenceBar';

interface Props {
  agent: string;
  decision: string;
  confidence: number;
  reasoning: string[];
  timestamp: string;
  defaultOpen?: boolean;
}

const ReasoningPanel: React.FC<Props> = ({
  agent,
  decision,
  confidence,
  reasoning,
  timestamp,
  defaultOpen = false,
}) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-xl border border-slate-200/60 bg-white shadow-[var(--shadow-xs)] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-slate-50/80"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-50 to-indigo-100/60 text-indigo-600">
            <Brain size={14} />
          </div>
          {open ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronRight size={14} className="text-slate-400" />}
          <div>
            <span className="text-sm font-semibold text-slate-800">{agent}</span>
            <span className="ml-2 text-sm text-slate-500">— {decision}</span>
          </div>
        </div>
        <div className="w-32">
          <ConfidenceBar value={confidence} />
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-100 bg-slate-50/30 px-4 py-4">
          <p className="mb-3 text-[11px] font-medium uppercase tracking-wider text-slate-400">
            {timestamp && !isNaN(new Date(timestamp).getTime())
              ? new Date(timestamp).toLocaleString()
              : '—'}
          </p>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Reasoning Chain</h4>
          <ol className="space-y-1.5">
            {reasoning.map((step, i) => (
              <li key={i} className="flex gap-2.5 text-sm leading-relaxed text-slate-600">
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-[10px] font-bold text-indigo-600">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

export default ReasoningPanel;
