import React, { useRef } from 'react';
import {
  DockviewReact,
  DockviewReadyEvent,
  IDockviewPanelProps,
  DockviewApi,
} from 'dockview';
import 'dockview/dist/styles/dockview.css';

import { ScenarioCatalog } from '../catalog/ScenarioCatalog';
import { Tactical2DMap } from '../viewports/Tactical2DMap';
import { DigitalTwin3D } from '../viewports/DigitalTwin3D';
import { NodeInspector } from '../inspector/NodeInspector';
import { ExecutiveDashboard } from '../telemetry/ExecutiveDashboard';
import { FleetMatrixTable } from '../telemetry/FleetMatrixTable';
import { LiveTerminal } from '../console/LiveTerminal';

const components: Record<string, React.FC<IDockviewPanelProps>> = {
  scenario_catalog: () => <ScenarioCatalog />,
  tactical_2d: () => <Tactical2DMap />,
  digital_twin_3d: () => <DigitalTwin3D />,
  node_inspector: () => <NodeInspector />,
  dashboard_kpi: () => <ExecutiveDashboard />,
  fleet_telemetry: () => <FleetMatrixTable />,
  live_terminal: () => <LiveTerminal />,
};

interface WorkspaceDockProps {
  apiRef?: React.MutableRefObject<DockviewApi | null>;
}

export const WorkspaceDock: React.FC<WorkspaceDockProps> = ({ apiRef }) => {
  const dockApiRef = useRef<DockviewApi | null>(null);

  const onReady = (event: DockviewReadyEvent) => {
    dockApiRef.current = event.api;
    if (apiRef) apiRef.current = event.api;

    // Build the initial Mission Control Workspace layout
    // 1. Left: Scenario Catalog
    event.api.addPanel({
      id: 'panel_catalog',
      component: 'scenario_catalog',
      title: 'Scenario Library',
      initialWidth: 280,
    });

    // 2. Center: 2D Tactical Map
    const mapPanel = event.api.addPanel({
      id: 'panel_2d',
      component: 'tactical_2d',
      title: 'Tactical 2D Map',
      position: { referencePanel: 'panel_catalog', direction: 'right' },
    });

    // 3. Center Right: 3D Digital Twin
    event.api.addPanel({
      id: 'panel_3d',
      component: 'digital_twin_3d',
      title: '3D Digital Twin',
      position: { referencePanel: mapPanel, direction: 'right' },
    });

    // 4. Far Right: Node Inspector
    event.api.addPanel({
      id: 'panel_inspector',
      component: 'node_inspector',
      title: 'Node Inspector',
      initialWidth: 260,
      position: { referencePanel: 'panel_3d', direction: 'right' },
    });

    // 5. Bottom Tabs (Executive Dashboard, Fleet Telemetry, Terminal)
    const dashPanel = event.api.addPanel({
      id: 'panel_dashboard',
      component: 'dashboard_kpi',
      title: 'Executive KPI Dashboard',
      position: { referencePanel: mapPanel, direction: 'below' },
      initialHeight: 280,
    });

    event.api.addPanel({
      id: 'panel_fleet',
      component: 'fleet_telemetry',
      title: 'Fleet Telemetry Matrix',
      position: { referencePanel: dashPanel, direction: 'within' },
    });

    event.api.addPanel({
      id: 'panel_console',
      component: 'live_terminal',
      title: 'Console Stream',
      position: { referencePanel: dashPanel, direction: 'within' },
    });
  };

  return (
    <div className="w-full h-full flex-1 min-h-0 bg-bg-base overflow-hidden">
      <DockviewReact
        components={components}
        onReady={onReady}
        className="dockview-theme-dark w-full h-full"
      />
    </div>
  );
};
