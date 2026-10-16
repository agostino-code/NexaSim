import React, { useState } from 'react';
import { LegendEntry } from '../../theme/palette';

interface LegendProps {
  entries: LegendEntry[];
  title?: string;
  className?: string;
  /** Render a collapse toggle (default true) */
  collapsible?: boolean;
  defaultOpen?: boolean;
}

const LegendSwatch: React.FC<{ entry: LegendEntry }> = ({ entry }) => {
  const { color, kind = 'dot' } = entry;
  if (kind === 'line' || kind === 'dashed') {
    return (
      <span
        className="inline-block w-4 h-0 shrink-0"
        style={{
          borderTopWidth: 2,
          borderTopStyle: kind === 'dashed' ? 'dashed' : 'solid',
          borderTopColor: color,
        }}
      />
    );
  }
  if (kind === 'square') {
    return (
      <span
        className="inline-block w-2.5 h-2.5 rounded-[2px] border shrink-0"
        style={{ borderColor: color, background: `${color}44` }}
      />
    );
  }
  if (kind === 'ring') {
    return (
      <span
        className="inline-block w-2.5 h-2.5 rounded-full border-2 bg-transparent shrink-0"
        style={{ borderColor: color }}
      />
    );
  }
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
      style={{ background: color, boxShadow: `0 0 5px ${color}88` }}
    />
  );
};

/**
 * Reusable legend card. Uses the shared semantic palette so the 2D map,
 * the globe HUD and the Studio panels always agree on colours.
 */
export const Legend: React.FC<LegendProps> = ({
  entries,
  title = 'Legend',
  className = '',
  collapsible = true,
  defaultOpen = true,
}) => {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={`bg-bg-panel/95 border border-border-medium rounded shadow-lg backdrop-blur text-[10px] text-slate-300 ${className}`}
    >
      <button
        type="button"
        onClick={() => collapsible && setOpen((v) => !v)}
        className={`w-full flex items-center justify-between px-2 py-1 font-mono font-bold text-slate-400 uppercase tracking-wider ${
          collapsible ? 'cursor-pointer hover:text-slate-200' : 'cursor-default'
        }`}
        title={collapsible ? 'Collapse / expand legend' : title}
      >
        <span>{title}</span>
        {collapsible && <span className="text-slate-500">{open ? '▾' : '▸'}</span>}
      </button>
      {open && (
        <div className="px-2 pb-1.5 grid grid-cols-1 gap-y-[3px]">
          {entries.map((entry, i) => (
            <div key={i} className="flex items-center gap-1.5 whitespace-nowrap">
              <LegendSwatch entry={entry} />
              <span className="text-slate-300">{entry.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
