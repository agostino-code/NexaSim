import React, { useEffect, useRef } from 'react';
import { DockviewApi } from 'dockview';
import { Header } from './components/layout/Header';
import { SystemStrip } from './components/layout/SystemStrip';
import { WorkspaceDock } from './components/dockview/WorkspaceDock';
import { DataProvenanceModal } from './components/common/DataProvenanceModal';
import { useStudioStore } from './store/useStudioStore';
import { fetchScenarios, fetchFleet } from './services/api';
import { wsManager } from './services/websocket';

export const App: React.FC = () => {
  // Zustand atomic selectors
  const setScenarios = useStudioStore((s) => s.setScenarios);
  const selectScenario = useStudioStore((s) => s.selectScenario);
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const setVehicles = useStudioStore((s) => s.setVehicles);

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

  // Load the recorded fleet snapshot (latest per-vehicle state) for the
  // selected scenario. While a live run is active, ws frames take over.
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

    return () => {
      abortCtrl.abort();
    };
  }, [currentScenario?.id, setVehicles]);

  const handleLayoutPreset = (preset: 'dual' | '2d' | '3d' | 'analytics') => {
    const api = dockApiRef.current;
    if (!api) return;

    const panel2D = api.getPanel('panel_2d');
    const panel3D = api.getPanel('panel_3d');
    const panelDash = api.getPanel('panel_dashboard');

    try {
      if (preset === 'dual') {
        // Restore the split workspace (exit any maximized group)
        api.exitMaximizedGroup();
        if (panel2D) panel2D.api.setActive();
        if (panel3D) panel3D.api.setActive();
      } else {
        const target = preset === '2d' ? panel2D : preset === '3d' ? panel3D : panelDash;
        if (target) {
          target.api.setActive();
          api.maximizeGroup(target);
        }
      }
    } catch (err) {
      console.warn('Layout preset failed:', err);
    }
  };

  return (
    <div className="flex flex-col w-screen h-screen overflow-hidden bg-bg-base font-sans select-none">
      <Header onLayoutPreset={handleLayoutPreset} />
      <SystemStrip />
      <WorkspaceDock apiRef={dockApiRef} />
      <DataProvenanceModal />
    </div>
  );
};

export default App;
