import React, { useEffect, useRef } from 'react';
import { Terminal, Trash2 } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

export const LiveTerminal: React.FC = () => {
  // Zustand atomic selectors
  const logs = useStudioStore((s) => s.logs);
  const clearLogs = useStudioStore((s) => s.clearLogs);
  const wsConnected = useStudioStore((s) => s.wsConnected);

  const containerRef = useRef<HTMLDivElement>(null);
  const isNearBottomRef = useRef(true);

  // Monitor user scroll position to maintain "sticky auto-scroll"
  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const threshold = 40; // px threshold from the bottom
    isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold;
  };

  // Direct container scrollTop assignment only if user is already near bottom
  useEffect(() => {
    const el = containerRef.current;
    if (el && isNearBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="flex flex-col h-full bg-[#03060a] border-t border-border-subtle p-2.5 font-mono select-none overflow-hidden">
      {/* Console Top Toolbar */}
      <div className="flex items-center justify-between pb-2 border-b border-border-subtle mb-2">
        <div className="flex items-center gap-2">
          <Terminal size={13} className="text-brand-cyan" />
          <span className="text-[11px] font-bold text-slate-300">NexaSim Console Stream</span>
          <span className="flex items-center gap-1 text-[10px] text-slate-500 ml-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                wsConnected ? 'bg-accent-green shadow-sm shadow-emerald-500' : 'bg-slate-600'
              }`}
            />
            {wsConnected ? 'Stream Active' : 'Offline'}
          </span>
        </div>
        <button
          onClick={clearLogs}
          className="flex items-center gap-1 px-2 py-0.5 bg-bg-card hover:bg-bg-card-hover border border-border-subtle rounded text-[10px] text-slate-400 hover:text-slate-200 transition"
          title="Clear Terminal Output"
        >
          <Trash2 size={11} /> Clear
        </button>
      </div>

      {/* Terminal Text Body with direct container scroll handling */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto text-xs text-sky-400 font-mono whitespace-pre-wrap leading-relaxed select-text pr-1"
      >
        {logs.map((line, i) => (
          <div key={i} className="py-0.5 hover:bg-white/[0.02]">
            {line}
          </div>
        ))}
      </div>
    </div>
  );
};
