import React, { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
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
    <div className="rounded-lg border border-slate-200 bg-white">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50"
      >
        <div className="flex items-center gap-3">
          {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          <div>
            <span className="text-sm font-semibold text-slate-900">{agent}</span>
            <span className="ml-2 text-sm text-slate-500">— {decision}</span>
          </div>
        </div>
        <div className="w-32">
          <ConfidenceBar value={confidence} />
        </div>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 py-3">
          <p className="mb-2 text-xs text-slate-400">
            {new Date(timestamp).toLocaleString()}
          </p>
          <h4 className="mb-1 text-xs font-semibold uppercase text-slate-500">Reasoning Chain</h4>
          <ol className="list-inside list-decimal space-y-1">
            {reasoning.map((step, i) => (
              <li key={i} className="text-sm text-slate-700">{step}</li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

export default ReasoningPanel;
