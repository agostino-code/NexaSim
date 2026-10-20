import React, { useRef, useEffect } from 'react';
import {
  DockviewReact,
  DockviewReadyEvent,
  IDockviewPanelProps,
  DockviewApi,
} from 'dockview';
import 'dockview/dist/styles/dockview.css';

import { UnifiedSimulationViewport } from '../viewports/UnifiedSimulationViewport';
import { ScenarioCatalog } from '../catalog/ScenarioCatalog';
import { NodeInspector } from '../inspector/NodeInspector';
import { SynchronizedTelemetryPanel } from '../telemetry/SynchronizedTelemetryPanel';
import { FleetMatrixTable } from '../telemetry/FleetMatrixTable';
import { LiveTerminal } from '../console/LiveTerminal';
import { MapScenarioDrawer } from '../builder/MapScenarioDrawer';
import { NetworkStackFlowEditor } from '../builder/NetworkStackFlowEditor';
import { ConstellationConfigurator } from '../builder/ConstellationConfigurator';
import { SchemaFormAndYamlSync } from '../builder/SchemaFormAndYamlSync';
import { useStudioStore } from '../../store/useStudioStore';

const components: Record<string, React.FC<IDockviewPanelProps>> = {
  unified_viewport: () => <UnifiedSimulationViewport />,
  scenario_catalog: () => <ScenarioCatalog />,
  node_inspector: () => <NodeInspector />,
  dashboard_kpi: () => <SynchronizedTelemetryPanel />,
  fleet_telemetry: () => <FleetMatrixTable />,
  live_terminal: () => <LiveTerminal />,
  map_drawer: () => <MapScenarioDrawer />,
  flow_editor: () => <NetworkStackFlowEditor />,
  constellation_config: () => <ConstellationConfigurator />,
  yaml_editor: () => <SchemaFormAndYamlSync />,
};

interface WorkspaceDockProps {
  apiRef?: React.MutableRefObject<DockviewApi | null>;
}

export const WorkspaceDock: React.FC<WorkspaceDockProps> = ({ apiRef }) => {
  const dockApiRef = useRef<DockviewApi | null>(null);
  const activeMode = useStudioStore((s) => s.activeMode);

  const applyLayoutForMode = (api: DockviewApi, mode: string) => {
    api.clear();

    if (mode === 'design') {
      // 1. Left Builder Tools
      const drawerPanel = api.addPanel({
        id: 'panel_drawer',
        component: 'map_drawer',
        title: 'Tactical Drawer',
        initialWidth: 280,
      });

      api.addPanel({
        id: 'panel_constellation',
        component: 'constellation_config',
        title: 'LEO Constellation',
        position: { referencePanel: drawerPanel },
      });

      api.addPanel({
        id: 'panel_catalog',
        component: 'scenario_catalog',
        title: 'Library',
        position: { referencePanel: drawerPanel },
      });

      // 2. Center: Unified Viewport
      const viewportPanel = api.addPanel({
        id: 'panel_viewport',
        component: 'unified_viewport',
        title: 'Space-to-Street Viewport',
        position: { referencePanel: drawerPanel, direction: 'right' },
      });

      // 3. Right: Node Inspector
      api.addPanel({
        id: 'panel_inspector',
        component: 'node_inspector',
        title: 'Node Inspector',
        initialWidth: 280,
        position: { referencePanel: viewportPanel, direction: 'right' },
      });

      // 4. Bottom: Network Stack Flow & Monaco YAML
      const flowPanel = api.addPanel({
        id: 'panel_flow',
        component: 'flow_editor',
        title: 'Network Stack Flow',
        position: { referencePanel: viewportPanel, direction: 'below' },
        initialHeight: 280,
      });

      api.addPanel({
        id: 'panel_yaml',
        component: 'yaml_editor',
        title: 'YAML Blueprint & Validation',
        position: { referencePanel: flowPanel },
      });
    } else if (mode === 'analyze') {
      // Analyze Mode Layout: Full screen deep analytics
      const catalogPanel = api.addPanel({
        id: 'panel_catalog',
        component: 'scenario_catalog',
        title: 'Scenario Library',
        initialWidth: 260,
      });

      const dashPanel = api.addPanel({
        id: 'panel_dashboard',
        component: 'dashboard_kpi',
        title: 'Synchronized Telemetry & ECharts Analytics',
        position: { referencePanel: catalogPanel, direction: 'right' },
      });

      api.addPanel({
        id: 'panel_fleet',
        component: 'fleet_telemetry',
        title: 'Fleet Matrix',
        initialWidth: 320,
        position: { referencePanel: dashPanel, direction: 'right' },
      });

      api.addPanel({
        id: 'panel_terminal',
        component: 'live_terminal',
        title: 'Simulation Log Stream',
        position: { referencePanel: dashPanel, direction: 'below' },
        initialHeight: 200,
      });
    } else {
      // Default LIVE Mission Control Mode
      const catalogPanel = api.addPanel({
        id: 'panel_catalog',
        component: 'scenario_catalog',
        title: 'Scenario Library',
        initialWidth: 260,
      });

      const viewportPanel = api.addPanel({
        id: 'panel_viewport',
        component: 'unified_viewport',
        title: 'Unified 2D/3D Tactical Viewport',
        position: { referencePanel: catalogPanel, direction: 'right' },
      });

      api.addPanel({
        id: 'panel_inspector',
        component: 'node_inspector',
        title: 'Node Inspector',
        initialWidth: 280,
        position: { referencePanel: viewportPanel, direction: 'right' },
      });

      const dashPanel = api.addPanel({
        id: 'panel_dashboard',
        component: 'dashboard_kpi',
        title: 'Real-Time Telemetry & KPIs',
        position: { referencePanel: viewportPanel, direction: 'below' },
        initialHeight: 250,
      });

      api.addPanel({
        id: 'panel_fleet',
        component: 'fleet_telemetry',
        title: 'Fleet Matrix (60 FPS)',
        position: { referencePanel: dashPanel },
      });

      api.addPanel({
        id: 'panel_terminal',
        component: 'live_terminal',
        title: 'OMNeT++ Console',
        position: { referencePanel: dashPanel },
      });
    }
  };

  const onReady = (event: DockviewReadyEvent) => {
    dockApiRef.current = event.api;
    if (apiRef) apiRef.current = event.api;
    applyLayoutForMode(event.api, activeMode);
  };

  // React to mode changes
  useEffect(() => {
    if (dockApiRef.current) {
      applyLayoutForMode(dockApiRef.current, activeMode);
    }
  }, [activeMode]);

  return (
    <div className="flex-1 w-full h-full relative overflow-hidden bg-bg-base">
      <DockviewReact
        onReady={onReady}
        components={components}
        className="dockview-theme-dark h-full w-full"
      />
    </div>
  );
};
