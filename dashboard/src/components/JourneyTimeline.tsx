import React from 'react';
import { CheckCircle } from 'lucide-react';

export interface JourneyStep {
  key: string;
  label: string;
  icon: React.ElementType;
  timestamp?: string;
}

interface Props {
  steps: JourneyStep[];
  currentStepIndex: number;
  isTerminal?: boolean;
  terminalLabel?: string;
}

/**
 * Horizontal journey timeline with timestamps and animated progress.
 * Used for submission pipeline, claim pipeline, etc.
 */
const JourneyTimeline: React.FC<Props> = ({
  steps,
  currentStepIndex,
  isTerminal = false,
  terminalLabel,
}) => (
  <div className="space-y-2">
    {/* Progress bar */}
    <div className="relative flex items-center">
      {steps.map((step, i) => {
        const Icon = step.icon;
        const isDone = !isTerminal && currentStepIndex > i;
        const isActive = !isTerminal && currentStepIndex === i;

        return (
          <React.Fragment key={step.key}>
            <div className="flex flex-col items-center gap-2 min-w-[72px]">
              {/* Node */}
              <div
                className={`relative flex h-11 w-11 items-center justify-center rounded-full transition-all duration-500 ${
                  isDone
                    ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/25'
                    : isActive
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/30 ring-[3px] ring-indigo-100 scale-110'
                    : 'bg-slate-100 text-slate-400'
                }`}
              >
                {isDone ? <CheckCircle size={18} /> : <Icon size={18} />}
                {isActive && (
                  <span className="absolute -right-0.5 -top-0.5 flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-50" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-indigo-500" />
                  </span>
                )}
              </div>
              {/* Label */}
              <span
                className={`text-[11px] font-semibold whitespace-nowrap ${
                  isDone
                    ? 'text-emerald-600'
                    : isActive
                    ? 'text-indigo-700'
                    : 'text-slate-400'
                }`}
              >
                {step.label}
              </span>
              {/* Timestamp */}
              {step.timestamp && (
                <span className="text-[9px] text-slate-400 -mt-1">
                  {new Date(step.timestamp).toLocaleString(undefined, {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </span>
              )}
            </div>
            {/* Connector */}
            {i < steps.length - 1 && (
              <div className="relative mx-1 h-1 flex-1 rounded-full bg-slate-100 overflow-hidden">
                <div
                  className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ${
                    !isTerminal && currentStepIndex > i
                      ? 'bg-gradient-to-r from-emerald-400 to-emerald-500 w-full'
                      : !isTerminal && currentStepIndex === i
                      ? 'bg-gradient-to-r from-indigo-400 to-indigo-300 w-1/2'
                      : 'w-0'
                  }`}
                />
              </div>
            )}
          </React.Fragment>
        );
      })}
    </div>
    {/* Terminal state banner */}
    {isTerminal && terminalLabel && (
      <div className="flex items-center gap-2 rounded-lg bg-red-50 border border-red-100 px-3 py-2 mt-2">
        <div className="h-2 w-2 rounded-full bg-red-500" />
        <span className="text-xs font-medium text-red-700">{terminalLabel}</span>
      </div>
    )}
  </div>
);

export default JourneyTimeline;
