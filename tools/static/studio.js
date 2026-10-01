        // Global State
        let map = null;
        let currentScenario = null;
        let activeTool = null;
        let mapLayers = [];
        let scenarioList = [];
        let yamlDirty = false;

        // Initialize Icons
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
                    ? `${scenario.area_name || 'Unknown area'}  /  ${scenario.duration_s || 0}s  /  ${scenario.vehicles || 0} UEs`
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
            if (id && runId) id.textContent = `RUN ${runId.slice(0, 8).toUpperCase()}`;
        }

        // Initialize Leaflet 2D Map
        function initMap() {
            if (map) return;

            if (typeof L === 'undefined') {
                setTimeout(initMap, 100);
                return;
            }

            map = L.map('map2d', {
                zoomControl: false,
                attributionControl: false
            }).setView([46.5286, 10.4531], 9);

            L.control.zoom({ position: 'bottomright' }).addTo(map);

            // Basemap Layers with authenticated CARTO key
            const cartoKey = window.NEXASIM_CONFIG?.cartoApiKey || '';
            const cartoParam = cartoKey ? `?key=${cartoKey}` : '';

            // 1. CARTO Dark Matter (Official authenticated endpoint)
            const cartoDark = L.tileLayer(`https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}.png${cartoParam}`, {
                subdomains: 'abcd',
                maxZoom: 19,
                attribution: '© OpenStreetMap, © CARTO'
            });

            // 2. CARTO Voyager (High-contrast tactical street view)
            const cartoVoyager = L.tileLayer(`https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png${cartoParam}`, {
                subdomains: 'abcd',
                maxZoom: 19,
                attribution: '© OpenStreetMap, © CARTO'
            });

            // 3. ESRI World Dark Gray Canvas
            const esriDark = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19,
                attribution: '© Esri, HERE, Garmin'
            });

            // 4. ESRI Satellite HD
            const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                maxZoom: 19,
                attribution: '© Esri, Maxar, Earthstar'
            });

            // 5. OpenStreetMap Standard
            const osmStandard = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '© OpenStreetMap contributors'
            });

            // CARTO requires an API key in some environments; keep local Studio usable without one.
            (cartoKey ? cartoDark : osmStandard).addTo(map);

            L.control.layers({
                "🗺️ CARTO Dark Matter": cartoDark,
                "🧭 CARTO Voyager": cartoVoyager,
                "🌌 ESRI Tactical Dark": esriDark,
                "🛰️ ESRI Satellite HD": esriSat,
                "🗺️ OpenStreetMap": osmStandard
            }, null, { position: 'topright' }).addTo(map);

            // If a scenario was already selected before map loaded, render it now
            if (currentScenario) {
                renderScenarioOnMap(currentScenario);
                if (currentScenario.center) {
                    map.setView(currentScenario.center, 11);
                }
            }

            // Handle Click for map tools
            map.on('click', function(e) {
                if (!activeTool || !currentScenario) return;
                handleMapClickTool(e.latlng);
            });

            // 2D <-> 3D Cross-Viewport Camera Synchronization (Dual Mode)
            map.on('moveend', function() {
                const activeBtn = document.querySelector('.view-btn.active');
                const isDual = (activeBtn && activeBtn.dataset.mode === 'dual');
                if (!isDual) return;

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
            });

            window.addEventListener('resize', () => {
                if (map) map.invalidateSize();
            });
        }

        // Load Scenario Catalog from backend API
        async function loadScenarios() {
            try {
                const res = await fetch('/api/scenarios');
                const list = await res.json();
                scenarioList = list;

                const countEl = document.getElementById('scCount');
                if (countEl) countEl.textContent = list.length;

                const container = document.getElementById('scenarioList');
                container.innerHTML = '';

                if (!list || list.length === 0) {
                    container.innerHTML = '<div style="color:var(--text-muted); font-size:12px; text-align:center; margin-top:20px;">No scenarios found.</div>';
                    return;
                }

                list.forEach((sc, idx) => {
                    const card = document.createElement('div');
                    card.className = 'scenario-card' + (idx === 0 ? ' active' : '');
                    card.id = 'sc-card-' + sc.id;
                    card.onclick = () => selectScenario(sc);
                    card.innerHTML = `
                        <div class="sc-card-title">${sc.name}</div>
                        <div style="font-size:11px; color:var(--text-secondary);">${sc.area_name}</div>
                        <div class="sc-card-badges">
                            <span class="badge badge-sat"><i data-lucide="satellite" size="11"></i> ${sc.satellites} Sats</span>
                            <span class="badge badge-gnb"><i data-lucide="radio" size="11"></i> ${sc.gnbs ? sc.gnbs.length : 0} gNBs</span>
                            <span class="badge badge-ue"><i data-lucide="car" size="11"></i> ${sc.vehicles || 0} UEs</span>
                        </div>
                    `;
                    container.appendChild(card);
                    if (idx === 0) {
                        selectScenario(sc);
                    }
                });

                renderIcons();
            } catch (err) {
                console.error("Failed to load scenarios:", err);
            }
        }

        // Select and display Scenario
        function selectScenario(sc) {
            currentScenario = sc;
            updateScenarioChrome(sc);
            updateSystemStatus('READY FOR DISPATCH', 'ready', null);

            document.querySelectorAll('.scenario-card').forEach(c => c.classList.remove('active'));
            const activeCard = document.getElementById('sc-card-' + sc.id);
            if (activeCard) activeCard.classList.add('active');

            // Populate Specs sidebar
            const details = document.getElementById('scDetails');
            if (details) {
                details.innerHTML = `
                    <div style="margin-bottom:8px;"><strong>Scenario:</strong> ${sc.name}</div>
                    <div style="margin-bottom:8px;"><strong>Area:</strong> ${sc.area_name}</div>
                    <div style="margin-bottom:8px;"><strong>Duration:</strong> ${sc.duration_s}s</div>
                    <div style="margin-bottom:8px;"><strong>Elevation Mask:</strong> ${sc.elevation_mask_deg}°</div>
                    <div style="margin-bottom:8px;"><strong>5G gNodeBs:</strong> ${sc.gnbs ? sc.gnbs.length : 0}</div>
                    <div style="margin-bottom:8px;"><strong>Ground Gateways:</strong> ${sc.ground_stations ? sc.ground_stations.length : 0}</div>
                    <div style="margin-bottom:8px;"><strong>Blind Spots:</strong> ${sc.blind_spots ? sc.blind_spots.length : 0}</div>
                    <div style="font-size:11px; color:var(--text-muted); margin-top:8px;">${sc.description || ''}</div>
                `;
            }

            // Sync Scenario Parameters tab controls with active scenario
            const stratSelect = document.getElementById('cfgStrategy');
            if (stratSelect && sc.switching_mode) {
                stratSelect.value = sc.switching_mode;
            }
            const rainInput = document.getElementById('cfgRain');
            if (rainInput && sc.rain_rate !== undefined) {
                rainInput.value = sc.rain_rate;
            }
            const elevInput = document.getElementById('cfgElevMask');
            if (elevInput && sc.elevation_mask_deg !== undefined) {
                elevInput.value = sc.elevation_mask_deg;
            }
            const durInput = document.getElementById('cfgDuration');
            if (durInput && sc.duration_s !== undefined) {
                durInput.value = sc.duration_s;
            }

            // Update Map Center and Elements
            if (map && sc.center) {
                map.setView(sc.center, 11);
                renderScenarioOnMap(sc);
                setTimeout(() => map.invalidateSize(), 100);
            }

            // Update 3D Globe Frame
            const shortName = sc.short_name || sc.id;
            const globeFrame = document.getElementById('globe3d-frame');
            const globeEmpty = document.getElementById('globeEmptyState');

            if (sc.has_globe) {
                if (globeEmpty) globeEmpty.style.display = 'none';
                if (globeFrame) {
                    globeFrame.style.display = 'block';
                    const activeMode = document.querySelector('.view-btn.active')?.dataset.mode;
                    const isDual = (activeMode === 'dual');
                    globeFrame.src = `/results/${shortName}/results/globe.html${isDual ? '?hud=0' : ''}`;
                    globeFrame.onload = function() {
                        const curMode = document.querySelector('.view-btn.active')?.dataset.mode;
                        try {
                            globeFrame.contentWindow.postMessage({ showHud: (curMode !== 'dual') }, '*');
                        } catch(e) {}
                    };
                }
            } else {
                if (globeFrame) {
                    globeFrame.src = 'about:blank';
                    globeFrame.style.display = 'none';
                }
                if (globeEmpty) globeEmpty.style.display = 'flex';
            }

            // Update Dashboard Frame
            const dashFrame = document.getElementById('dashFrame');
            if (dashFrame) {
                if (sc.has_dashboard) {
                    dashFrame.src = `/results/${shortName}/results/dashboard.html`;
                } else {
                    dashFrame.src = 'about:blank';
                }
            }
        }

        // Render Scenario Geometries on 2D Leaflet Map
        function renderScenarioOnMap(sc) {
            // Remove previous layers
            mapLayers.forEach(l => map.removeLayer(l));
            mapLayers = [];

            // 1. Scenario Bounding Box
            if (sc.bbox && sc.bbox.length === 4) {
                const [minLon, minLat, maxLon, maxLat] = sc.bbox;
                const bounds = [[minLat, minLon], [maxLat, maxLon]];
                const bboxPoly = L.rectangle(bounds, {
                    color: '#38bdf8',
                    weight: 1.5,
                    dashArray: '5, 5',
                    fillOpacity: 0.05
                }).addTo(map);
                bboxPoly.bindTooltip(`Simulation Area: ${sc.area_name}`, { sticky: true });
                mapLayers.push(bboxPoly);
            }

            // 2. 5G-NR gNodeBs
            if (sc.gnbs) {
                sc.gnbs.forEach((gnb, i) => {
                    const radius = gnb.coverage_radius_m || 1500;
                    // Coverage circle
                    const covCircle = L.circle([gnb.lat, gnb.lon], {
                        radius: radius,
                        color: '#10b981',
                        weight: 1,
                        fillColor: '#10b981',
                        fillOpacity: 0.12
                    }).addTo(map);
                    mapLayers.push(covCircle);

                    // Marker
                    const marker = L.circleMarker([gnb.lat, gnb.lon], {
                        radius: 7,
                        color: '#ffffff',
                        weight: 2,
                        fillColor: '#10b981',
                        fillOpacity: 1.0
                    }).addTo(map);

                    marker.bindPopup(`
                        <div style="font-family:inherit; font-size:12px; line-height:1.5;">
                            <strong style="color:#10b981;">5G-NR gNodeB</strong><br>
                            <b>Name:</b> ${gnb.name || 'gNodeB ' + i}<br>
                            <b>Frequency:</b> ${gnb.frequency_ghz || 3.5} GHz<br>
                            <b>Bandwidth:</b> ${gnb.bandwidth_mhz || 100} MHz<br>
                            <b>Tx Power:</b> ${gnb.tx_power_dbm || 46} dBm<br>
                            <b>Height:</b> ${gnb.height_m || 25} m
                        </div>
                    `);
                    mapLayers.push(marker);
                });
            }

            // 3. Ground Gateways
            if (sc.ground_stations) {
                sc.ground_stations.forEach((gw, i) => {
                    const marker = L.circleMarker([gw.lat, gw.lon], {
                        radius: 8,
                        color: '#ffffff',
                        weight: 2,
                        fillColor: '#f59e0b',
                        fillOpacity: 1.0
                    }).addTo(map);

                    marker.bindPopup(`
                        <div style="font-family:inherit; font-size:12px; line-height:1.5;">
                            <strong style="color:#f59e0b;">NTN Ground Gateway</strong><br>
                            <b>Name:</b> ${gw.name || 'Gateway ' + i}<br>
                            <b>Altitude:</b> ${gw.altitude_m || 100} m<br>
                            <b>Feeder Link:</b> Ka-Band (28 GHz)
                        </div>
                    `);
                    mapLayers.push(marker);
                });
            }

            // 4. Blind Spots / Shadow Zones
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

                        bsRect.bindPopup(`
                            <div style="font-family:inherit; font-size:12px; line-height:1.5;">
                                <strong style="color:#ef4444;">⛰️ Blind Spot Shadow Zone</strong><br>
                                <b>Name:</b> ${bs.name || 'Zone ' + i}<br>
                                <b>Attenuation:</b> -${bs.attenuation_db || 45} dB<br>
                                <b>Status:</b> RF Terrestrial Blackout (VHO to LEO Triggered)
                            </div>
                        `);
                        mapLayers.push(bsRect);
                    }
                });
            }

            // 5. Vehicles Convoy & Dynamic Corridor Trajectory
            if (sc.center) {
                const duration = sc.duration_s || 200;

                // Query real road geometry from backend API
                fetch(`/api/route?name=${encodeURIComponent(sc.id)}`)
                    .then(res => res.json())
                    .then(routeData => {
                        let routePoints = [];
                        if (routeData && routeData.coordinates && routeData.coordinates.length >= 2) {
                            routePoints = routeData.coordinates;
                        } else {
                            for (let t = 0; t <= duration; t += 2) {
                                const lat_offset = (t / duration) * 0.025 - 0.010;
                                const lon_offset = (t / duration) * 0.015;
                                routePoints.push([sc.center[0] + lat_offset, sc.center[1] + lon_offset]);
                            }
                        }
                        setupVehicleAnimation(sc, routePoints, duration);
                    })
                    .catch(() => {
                        const fallbackPoints = [];
                        for (let t = 0; t <= duration; t += 2) {
                            fallbackPoints.push([sc.center[0] + (t/duration)*0.02, sc.center[1] + (t/duration)*0.015]);
                        }
                        setupVehicleAnimation(sc, fallbackPoints, duration);
                    });
            }
        }

        function setupVehicleAnimation(sc, routePoints, duration) {
            // Draw Corridor Route Polyline
            const routeLine = L.polyline(routePoints, {
                color: '#ec4899',
                weight: 3.5,
                opacity: 0.75,
                dashArray: '5, 8'
            }).addTo(map);
            routeLine.bindTooltip(`🚗 Vehicular Route Corridor (${sc.vehicles || 4} UEs)`, { sticky: true });
            mapLayers.push(routeLine);

            // Clear previous animation loop
            if (window.vehicleAnimTimer) {
                cancelAnimationFrame(window.vehicleAnimTimer);
                window.vehicleAnimTimer = null;
            }

            // Create Vehicle Markers
            const numVehicles = Math.min(sc.vehicles || 4, 6);
            const vehicleMarkers = [];

            for (let v = 0; v < numVehicles; v++) {
                const isLeader = (v === 0);
                const initProgress = (0.05 + v * 0.06) % 1.0;
                const initIdx = Math.floor(initProgress * (routePoints.length - 1));
                const initPos = routePoints[initIdx];

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
                        transition: background-color 0.25s ease, box-shadow 0.25s ease;
                    ">${isLeader ? '★' : v}</div>`,
                    iconSize: [isLeader ? 18 : 13, isLeader ? 18 : 13],
                    iconAnchor: [isLeader ? 9 : 6, isLeader ? 9 : 6]
                });

                const marker = L.marker(initPos, { icon: icon }).addTo(map);
                mapLayers.push(marker);

                // Add popup template, update dynamically on open
                marker.bindPopup(`<div id="veh-popup-${v}">Loading telemetry...</div>`);

                vehicleMarkers.push({
                    marker: marker,
                    vIdx: v,
                    isLeader: isLeader,
                    inBlind: false
                });
            }

            // Real-time 2D Vehicle Movement Animation along actual road geometry
            let animSimSec = 0;
            let lastTimestamp = null;

            function animateVehicles(timestamp) {
                if (!lastTimestamp) lastTimestamp = timestamp;
                const deltaMs = timestamp - lastTimestamp;

                // Throttle updates to ~20fps (50ms) to save CPU/battery
                if (deltaMs >= 50) {
                    lastTimestamp = timestamp;
                    animSimSec = (animSimSec + (deltaMs / 1000) * 6.0) % duration;

                    vehicleMarkers.forEach(vm => {
                        const curProgress = ((animSimSec / duration) + vm.vIdx * 0.05) % 1.0;
                        const idx = Math.floor(curProgress * (routePoints.length - 1));
                        const curPos = routePoints[idx];
                        vm.marker.setLatLng(curPos);

                        // Check if in blind spot
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
                        }

                        // Only update popup DOM if it's currently open
                        if (vm.marker.isPopupOpen()) {
                            const ratColor = inBlind ? '#38bdf8' : '#10b981';
                            const ratText = inBlind ? 'Satellite LEO NTN' : '5G-NR Terrestrial';
                            const popupEl = document.getElementById(`veh-popup-${vm.vIdx}`);
                            if (popupEl) {
                                popupEl.innerHTML = `
                                    <div style="font-family:inherit; font-size:12px; line-height:1.6;">
                                        <strong style="color:#ec4899;">🚗 Vehicle ${vm.vIdx} ${vm.isLeader ? '(Convoy Leader)' : ''}</strong><br>
                                        <b>Active Link:</b> <span style="color:${ratColor};font-weight:bold;">${ratText}</span><br>
                                        <b>Status:</b> ${inBlind ? '⚠️ 5G Outage - Satellite Handover Active' : '🟢 5G Primary Connected'}<br>
                                        <b>Speed:</b> ${(48.5 - vm.vIdx * 1.5).toFixed(1)} km/h<br>
                                        <b>MEC Latency:</b> ${inBlind ? '24.2 ms (LEO)' : '5.1 ms (5G Edge)'}<br>
                                        <b>Battery SoC:</b> ${(98.5 - vm.vIdx * 0.3).toFixed(1)}%
                                    </div>
                                `;
                            }
                        }
                    });
                }
                window.vehicleAnimTimer = requestAnimationFrame(animateVehicles);
            }
            window.vehicleAnimTimer = requestAnimationFrame(animateVehicles);
        }

        // View Mode Switcher (2D / Dual / 3D)
        function switchView(mode) {
            document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
            const targetBtn = document.querySelector(`.view-btn[data-mode="${mode}"]`);
            if (targetBtn) targetBtn.classList.add('active');

            const m2d = document.getElementById('map2d');
            const g3d = document.getElementById('globe3d-container');
            const tools = document.getElementById('mapTools');
            const gFrame = document.getElementById('globe3d-frame');

            if (mode === '2d') {
                m2d.style.display = 'block';
                m2d.style.width = '100%';
                g3d.style.display = 'none';
                g3d.style.width = '0%';
                if (tools) tools.style.display = 'flex';
            } else if (mode === '3d') {
                m2d.style.display = 'none';
                m2d.style.width = '0%';
                g3d.style.display = 'block';
                g3d.style.width = '100%';
                if (tools) tools.style.display = 'none';

                // In 3D mode, show HUD panel
                try {
                    if (gFrame && gFrame.contentWindow) {
                        gFrame.contentWindow.postMessage({ showHud: true }, '*');
                    }
                } catch(e) {}
            } else if (mode === 'dual') {
                m2d.style.display = 'block';
                m2d.style.width = '50%';
                g3d.style.display = 'block';
                g3d.style.width = '50%';
                if (tools) tools.style.display = 'none';

                // In Dual mode, HIDE the 3D HUD panel so it does not obstruct the 3D view!
                try {
                    if (gFrame && gFrame.contentWindow) {
                        gFrame.contentWindow.postMessage({ showHud: false }, '*');
                    }
                } catch(e) {}

                // Close bottom drawer if open to maximize dual view area
                const drawer = document.getElementById('lowerDrawer');
                if (drawer && drawer.classList.contains('open')) {
                    toggleDrawer();
                }
            }

            setTimeout(() => {
                if (map) map.invalidateSize();
                try {
                    if (gFrame && gFrame.contentWindow) {
                        gFrame.contentWindow.dispatchEvent(new Event('resize'));
                    }
                } catch(e) {}
            }, 250);
        }

        // Toggle Drawer
        function toggleDrawer() {
            const drawer = document.getElementById('lowerDrawer');
            const chevron = document.getElementById('drawerChevron');
            const text = document.getElementById('drawerHandleText');

            drawer.classList.toggle('open');
            const isOpen = drawer.classList.contains('open');

            if (isOpen) {
                chevron.setAttribute('data-lucide', 'chevron-down');
                text.textContent = 'Close Analytics & Console';
            } else {
                chevron.setAttribute('data-lucide', 'chevron-up');
                text.textContent = 'Open Dashboard & Console';
            }
            renderIcons();
        }

        // Switch Drawer Tabs
        function switchDrawerTab(paneId) {
            document.querySelectorAll('.drawer-tab').forEach(b => b.classList.remove('active'));
            const activeTab = document.querySelector(`.drawer-tab[data-pane="${paneId}"]`);
            if (activeTab) activeTab.classList.add('active');

            document.querySelectorAll('.drawer-pane').forEach(p => p.classList.remove('active'));
            const activePane = document.getElementById(paneId);
            if (activePane) activePane.classList.add('active');
        }

        // Generate / Sync 3D Digital Twin
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
                if (!res.ok) {
                    throw new Error(data.detail || '3D twin generation failed');
                }

                const shortName = currentScenario.short_name || currentScenario.id;
                currentScenario.has_globe = true;

                const globeEmpty = document.getElementById('globeEmptyState');
                if (globeEmpty) globeEmpty.style.display = 'none';

                const globeFrame = document.getElementById('globe3d-frame');
                if (globeFrame) {
                    globeFrame.style.display = 'block';
                    globeFrame.src = `/results/${shortName}/results/globe.html?t=${Date.now()}`;
                }
            } catch (e) {
                console.error("3D Digital Twin sync error:", e);
            } finally {
                if (btn) btn.innerHTML = oldHtml;
                renderIcons();
            }
        }

        // Run Simulation
        async function runSimulation() {
            if (!currentScenario) return;

            const btn = document.getElementById('runBtn');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i data-lucide="loader" class="spin" size="14"></i> Simulating...';
            }
            renderIcons();

            // Auto-open drawer to console tab
            const drawer = document.getElementById('lowerDrawer');
            if (!drawer.classList.contains('open')) toggleDrawer();
            switchDrawerTab('pane-console');

            const term = document.getElementById('termLogs');
            term.textContent = `[*] Dispatching simulation job for '${currentScenario.id}'...\n`;
            updateSystemStatus('DISPATCHING SIMULATION', 'busy');

            try {
                const res = await fetch('/api/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: currentScenario.id })
                });
                const data = await res.json();
                if (!res.ok) {
                    throw new Error(data.detail || 'Simulation dispatch failed');
                }
                updateSystemStatus('SIMULATION RUNNING', 'busy', data.run_id);
                pollSimulation();
            } catch (err) {
                const message = err instanceof TypeError
                    ? 'Studio server unavailable. Start the NexaSim Studio service and retry.'
                    : (err.message || String(err));
                term.textContent += `[!] Run dispatch error: ${message}\n`;
                updateSystemStatus('DISPATCH FAILED', 'error');
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<i data-lucide="play" size="14"></i> Run Simulation';
                }
                renderIcons();
            }
        }

        // Poll simulation logs
        function pollSimulation() {
            const term = document.getElementById('termLogs');
            const interval = setInterval(async () => {
                try {
                    const res = await fetch('/api/status');
                    const st = await res.json();

                    if (st.logs && st.logs.length > 0) {
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

                        // Refresh Dashboard
                        const dashFrame = document.getElementById('dashFrame');
                        if (dashFrame) {
                            dashFrame.src = `/results/${shortName}/results/dashboard.html?t=${Date.now()}`;
                        }
                        switchDrawerTab('pane-dash');

                        // Refresh 3D Twin
                        buildDigitalTwin3D();
                    }
                } catch (e) {
                    console.error("Status polling error:", e);
                }
            }, 1200);
        }

        // Toast Notifications
        function showToast(message, type = 'info', duration = 3500) {
            const container = document.getElementById('toastContainer');
            if (!container) return;
            const toast = document.createElement('div');
            toast.className = `toast-item ${type}`;
            let iconName = 'info';
            if (type === 'success') iconName = 'check-circle';
            else if (type === 'error') iconName = 'alert-triangle';
            toast.innerHTML = `<i data-lucide="${iconName}" size="16"></i> <span>${message}</span>`;
            container.appendChild(toast);
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
            setTimeout(() => {
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(100%)';
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }

        // Modal for Adding Nodes (Non-blocking replacement for prompt)
        let pendingPlacement = null;

        function closeNodeModal() {
            const backdrop = document.getElementById('nodeModalBackdrop');
            if (backdrop) backdrop.style.display = 'none';
            pendingPlacement = null;
        }

        // Map Editing Tools
        function toggleTool(toolName) {
            document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active-tool'));
            if (activeTool === toolName) {
                activeTool = null;
            } else {
                activeTool = toolName;
                const toolBtn = document.getElementById(`tool${toolName.charAt(0).toUpperCase() + toolName.slice(1)}Btn`);
                if (toolBtn) toolBtn.classList.add('active-tool');
            }
        }

        function handleMapClickTool(latlng) {
            if (!currentScenario || !activeTool) return;
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
                        <input type="text" class="form-input" id="nmName" value="gnb_custom_${Date.now() % 1000}">
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
                heading.textContent = "Deploy NTN Ground Gateway";
                body.innerHTML = `
                    <div class="form-group">
                        <label class="form-label">Gateway Identifier</label>
                        <input type="text" class="form-input" id="nmName" value="gw_custom_${Date.now() % 1000}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Altitude ASL (m)</label>
                        <input type="number" class="form-input" id="nmAlt" value="250">
                    </div>
                    <div style="font-size:11px; color:var(--text-muted);">Coordinates: ${lat}°, ${lon}° (Ka-Band Feeder Link)</div>
                `;
            } else if (activeTool === 'blind') {
                heading.textContent = "Define RF Shadow / Blind Spot";
                body.innerHTML = `
                    <div class="form-group">
                        <label class="form-label">Zone Identifier</label>
                        <input type="text" class="form-input" id="nmName" value="blind_zone_${Date.now() % 1000}">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Attenuation (dB)</label>
                        <input type="number" class="form-input" id="nmAtten" value="45.0">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Zone Radius (deg span)</label>
                        <input type="number" step="0.001" class="form-input" id="nmSpan" value="0.008">
                    </div>
                    <div style="font-size:11px; color:var(--text-muted);">Center: ${lat}°, ${lon}°</div>
                `;
            }

            backdrop.style.display = 'flex';
            if (window.lucide && typeof window.lucide.createIcons === 'function') {
                window.lucide.createIcons();
            }
        }

        function confirmNodeModal() {
            if (!pendingPlacement || !currentScenario) {
                closeNodeModal();
                return;
            }
            const { tool, latlng } = pendingPlacement;
            const name = document.getElementById('nmName')?.value?.trim();
            if (!name) {
                showToast("Please enter a valid node name", "error");
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
                showToast(`Saving configuration for '${currentScenario.name}'...`, "info", 1500);

                // Fetch current full scenario structure from backend
                const res = await fetch(`/api/scenario?name=${currentScenario.id}`);
                if (!res.ok) throw new Error(`Failed to load scenario: ${res.statusText}`);
                const payload = await res.json();
                const docData = payload.data || {};
                if (!docData.scenario) docData.scenario = {};

                // Synchronize parameters from UI controls
                if (!docData.scenario.time) docData.scenario.time = {};
                docData.scenario.time.duration_s = Number(document.getElementById('cfgDuration')?.value) || currentScenario.duration_s || 300;

                if (!docData.scenario.area) docData.scenario.area = {};
                docData.scenario.area.elevation_mask_deg = Number(document.getElementById('cfgElevMask')?.value) || currentScenario.elevation_mask_deg || 25.0;

                if (!docData.scenario.terrestrial) docData.scenario.terrestrial = {};
                const stratVal = document.getElementById('cfgStrategy')?.value || 'coverage-based';
                docData.scenario.terrestrial.switching_mode = stratVal;

                if (!docData.scenario.terrestrial.alpine_weather) docData.scenario.terrestrial.alpine_weather = {};
                docData.scenario.terrestrial.alpine_weather.rain_rate_mm_hr = Number(document.getElementById('cfgRain')?.value) || 15.0;

                // Synchronize visual entities
                if (currentScenario.gnbs) {
                    if (!docData.scenario.terrestrial.gnb) docData.scenario.terrestrial.gnb = {};
                    docData.scenario.terrestrial.gnb.sites = currentScenario.gnbs;
                }
                if (currentScenario.blind_spots) {
                    docData.scenario.terrestrial.blind_spots = currentScenario.blind_spots;
                }
                if (currentScenario.ground_stations) {
                    if (!docData.scenario.constellation) docData.scenario.constellation = {};
                    docData.scenario.constellation.ground_stations = currentScenario.ground_stations;
                }

                // Send updated scenario to backend API
                const saveRes = await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: currentScenario.id,
                        data: docData
                    })
                });

                if (!saveRes.ok) {
                    const errBody = await saveRes.json().catch(() => ({}));
                    throw new Error(errBody.detail || `Server returned ${saveRes.status}`);
                }

                yamlDirty = false;
                showToast(`Scenario '${currentScenario.name}' saved to disk!`, "success", 4000);

                // Update current scenario metadata
                currentScenario.duration_s = docData.scenario.time.duration_s;
                currentScenario.elevation_mask_deg = docData.scenario.area.elevation_mask_deg;
                currentScenario.switching_mode = stratVal;
                currentScenario.rain_rate = docData.scenario.terrestrial.alpine_weather.rain_rate_mm_hr;
                selectScenario(currentScenario);
            } catch (err) {
                console.error("Save error:", err);
                showToast(`Error saving scenario: ${err.message || err}`, "error", 5000);
            }
        }

        // Boot
        function boot() {
            loadScenarios();
            initMap();
            renderIcons();
        }

        if (document.readyState === 'loading') {
            window.addEventListener('DOMContentLoaded', boot);
        } else {
            boot();
        }
