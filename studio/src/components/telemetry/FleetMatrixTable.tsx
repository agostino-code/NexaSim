import React, { useState, useMemo, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import {
  Search,
  Filter,
  Car,
  ShieldAlert,
  ArrowUpDown,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { VehicleTelemetry } from '../../types/scenario';
import { ratColor, ratLabel } from '../../theme/palette';

type SortKey = 'id' | 'name' | 'active_rat' | 'speed_kmh' | 'mec_latency_ms' | 'qos_score' | 'battery_soc_pct';

export const FleetMatrixTable: React.FC = () => {
  const vehicles = useStudioStore((s) => s.vehicles);
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const selectNode = useStudioStore((s) => s.selectNode);
  const requestFlyTo = useStudioStore((s) => s.requestFlyTo);

  const [searchFilter, setSearchFilter] = useState('');
  const [ratFilter, setRatFilter] = useState<string>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('id');
  const [sortAsc, setSortAsc] = useState<boolean>(true);

  // Filter & sort dataset
  const filteredData = useMemo(() => {
    let list = vehicles.filter((v) => {
      if (searchFilter && !v.name.toLowerCase().includes(searchFilter.toLowerCase())) {
        return false;
      }
      if (ratFilter !== 'ALL') {
        if (ratFilter === 'BLIND' && !v.in_blind) return false;
        if (ratFilter !== 'BLIND' && v.active_rat !== ratFilter) return false;
      }
      return true;
    });

    list.sort((a, b) => {
      let va: any = a[sortKey];
      let vb: any = b[sortKey];
      if (va == null) va = -Infinity;
      if (vb == null) vb = -Infinity;
      if (va < vb) return sortAsc ? -1 : 1;
      if (va > vb) return sortAsc ? 1 : -1;
      return 0;
    });

    return list;
  }, [vehicles, searchFilter, ratFilter, sortKey, sortAsc]);

  const tableContainerRef = useRef<HTMLDivElement>(null);

  // High-performance virtualizer for 60 FPS scrolling
  const rowVirtualizer = useVirtualizer({
    count: filteredData.length,
    getScrollElement: () => tableContainerRef.current,
    estimateSize: () => 36,
    overscan: 10,
  });

  const handleRowClick = (veh: VehicleTelemetry) => {
    selectNode({ type: 'veh', index: veh.id, data: veh });
    if (veh.lat !== null && veh.lon !== null) {
      requestFlyTo('veh', veh.id, veh.lat, veh.lon);
    }
  };

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(true);
    }
  };

  return (
    <div className="w-full h-full flex flex-col bg-bg-panel select-none text-xs text-slate-200">
      {/* Search & Filter Bar */}
      <div className="h-10 bg-bg-card border-b border-border-subtle px-3 flex items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-2 flex-1 max-w-xs">
          <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Filter by vehicle name or ID..."
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            className="w-full bg-bg-panel border border-border-subtle rounded px-2 py-0.5 text-xs text-slate-100 placeholder-slate-500 outline-none font-mono focus:border-brand-cyan"
          />
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <select
            value={ratFilter}
            onChange={(e) => setRatFilter(e.target.value)}
            className="bg-bg-panel border border-border-subtle rounded px-2 py-0.5 text-xs font-mono text-slate-200 outline-none cursor-pointer"
          >
            <option value="ALL">All RATs</option>
            <option value="5G">5G NR Only</option>
            <option value="LEO">LEO NTN Only</option>
            <option value="V2X">V2X Only</option>
            <option value="BLIND">In Blind Spot</option>
          </select>
          <span className="font-mono text-[10px] text-slate-500">
            {filteredData.length} Nodes
          </span>
        </div>
      </div>

      {/* Virtualized Table Body */}
      <div ref={tableContainerRef} className="flex-1 overflow-y-auto">
        <div className="w-full border-collapse">
          {/* Header Row */}
          <div className="sticky top-0 bg-bg-panel-solid border-b border-border-subtle z-10 font-mono text-[10px] text-slate-400 uppercase tracking-wider flex items-center px-2 py-2">
            <div className="w-16 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('id')}>
              ID <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-36 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('name')}>
              Entity / Node <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-36 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('active_rat')}>
              Active RAT <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-24 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('speed_kmh')}>
              Speed <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-24 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('mec_latency_ms')}>
              Latency <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-20 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('qos_score')}>
              QoS <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="w-20 cursor-pointer hover:text-white flex items-center gap-1" onClick={() => handleSort('battery_soc_pct')}>
              Battery <ArrowUpDown className="w-2.5 h-2.5" />
            </div>
            <div className="flex-1">Status</div>
          </div>

          {/* Virtual Body */}
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              position: 'relative',
              width: '100%',
            }}
          >
            {rowVirtualizer.getVirtualItems().map((virtualRow) => {
              const veh = filteredData[virtualRow.index];
              if (!veh) return null;
              const isSelected = selectedNode?.type === 'veh' && selectedNode.data?.id === veh.id;

              return (
                <div
                  key={veh.id}
                  onClick={() => handleRowClick(veh)}
                  className={`absolute w-full flex items-center px-2 border-b border-border-subtle/50 cursor-pointer transition ${
                    isSelected
                      ? 'bg-brand-cyan/20 border-brand-cyan/40'
                      : 'hover:bg-bg-card'
                  }`}
                  style={{
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                  }}
                >
                  <div className="w-16 font-mono text-slate-400 font-bold">#{veh.id}</div>
                  <div className="w-36 flex items-center gap-1.5 font-mono text-slate-100 font-semibold truncate">
                    <Car className="w-3.5 h-3.5 text-brand-cyan shrink-0" />
                    <span className="truncate">{veh.name}</span>
                  </div>
                  <div className="w-36 flex items-center gap-1.5 font-mono text-[11px]">
                    <span
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: ratColor(veh.active_rat as any) }}
                    />
                    <span className="font-bold truncate" style={{ color: ratColor(veh.active_rat as any) }}>
                      {ratLabel(veh.active_rat as any)}
                    </span>
                  </div>
                  <div className="w-24 font-mono text-slate-200">
                    {veh.speed_kmh !== null && veh.speed_kmh !== undefined ? `${veh.speed_kmh.toFixed(1)} km/h` : '—'}
                  </div>
                  <div className="w-24 font-mono text-slate-200">
                    {veh.mec_latency_ms !== null && veh.mec_latency_ms !== undefined ? `${veh.mec_latency_ms.toFixed(1)} ms` : '—'}
                  </div>
                  <div className="w-20 font-mono font-bold">
                    <span
                      className={
                        veh.qos_score !== null && veh.qos_score !== undefined && veh.qos_score >= 0.8
                          ? 'text-emerald-400'
                          : veh.qos_score !== null && veh.qos_score !== undefined && veh.qos_score >= 0.5
                          ? 'text-amber-400'
                          : 'text-red-400'
                      }
                    >
                      {veh.qos_score !== null && veh.qos_score !== undefined ? veh.qos_score.toFixed(2) : '—'}
                    </span>
                  </div>
                  <div className="w-20 font-mono text-emerald-400">
                    {veh.battery_soc_pct !== null && veh.battery_soc_pct !== undefined ? `${veh.battery_soc_pct.toFixed(0)}%` : '—'}
                  </div>
                  <div className="flex-1">
                    {veh.in_blind ? (
                      <span className="flex items-center gap-1 text-[10px] text-accent-red font-mono font-bold bg-red-500/10 px-1.5 py-0.5 rounded w-max">
                        <ShieldAlert className="w-3 h-3" /> BLIND
                      </span>
                    ) : (
                      <span className="text-[10px] text-emerald-400 font-mono font-bold bg-emerald-500/10 px-1.5 py-0.5 rounded w-max">
                        NORMAL
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {filteredData.length === 0 && (
          <div className="py-12 text-center text-slate-500 text-xs font-mono">
            No vehicle telemetries matching filter.
          </div>
        )}
      </div>
    </div>
  );
};

