import React, { useMemo } from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  RotateCcw,
  Clock,
  Zap,
  Activity,
  AlertTriangle,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

const SPEED_OPTIONS = [0.1, 0.5, 1, 2, 5, 10];

export const TimelineControlBar: React.FC = () => {
  const currentTime = useStudioStore((s) => s.currentTime);
  const duration = useStudioStore((s) => s.duration);
  const isPlaying = useStudioStore((s) => s.isPlaying);
  const playbackSpeed = useStudioStore((s) => s.playbackSpeed);
  const togglePlay = useStudioStore((s) => s.togglePlay);
  const seek = useStudioStore((s) => s.seek);
  const stepForward = useStudioStore((s) => s.stepForward);
  const stepBackward = useStudioStore((s) => s.stepBackward);
  const setPlaybackSpeed = useStudioStore((s) => s.setPlaybackSpeed);
  const telemetrySeries = useStudioStore((s) => s.telemetrySeries);
  const activeMode = useStudioStore((s) => s.activeMode);

  // Derive handover / anomaly timestamps for markers on the timeline
  const timelineMarkers = useMemo(() => {
    if (!telemetrySeries || !telemetrySeries.timestamps) return [];
    const markers: { time: number; type: 'handover' | 'outage'; label: string }[] = [];
    const ts = telemetrySeries.timestamps;
    const ho = telemetrySeries.handover_events || [];
    const qos = telemetrySeries.qos_score || [];

    for (let i = 0; i < ts.length; i++) {
      if (ho[i] !== null && ho[i]! > 0) {
        markers.push({ time: ts[i], type: 'handover', label: `VHO @ T+${ts[i]}s` });
      } else if (qos[i] !== null && qos[i]! < 0.2) {
        markers.push({ time: ts[i], type: 'outage', label: `QoS Drop @ T+${ts[i]}s` });
      }
    }
    return markers.slice(0, 30); // Cap to avoid clutter
  }, [telemetrySeries]);

  const minutes = Math.floor(currentTime / 60);
  const seconds = (currentTime % 60).toFixed(1);
  const durMinutes = Math.floor(duration / 60);
  const durSeconds = (duration % 60).toFixed(1);

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="h-12 bg-bg-panel border-t border-border-subtle px-4 flex items-center justify-between gap-4 select-none z-30 shrink-0">
      {/* Playback Transport Buttons */}
      <div className="flex items-center gap-1.5 shrink-0">
        <button
          onClick={() => seek(0)}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-bg-card rounded transition"
          title="Reset to T+00:00.0s"
        >
          <RotateCcw className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={() => stepBackward(0.5)}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-bg-card rounded transition"
          title="Step Backward -0.5s"
        >
          <SkipBack className="w-3.5 h-3.5" />
        </button>

        <button
          onClick={togglePlay}
          className={`px-3 py-1.5 rounded flex items-center gap-1.5 font-bold text-xs transition ${
            isPlaying
              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30'
              : 'bg-brand-cyan/20 text-brand-cyan border border-brand-cyan/40 hover:bg-brand-cyan/30'
          }`}
          title={isPlaying ? 'Pause' : 'Play'}
        >
          {isPlaying ? <Pause className="w-3.5 h-3.5 fill-current" /> : <Play className="w-3.5 h-3.5 fill-current" />}
          <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
        </button>

        <button
          onClick={() => stepForward(0.5)}
          className="p-1.5 text-slate-400 hover:text-slate-100 hover:bg-bg-card rounded transition"
          title="Step Forward +0.5s"
        >
          <SkipForward className="w-3.5 h-3.5" />
        </button>

        {/* Speed multiplier selector */}
        <div className="flex items-center bg-bg-card border border-border-subtle rounded ml-2 p-0.5 text-[10px] font-mono">
          {SPEED_OPTIONS.map((speed) => (
            <button
              key={speed}
              onClick={() => setPlaybackSpeed(speed)}
              className={`px-1.5 py-0.5 rounded transition ${
                playbackSpeed === speed
                  ? 'bg-brand-cyan text-slate-950 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {speed}x
            </button>
          ))}
        </div>
      </div>

      {/* Scrubbing Track & Timeline Slider */}
      <div className="flex-1 flex flex-col justify-center max-w-3xl relative">
        <div className="relative w-full h-5 flex items-center">
          {/* Background Track */}
          <div className="w-full h-1.5 bg-bg-card border border-border-subtle rounded-full overflow-hidden relative">
            <div
              className="h-full bg-gradient-to-r from-brand-blue via-brand-cyan to-emerald-400 transition-all duration-75"
              style={{ width: `${progressPercent}%` }}
            />
          </div>

          {/* Interactive Range Input overlay */}
          <input
            type="range"
            min={0}
            max={duration || 300}
            step={0.1}
            value={currentTime}
            onChange={(e) => seek(Number(e.target.value))}
            className="absolute inset-0 w-full opacity-0 cursor-pointer h-full z-10"
            aria-label="Simulation Time Slider"
          />

          {/* Event markers on timeline */}
          {timelineMarkers.map((marker, idx) => {
            const leftPct = duration > 0 ? (marker.time / duration) * 100 : 0;
            return (
              <div
                key={`m-${idx}`}
                className={`absolute top-0.5 w-1 h-2 -translate-x-1/2 pointer-events-none rounded-full ${
                  marker.type === 'handover' ? 'bg-amber-400' : 'bg-accent-red'
                }`}
                style={{ left: `${leftPct}%` }}
                title={marker.label}
              />
            );
          })}
        </div>
      </div>

      {/* High-Precision Clock Readout */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1.5 font-mono text-xs text-slate-300 bg-bg-card border border-border-subtle px-2.5 py-1 rounded tabular-nums">
          <Clock className="w-3.5 h-3.5 text-brand-cyan shrink-0" />
          <span className="text-brand-cyan font-bold">
            T+{String(minutes).padStart(2, '0')}:{String(seconds).padStart(4, '0')}s
          </span>
          <span className="text-slate-500">/</span>
          <span className="text-slate-400">
            T+{String(durMinutes).padStart(2, '0')}:{String(durSeconds).padStart(4, '0')}s
          </span>
        </div>

        {/* Live / Replay indicator badge */}
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded border border-border-subtle bg-bg-card text-[10px] font-mono">
          <div className={`w-1.5 h-1.5 rounded-full ${isPlaying ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
          <span className={isPlaying ? 'text-emerald-400 font-bold' : 'text-slate-400'}>
            {isPlaying ? 'RUNNING' : 'PAUSED'}
          </span>
        </div>
      </div>
    </div>
  );
};
