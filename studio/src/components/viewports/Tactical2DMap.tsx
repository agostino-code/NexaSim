import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import { Radio, Satellite, ShieldAlert, MousePointer, Maximize2 } from 'lucide-react';
import { useStudioStore } from '../../store/useStudioStore';
import { fetchRoute } from '../../services/api';
import { VehicleTelemetry, RatType, BlindSpotZone } from '../../types/scenario';
import { Legend } from '../common/Legend';
import {
  MAP_LEGEND,
  WARNING_COLOR,
  UNKNOWN_LINK_COLOR,
  BLIND_SPOT_COLOR,
  GNB_COLOR,
  GATEWAY_COLOR,
  ROUTE_COLOR,
  LINK_DERIVED_COLOR,
  ratColor,
  ratLabel,
} from '../../theme/palette';

/** Sanitizes untrusted or dynamic strings before HTML interpolation into Leaflet DOM */
function escapeHtml(str: string | null | undefined): string {
  if (str == null) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const isInsideBlindSpot = (
  lat: number,
  lon: number,
  spots: BlindSpotZone[] | undefined
): boolean =>
  !!spots?.some(
    (bs) => lat >= bs.lat_min && lat <= bs.lat_max && lon >= bs.lon_min && lon <= bs.lon_max
  );

/** "—" for not-recorded (null) metrics; never fabricates a number. */
const fmtNum = (v: number | null | undefined, digits = 1, suffix = ''): string =>
  v == null || Number.isNaN(v) ? '—' : `${v.toFixed(digits)}${suffix}`;

/** Initial bearing (deg, 0 = north, clockwise) between two coordinates. */
const bearingDeg = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
};

/** Equirectangular squared distance — sufficient to pick the nearest node. */
const approxDist2 = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const dLat = lat2 - lat1;
  const dLon = (lon2 - lon1) * Math.cos(((lat1 + lat2) / 2) * (Math.PI / 180));
  return dLat * dLat + dLon * dLon;
};

export const Tactical2DMap: React.FC = () => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const coordRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  // Layer groups (created once with the map; the layers control toggles them)
  const infraGroupRef = useRef<L.LayerGroup | null>(null);
  const routeGroupRef = useRef<L.LayerGroup | null>(null);
  const blindGroupRef = useRef<L.LayerGroup | null>(null);
  const linksGroupRef = useRef<L.LayerGroup | null>(null);
  const vehicleGroupRef = useRef<L.LayerGroup | null>(null);

  const vehicleMarkersRef = useRef<Map<number, L.Marker>>(new Map());
  const routePointsRef = useRef<[number, number][]>([]);
  const lastPosRef = useRef<Map<number, [number, number]>>(new Map());
  const bearingRef = useRef<Map<number, number>>(new Map());
  const lastLinksUpdateRef = useRef(0);
  const derivedPolylinesRef = useRef<L.Polyline[]>([]);
  const popupGeneratorsRef = useRef<Map<number, () => string>>(new Map());
  const activeDragCleanupRef = useRef<(() => void) | null>(null);

  // Zustand atomic selectors — notice simTime is intentionally omitted to prevent React re-renders at 60 FPS
  const currentScenario = useStudioStore((s) => s.currentScenario);
  const selectNode = useStudioStore((s) => s.selectNode);
  const updateNode = useStudioStore((s) => s.updateNode);
  const addNode = useStudioStore((s) => s.addNode);
  const vehicles = useStudioStore((s) => s.vehicles);
  const selectedNode = useStudioStore((s) => s.selectedNode);
  const flyToRequest = useStudioStore((s) => s.flyToRequest);

  const [activeTool, setActiveTool] = useState<'select' | 'gnb' | 'gs' | 'blind'>('select');
  const [routeVersion, setRouteVersion] = useState(0);

  // The map is created exactly once; keep a ref to the latest click handler
  // so tool switching and scenario edits are never captured stale.
  const clickRef = useRef<(latlng: L.LatLng) => void>(() => undefined);
  useEffect(() => {
    clickRef.current = (latlng: L.LatLng) => {
      if (activeTool === 'select') {
        selectNode(null);
        return;
      }
      if (!currentScenario) return;
      const lat = parseFloat(latlng.lat.toFixed(5));
      const lon = parseFloat(latlng.lng.toFixed(5));
      const stamp = Date.now() % 100000;

      if (activeTool === 'gnb') {
        const data = {
          name: `gnb_site_${stamp}`,
          lat,
          lon,
          height_m: 25,
          tx_power_dbm: 46,
          frequency_ghz: 3.5,
          bandwidth_mhz: 100,
          coverage_radius_m: 1500,
        };
        const index = currentScenario.gnbs?.length ?? 0;
        addNode('gnb', data);
        selectNode({ type: 'gnb', index, data });
      } else if (activeTool === 'gs') {
        const data = { name: `gw_site_${stamp}`, lat, lon, altitude_m: 250 };
        const index = currentScenario.ground_stations?.length ?? 0;
        addNode('gs', data);
        selectNode({ type: 'gs', index, data });
      } else if (activeTool === 'blind') {
        const d = 0.008;
        const data = {
          name: `shadow_${stamp}`,
          lat_min: parseFloat((lat - d).toFixed(5)),
          lat_max: parseFloat((lat + d).toFixed(5)),
          lon_min: parseFloat((lon - d).toFixed(5)),
          lon_max: parseFloat((lon + d).toFixed(5)),
          attenuation_db: 45.0,
        };
        const index = currentScenario.blind_spots?.length ?? 0;
        addNode('blind', data);
        selectNode({ type: 'blind', index, data });
      }
      setActiveTool('select');
    };
  });

  // Initialize the map (once): basemaps, scale bar, coordinate readout,
  // feature layer groups and the themed layers control.
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    const map = L.map(mapContainerRef.current, {
      zoomControl: false,
      attributionControl: false,
    }).setView([46.5286, 10.4531], 10);

    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.control.scale({ position: 'bottomright', metric: true, imperial: false }).addTo(map);

    const coordEl = coordRef.current;
    map.on('mousemove', (e: L.LeafletMouseEvent) => {
      if (coordEl) {
        coordEl.textContent = `${e.latlng.lat.toFixed(4)}°, ${e.latlng.lng.toFixed(4)}° · z${map.getZoom()}`;
      }
    });
    map.on('mouseout', () => {
      if (coordEl) coordEl.textContent = '—';
    });

    // Basemaps
    const esriDark = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: '© Esri' }
    );
    const cartoDark = L.tileLayer(
      'https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png',
      { subdomains: 'abcd', maxZoom: 19, attribution: '© CARTO' }
    );
    const esriSat = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      { maxZoom: 19, attribution: '© Esri Satellite' }
    );
    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '© OpenStreetMap',
    });

    esriDark.addTo(map);

    // Feature layer groups — every category is individually toggleable
    const infraGroup = L.layerGroup().addTo(map);
    const routeGroup = L.layerGroup().addTo(map);
    const blindGroup = L.layerGroup().addTo(map);
    const linksGroup = L.layerGroup().addTo(map);
    const vehicleGroup = L.layerGroup().addTo(map);
    infraGroupRef.current = infraGroup;
    routeGroupRef.current = routeGroup;
    blindGroupRef.current = blindGroup;
    linksGroupRef.current = linksGroup;
    vehicleGroupRef.current = vehicleGroup;

    L.control
      .layers(
        {
          'Tactical Dark (ESRI)': esriDark,
          'Dark Matter (CARTO)': cartoDark,
          'Satellite HD (ESRI)': esriSat,
          'OpenStreetMap': osmStandard,
        },
        {
          'Infrastructure (gNB · gateway)': infraGroup,
          'Recorded routes': routeGroup,
          'Blind spots': blindGroup,
          'Vehicles': vehicleGroup,
          'Derived links (estimate)': linksGroup,
        },
        { position: 'topleft', collapsed: true }
      )
      .addTo(map);

    map.on('click', (e: L.LeafletMouseEvent) => clickRef.current(e.latlng));

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Render scenario geometries whenever the scenario changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !currentScenario) return;

    const infraGroup = infraGroupRef.current;
    const routeGroup = routeGroupRef.current;
    const blindGroup = blindGroupRef.current;
    const linksGroup = linksGroupRef.current;
    const vehicleGroup = vehicleGroupRef.current;
    if (!infraGroup || !routeGroup || !blindGroup || !linksGroup || !vehicleGroup) return;

    infraGroup.clearLayers();
    routeGroup.clearLayers();
    blindGroup.clearLayers();
    linksGroup.clearLayers();
    vehicleGroup.clearLayers();
    vehicleMarkersRef.current.clear();
    lastPosRef.current.clear();
    bearingRef.current.clear();
    derivedPolylinesRef.current = [];
    popupGeneratorsRef.current.clear();
    routePointsRef.current = [];

    // Frame the scenario (bbox when available)
    if (currentScenario.bbox && currentScenario.bbox.length === 4) {
      const [minLon, minLat, maxLon, maxLat] = currentScenario.bbox;
      map.fitBounds(L.latLngBounds([minLat, minLon], [maxLat, maxLon]), { padding: [40, 40] });
    } else {
      map.setView(currentScenario.center, 11);
    }

    // 1. 5G gNodeBs (draggable markers with synchronized coverage circles)
    currentScenario.gnbs?.forEach((gnb, index) => {
      const radius = gnb.coverage_radius_m || 1500;
      const circle = L.circle([gnb.lat, gnb.lon], {
        radius,
        color: GNB_COLOR,
        weight: 1,
        fillColor: GNB_COLOR,
        fillOpacity: 0.1,
        dashArray: '2 4',
      }).addTo(infraGroup);

      const marker = L.circleMarker([gnb.lat, gnb.lon], {
        radius: 9,
        color: '#ffffff',
        weight: 2,
        fillColor: GNB_COLOR,
        fillOpacity: 1.0,
      }).addTo(infraGroup);

      marker.bindTooltip(`5G gNB: ${escapeHtml(gnb.name)}`, {
        permanent: true,
        direction: 'top',
        offset: [0, -10],
        className: 'nx-label',
      });

      // Drag support: the marker and coverage circle follow the pointer
      // locally; the store is updated once on mouse-up so the map is not
      // rebuilt mid-drag (updateNode creates a new scenario object).
      let isDragging = false;
      marker.on('mousedown', () => {
        if (activeDragCleanupRef.current) {
          activeDragCleanupRef.current();
        }
        isDragging = true;
        map.dragging.disable();

        const onMouseMove = (me: L.LeafletMouseEvent) => {
          if (!isDragging) return;
          const pos = me.latlng;
          marker.setLatLng(pos);
          circle.setLatLng(pos);
        };

        const cleanupDrag = () => {
          if (!isDragging) return;
          isDragging = false;
          map.dragging.enable();
          map.off('mousemove', onMouseMove);
          map.off('mouseup', onMouseUp);
          activeDragCleanupRef.current = null;
        };

        const onMouseUp = () => {
          cleanupDrag();
          const pos = marker.getLatLng();
          updateNode('gnb', index, {
            lat: parseFloat(pos.lat.toFixed(5)),
            lon: parseFloat(pos.lng.toFixed(5)),
          });
        };

        activeDragCleanupRef.current = cleanupDrag;
        map.on('mousemove', onMouseMove);
        map.on('mouseup', onMouseUp);
      });

      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        selectNode({ type: 'gnb', index, data: gnb });
      });
    });

    // 2. Ground gateways
    currentScenario.ground_stations?.forEach((gw, index) => {
      const marker = L.circleMarker([gw.lat, gw.lon], {
        radius: 8,
        color: '#ffffff',
        weight: 2,
        fillColor: GATEWAY_COLOR,
        fillOpacity: 1.0,
      }).addTo(infraGroup);
      marker.bindTooltip(`Gateway: ${escapeHtml(gw.name)}`, {
        permanent: true,
        direction: 'bottom',
        offset: [0, 10],
        className: 'nx-label',
      });

      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        selectNode({ type: 'gs', index, data: gw });
      });
    });

    // 3. Blind spots — dashed warning zones (not solid red blocks)
    currentScenario.blind_spots?.forEach((bs, index) => {
      if (bs.lat_min && bs.lat_max && bs.lon_min && bs.lon_max) {
        const rect = L.rectangle(
          [
            [bs.lat_min, bs.lon_min],
            [bs.lat_max, bs.lon_max],
          ],
          {
            color: BLIND_SPOT_COLOR,
            weight: 1.5,
            dashArray: '5 5',
            fillColor: BLIND_SPOT_COLOR,
            fillOpacity: 0.12,
          }
        ).addTo(blindGroup);

        rect.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          selectNode({ type: 'blind', index, data: bs });
        });

        rect.bindTooltip(
          `Blind spot: ${escapeHtml(bs.name || 'zone ' + index)}${
            bs.attenuation_db != null ? ` · ${bs.attenuation_db} dB` : ''
          }`,
          { sticky: true }
        );
      }
    });

    // 4. Route corridor (recorded geometry only, neutral colour)
    const abortCtrl = new AbortController();
    fetchRoute(currentScenario.id, abortCtrl.signal)
      .then((routeData) => {
        const points = routeData.coordinates;
        routePointsRef.current = points && points.length >= 2 ? points : [];
        if (!routePointsRef.current.length) return;
        L.polyline(routePointsRef.current, {
          color: ROUTE_COLOR,
          weight: 2,
          opacity: 0.55,
          dashArray: '4 8',
        }).addTo(routeGroup);
        // Vehicle placement depends on the route: re-run the tick effect once
        setRouteVersion((v) => v + 1);
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          /* no route geometry recorded — nothing honest to draw */
        }
      });

    return () => {
      abortCtrl.abort();
      if (activeDragCleanupRef.current) {
        activeDragCleanupRef.current();
      }
    };
  }, [currentScenario, selectNode, updateNode]);

  // Imperative vehicle position updater — called on Zustand simTime subscriptions
  // or state updates WITHOUT causing React re-renders of Tactical2DMap.
  const updateVehiclePositions = (currentTime: number) => {
    if (!currentScenario) return;
    const vehicleGroup = vehicleGroupRef.current;
    const linksGroup = linksGroupRef.current;
    if (!vehicleGroup || !linksGroup) return;

    const points = routePointsRef.current;
    const duration = currentScenario.duration_s || 0;

    const vehById = new Map<number, VehicleTelemetry>();
    vehicles.forEach((v) => vehById.set(v.id, v));

    const expectedCount = Math.min(Math.max(currentScenario.vehicles || 4, vehicles.length), 8);

    vehicleMarkersRef.current.forEach((marker, vIdx) => {
      if (vIdx >= expectedCount) {
        vehicleGroup.removeLayer(marker);
        vehicleMarkersRef.current.delete(vIdx);
        lastPosRef.current.delete(vIdx);
        bearingRef.current.delete(vIdx);
        popupGeneratorsRef.current.delete(vIdx);
      }
    });

    const nowMs = performance.now();
    const updateLinks = nowMs - lastLinksUpdateRef.current >= 250;
    if (updateLinks) lastLinksUpdateRef.current = nowMs;
    const linkTargets: { from: [number, number]; rat: RatType | null }[] = [];

    for (let v = 0; v < expectedCount; v++) {
      const isLeader = v === 0;
      const realVeh = vehById.get(v);
      const hasRealPos = !!realVeh && realVeh.lat != null && realVeh.lon != null;

      let latLng: [number, number] | null = null;
      let speedLabel: string | null = null;
      let inBlind = false;
      let activeRat: RatType | null = null;
      let posDerived = false;
      let segBearing: number | null = null;

      if (hasRealPos && realVeh) {
        const lat = realVeh.lat as number;
        const lon = realVeh.lon as number;
        latLng = [lat, lon];
        activeRat = realVeh.active_rat ?? null;
        inBlind = realVeh.in_blind || isInsideBlindSpot(lat, lon, currentScenario.blind_spots);
        speedLabel = realVeh.speed_kmh != null ? `${realVeh.speed_kmh.toFixed(1)} km/h` : null;
      } else if (points.length >= 2 && duration > 0) {
        const progress = (((currentTime / duration + v * 0.04) % 1.0) + 1.0) % 1.0;
        const f = progress * (points.length - 1);
        const i0 = Math.min(Math.floor(f), points.length - 2);
        const frac = f - i0;
        const p0 = points[i0];
        const p1 = points[i0 + 1];
        latLng = [p0[0] + (p1[0] - p0[0]) * frac, p0[1] + (p1[1] - p0[1]) * frac];
        inBlind = isInsideBlindSpot(latLng[0], latLng[1], currentScenario.blind_spots);
        posDerived = true;
        segBearing = bearingDeg(p0[0], p0[1], p1[0], p1[1]);
      }

      if (!latLng) {
        // No recorded position and no route geometry: nothing honest to draw
        const stale = vehicleMarkersRef.current.get(v);
        if (stale) {
          vehicleGroup.removeLayer(stale);
          vehicleMarkersRef.current.delete(v);
          popupGeneratorsRef.current.delete(v);
        }
        continue;
      }

      // Heading: recorded heading wins, then movement between ticks, then
      // the direction of the interpolated route segment. Null = unknown.
      let bearing: number | null = bearingRef.current.get(v) ?? null;
      if (realVeh?.heading_deg != null) {
        bearing = realVeh.heading_deg;
      } else {
        const prev = lastPosRef.current.get(v);
        if (prev && prev[0] === latLng[0] && prev[1] === latLng[1]) {
          if (bearing == null) bearing = segBearing;
        } else if (prev) {
          const d = approxDist2(prev[0], prev[1], latLng[0], latLng[1]);
          if (d > 1e-10) bearing = bearingDeg(prev[0], prev[1], latLng[0], latLng[1]);
          else if (bearing == null) bearing = segBearing;
        } else {
          bearing = segBearing;
        }
      }
      if (bearing != null) bearingRef.current.set(v, bearing);
      lastPosRef.current.set(v, latLng);

      const markerColor = inBlind
        ? WARNING_COLOR
        : activeRat
          ? ratColor(activeRat)
          : UNKNOWN_LINK_COLOR;

      const name = realVeh?.name || (isLeader ? 'Convoy Leader' : `Vehicle ${v}`);

      let marker = vehicleMarkersRef.current.get(v);
      if (!marker) {
        const icon = L.divIcon({
          className: '',
          html: `<div class="nx-veh${isLeader ? ' nx-veh--leader' : ''}">
              <div class="nx-veh-rot" style="display:none;"><div class="nx-veh-arrow"></div></div>
              <div class="nx-veh-badge">${isLeader ? '★' : v}</div>
            </div>`,
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        });
        const newMarker = L.marker(latLng, { icon, zIndexOffset: isLeader ? 500 : 0 });
        marker = newMarker;
        const markerIdx = v;
        newMarker.on('click', () => {
          const latest = useStudioStore.getState().vehicles.find((x) => x.id === markerIdx);
          selectNode({
            type: 'veh',
            index: markerIdx,
            data: { id: markerIdx, name: latest?.name ?? name, ...(latest ?? {}) },
          });
        });
        newMarker.bindTooltip('', { direction: 'top', offset: [0, -16], opacity: 1 });
        newMarker.bindPopup('', { closeButton: true, autoPan: true, maxWidth: 260 });

        // Update popup content on popupopen event to avoid 60 FPS DOM generation for closed popups
        newMarker.on('popupopen', () => {
          const gen = popupGeneratorsRef.current.get(markerIdx);
          if (gen) {
            newMarker.setPopupContent(gen());
          }
        });

        newMarker.addTo(vehicleGroup);
        vehicleMarkersRef.current.set(v, newMarker);
      } else {
        marker.setLatLng(latLng);
      }

      // Sync the marker DOM (colour, heading arrow, selection ring)
      const el = marker.getElement();
      if (el) {
        el.style.setProperty('--nx-veh-color', markerColor);
        const rot = el.querySelector('.nx-veh-rot') as HTMLElement | null;
        if (rot) {
          if (bearing == null) {
            rot.style.display = 'none';
          } else {
            rot.style.display = 'block';
            rot.style.transform = `rotate(${bearing.toFixed(1)}deg)`;
          }
        }
        if (isLeader) {
          const badge = el.querySelector('.nx-veh-badge') as HTMLElement | null;
          if (badge) badge.textContent = '★';
        }
        el.classList.toggle(
          'nx-veh--selected',
          selectedNode?.type === 'veh' && selectedNode.index === v
        );
      }

      // Tooltip (compact) with XSS escaping
      marker.setTooltipContent(
        `<b>${escapeHtml(name)}</b> · ${ratLabel(activeRat)}${inBlind ? ' · ⚠ blind spot' : ''}`
      );

      // Lazy popup generator with XSS escaping
      const generatePopupContent = () => `
        <span class="nx-popup-title">${escapeHtml(name)}</span>
        <div class="nx-popup-row"><span class="k">Active link</span><span class="v" style="color:${markerColor}">${ratLabel(activeRat)}</span></div>
        <div class="nx-popup-row"><span class="k">Speed</span><span class="v">${speedLabel ?? '—'}</span></div>
        <div class="nx-popup-row"><span class="k">MEC latency</span><span class="v">${fmtNum(realVeh?.mec_latency_ms, 1, ' ms')}</span></div>
        <div class="nx-popup-row"><span class="k">QoS utility</span><span class="v">${fmtNum(realVeh?.qos_score, 3)}</span></div>
        <div class="nx-popup-row"><span class="k">Battery SoC</span><span class="v">${fmtNum(realVeh?.battery_soc_pct, 1, '%')}</span></div>
        <div class="nx-popup-row"><span class="k">VHO switches</span><span class="v">${realVeh?.vho_count ?? '—'}</span></div>
        ${inBlind ? '<div class="nx-popup-note">⚠ Currently inside a blind-spot zone</div>' : ''}
        <div class="nx-popup-note">${
          posDerived
            ? 'Derived geometry: position interpolated along the recorded route at the current sim time'
            : 'Position from recorded telemetry'
        }</div>
      `;

      popupGeneratorsRef.current.set(v, generatePopupContent);

      // Only update popup content if the popup is currently open
      if (marker.isPopupOpen()) {
        marker.setPopupContent(generatePopupContent());
      }

      linkTargets.push({ from: latLng, rat: activeRat });
    }

    // Derived serving links (throttled): reuse existing L.polyline instances
    // instead of destroying and recreating layers every 250ms.
    if (updateLinks) {
      const gnbs = currentScenario.gnbs ?? [];
      const gss = currentScenario.ground_stations ?? [];
      const polylines = derivedPolylinesRef.current;
      let polyIdx = 0;

      linkTargets.forEach(({ from, rat }) => {
        if (rat === 'V2X' || rat == null) return; // sidelink / unknown: nothing honest to draw
        const candidates: [number, number][] =
          rat === '5G' ? gnbs.map((g) => [g.lat, g.lon]) : gss.map((g) => [g.lat, g.lon]);
        let best: [number, number] | null = null;
        let bestD = Infinity;
        candidates.forEach((c) => {
          const d = approxDist2(from[0], from[1], c[0], c[1]);
          if (d < bestD) {
            bestD = d;
            best = c;
          }
        });
        const target = best as [number, number] | null;
        if (target) {
          const segmentCoords: [number, number][] = [from, target];
          if (polyIdx < polylines.length) {
            polylines[polyIdx].setLatLngs(segmentCoords);
          } else {
            const poly = L.polyline(segmentCoords, {
              color: LINK_DERIVED_COLOR,
              weight: 1.2,
              opacity: 0.5,
              dashArray: '3 6',
              interactive: false,
            }).addTo(linksGroup);
            polylines.push(poly);
          }
          polyIdx++;
        }
      });

      // Prune surplus polylines
      while (polylines.length > polyIdx) {
        const excess = polylines.pop();
        if (excess) linksGroup.removeLayer(excess);
      }
    }
  };

  const updateVehiclePositionsRef = useRef(updateVehiclePositions);
  updateVehiclePositionsRef.current = updateVehiclePositions;

  // Subscribe imperatively to simTime ticks without causing React component re-renders
  useEffect(() => {
    const unsubscribe = useStudioStore.subscribe((state) => {
      updateVehiclePositionsRef.current(state.simTime);
    });
    // Initial run
    updateVehiclePositionsRef.current(useStudioStore.getState().simTime);
    return () => {
      unsubscribe();
    };
  }, []);

  // Update vehicle markers when scenario, vehicles, selection, or route change
  useEffect(() => {
    updateVehiclePositionsRef.current(useStudioStore.getState().simTime);
  }, [currentScenario, vehicles, selectedNode, routeVersion]);

  // Fly-to requests (from the Node Inspector "Focus 2D" buttons)
  const flyNonce = flyToRequest?.nonce;
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyToRequest) return;
    const zoom = flyToRequest.target === 'veh' ? 15 : 14;
    map.flyTo([flyToRequest.lat, flyToRequest.lon], zoom, { duration: 0.8 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flyNonce]);

  const handleFit = () => {
    const map = mapRef.current;
    if (!map || !currentScenario) return;
    const pts: L.LatLng[] = [];
    currentScenario.gnbs?.forEach((g) => pts.push(L.latLng(g.lat, g.lon)));
    currentScenario.ground_stations?.forEach((g) => pts.push(L.latLng(g.lat, g.lon)));
    currentScenario.blind_spots?.forEach((b) => {
      pts.push(L.latLng(b.lat_min, b.lon_min));
      pts.push(L.latLng(b.lat_max, b.lon_max));
    });
    routePointsRef.current.forEach((p) => pts.push(L.latLng(p[0], p[1])));
    vehicleMarkersRef.current.forEach((m) => pts.push(m.getLatLng()));
    if (pts.length >= 2) {
      map.fitBounds(L.latLngBounds(pts), { padding: [40, 40] });
    } else if (currentScenario.bbox?.length === 4) {
      const [minLon, minLat, maxLon, maxLat] = currentScenario.bbox;
      map.fitBounds(L.latLngBounds([minLat, minLon], [maxLat, maxLon]), { padding: [40, 40] });
    } else {
      map.setView(currentScenario.center, 11);
    }
  };

  const toolButtonClass = (tool: typeof activeTool) =>
    `px-2.5 py-1 text-xs font-semibold rounded flex items-center gap-1.5 transition ${
      activeTool === tool
        ? 'bg-sky-500/20 text-brand-cyan border border-brand-cyan'
        : 'text-slate-300 hover:text-white'
    }`;

  return (
    <div className="relative w-full h-full bg-black select-none">
      <div ref={mapContainerRef} className="w-full h-full" />

      {/* Floating toolbar (top-right) */}
      <div className="absolute top-3 right-3 z-[600] bg-bg-panel/95 border border-border-medium rounded p-1 flex items-center gap-1 shadow-lg backdrop-blur">
        <button
          onClick={() => setActiveTool('select')}
          className={toolButtonClass('select')}
          title="Select nodes (click) and drag gNBs"
        >
          <MousePointer size={12} /> Select
        </button>
        <button
          onClick={() => setActiveTool('gnb')}
          className={toolButtonClass('gnb')}
          title="Click the map to deploy a 5G gNodeB"
          disabled={!currentScenario}
        >
          <Radio size={12} /> +5G gNB
        </button>
        <button
          onClick={() => setActiveTool('gs')}
          className={toolButtonClass('gs')}
          title="Click the map to deploy a satellite gateway"
          disabled={!currentScenario}
        >
          <Satellite size={12} /> +Gateway
        </button>
        <button
          onClick={() => setActiveTool('blind')}
          className={toolButtonClass('blind')}
          title="Click the map to define an RF blind-spot zone"
          disabled={!currentScenario}
        >
          <ShieldAlert size={12} /> +Blind
        </button>
        <span className="w-px h-4 bg-border-medium mx-0.5" />
        <button
          onClick={handleFit}
          className="px-2.5 py-1 text-xs font-semibold rounded flex items-center gap-1.5 text-slate-300 hover:text-white transition"
          title="Fit the scenario (nodes, route, vehicles) in view"
          disabled={!currentScenario}
        >
          <Maximize2 size={12} /> Fit
        </button>
      </div>

      {/* Legend (bottom-left) */}
      <Legend
        entries={MAP_LEGEND}
        title="Tactical legend"
        className="absolute bottom-3 left-3 z-[600] w-60 max-h-[45%] overflow-y-auto"
      />

      {/* Live coordinate / zoom readout (bottom-centre) */}
      <div className="absolute bottom-1.5 left-1/2 -translate-x-1/2 z-[600] pointer-events-none">
        <div
          ref={coordRef}
          className="text-[10px] font-mono text-slate-400 bg-bg-panel/85 border border-border-subtle rounded px-2 py-0.5 tabular-nums"
        >
          —
        </div>
      </div>

      {/* Empty state when no scenario is selected */}
      {!currentScenario && (
        <div className="absolute inset-0 z-[550] flex items-center justify-center pointer-events-none">
          <div className="bg-bg-panel/90 border border-border-medium rounded px-5 py-4 text-center">
            <span className="text-xs font-bold text-slate-200 block">No scenario selected</span>
            <span className="text-[11px] text-slate-500">
              Pick a scenario from the Scenario Library to load its map.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
