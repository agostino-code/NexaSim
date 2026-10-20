import React, { useEffect, useRef } from 'react';
import { DockviewApi } from 'dockview';
import { Header } from './components/layout/Header';
import { SystemStrip } from './components/layout/SystemStrip';
import { TimelineControlBar } from './components/layout/TimelineControlBar';
import { WorkspaceDock } from './components/dockview/WorkspaceDock';
import { CommandPalette } from './components/common/CommandPalette';
import { DataProvenanceModal } from './components/common/DataProvenanceModal';
import { useStudioStore } from './store/useStudioStore';
import { fetchScenarios, fetchFleet, fetchFleetTimeline, fetchCompare } from './services/api';
import { wsManager } from './services/websocket';

export const App: React.FC = () => {
  // Zustand atomic selectors
  const setScenarios = useStudioStore((s) => s.setScenarios);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const setVehicles = useStudioStore((s) => s.setVehicles);
  const setFleetTimeline = useStudioStore((s) => s.setFleetTimeline);
  const setCompareData = useStudioStore((s) => s.setCompareData);

  const dockApiRef = useRef<DockviewApi | null>(null);

  useEffect(() => {
    // Connect WebSockets
    wsManager.connect();

    const abortCtrl = new AbortController();

    // Fetch Initial Scenario Catalog with abort signal
    fetchScenarios(abortCtrl.signal)
      .then((scenarios) => {
        setScenarios(scenarios);
        if (scenarios.length > 0 && !useStudioStore.getState().currentScenario) {
          selectScenario(scenarios[0]);
        }
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        console.error('Failed to load scenarios:', err);
      });

    return () => {
      abortCtrl.abort();
      wsManager.disconnect();
    };
  }, [setScenarios, selectScenario]);

  // Load the recorded fleet snapshot for the selected scenario
  useEffect(() => {
    if (!currentScenario) return;
    const abortCtrl = new AbortController();

    fetchFleet(currentScenario.id, undefined, abortCtrl.signal)
      .then((snap) => {
        setVehicles(snap.vehicles);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        console.error('Failed to load fleet snapshot:', err);
      });

    fetchFleetTimeline(currentScenario.id, abortCtrl.signal)
      .then((tl) => {
        setFleetTimeline(tl);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
      });

    fetchCompare(currentScenario.id, abortCtrl.signal)
      .then((cmp) => {
        setCompareData(cmp);
      })
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
      });

    return () => {
      abortCtrl.abort();
    };
  }, [currentScenario?.id, setVehicles, setFleetTimeline, setCompareData]);

  return (
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-bg-base font-sans select-none">
      <Header />
      <SystemStrip />
      <WorkspaceDock apiRef={dockApiRef} />
      <TimelineControlBar />
      <CommandPalette />
      <DataProvenanceModal />
    </div>
  );
};

export default App;
