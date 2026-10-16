/**
 * NexaSim Studio Next-Gen Client Engine
 * Aerospace-Grade 2D/3D Unified Command Center & Interactive Scenario Editor
 * Horizon Europe NexaSphere Research Project
 */

// Global Application State
let map = null;
let currentScenario = null;
let activeTool = 'select';
let mapLayers = [];
let scenarioList = [];
let yamlDirty = false;
let selectedNode = null;
let wsTelemetry = null;
let wsLogs = null;

// Virtual Playback State
const playback = {
    playing: true,
    speed: 2.0,
    simTime: 0.0,
    duration: 300.0,
    lastFrameTime: null,
    vehicleMarkers: [],
    routePoints: []
};

// Drawer state
let drawerHeight = null;
let drawerPreviousHeight = null;

// ==========================================================================
// 1. Icon & Chrome Rendering
// ==========================================================================
function renderIcons() {
    if (window.lucide && typeof window.lucide.createIcons === 'function') {
        window.lucide.createIcons();
    }
}

function updateScenarioChrome(scenario) {
    const title = document.getElementById('mapScenarioTitle');
    const meta = document.getElementById('mapScenarioMeta');
    const systemScenario = document.getElementById('systemScenario');

    if (title) title.textContent = scenario?.name || 'Select a scenario';
    if (meta) {
        meta.textContent = scenario
            ? `${scenario.area_name || 'Alpine Corridor'}  /  ${scenario.duration_s || 0}s  /  ${scenario.vehicles || 4} UEs`
            : 'Awaiting scenario selection';
    }
    if (systemScenario) systemScenario.textContent = scenario?.name || 'No scenario selected';
}

function updateSystemStatus(status, tone = 'ready', runId = null) {
    const label = document.getElementById('systemStatus');
    const dot = document.getElementById('systemStateDot');
    const id = document.getElementById('systemRunId');
    if (label) label.textContent = status;
    if (dot) dot.dataset.tone = tone;
    if (id) {
        id.textContent = runId ? `RUN ${runId.slice(0, 8).toUpperCase()}` : 'LOCAL CONTROL PLANE';
    }
}

function updateTelemetryChips(tpMbps, latencyMs, activeRat) {
    const tpEl = document.getElementById('valThroughput');
    const latEl = document.getElementById('valLatency');
    const ratEl = document.getElementById('valActiveRat');

    if (tpEl && tpMbps !== undefined && tpMbps !== null) tpEl.textContent = `${Number(tpMbps).toFixed(1)} Mbps`;
    if (latEl && latencyMs !== undefined && latencyMs !== null) latEl.textContent = `${Number(latencyMs).toFixed(1)} ms`;
    if (ratEl && activeRat) ratEl.textContent = activeRat;
}

// ==========================================================================
// 2. Interactive Resizers & Layout Management
// ==========================================================================
function toggleSidebar() {
    document.body.classList.toggle('sidebar-collapsed');
    setTimeout(() => {
        if (map) map.invalidateSize();
        syncGlobeResize();
    }, 260);
}

function initSplitter() {
    const splitter = document.getElementById('viewportSplitter');
    const deck = document.getElementById('canvasDeck');
    const mapWrapper = document.getElementById('map2d-wrapper');
    const globeWrapper = document.getElementById('globe3d-container');
    const shield = document.getElementById('dragShield');

    if (!splitter || !deck || !mapWrapper || !globeWrapper) return;

    let isDragging = false;

    function startDrag(e) {
        const mode = document.querySelector('.view-btn.active')?.dataset.mode;
        if (mode !== 'dual') return;

        isDragging = true;
        splitter.classList.add('active-drag');
        if (shield) {
            shield.style.display = 'block';
            shield.style.cursor = 'col-resize';
        }
        document.body.style.userSelect = 'none';
    }

    function doDrag(e) {
        if (!isDragging) return;
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const rect = deck.getBoundingClientRect();
        const offsetX = clientX - rect.left;
        const totalWidth = rect.width;

        let pct = (offsetX / totalWidth) * 100;
        pct = Math.max(15, Math.min(85, pct)); // Clamp between 15% and 85%

        mapWrapper.style.flex = `0 0 ${pct}%`;
        globeWrapper.style.flex = `0 0 ${100 - pct}%`;

        if (map) map.invalidateSize();
    }

    function stopDrag() {
        if (!isDragging) return;
        isDragging = false;
        splitter.classList.remove('active-drag');
        if (shield) shield.style.display = 'none';
        document.body.style.userSelect = '';
        if (map) map.invalidateSize();
        syncGlobeResize();
    }

    splitter.addEventListener('mousedown', startDrag);
    splitter.addEventListener('touchstart', startDrag, { passive: true });
    window.addEventListener('mousemove', doDrag);
    window.addEventListener('touchmove', doDrag, { passive: true });
    window.addEventListener('mouseup', stopDrag);
    window.addEventListener('touchend', stopDrag);
}

function initDrawerResizer() {
    const resizer = document.getElementById('drawerResizer');
    const drawer = document.getElementById('lowerDrawer');
    const shield = document.getElementById('dragShield');

    if (!resizer || !drawer) return;

    let isDragging = false;
    let startY = 0;
    let startHeight = 0;

    function startDrag(e) {
        isDragging = true;
        resizer.classList.add('active-drag');
        drawer.classList.add('resizing');
        if (shield) {
            shield.style.display = 'block';
            shield.style.cursor = 'row-resize';
        }
        document.body.style.userSelect = 'none';

        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        startY = clientY;
        startHeight = drawer.offsetHeight;

        // Auto-open drawer if currently closed
        if (!drawer.classList.contains('open')) {
            toggleDrawer(true);
        }
    }

    function doDrag(e) {
        if (!isDragging) return;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        const delta = startY - clientY;
        let newH = startHeight + delta;

        const minH = 100;
        const maxH = window.innerHeight * 0.88;
        newH = Math.max(minH, Math.min(maxH, newH));

        drawer.style.height = `${newH}px`;
        drawerHeight = newH;
    }

    function stopDrag() {
        if (!isDragging) return;
        isDragging = false;
        resizer.classList.remove('active-drag');
        drawer.classList.remove('resizing');
        if (shield) shield.style.display = 'none';
        document.body.style.userSelect = '';
    }

    resizer.addEventListener('mousedown', startDrag);
    resizer.addEventListener('touchstart', startDrag, { passive: true });
    window.addEventListener('mousemove', doDrag);
    window.addEventListener('touchmove', doDrag, { passive: true });
    window.addEventListener('mouseup', stopDrag);
    window.addEventListener('touchend', stopDrag);
}

function toggleDrawer(forceOpen = null) {
    const drawer = document.getElementById('lowerDrawer');
    const chevron = document.getElementById('drawerChevron');
    const text = document.getElementById('drawerHandleText');

    if (forceOpen === true) {
        drawer.classList.add('open');
    } else if (forceOpen === false) {
        drawer.classList.remove('open');
    } else {
        drawer.classList.toggle('open');
    }

    const isOpen = drawer.classList.contains('open');
    if (isOpen) {
        chevron?.setAttribute('data-lucide', 'chevron-down');
        if (text) text.textContent = 'Close Analytics & Console';
        if (drawerHeight) drawer.style.height = `${drawerHeight}px`;
    } else {
        chevron?.setAttribute('data-lucide', 'chevron-up');
        if (text) text.textContent = 'Open Dashboard & Console';
    }
    renderIcons();
}

function toggleDrawerMax() {
    const drawer = document.getElementById('lowerDrawer');
    const maxIcon = document.getElementById('drawerMaxIcon');
    if (!drawer) return;

    if (!drawer.classList.contains('open')) {
        toggleDrawer(true);
    }

    const maxH = Math.round(window.innerHeight * 0.85);
    if (drawer.offsetHeight >= maxH - 20) {
        // Restore to normal
        const restoredH = drawerPreviousHeight || Math.round(window.innerHeight * 0.45);
        drawer.style.height = `${restoredH}px`;
        drawerHeight = restoredH;
        maxIcon?.setAttribute('data-lucide', 'maximize-2');
    } else {
        // Maximize
        drawerPreviousHeight = drawer.offsetHeight;
        drawer.style.height = `${maxH}px`;
        drawerHeight = maxH;
        maxIcon?.setAttribute('data-lucide', 'minimize-2');
    }
    renderIcons();
}

function syncGlobeResize() {
    try {
        const frame = document.getElementById('globe3d-frame');
        if (frame && frame.contentWindow) {
            frame.contentWindow.dispatchEvent(new Event('resize'));
        }
    } catch (e) {}
}

// ==========================================================================
// 3. Leaflet 2D Map Initialization & Basemaps
// ==========================================================================
function initMap() {
    if (map) return;
    if (typeof L === 'undefined') {
        setTimeout(initMap, 100);
        return;
    }

    map = L.map('map2d', {
        zoomControl: false,
        attributionControl: false
    }).setView([46.5286, 10.4531], 10);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    const cartoKey = window.NEXASIM_CONFIG?.cartoApiKey || '';
    const cartoParam = cartoKey ? `?key=${cartoKey}` : '';

    const cartoDark = L.tileLayer(`https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png${cartoParam}`, {
        subdomains: 'abcd',
        maxZoom: 19,
        attribution: '© CARTO'
    });

    const esriDark = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: '© Esri'
    });

    const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19,
        attribution: '© Esri Satellite'
    });

    const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '© OpenStreetMap'
    });

    (cartoKey ? cartoDark : esriDark).addTo(map);

    L.control.layers({
        "🌌 ESRI Tactical Dark": esriDark,
        "🗺️ CARTO Dark Matter": cartoDark,
        "🛰️ ESRI Satellite HD": esriSat,
        "🗺️ OpenStreetMap": osmStandard
    }, null, { position: 'topleft' }).addTo(map);

    map.on('click', function(e) {
        if (activeTool && activeTool !== 'select') {
            handleMapClickTool(e.latlng);
        } else {
            // Click on empty space deselects node
            closeNodeInspector();
        }
    });

    map.on('moveend', function() {
        const activeBtn = document.querySelector('.view-btn.active');
        if (activeBtn && activeBtn.dataset.mode === 'dual') {
            const center = map.getCenter();
            const zoom = map.getZoom();
            const globeFrame = document.getElementById('globe3d-frame');
            if (globeFrame && globeFrame.contentWindow) {
                try {
                    const targetAlt = Math.max(1000, 28000000 / Math.pow(2, zoom));
                    globeFrame.contentWindow.postMessage({
                        action: 'syncCamera',
                        lat: center.lat,
                        lon: center.lng,
                        altitude: targetAlt
                    }, '*');
                } catch (e) {}
            }
        }
    });

    window.addEventListener('resize', () => {
        if (map) map.invalidateSize();
    });
}

// ==========================================================================
// 4. Scenario Catalog & Filtering
// ==========================================================================
async function loadScenarios() {
    try {
        const res = await fetch('/api/scenarios');
        const list = await res.json();
        scenarioList = list;

        const countEl = document.getElementById('scCount');
        if (countEl) countEl.textContent = list.length;

        renderScenarioCards(list);
    } catch (err) {
        console.error("Failed to load scenarios:", err);
    }
}

function renderScenarioCards(list) {
    const container = document.getElementById('scenarioList');
    if (!container) return;
    container.innerHTML = '';

    if (!list || list.length === 0) {
        container.innerHTML = '<div class="sidebar-loading">No matching scenarios found.</div>';
        return;
    }

    list.forEach((sc, idx) => {
        const card = document.createElement('div');
        card.className = 'scenario-card' + (currentScenario && currentScenario.id === sc.id ? ' active' : (idx === 0 && !currentScenario ? ' active' : ''));
        card.id = 'sc-card-' + sc.id;
        card.onclick = () => selectScenario(sc);
        card.innerHTML = `
            <div class="sc-card-title">${sc.name}</div>
            <div style="font-size:11px; color:var(--text-secondary);">${sc.area_name || 'Standard Area'}</div>
            <div class="sc-card-badges">
                <span class="badge badge-sat"><i data-lucide="satellite" size="10"></i> ${sc.satellites || 0} Sats</span>
                <span class="badge badge-gnb"><i data-lucide="radio" size="10"></i> ${sc.gnbs ? sc.gnbs.length : 0} gNBs</span>
                <span class="badge badge-ue"><i data-lucide="car" size="10"></i> ${sc.vehicles || 4} UEs</span>
            </div>
        `;
        container.appendChild(card);
        if (idx === 0 && !currentScenario) {
            selectScenario(sc);
        }
    });

    renderIcons();
}

function filterScenarios(query) {
    const q = (query || '').toLowerCase().trim();
    if (!q) {
        renderScenarioCards(scenarioList);
        return;
    }
    const filtered = scenarioList.filter(sc =>
        sc.name.toLowerCase().includes(q) ||
        (sc.area_name && sc.area_name.toLowerCase().includes(q)) ||
        (sc.description && sc.description.toLowerCase().includes(q))
    );
    renderScenarioCards(filtered);
}

function selectScenario(sc) {
    currentScenario = sc;
    playback.simTime = 0.0;
    playback.duration = sc.duration_s || 300.0;
    closeNodeInspector();

    updateScenarioChrome(sc);
    updateSystemStatus('READY FOR DISPATCH', 'ready', null);

    document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active'));
    const activeCard = document.getElementById('sc-card-' + sc.id);
    if (activeCard) activeCard.classList.add('active');

    // Populate Sidebar Details Pane
    const details = document.getElementById('scDetails');
    if (details) {
        details.innerHTML = `
            <div style="margin-bottom:6px;"><strong>Name:</strong> ${sc.name}</div>
            <div style="margin-bottom:6px;"><strong>Area:</strong> ${sc.area_name}</div>
            <div style="margin-bottom:6px;"><strong>Duration:</strong> ${sc.duration_s}s</div>
            <div style="margin-bottom:6px;"><strong>Elevation Mask:</strong> ${sc.elevation_mask_deg}°</div>
            <div style="margin-bottom:6px;"><strong>5G gNodeBs:</strong> ${sc.gnbs ? sc.gnbs.length : 0}</div>
            <div style="margin-bottom:6px;"><strong>Ground Gateways:</strong> ${sc.ground_stations ? sc.ground_stations.length : 0}</div>
            <div style="margin-bottom:6px;"><strong>Blind Spots:</strong> ${sc.blind_spots ? sc.blind_spots.length : 0}</div>
            <div style="font-size:10px; color:var(--text-muted); margin-top:8px; line-height:1.4;">${sc.description || ''}</div>
        `;
    }

    // Populate Config Tab
    const stratSelect = document.getElementById('cfgStrategy');
    if (stratSelect && sc.switching_mode) stratSelect.value = sc.switching_mode;
    const rainInput = document.getElementById('cfgRain');
    if (rainInput && sc.rain_rate !== undefined) rainInput.value = sc.rain_rate;
    const elevInput = document.getElementById('cfgElevMask');
    if (elevInput && sc.elevation_mask_deg !== undefined) elevInput.value = sc.elevation_mask_deg;
    const durInput = document.getElementById('cfgDuration');
    if (durInput && sc.duration_s !== undefined) durInput.value = sc.duration_s;
    const ueInput = document.getElementById('cfgUeCount');
    if (ueInput && sc.vehicles !== undefined) ueInput.value = sc.vehicles;

    // Render Geometries on 2D Leaflet
    if (map && sc.center) {
        map.setView(sc.center, 11);
        renderScenarioOnMap(sc);
    }

    // Update 3D Globe
    const shortName = sc.short_name || sc.id;
    const globeFrame = document.getElementById('globe3d-frame');
    const globeEmpty = document.getElementById('globeEmptyState');

    if (sc.has_globe) {
        if (globeEmpty) globeEmpty.style.display = 'none';
        if (globeFrame) {
            globeFrame.style.display = 'block';
            const curMode = document.querySelector('.view-btn.active')?.dataset.mode;
            globeFrame.src = `/results/${shortName}/results/globe.html${curMode === 'dual' ? '?hud=0' : ''}`;
        }
    } else {
        if (globeFrame) {
            globeFrame.src = 'about:blank';
            globeFrame.style.display = 'none';
        }
        if (globeEmpty) globeEmpty.style.display = 'flex';
    }

    // Update Executive Dashboard Frame
    const dashFrame = document.getElementById('dashFrame');
    if (dashFrame) {
        dashFrame.src = sc.has_dashboard ? `/results/${shortName}/results/dashboard.html` : 'about:blank';
    }

    // Initialize Fleet Telemetry Table
    initFleetTable(sc);
}

// ==========================================================================
// 5. Draggable Map Geometries & Node Inspector
// ==========================================================================
function renderScenarioOnMap(sc) {
    mapLayers.forEach(l => map.removeLayer(l));
    mapLayers = [];

    // 1. Simulation Area Bounding Box
    if (sc.bbox && sc.bbox.length === 4) {
        const [minLon, minLat, maxLon, maxLat] = sc.bbox;
        const bboxPoly = L.rectangle([[minLat, minLon], [maxLat, maxLon]], {
            color: '#38bdf8',
            weight: 1.5,
            dashArray: '6, 6',
            fillOpacity: 0.04
        }).addTo(map);
        bboxPoly.bindTooltip(`Simulation Area: ${sc.area_name}`, { sticky: true });
        mapLayers.push(bboxPoly);
    }

    // 2. 5G-NR gNodeBs (Draggable markers with synchronized coverage circles)
    if (sc.gnbs) {
        sc.gnbs.forEach((gnb, i) => {
            const radius = gnb.coverage_radius_m || 1500;
            const covCircle = L.circle([gnb.lat, gnb.lon], {
                radius: radius,
                color: '#10b981',
                weight: 1,
                fillColor: '#10b981',
                fillOpacity: 0.12
            }).addTo(map);
            mapLayers.push(covCircle);

            const marker = L.circleMarker([gnb.lat, gnb.lon], {
                radius: 8,
                color: '#ffffff',
                weight: 2,
                fillColor: '#10b981',
                fillOpacity: 1.0
            }).addTo(map);

            // Click opens Inspector
            marker.on('click', (e) => {
                L.DomEvent.stopPropagation(e);
                openNodeInspector(gnb, 'gnb', i, marker, covCircle);
            });

            // Draggable Marker Handling
            makeMarkerDraggable(marker, gnb, covCircle);
            mapLayers.push(marker);
        });
    }

    // 3. NTN Ground Gateways
    if (sc.ground_stations) {
        sc.ground_stations.forEach((gw, i) => {
            const marker = L.circleMarker([gw.lat, gw.lon], {
                radius: 8,
                color: '#ffffff',
                weight: 2,
                fillColor: '#f59e0b',
                fillOpacity: 1.0
            }).addTo(map);

            marker.on('click', (e) => {
                L.DomEvent.stopPropagation(e);
                openNodeInspector(gw, 'gs', i, marker);
            });

            makeMarkerDraggable(marker, gw);
            mapLayers.push(marker);
        });
    }

    // 4. Blind Spots
    if (sc.blind_spots) {
        sc.blind_spots.forEach((bs, i) => {
            if (bs.lat_min && bs.lat_max && bs.lon_min && bs.lon_max) {
                const bounds = [[bs.lat_min, bs.lon_min], [bs.lat_max, bs.lon_max]];
                const bsRect = L.rectangle(bounds, {
                    color: '#ef4444',
                    weight: 2,
                    fillColor: '#ef4444',
                    fillOpacity: 0.35
                }).addTo(map);

                bsRect.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    openNodeInspector(bs, 'blind', i, bsRect);
                });

                bsRect.bindTooltip(`⛰️ Blind Spot: ${bs.name || 'Zone ' + i}`, { sticky: true });
                mapLayers.push(bsRect);
            }
        });
    }

    // 5. Dynamic Vehicle Trajectories & Sidelink Convoy
    if (sc.center) {
        fetch(`/api/route?name=${encodeURIComponent(sc.id)}`)
            .then(res => res.json())
            .then(routeData => {
                let pts = [];
                if (routeData && routeData.coordinates && routeData.coordinates.length >= 2) {
                    pts = routeData.coordinates;
                } else {
                    for (let t = 0; t <= sc.duration_s; t += 2) {
                        pts.push([sc.center[0] + (t / sc.duration_s) * 0.025 - 0.01, sc.center[1] + (t / sc.duration_s) * 0.015]);
                    }
                }
                playback.routePoints = pts;
                setupVehicleAnimation(sc, pts);
            })
            .catch(() => {
                const fallback = [];
                for (let t = 0; t <= sc.duration_s; t += 2) {
                    fallback.push([sc.center[0] + (t / sc.duration_s) * 0.02, sc.center[1] + (t / sc.duration_s) * 0.015]);
                }
                playback.routePoints = fallback;
                setupVehicleAnimation(sc, fallback);
            });
    }
}

function makeMarkerDraggable(marker, nodeData, circle = null) {
    let isMoving = false;

    marker.on('mousedown', function(e) {
        if (activeTool !== 'select') return;
        isMoving = true;
        map.dragging.disable();

        function onMouseMove(moveEvent) {
            if (!isMoving) return;
            const newLL = moveEvent.latlng;
            marker.setLatLng(newLL);
            if (circle) circle.setLatLng(newLL);
            nodeData.lat = parseFloat(newLL.lat.toFixed(5));
            nodeData.lon = parseFloat(newLL.lng.toFixed(5));
            updateInspectorCoordinates(nodeData.lat, nodeData.lon);
        }

        function onMouseUp() {
            if (!isMoving) return;
            isMoving = false;
            map.dragging.enable();
            map.off('mousemove', onMouseMove);
            map.off('mouseup', onMouseUp);
            markYamlDirty();
            showToast(`${nodeData.name || 'Node'} position updated. Click Save to persist.`, 'info', 2500);
        }

        map.on('mousemove', onMouseMove);
        map.on('mouseup', onMouseUp);
    });
}

// ==========================================================================
// 6. Node Property Inspector
// ==========================================================================
function openNodeInspector(node, type, index, markerRef, circleRef = null) {
    selectedNode = { data: node, type: type, index: index, marker: markerRef, circle: circleRef };

    const pane = document.getElementById('nodeInspector');
    const heading = document.getElementById('inspectorHeading');
    const body = document.getElementById('inspectorBody');
    if (!pane || !heading || !body) return;

    if (type === 'gnb') {
        heading.textContent = `5G-NR gNodeB: ${node.name || 'gNB ' + index}`;
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Identifier</label>
                <input type="text" class="form-input" id="inspName" value="${node.name || ''}">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div class="form-group">
                    <label class="form-label">Latitude</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLat" value="${node.lat}">
                </div>
                <div class="form-group">
                    <label class="form-label">Longitude</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLon" value="${node.lon}">
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div class="form-group">
                    <label class="form-label">Antenna Height (m)</label>
                    <input type="number" class="form-input" id="inspHeight" value="${node.height_m || 25}">
                </div>
                <div class="form-group">
                    <label class="form-label">Tx Power (dBm)</label>
                    <input type="number" class="form-input" id="inspPower" value="${node.tx_power_dbm || 46}">
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div class="form-group">
                    <label class="form-label">Carrier Freq (GHz)</label>
                    <input type="number" step="0.1" class="form-input" id="inspFreq" value="${node.frequency_ghz || 3.5}">
                </div>
                <div class="form-group">
                    <label class="form-label">Coverage Radius (m)</label>
                    <input type="number" class="form-input" id="inspRadius" value="${node.coverage_radius_m || 1500}">
                </div>
            </div>
        `;
    } else if (type === 'gs') {
        heading.textContent = `NTN Gateway: ${node.name || 'Gateway ' + index}`;
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Identifier</label>
                <input type="text" class="form-input" id="inspName" value="${node.name || ''}">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div class="form-group">
                    <label class="form-label">Latitude</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLat" value="${node.lat}">
                </div>
                <div class="form-group">
                    <label class="form-label">Longitude</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLon" value="${node.lon}">
                </div>
            </div>
            <div class="form-group">
                <label class="form-label">Altitude ASL (m)</label>
                <input type="number" class="form-input" id="inspAlt" value="${node.altitude_m || 250}">
            </div>
        `;
    } else if (type === 'blind') {
        heading.textContent = `RF Blind Spot: ${node.name || 'Zone ' + index}`;
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Identifier</label>
                <input type="text" class="form-input" id="inspName" value="${node.name || ''}">
            </div>
            <div class="form-group">
                <label class="form-label">Attenuation (dB)</label>
                <input type="number" class="form-input" id="inspAtten" value="${node.attenuation_db || 45.0}">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                <div class="form-group">
                    <label class="form-label">Lat Min</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLatMin" value="${node.lat_min}">
                </div>
                <div class="form-group">
                    <label class="form-label">Lat Max</label>
                    <input type="number" step="0.0001" class="form-input" id="inspLatMax" value="${node.lat_max}">
                </div>
            </div>
        `;
    }

    pane.style.display = 'flex';
    renderIcons();
}

function updateInspectorCoordinates(lat, lon) {
    const latIn = document.getElementById('inspLat');
    const lonIn = document.getElementById('inspLon');
    if (latIn) latIn.value = lat;
    if (lonIn) lonIn.value = lon;
}

function closeNodeInspector() {
    const pane = document.getElementById('nodeInspector');
    if (pane) pane.style.display = 'none';
    selectedNode = null;
}

function applyNodeInspectorChanges() {
    if (!selectedNode || !selectedNode.data) return;
    const { data, type, marker, circle } = selectedNode;

    const name = document.getElementById('inspName')?.value?.trim();
    if (name) data.name = name;

    if (type === 'gnb') {
        data.lat = parseFloat(document.getElementById('inspLat')?.value) || data.lat;
        data.lon = parseFloat(document.getElementById('inspLon')?.value) || data.lon;
        data.height_m = Number(document.getElementById('inspHeight')?.value) || data.height_m;
        data.tx_power_dbm = Number(document.getElementById('inspPower')?.value) || data.tx_power_dbm;
        data.frequency_ghz = Number(document.getElementById('inspFreq')?.value) || data.frequency_ghz;
        data.coverage_radius_m = Number(document.getElementById('inspRadius')?.value) || data.coverage_radius_m;

        if (marker) marker.setLatLng([data.lat, data.lon]);
        if (circle) {
            circle.setLatLng([data.lat, data.lon]);
            circle.setRadius(data.coverage_radius_m);
        }
    } else if (type === 'gs') {
        data.lat = parseFloat(document.getElementById('inspLat')?.value) || data.lat;
        data.lon = parseFloat(document.getElementById('inspLon')?.value) || data.lon;
        data.altitude_m = Number(document.getElementById('inspAlt')?.value) || data.altitude_m;
        if (marker) marker.setLatLng([data.lat, data.lon]);
    } else if (type === 'blind') {
        data.attenuation_db = Number(document.getElementById('inspAtten')?.value) || data.attenuation_db;
        data.lat_min = parseFloat(document.getElementById('inspLatMin')?.value) || data.lat_min;
        data.lat_max = parseFloat(document.getElementById('inspLatMax')?.value) || data.lat_max;
        if (marker && marker.setBounds) {
            marker.setBounds([[data.lat_min, data.lon_min], [data.lat_max, data.lon_max]]);
        }
    }

    markYamlDirty();
    showToast(`Updated '${data.name || type}'. Save to persist.`, 'info');
    closeNodeInspector();
}

function deleteSelectedNode() {
    if (!selectedNode || !currentScenario) return;
    const { type, index } = selectedNode;

    if (type === 'gnb' && currentScenario.gnbs) {
        currentScenario.gnbs.splice(index, 1);
    } else if (type === 'gs' && currentScenario.ground_stations) {
        currentScenario.ground_stations.splice(index, 1);
    } else if (type === 'blind' && currentScenario.blind_spots) {
        currentScenario.blind_spots.splice(index, 1);
    }

    closeNodeInspector();
    renderScenarioOnMap(currentScenario);
    markYamlDirty();
    showToast("Node deleted from scenario. Click Save to persist.", "info");
}

// ==========================================================================
// 7. Simulation Playback Controls & Convoy Animation
// ==========================================================================
function togglePlayback() {
    playback.playing = !playback.playing;
    const icon = document.getElementById('playerPlayIcon');
    if (icon) {
        icon.setAttribute('data-lucide', playback.playing ? 'pause' : 'play');
    }
    renderIcons();
}

function stepPlayback(delta = 2.0) {
    playback.simTime = (playback.simTime + delta) % playback.duration;
    updatePlaybackClock();
}

function setPlaybackSpeed(val) {
    playback.speed = parseFloat(val) || 2.0;
}

function updatePlaybackClock() {
    const el = document.getElementById('playerTimeDisplay');
    if (el) {
        const m = Math.floor(playback.simTime / 60);
        const s = (playback.simTime % 60).toFixed(1);
        el.textContent = `T+${String(m).padStart(2, '0')}:${String(s).padStart(4, '0')}s`;
    }
}

function setupVehicleAnimation(sc, routePoints) {
    const routeLine = L.polyline(routePoints, {
        color: '#ec4899',
        weight: 3.5,
        opacity: 0.8,
        dashArray: '6, 8'
    }).addTo(map);
    mapLayers.push(routeLine);

    if (window.vehicleAnimTimer) {
        cancelAnimationFrame(window.vehicleAnimTimer);
        window.vehicleAnimTimer = null;
    }

    const numVehicles = Math.min(sc.vehicles || 4, 8);
    const vehicleMarkers = [];

    for (let v = 0; v < numVehicles; v++) {
        const isLeader = (v === 0);
        const icon = L.divIcon({
            className: 'veh-icon-wrapper',
            html: `<div id="veh-icon-${v}" style="
                background: #10b981;
                border: 2px solid #ffffff;
                border-radius: 50%;
                width: ${isLeader ? 18 : 13}px;
                height: ${isLeader ? 18 : 13}px;
                box-shadow: 0 0 12px #10b981;
                display: flex; align-items: center; justify-content: center;
                font-size: ${isLeader ? 10 : 8}px; font-weight: bold; color: #000;
                transition: background-color 0.2s ease, box-shadow 0.2s ease;
            ">${isLeader ? '★' : v}</div>`,
            iconSize: [isLeader ? 18 : 13, isLeader ? 18 : 13],
            iconAnchor: [isLeader ? 9 : 6, isLeader ? 9 : 6]
        });

        const marker = L.marker(routePoints[0], { icon: icon }).addTo(map);
        mapLayers.push(marker);

        vehicleMarkers.push({
            marker: marker,
            vIdx: v,
            isLeader: isLeader,
            inBlind: false
        });
    }

    playback.vehicleMarkers = vehicleMarkers;

    function animateVehicles(timestamp) {
        if (!playback.lastFrameTime) playback.lastFrameTime = timestamp;
        const deltaMs = timestamp - playback.lastFrameTime;

        if (deltaMs >= 40) { // ~25 fps throttle
            playback.lastFrameTime = timestamp;

            if (playback.playing) {
                playback.simTime = (playback.simTime + (deltaMs / 1000) * playback.speed * 4.0) % playback.duration;
                updatePlaybackClock();
            }

            vehicleMarkers.forEach(vm => {
                const curProgress = ((playback.simTime / playback.duration) + vm.vIdx * 0.04) % 1.0;
                const idx = Math.floor(curProgress * (routePoints.length - 1));
                const curPos = routePoints[idx];
                vm.marker.setLatLng(curPos);

                // Blind spot check
                let inBlind = false;
                if (sc.blind_spots) {
                    inBlind = sc.blind_spots.some(bs =>
                        curPos[0] >= bs.lat_min && curPos[0] <= bs.lat_max &&
                        curPos[1] >= bs.lon_min && curPos[1] <= bs.lon_max
                    );
                }

                if (inBlind !== vm.inBlind) {
                    vm.inBlind = inBlind;
                    const ratColor = inBlind ? '#38bdf8' : '#10b981';
                    const el = document.getElementById(`veh-icon-${vm.vIdx}`);
                    if (el) {
                        el.style.background = ratColor;
                        el.style.boxShadow = `0 0 12px ${ratColor}`;
                    }
                    updateFleetTableRow(vm.vIdx, inBlind);
                }
            });
        }
        window.vehicleAnimTimer = requestAnimationFrame(animateVehicles);
    }

    window.vehicleAnimTimer = requestAnimationFrame(animateVehicles);
}

// ==========================================================================
// 8. Fleet Telemetry Table
// ==========================================================================
function initFleetTable(sc) {
    const tbody = document.getElementById('fleetTableBody');
    const badge = document.getElementById('fleetVehicleCountBadge');
    if (!tbody) return;

    const count = Math.min(sc.vehicles || 4, 8);
    if (badge) badge.textContent = `${count} Vehicles`;

    tbody.innerHTML = '';
    for (let i = 0; i < count; i++) {
        const isLeader = (i === 0);
        const row = document.createElement('tr');
        row.id = `fleet-row-${i}`;
        row.innerHTML = `
            <td><strong>Vehicle ${i}</strong> ${isLeader ? '<span style="color:var(--accent-amber); font-size:10px;">(Leader)</span>' : ''}</td>
            <td><span class="badge badge-gnb" id="f-link-${i}">5G-NR Terrestrial</span></td>
            <td><span id="f-status-${i}" style="color:var(--accent-green);">🟢 Primary Connected</span></td>
            <td><span id="f-speed-${i}">48.5</span></td>
            <td><span id="f-lat-${i}">5.2 ms</span></td>
            <td><span id="f-qos-${i}">0.94</span></td>
            <td><span id="f-soc-${i}">98.5%</span></td>
            <td><span id="f-vho-${i}">0</span></td>
        `;
        tbody.appendChild(row);
    }
}

function updateFleetTableRow(vIdx, inBlind) {
    const linkEl = document.getElementById(`f-link-${vIdx}`);
    const statusEl = document.getElementById(`f-status-${vIdx}`);
    const latEl = document.getElementById(`f-lat-${vIdx}`);

    if (linkEl) {
        linkEl.className = inBlind ? 'badge badge-sat' : 'badge badge-gnb';
        linkEl.textContent = inBlind ? 'Satellite LEO NTN' : '5G-NR Terrestrial';
    }
    if (statusEl) {
        statusEl.innerHTML = inBlind
            ? '<span style="color:var(--brand-cyan);">🌐 Satellite Handover Active</span>'
            : '<span style="color:var(--accent-green);">🟢 5G Primary Connected</span>';
    }
    if (latEl) {
        latEl.textContent = inBlind ? '23.4 ms' : '5.1 ms';
    }

    if (vIdx === 0) {
        updateTelemetryChips(inBlind ? 62.4 : 94.8, inBlind ? 23.4 : 5.1, inBlind ? 'NTN/LEO' : 'TN/5G');
    }
}

// ==========================================================================
// 9. View Switcher (2D / Dual / 3D)
// ==========================================================================
function switchView(mode) {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    const targetBtn = document.querySelector(`.view-btn[data-mode="${mode}"]`);
    if (targetBtn) targetBtn.classList.add('active');

    const mWrapper = document.getElementById('map2d-wrapper');
    const gContainer = document.getElementById('globe3d-container');
    const splitter = document.getElementById('viewportSplitter');
    const tools = document.getElementById('mapTools');
    const gFrame = document.getElementById('globe3d-frame');

    if (mode === '2d') {
        mWrapper.style.display = 'block';
        mWrapper.style.flex = '1 1 100%';
        gContainer.style.display = 'none';
        if (splitter) splitter.style.display = 'none';
        if (tools) tools.style.display = 'flex';
    } else if (mode === '3d') {
        mWrapper.style.display = 'none';
        gContainer.style.display = 'block';
        gContainer.style.flex = '1 1 100%';
        if (splitter) splitter.style.display = 'none';
        if (tools) tools.style.display = 'none';

        try {
            if (gFrame && gFrame.contentWindow) {
                gFrame.contentWindow.postMessage({ showHud: true }, '*');
            }
        } catch (e) {}
    } else if (mode === 'dual') {
        mWrapper.style.display = 'block';
        mWrapper.style.flex = '0 0 50%';
        gContainer.style.display = 'block';
        gContainer.style.flex = '0 0 50%';
        if (splitter) splitter.style.display = 'flex';
        if (tools) tools.style.display = 'none';

        try {
            if (gFrame && gFrame.contentWindow) {
                gFrame.contentWindow.postMessage({ showHud: false }, '*');
            }
        } catch (e) {}
    }

    setTimeout(() => {
        if (map) map.invalidateSize();
        syncGlobeResize();
    }, 200);
}

function switchDrawerTab(paneId) {
    document.querySelectorAll('.drawer-tab').forEach(b => b.classList.remove('active'));
    const activeTab = document.querySelector(`.drawer-tab[data-pane="${paneId}"]`);
    if (activeTab) activeTab.classList.add('active');

    document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));
    const activePane = document.getElementById(paneId);
    if (activePane) activePane.classList.add('active');
}

// ==========================================================================
// 10. Real-Time WebSocket Streaming & Simulation Execution
// ==========================================================================
function initWebSockets() {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;

    try {
        wsTelemetry = new WebSocket(`${proto}//${host}/ws/telemetry`);
        wsTelemetry.onopen = () => {
            const dot = document.getElementById('wsDot');
            if (dot) dot.className = 'ws-dot online';
        };
        wsTelemetry.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'telemetry') {
                    updateTelemetryChips(data.throughput_mbps, data.latency_ms, data.active_rat);
                }
            } catch (e) {}
        };
        wsTelemetry.onclose = () => {
            const dot = document.getElementById('wsDot');
            if (dot) dot.className = 'ws-dot';
            setTimeout(initWebSockets, 5000);
        };
    } catch (e) {}

    try {
        wsLogs = new WebSocket(`${proto}//${host}/ws/logs`);
        wsLogs.onmessage = (event) => {
            const term = document.getElementById('termLogs');
            if (term && event.data) {
                term.textContent += event.data + '\n';
                term.scrollTop = term.scrollHeight;
            }
        };
    } catch (e) {}
}

async function runSimulation() {
    if (!currentScenario) return;

    const btn = document.getElementById('runBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i data-lucide="loader" class="spin" size="14"></i> Simulating...';
    }
    renderIcons();

    // Open drawer to console tab
    toggleDrawer(true);
    switchDrawerTab('pane-console');

    const term = document.getElementById('termLogs');
    if (term) term.textContent = `[*] Dispatching simulation job for '${currentScenario.id}'...\n`;
    updateSystemStatus('DISPATCHING SIMULATION', 'busy');

    try {
        const res = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: currentScenario.id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Simulation dispatch failed');

        updateSystemStatus('SIMULATION RUNNING', 'busy', data.run_id);
        pollSimulation();
    } catch (err) {
        const message = err.message || String(err);
        if (term) term.textContent += `[!] Run dispatch error: ${message}\n`;
        updateSystemStatus('DISPATCH FAILED', 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i data-lucide="play" size="14"></i> Run Simulation';
        }
        renderIcons();
    }
}

function pollSimulation() {
    const term = document.getElementById('termLogs');
    const interval = setInterval(async () => {
        try {
            const res = await fetch('/api/status');
            const st = await res.json();

            if (st.logs && st.logs.length > 0 && term) {
                term.textContent = st.logs.join('\n');
                term.scrollTop = term.scrollHeight;
            }

            if (!st.running) {
                clearInterval(interval);
                updateSystemStatus(
                    st.exit_code === 0 ? 'RUN COMPLETE' : 'RUN FAILED',
                    st.exit_code === 0 ? 'ready' : 'error',
                    st.run_id
                );

                const btn = document.getElementById('runBtn');
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i data-lucide="play" size="14"></i> Run Simulation';
                }
                renderIcons();

                if (st.exit_code !== 0) {
                    showToast(`Simulation failed (exit code ${st.exit_code})`, 'error', 6000);
                    return;
                }

                const shortName = currentScenario.short_name || currentScenario.id;
                const dashFrame = document.getElementById('dashFrame');
                if (dashFrame) {
                    dashFrame.src = `/results/${shortName}/results/dashboard.html?t=${Date.now()}`;
                }
                switchDrawerTab('pane-dash');
                buildDigitalTwin3D();
            }
        } catch (e) {
            console.error("Status polling error:", e);
        }
    }, 1200);
}

async function buildDigitalTwin3D() {
    if (!currentScenario) return;

    const btn = document.getElementById('sync3dBtn');
    const oldHtml = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<i data-lucide="loader" class="spin" size="14"></i> Syncing...';
    renderIcons();

    try {
        const res = await fetch('/api/view3d', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: currentScenario.id })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || '3D twin generation failed');

        const shortName = currentScenario.short_name || currentScenario.id;
        currentScenario.has_globe = true;

        const globeEmpty = document.getElementById('globeEmptyState');
        if (globeEmpty) globeEmpty.style.display = 'none';

        const globeFrame = document.getElementById('globe3d-frame');
        if (globeFrame) {
            globeFrame.style.display = 'block';
            globeFrame.src = `/results/${shortName}/results/globe.html?t=${Date.now()}`;
        }
        showToast("3D Digital Twin synchronized!", "success");
    } catch (e) {
        showToast(`3D Twin error: ${e.message}`, "error");
    } finally {
        if (btn) btn.innerHTML = oldHtml;
        renderIcons();
    }
}

// ==========================================================================
// 11. Scenario Saving & Map Tools
// ==========================================================================
function toggleTool(toolName) {
    document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active-tool'));
    if (activeTool === toolName) {
        activeTool = 'select';
        const selBtn = document.getElementById('toolSelectBtn');
        if (selBtn) selBtn.classList.add('active-tool');
    } else {
        activeTool = toolName;
        const btn = document.getElementById(`tool${toolName.charAt(0).toUpperCase() + toolName.slice(1)}Btn`);
        if (btn) btn.classList.add('active-tool');
    }
}

let pendingPlacement = null;

function handleMapClickTool(latlng) {
    if (!currentScenario || !activeTool || activeTool === 'select') return;
    pendingPlacement = { tool: activeTool, latlng: latlng };

    const backdrop = document.getElementById('nodeModalBackdrop');
    const heading = document.getElementById('nodeModalHeading');
    const body = document.getElementById('nodeModalBody');
    if (!backdrop || !heading || !body) return;

    const lat = parseFloat(latlng.lat.toFixed(5));
    const lon = parseFloat(latlng.lng.toFixed(5));

    if (activeTool === 'gnb') {
        heading.textContent = "Deploy 5G-NR gNodeB";
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Station Identifier</label>
                <input type="text" class="form-input" id="nmName" value="gnb_site_${Date.now() % 1000}">
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                <div class="form-group">
                    <label class="form-label">Antenna Height (m)</label>
                    <input type="number" class="form-input" id="nmHeight" value="25">
                </div>
                <div class="form-group">
                    <label class="form-label">Tx Power (dBm)</label>
                    <input type="number" class="form-input" id="nmPower" value="46">
                </div>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
                <div class="form-group">
                    <label class="form-label">Frequency (GHz)</label>
                    <input type="number" step="0.1" class="form-input" id="nmFreq" value="3.5">
                </div>
                <div class="form-group">
                    <label class="form-label">Coverage Radius (m)</label>
                    <input type="number" class="form-input" id="nmRadius" value="1500">
                </div>
            </div>
            <div style="font-size:11px; color:var(--text-muted);">Coordinates: ${lat}°, ${lon}°</div>
        `;
    } else if (activeTool === 'gs') {
        heading.textContent = "Deploy NTN Satellite Gateway";
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Gateway Identifier</label>
                <input type="text" class="form-input" id="nmName" value="gw_site_${Date.now() % 1000}">
            </div>
            <div class="form-group">
                <label class="form-label">Altitude ASL (m)</label>
                <input type="number" class="form-input" id="nmAlt" value="250">
            </div>
            <div style="font-size:11px; color:var(--text-muted);">Coordinates: ${lat}°, ${lon}° (Ka-Band Feeder)</div>
        `;
    } else if (activeTool === 'blind') {
        heading.textContent = "Define RF Shadow / Blind Spot";
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">Zone Identifier</label>
                <input type="text" class="form-input" id="nmName" value="shadow_${Date.now() % 1000}">
            </div>
            <div class="form-group">
                <label class="form-label">Attenuation (dB)</label>
                <input type="number" class="form-input" id="nmAtten" value="45.0">
            </div>
            <div class="form-group">
                <label class="form-label">Radius Span (°)</label>
                <input type="number" step="0.001" class="form-input" id="nmSpan" value="0.008">
            </div>
            <div style="font-size:11px; color:var(--text-muted);">Center: ${lat}°, ${lon}°</div>
        `;
    }

    backdrop.style.display = 'flex';
    renderIcons();
}

function closeNodeModal() {
    const backdrop = document.getElementById('nodeModalBackdrop');
    if (backdrop) backdrop.style.display = 'none';
    pendingPlacement = null;
}

function confirmNodeModal() {
    if (!pendingPlacement || !currentScenario) {
        closeNodeModal();
        return;
    }
    const { tool, latlng } = pendingPlacement;
    const name = document.getElementById('nmName')?.value?.trim();
    if (!name) {
        showToast("Enter a valid identifier", "error");
        return;
    }

    const lat = parseFloat(latlng.lat.toFixed(5));
    const lon = parseFloat(latlng.lng.toFixed(5));

    if (tool === 'gnb') {
        if (!currentScenario.gnbs) currentScenario.gnbs = [];
        currentScenario.gnbs.push({
            name: name,
            lat: lat,
            lon: lon,
            height_m: Number(document.getElementById('nmHeight')?.value) || 25,
            tx_power_dbm: Number(document.getElementById('nmPower')?.value) || 46,
            frequency_ghz: Number(document.getElementById('nmFreq')?.value) || 3.5,
            bandwidth_mhz: 100,
            coverage_radius_m: Number(document.getElementById('nmRadius')?.value) || 1500
        });
        showToast(`gNodeB '${name}' placed on map`, "info");
    } else if (tool === 'gs') {
        if (!currentScenario.ground_stations) currentScenario.ground_stations = [];
        currentScenario.ground_stations.push({
            name: name,
            lat: lat,
            lon: lon,
            altitude_m: Number(document.getElementById('nmAlt')?.value) || 250
        });
        showToast(`Gateway '${name}' placed on map`, "info");
    } else if (tool === 'blind') {
        if (!currentScenario.blind_spots) currentScenario.blind_spots = [];
        const d = Number(document.getElementById('nmSpan')?.value) || 0.008;
        currentScenario.blind_spots.push({
            name: name,
            lat_min: parseFloat((lat - d).toFixed(5)),
            lat_max: parseFloat((lat + d).toFixed(5)),
            lon_min: parseFloat((lon - d).toFixed(5)),
            lon_max: parseFloat((lon + d).toFixed(5)),
            attenuation_db: Number(document.getElementById('nmAtten')?.value) || 45.0
        });
        showToast(`Blind spot '${name}' defined on map`, "info");
    }

    renderScenarioOnMap(currentScenario);
    markYamlDirty();
    closeNodeModal();
    toggleTool('select');
}

function markYamlDirty() {
    yamlDirty = true;
}

async function saveYamlChanges() {
    if (!currentScenario) {
        showToast("No scenario selected to save", "error");
        return;
    }

    try {
        showToast(`Saving scenario '${currentScenario.name}'...`, "info", 1500);

        const res = await fetch(`/api/scenario?name=${currentScenario.id}`);
        if (!res.ok) throw new Error(`Failed to load scenario: ${res.statusText}`);
        const payload = await res.json();
        const docData = payload.data || {};
        if (!docData.scenario) docData.scenario = {};

        // Sync Time parameters
        if (!docData.scenario.time) docData.scenario.time = {};
        docData.scenario.time.duration_s = Number(document.getElementById('cfgDuration')?.value) || currentScenario.duration_s || 300;

        // Sync Area parameters
        if (!docData.scenario.area) docData.scenario.area = {};
        docData.scenario.area.elevation_mask_deg = Number(document.getElementById('cfgElevMask')?.value) || currentScenario.elevation_mask_deg || 25.0;

        // Sync Terrestrial parameters
        if (!docData.scenario.terrestrial) docData.scenario.terrestrial = {};
        docData.scenario.terrestrial.switching_mode = document.getElementById('cfgStrategy')?.value || 'coverage-based';

        if (!docData.scenario.terrestrial.alpine_weather) docData.scenario.terrestrial.alpine_weather = {};
        docData.scenario.terrestrial.alpine_weather.rain_rate_mm_hr = Number(document.getElementById('cfgRain')?.value) || 15.0;

        if (document.getElementById('cfgUeCount')) {
            if (!docData.scenario.terrestrial.ue) docData.scenario.terrestrial.ue = {};
            docData.scenario.terrestrial.ue.count = Number(document.getElementById('cfgUeCount').value) || 4;
        }

        // Sync Nodes
        if (currentScenario.gnbs) {
            if (!docData.scenario.terrestrial.gnb) docData.scenario.terrestrial.gnb = {};
            docData.scenario.terrestrial.gnb.sites = currentScenario.gnbs;
            docData.scenario.terrestrial.gnb.count = currentScenario.gnbs.length;
        }
        if (currentScenario.blind_spots) {
            docData.scenario.terrestrial.blind_spots = currentScenario.blind_spots;
        }
        if (currentScenario.ground_stations) {
            if (!docData.scenario.constellation) docData.scenario.constellation = {};
            docData.scenario.constellation.ground_stations = currentScenario.ground_stations;
        }

        const saveRes = await fetch('/api/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                id: currentScenario.id,
                data: docData
            })
        });

        if (!saveRes.ok) {
            const err = await saveRes.json().catch(() => ({}));
            throw new Error(err.detail || `Server returned ${saveRes.status}`);
        }

        yamlDirty = false;
        showToast(`Scenario '${currentScenario.name}' saved to disk!`, "success", 4000);
        selectScenario(currentScenario);
    } catch (err) {
        showToast(`Save error: ${err.message || err}`, "error", 5000);
    }
}

function clearConsole() {
    const term = document.getElementById('termLogs');
    if (term) term.textContent = 'Console cleared.\n';
}

function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast-item ${type}`;
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    else if (type === 'error') iconName = 'alert-triangle';

    toast.innerHTML = `<i data-lucide="${iconName}" size="15"></i> <span>${message}</span>`;
    container.appendChild(toast);
    renderIcons();

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 250);
    }, duration);
}

// ==========================================================================
// 12. Boot & Initialization
// ==========================================================================
function boot() {
    loadScenarios();
    initMap();
    initSplitter();
    initDrawerResizer();
    initWebSockets();
    renderIcons();
}

if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', boot);
} else {
    boot();
}
