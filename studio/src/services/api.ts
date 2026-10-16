import {
  ScenarioSummary,
  ScenarioDetail,
  SimStatus,
  TelemetrySeries,
  FleetSnapshot,
  KpiSummary,
  FleetTimelineResponse,
  CompareResponse,
} from '../types/scenario';

export async function fetchScenarios(signal?: AbortSignal): Promise<ScenarioSummary[]> {
  const res = await fetch('/api/scenarios', { signal });
  if (!res.ok) throw new Error(`Failed to fetch scenarios: ${res.statusText}`);
  return res.json();
}

export async function fetchScenario(id: string, signal?: AbortSignal): Promise<ScenarioDetail> {
  const res = await fetch(`/api/scenario?name=${encodeURIComponent(id)}`, { signal });
  if (!res.ok) throw new Error(`Failed to fetch scenario ${id}`);
  return res.json();
}

export async function fetchStatus(signal?: AbortSignal): Promise<SimStatus> {
  const res = await fetch('/api/status', { signal });
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function runSimulation(id: string, signal?: AbortSignal): Promise<{ status: string; run_id: string }> {
  const res = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to dispatch simulation');
  }
  return res.json();
}

export async function build3dTwin(id: string, signal?: AbortSignal): Promise<{ status: string; html: string }> {
  const res = await fetch('/api/view3d', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to generate 3D twin');
  }
  return res.json();
}

export async function saveScenario(id: string, data: unknown, signal?: AbortSignal): Promise<{ status: string }> {
  const res = await fetch('/api/save', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, data }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to save scenario');
  }
  return res.json();
}

export async function deleteNode(id: string, type: string, name: string, signal?: AbortSignal): Promise<unknown> {
  const res = await fetch('/api/scenario/node/delete', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ id, type, name }),
    signal,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to delete node');
  }
  return res.json();
}

export async function fetchRoute(id: string, signal?: AbortSignal): Promise<{ coordinates: [number, number][] }> {
  const res = await fetch(`/api/route?name=${encodeURIComponent(id)}`, { signal });
  if (!res.ok) return { coordinates: [] };
  return res.json();
}

export async function fetchTelemetry(name: string, signal?: AbortSignal): Promise<TelemetrySeries> {
  const res = await fetch(`/api/telemetry?name=${encodeURIComponent(name)}`, { signal });
  if (!res.ok) {
    // Honest empty series: the UI renders "not recorded" instead of fake data.
    return {
      timestamps: [],
      throughput_mbps: [],
      rtt_ms: [],
      handover_events: [],
      active_interface: [],
      qos_score: [],
    };
  }
  return res.json();
}

export async function fetchFleet(name: string, t?: number, signal?: AbortSignal): Promise<FleetSnapshot> {
  const url =
    t != null
      ? `/api/fleet?name=${encodeURIComponent(name)}&t=${t}`
      : `/api/fleet?name=${encodeURIComponent(name)}`;
  const res = await fetch(url, { signal });
  if (!res.ok) {
    return { scenario: name, sim_time: null, vehicles: [] };
  }
  const data: FleetSnapshot = await res.json();
  return { ...data, vehicles: data.vehicles ?? [] };
}

export async function fetchKpis(name: string, signal?: AbortSignal): Promise<KpiSummary> {
  const res = await fetch(`/api/results?name=${encodeURIComponent(name)}`, { signal });
  if (!res.ok) {
    return { scenario: name };
  }
  const data = await res.json();
  return data;
}

export async function fetchFleetTimeline(name: string, signal?: AbortSignal): Promise<FleetTimelineResponse> {
  const res = await fetch(`/api/fleet_timeline?name=${encodeURIComponent(name)}`, { signal });
  if (!res.ok) {
    return { scenario: name, timestamps: [], vehicles_timeline: {} };
  }
  return res.json();
}

export async function fetchCompare(name: string, signal?: AbortSignal): Promise<CompareResponse> {
  const res = await fetch(`/api/compare?name=${encodeURIComponent(name)}`, { signal });
  if (!res.ok) {
    return { available: false, scenario: name };
  }
  return res.json();
}
