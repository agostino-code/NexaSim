import React, { useCallback } from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  applyNodeChanges,
  applyEdgeChanges,
  addEdge,
  Node,
  Edge,
  Connection,
  NodeChange,
  EdgeChange,
  Position,
  Handle,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Radio,
  Satellite,
  Car,
  Cpu,
  Server,
  Layers,
  Sparkles,
  Zap,
  Sliders,
  CheckCircle2,
} from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';

// Custom Node for Mobility Domain
const SourceMobilityNode = ({ data }: { data: any }) => (
  <div className="bg-bg-panel border-2 border-brand-cyan/60 rounded-lg p-3 shadow-xl min-w-[170px] text-xs font-mono">
    <div className="flex items-center gap-2 text-brand-cyan font-bold pb-1 mb-1 border-b border-border-subtle">
      <Car className="w-4 h-4" />
      <span>{data.label}</span>
    </div>
    <div className="text-[10px] text-slate-400">
      <div>Domain: <strong className="text-slate-200">{data.domain || 'Terrestrial'}</strong></div>
      <div>Nodes: <strong className="text-slate-200">{data.count || 4} UEs</strong></div>
    </div>
    <Handle type="source" position={Position.Right} className="!bg-brand-cyan w-2.5 h-2.5" />
  </div>
);

// Custom Node for Services & Sensors
const ServiceSensorNode = ({ data }: { data: any }) => (
  <div className="bg-bg-panel border-2 border-amber-400/60 rounded-lg p-3 shadow-xl min-w-[170px] text-xs font-mono">
    <Handle type="target" position={Position.Left} className="!bg-amber-400 w-2.5 h-2.5" />
    <div className="flex items-center gap-2 text-amber-400 font-bold pb-1 mb-1 border-b border-border-subtle">
      <Cpu className="w-4 h-4" />
      <span>{data.label}</span>
    </div>
    <div className="text-[10px] text-slate-400">
      <div>Standard: <strong className="text-slate-200">{data.standard}</strong></div>
      <div>Interval: <strong className="text-slate-200">{data.rate || '10 Hz'}</strong></div>
    </div>
    <Handle type="source" position={Position.Right} className="!bg-amber-400 w-2.5 h-2.5" />
  </div>
);

// Custom Node for Hybrid Interface Manager
const HybridManagerNode = ({ data }: { data: any }) => (
  <div className="bg-bg-panel border-2 border-emerald-400 rounded-lg p-3.5 shadow-2xl min-w-[210px] text-xs font-mono">
    <Handle type="target" position={Position.Left} className="!bg-emerald-400 w-2.5 h-2.5" />
    <div className="flex items-center gap-2 text-emerald-400 font-bold pb-1.5 mb-1.5 border-b border-border-subtle">
      <Sliders className="w-4 h-4" />
      <span>HybridInterfaceManager</span>
    </div>
    <div className="text-[10px] text-slate-300 flex flex-col gap-1">
      <div>Mode: <strong className="text-emerald-400">{data.mode || 'predictive_mbb'}</strong></div>
      <div>Outage AoI Threshold: <strong className="text-slate-200">250 ms</strong></div>
      <div className="text-slate-400 text-[9px] mt-0.5">Closed-Loop Kinematics: ACTIVE</div>
    </div>
    <Handle type="source" position={Position.Right} className="!bg-emerald-400 w-2.5 h-2.5" />
  </div>
);

// Custom Node for Physical RAT
const PhysicalRatNode = ({ data }: { data: any }) => {
  const color = data.rat === '5G' ? 'border-emerald-400 text-emerald-400' : data.rat === 'LEO' ? 'border-brand-cyan text-brand-cyan' : 'border-purple-400 text-purple-400';
  return (
    <div className={`bg-bg-panel border-2 ${color} rounded-lg p-3 shadow-xl min-w-[170px] text-xs font-mono`}>
      <Handle type="target" position={Position.Left} className="!bg-slate-200 w-2.5 h-2.5" />
      <div className="flex items-center gap-2 font-bold pb-1 mb-1 border-b border-border-subtle">
        {data.rat === 'LEO' ? <Satellite className="w-4 h-4" /> : <Radio className="w-4 h-4" />}
        <span>{data.label}</span>
      </div>
      <div className="text-[10px] text-slate-400">
        <div>Band: <strong className="text-slate-200">{data.band}</strong></div>
        <div>Model: <strong className="text-slate-200">{data.model}</strong></div>
      </div>
    </div>
  );
};

const nodeTypes = {
  mobility: SourceMobilityNode,
  service: ServiceSensorNode,
  hybrid: HybridManagerNode,
  rat: PhysicalRatNode,
};

const initialNodes: Node[] = [
  {
    id: '1',
    type: 'mobility',
    position: { x: 40, y: 120 },
    data: { label: 'Vehicle Fleet', domain: 'V2X SUMO', count: 4 },
  },
  {
    id: '2',
    type: 'service',
    position: { x: 260, y: 50 },
    data: { label: 'Real ETSI CPM', standard: 'ETSI TS 103 324', rate: '10 Hz' },
  },
  {
    id: '3',
    type: 'service',
    position: { x: 260, y: 190 },
    data: { label: 'MEC Offloader', standard: 'ETSI MEC 003', rate: 'On-Demand' },
  },
  {
    id: '4',
    type: 'hybrid',
    position: { x: 500, y: 110 },
    data: { label: 'Hybrid Switcher', mode: 'predictive_mbb' },
  },
  {
    id: '5',
    type: 'rat',
    position: { x: 770, y: 30 },
    data: { label: '5G-NR gNodeB', rat: '5G', band: '3.5 GHz (100MHz)', model: '3GPP UMa' },
  },
  {
    id: '6',
    type: 'rat',
    position: { x: 770, y: 160 },
    data: { label: 'LEO Satellites', rat: 'LEO', band: 'Ka 28 GHz (1GHz)', model: '3GPP Rel-17 NTN' },
  },
  {
    id: '7',
    type: 'rat',
    position: { x: 770, y: 290 },
    data: { label: 'ITS-G5 Sidelink', rat: 'V2X', band: '5.9 GHz (10MHz)', model: 'IEEE 802.11p' },
  },
];

const initialEdges: Edge[] = [
  { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#38bdf8' } },
  { id: 'e1-3', source: '1', target: '3', animated: true, style: { stroke: '#38bdf8' } },
  { id: 'e2-4', source: '2', target: '4', animated: true, style: { stroke: '#f59e0b' } },
  { id: 'e3-4', source: '3', target: '4', animated: true, style: { stroke: '#f59e0b' } },
  { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#10b981' } },
  { id: 'e4-6', source: '4', target: '6', animated: true, style: { stroke: '#38bdf8' } },
  { id: 'e4-7', source: '4', target: '7', animated: true, style: { stroke: '#a855f7' } },
];

export const NetworkStackFlowEditor: React.FC = () => {
  const [nodes, setNodes] = React.useState<Node[]>(initialNodes);
  const [edges, setEdges] = React.useState<Edge[]>(initialEdges);
  const appendLog = useStudioStore((s) => s.appendLog);
  const updateScenarioParams = useStudioStore((s) => s.updateScenarioParams);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds) => applyNodeChanges(changes, nds)),
    []
  );

  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  );

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, animated: true }, eds)),
    []
  );

  return (
    <div className="w-full h-full bg-bg-base relative select-none">
      <div className="absolute top-3 left-3 z-10 bg-bg-panel/90 backdrop-blur-md border border-border-subtle p-2 rounded-lg shadow-xl text-xs font-mono flex items-center gap-2">
        <Layers className="w-4 h-4 text-brand-cyan" />
        <span className="font-bold text-slate-100">Multi-Domain Network Stack Flow</span>
        <span className="text-[10px] text-slate-500">• Drag & Connect Interfaces</span>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        fitView
      >
        <Background color="#1c2838" gap={16} />
        <Controls className="!bg-bg-panel !border-border-subtle !fill-slate-200" />
      </ReactFlow>
    </div>
  );
};
