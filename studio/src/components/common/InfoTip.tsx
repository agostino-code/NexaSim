import React from 'react';
import { HelpCircle } from 'lucide-react';

interface InfoTipProps {
  /** Plain-language explanation shown on hover / focus. */
  text: string;
  className?: string;
}

/** Small "?" affordance carrying a plain-language definition of a metric. */
export const InfoTip: React.FC<InfoTipProps> = ({ text, className = '' }) => (
  <span
    className={`inline-flex items-center text-slate-500 hover:text-brand-cyan cursor-help align-middle ${className}`}
    title={text}
    aria-label={text}
  >
    <HelpCircle size={11} />
  </span>
);
