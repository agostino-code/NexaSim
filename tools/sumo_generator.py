#!/usr/bin/env python3
"""
NexaSim Procedural SUMO Network & Route Generator
Generates realistic microscopic traffic topologies for multi-tier TN-NTN scenarios:
- Alpine Pass Traversal (hairpin curves & mountain elevation)
- Highway Platooning (multi-lane straight corridor with low-headway convoys)
- Emergency Telemedicine Corridor (code-red ambulance overtaking traffic)
- Urban Canyon / Manhattan Grid (dense microcells & high-rise street canyons)
- High-Speed Rail Corridor (300 km/h train line)
- Maritime SAR & UAV corridors
"""

import os
import sys
import json
import math
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    from tools.osm_downloader import download_osm_bbox
except ImportError:
    try:
        from osm_downloader import download_osm_bbox
    except ImportError:
        download_osm_bbox = None

def generate_sumo_scenario(scenario_config: Dict[str, Any], output_dir: Path) -> Dict[str, str]:
    """
    Generate all required SUMO files in output_dir:
    - <scenario_name>.sumocfg
    - <scenario_name>.net.xml
    - <scenario_name>.rou.xml
    - <scenario_name>.nod.xml
    - <scenario_name>.edg.xml
    - <scenario_name>.view.xml
    - route_geo.json (Georeferenced WGS84 route coordinates for 2D/3D viewers)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    scenario_meta = scenario_config.get('scenario', {})
    scenario_name = scenario_meta.get('name', 'scenario')
    time_cfg = scenario_meta.get('time', {})
    duration_s = int(time_cfg.get('duration_s', 300))
    area_cfg = scenario_meta.get('area', {})

    terrestrial = scenario_meta.get('terrestrial', {})
    ue_cfg = terrestrial.get('ue', {})
    mobility_model = ue_cfg.get('mobility_model', 'highway_platooning_linear')
    veh_count = int(ue_cfg.get('count', 12))
    speed_kmh = float(ue_cfg.get('speed_kmh', 50.0))
    speed_ms = speed_kmh / 3.6

    incident_cfg = scenario_meta.get('incident', {})

    # 1. Determine Archetype
    if 'alpine' in mobility_model or 'stelvio' in scenario_name:
        archetype = 'alpine'
    elif 'highway' in mobility_model or 'platoon' in mobility_model:
        archetype = 'highway'
    elif 'emergency' in mobility_model:
        archetype = 'emergency'
    elif 'urban' in mobility_model or 'cpm' in mobility_model or 'canyon' in mobility_model:
        archetype = 'urban'
    elif 'rail' in mobility_model or 'train' in mobility_model:
        archetype = 'rail'
    elif 'uav' in mobility_model:
        archetype = 'uav'
    elif 'maritime' in mobility_model or 'vessel' in mobility_model:
        archetype = 'maritime'
    else:
        archetype = 'highway'

    # Check if Stelvio files already exist in scenarios/generated/stelvio to preserve exact topography
    stelvio_source = Path(__file__).parent.parent / 'scenarios' / 'generated' / 'stelvio'
    if archetype == 'alpine' and (stelvio_source / 'stelvio.net.xml').exists():
        _copy_or_link_stelvio(stelvio_source, output_dir, scenario_name)
        _generate_route_geo_json(output_dir, scenario_name, archetype, area_cfg)
        return {
            'sumocfg': str(output_dir / f"{scenario_name}.sumocfg"),
            'net': str(output_dir / f"{scenario_name}.net.xml"),
            'rou': str(output_dir / f"{scenario_name}.rou.xml"),
        }

    # Generate procedural nodes, edges, routes, and network
    nodes_xml, edges_xml, net_xml, view_xml, boundary = _build_topology(archetype, speed_ms)

    # Write .nod.xml
    nod_file = output_dir / f"{scenario_name}.nod.xml"
    with open(nod_file, 'w', encoding='utf-8') as f:
        f.write(nodes_xml)

    # Write .edg.xml
    edg_file = output_dir / f"{scenario_name}.edg.xml"
    with open(edg_file, 'w', encoding='utf-8') as f:
        f.write(edges_xml)

    # Write .net.xml
    net_file = output_dir / f"{scenario_name}.net.xml"
    with open(net_file, 'w', encoding='utf-8') as f:
        f.write(net_xml)

    # If netconvert binary is available (e.g. inside Docker or local SUMO), compile full network
    import shutil
    import subprocess
    netconvert_bin = shutil.which("netconvert") or ("/usr/local/bin/netconvert" if Path("/usr/local/bin/netconvert").exists() else None)
    if netconvert_bin:
        try:
            res = subprocess.run([
                str(netconvert_bin),
                "--node-files", str(nod_file),
                "--edge-files", str(edg_file),
                "-o", str(net_file)
            ], capture_output=True, text=True)
            if res.returncode == 0:
                print(f"[SUMO Generator] Compiled validated net with netconvert: {net_file.name}")
        except Exception:
            pass

    # Write .rou.xml
    rou_xml = _build_routes(archetype, veh_count, speed_ms, duration_s, incident_cfg)
    rou_file = output_dir / f"{scenario_name}.rou.xml"
    with open(rou_file, 'w', encoding='utf-8') as f:
        f.write(rou_xml)

    # Write .view.xml
    view_file = output_dir / f"{scenario_name}.view.xml"
    with open(view_file, 'w', encoding='utf-8') as f:
        f.write(view_xml)

    # Write .sumocfg with real FCD geo output
    sumocfg_file = output_dir / f"{scenario_name}.sumocfg"
    sumocfg_xml = f"""<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{scenario_name}.net.xml"/>
        <route-files value="{scenario_name}.rou.xml"/>
    </input>
    <output>
        <fcd-output value="trace_fcd.xml"/>
        <fcd-output.geo value="true"/>
    </output>
    <time>
        <begin value="0"/>
        <end value="{duration_s}"/>
        <step-length value="0.1"/>
    </time>
    <gui_only>
        <start value="true"/>
        <gui-settings-file value="{scenario_name}.view.xml"/>
    </gui_only>
</configuration>
"""
    with open(sumocfg_file, 'w', encoding='utf-8') as f:
        f.write(sumocfg_xml)

    # Generate WGS84 real road route points for 2D/3D visualizers
    _generate_route_geo_json(output_dir, scenario_name, archetype, area_cfg)

    print(f"[SUMO Generator] Generated complete {archetype.upper()} traffic network: {sumocfg_file.name}")
    return {
        'sumocfg': str(sumocfg_file),
        'net': str(net_file),
        'rou': str(rou_file)
    }

def _copy_or_link_stelvio(source_dir: Path, target_dir: Path, scenario_name: str):
    import shutil
    for ext in ['nod.xml', 'edg.xml', 'net.xml', 'rou.xml', 'view.xml', 'sumocfg']:
        src = source_dir / f"stelvio.{ext}"
        dst = target_dir / f"{scenario_name}.{ext}"
        if src.exists():
            shutil.copyfile(src, dst)
    # Fix references inside sumocfg if renamed
    sumocfg_path = target_dir / f"{scenario_name}.sumocfg"
    if sumocfg_path.exists():
        with open(sumocfg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace("stelvio.net.xml", f"{scenario_name}.net.xml")
        content = content.replace("stelvio.rou.xml", f"{scenario_name}.rou.xml")
        content = content.replace("stelvio.view.xml", f"{scenario_name}.view.xml")
        if "<fcd-output" not in content:
            content = content.replace(
                "</configuration>",
                "    <output>\n        <fcd-output value=\"trace_fcd.xml\"/>\n        <fcd-output.geo value=\"true\"/>\n    </output>\n</configuration>"
            )
        with open(sumocfg_path, 'w', encoding='utf-8') as f:
            f.write(content)

def _densify_polyline(points: List[Tuple[float, float]], max_dist_m: float = 25.0) -> List[Tuple[float, float]]:
    """Densifies a WGS84 polyline [lat, lon] inserting equidistant intermediate points."""
    if len(points) < 2:
        return points
    dense = [points[0]]
    for i in range(len(points) - 1):
        lat1, lon1 = points[i]
        lat2, lon2 = points[i+1]
        # Approximate distance in meters
        d_lat = (lat2 - lat1) * 111139.0
        d_lon = (lon2 - lon1) * 111139.0 * math.cos(math.radians((lat1 + lat2) / 2))
        segment_dist = math.hypot(d_lat, d_lon)
        steps = max(1, int(math.ceil(segment_dist / max_dist_m)))
        for s in range(1, steps + 1):
            f = s / steps
            interp_lat = lat1 + f * (lat2 - lat1)
            interp_lon = lon1 + f * (lon2 - lon1)
            dense.append((interp_lat, interp_lon))
    return dense

def _generate_route_geo_json(output_dir: Path, scenario_name: str, archetype: str, area_cfg: Dict[str, Any]):
    """
    Generates high-precision georeferenced real-world road coordinates
    and writes route_geo.json into output_dir.
    """
    center_lat = float(area_cfg.get('center_lat', 46.5286))
    center_lon = float(area_cfg.get('center_lon', 10.4531))

    # Real geodetic route templates corresponding to real corridors
    if archetype == 'alpine':
        # SS38 Passo dello Stelvio (Winding Hairpin Turns from Trafoi up to Summit and Umbrail Pass)
        key_nodes = [
            (46.5540, 10.5100), (46.5515, 10.5050), (46.5492, 10.4985),
            (46.5468, 10.4920), (46.5440, 10.4855), (46.5412, 10.4790),
            (46.5385, 10.4725), (46.5360, 10.4670), (46.5338, 10.4635),
            (46.5310, 10.4590), (46.5286, 10.4531), (46.5305, 10.4475),
            (46.5340, 10.4410), (46.5380, 10.4360), (46.5410, 10.4320)
        ]
    elif archetype == 'highway':
        # Autostrada del Brennero A22 (Sterzing / Vipiteno to Brenner Pass)
        key_nodes = [
            (46.8850, 11.4400), (46.9020, 11.4510), (46.9200, 11.4650),
            (46.9450, 11.4850), (46.9750, 11.5050), (47.0050, 11.5120)
        ]
    elif archetype == 'urban':
        # Milano CityLife / Piazza Tre Torri Street Grid
        key_nodes = [
            (45.4740, 9.1510), (45.4765, 9.1535), (45.4780, 9.1560),
            (45.4810, 9.1590), (45.4835, 9.1620)
        ]
    elif archetype == 'emergency':
        # Florence Hospital Corridor (Meyer / Careggi University Hospital to Pieraccini)
        key_nodes = [
            (43.7920, 11.2420), (43.7950, 11.2460), (43.7985, 11.2485),
            (43.8010, 11.2505), (43.8040, 11.2530)
        ]
    elif archetype == 'rail':
        # Bologna-Firenze High-Speed Line (Bologna South to Apennine Tunnel Portal)
        key_nodes = [
            (44.1100, 11.2300), (44.1350, 11.2420), (44.1600, 11.2550),
            (44.1850, 11.2680), (44.2100, 11.2800)
        ]
    elif archetype == 'uav':
        # Trento Adige Valley Drone Corridor
        key_nodes = [
            (46.1800, 11.1100), (46.2000, 11.1200), (46.2200, 11.1300), (46.2400, 11.1400)
        ]
    elif archetype == 'maritime':
        # Adriatic Sea Offshore SAR Corridor
        key_nodes = [
            (42.4000, 15.4000), (42.4500, 15.4500), (42.5000, 15.5000), (42.5500, 15.5500)
        ]
    else:
        key_nodes = [
            (center_lat - 0.015, center_lon - 0.015),
            (center_lat, center_lon),
            (center_lat + 0.015, center_lon + 0.015)
        ]

    # Densify along genuine road curves
    dense_coords = _densify_polyline(key_nodes, max_dist_m=35.0)

    route_data = {
        "scenario": scenario_name,
        "archetype": archetype,
        "center": [center_lat, center_lon],
        "node_count": len(dense_coords),
        "coordinates": [[round(lat, 6), round(lon, 6)] for lat, lon in dense_coords]
    }

    route_json_path = output_dir / "route_geo.json"
    with open(route_json_path, 'w', encoding='utf-8') as f:
        json.dump(route_data, f, indent=2)

def _build_topology(archetype: str, speed_ms: float):
    """Generates procedural nodes, edges, net and view XML based on archetype."""
    if archetype == 'highway':
        # 8 km 3-lane Highway corridor (e.g. Brenner A22)
        length = 8000.0
        nodes_xml = f"""<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <node id="highway_start" x="0.0" y="0.0" type="priority"/>
    <node id="highway_mid" x="{length/2:.1f}" y="0.0" type="priority"/>
    <node id="highway_end" x="{length:.1f}" y="0.0" type="priority"/>
</nodes>
"""
        edges_xml = f"""<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <edge id="e_fwd_1" from="highway_start" to="highway_mid" priority="4" numLanes="3" speed="{max(speed_ms, 33.3):.1f}"/>
    <edge id="e_fwd_2" from="highway_mid" to="highway_end" priority="4" numLanes="3" speed="{max(speed_ms, 33.3):.1f}"/>
    <edge id="e_rev_2" from="highway_end" to="highway_mid" priority="4" numLanes="3" speed="{max(speed_ms, 33.3):.1f}"/>
    <edge id="e_rev_1" from="highway_mid" to="highway_start" priority="4" numLanes="3" speed="{max(speed_ms, 33.3):.1f}"/>
</edges>
"""
        net_xml = f"""<net version="1.20" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
    <location netOffset="0.00,0.00" convBoundary="0.00,-15.00,{length:.2f},15.00" origBoundary="0.00,-15.00,{length:.2f},15.00" projParameter="!"/>
    <edge id="e_fwd_1" from="highway_start" to="highway_mid" priority="4">
        <lane id="e_fwd_1_0" index="0" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="0.00,-8.00 {length/2:.2f},-8.00"/>
        <lane id="e_fwd_1_1" index="1" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="0.00,-4.80 {length/2:.2f},-4.80"/>
        <lane id="e_fwd_1_2" index="2" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="0.00,-1.60 {length/2:.2f},-1.60"/>
    </edge>
    <edge id="e_fwd_2" from="highway_mid" to="highway_end" priority="4">
        <lane id="e_fwd_2_0" index="0" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},-8.00 {length:.2f},-8.00"/>
        <lane id="e_fwd_2_1" index="1" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},-4.80 {length:.2f},-4.80"/>
        <lane id="e_fwd_2_2" index="2" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},-1.60 {length:.2f},-1.60"/>
    </edge>
    <edge id="e_rev_2" from="highway_end" to="highway_mid" priority="4">
        <lane id="e_rev_2_0" index="0" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length:.2f},8.00 {length/2:.2f},8.00"/>
        <lane id="e_rev_2_1" index="1" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length:.2f},4.80 {length/2:.2f},4.80"/>
        <lane id="e_rev_2_2" index="2" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length:.2f},1.60 {length/2:.2f},1.60"/>
    </edge>
    <edge id="e_rev_1" from="highway_mid" to="highway_start" priority="4">
        <lane id="e_rev_1_0" index="0" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},8.00 0.00,8.00"/>
        <lane id="e_rev_1_1" index="1" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},4.80 0.00,4.80"/>
        <lane id="e_rev_1_2" index="2" speed="{max(speed_ms, 33.3):.2f}" length="{length/2:.2f}" shape="{length/2:.2f},1.60 0.00,1.60"/>
    </edge>
    <junction id="highway_start" type="dead_end" x="0.00" y="0.00" incLanes="e_rev_1_0 e_rev_1_1 e_rev_1_2" intLanes="" shape="0.00,9.60 0.00,-9.60"/>
    <junction id="highway_mid" type="priority" x="{length/2:.2f}" y="0.00" incLanes="e_fwd_1_0 e_fwd_1_1 e_fwd_1_2 e_rev_2_0 e_rev_2_1 e_rev_2_2" intLanes="" shape="{length/2:.2f},9.60 {length/2:.2f},-9.60"/>
    <junction id="highway_end" type="dead_end" x="{length:.2f}" y="0.00" incLanes="e_fwd_2_0 e_fwd_2_1 e_fwd_2_2" intLanes="" shape="{length:.2f},-9.60 {length:.2f},9.60"/>
    <connection from="e_fwd_1" to="e_fwd_2" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_fwd_1" to="e_fwd_2" fromLane="1" toLane="1" dir="s" state="M"/>
    <connection from="e_fwd_1" to="e_fwd_2" fromLane="2" toLane="2" dir="s" state="M"/>
    <connection from="e_rev_2" to="e_rev_1" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_rev_2" to="e_rev_1" fromLane="1" toLane="1" dir="s" state="M"/>
    <connection from="e_rev_2" to="e_rev_1" fromLane="2" toLane="2" dir="s" state="M"/>
</net>
"""
        view_xml = f"""<viewsettings>
    <scheme name="real world"/>
    <delay value="10"/>
    <viewport zoom="120" x="{length/4:.1f}" y="0"/>
</viewsettings>
"""
        return nodes_xml, edges_xml, net_xml, view_xml, (0, length)

    elif archetype == 'urban':
        # 3x3 Manhattan Street Grid
        grid_size = 600.0
        nodes = []
        for r in range(3):
            for c in range(3):
                nid = f"node_{r}_{c}"
                nodes.append(f'<node id="{nid}" x="{c*grid_size:.1f}" y="{r*grid_size:.1f}" type="priority"/>')
        nodes_xml = f"""<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    {chr(10).join(nodes)}
</nodes>
"""
        edges = []
        for r in range(3):
            for c in range(2):
                edges.append(f'<edge id="e_h_{r}_{c}_{c+1}" from="node_{r}_{c}" to="node_{r}_{c+1}" priority="3" numLanes="2" speed="13.8"/>')
                edges.append(f'<edge id="e_h_{r}_{c+1}_{c}" from="node_{r}_{c+1}" to="node_{r}_{c}" priority="3" numLanes="2" speed="13.8"/>')
        for r in range(2):
            for c in range(3):
                edges.append(f'<edge id="e_v_{r}_{r+1}_{c}" from="node_{r}_{c}" to="node_{r+1}_{c}" priority="3" numLanes="2" speed="13.8"/>')
                edges.append(f'<edge id="e_v_{r+1}_{r}_{c}" from="node_{r+1}_{c}" to="node_{r}_{c}" priority="3" numLanes="2" speed="13.8"/>')
        edges_xml = f"""<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    {chr(10).join(edges)}
</edges>
"""
        # Build clean direct net.xml for the grid
        net_edges = []
        for e in edges:
            eid = e.split('id="')[1].split('"')[0]
            frm = e.split('from="')[1].split('"')[0]
            to = e.split('to="')[1].split('"')[0]
            # Coordinates
            r1, c1 = [int(x) for x in frm.split('_')[1:]]
            r2, c2 = [int(x) for x in to.split('_')[1:]]
            x1, y1 = c1 * grid_size, r1 * grid_size
            x2, y2 = c2 * grid_size, r2 * grid_size
            dist = math.hypot(x2 - x1, y2 - y1)
            net_edges.append(f"""    <edge id="{eid}" from="{frm}" to="{to}" priority="3">
        <lane id="{eid}_0" index="0" speed="13.80" length="{dist:.2f}" shape="{x1:.2f},{y1-1.6:.2f} {x2:.2f},{y2-1.6:.2f}"/>
        <lane id="{eid}_1" index="1" speed="13.80" length="{dist:.2f}" shape="{x1:.2f},{y1+1.6:.2f} {x2:.2f},{y2+1.6:.2f}"/>
    </edge>""")
        net_xml = f"""<net version="1.20" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
    <location netOffset="0.00,0.00" convBoundary="0.00,0.00,{2*grid_size:.2f},{2*grid_size:.2f}" origBoundary="0.00,0.00,{2*grid_size:.2f},{2*grid_size:.2f}" projParameter="!"/>
{chr(10).join(net_edges)}
</net>
"""
        view_xml = f"""<viewsettings>
    <scheme name="real world"/>
    <delay value="20"/>
    <viewport zoom="150" x="{grid_size:.1f}" y="{grid_size:.1f}"/>
</viewsettings>
"""
        return nodes_xml, edges_xml, net_xml, view_xml, (0, 2*grid_size)

    elif archetype == 'rail':
        # 15 km High-speed rail track
        length = 15000.0
        nodes_xml = f"""<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <node id="rail_start" x="0.0" y="0.0" type="priority"/>
    <node id="rail_tunnel_in" x="5000.0" y="0.0" type="priority"/>
    <node id="rail_tunnel_out" x="10000.0" y="0.0" type="priority"/>
    <node id="rail_end" x="{length:.1f}" y="0.0" type="priority"/>
</nodes>
"""
        edges_xml = f"""<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <edge id="e_rail_1" from="rail_start" to="rail_tunnel_in" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
    <edge id="e_rail_tunnel" from="rail_tunnel_in" to="rail_tunnel_out" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
    <edge id="e_rail_2" from="rail_tunnel_out" to="rail_end" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
    <edge id="e_rail_rev_2" from="rail_end" to="rail_tunnel_out" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
    <edge id="e_rail_rev_tunnel" from="rail_tunnel_out" to="rail_tunnel_in" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
    <edge id="e_rail_rev_1" from="rail_tunnel_in" to="rail_start" priority="5" numLanes="1" speed="{speed_ms:.1f}"/>
</edges>
"""
        net_xml = f"""<net version="1.20" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
    <location netOffset="0.00,0.00" convBoundary="0.00,-10.00,{length:.2f},10.00" origBoundary="0.00,-10.00,{length:.2f},10.00" projParameter="!"/>
    <edge id="e_rail_1" from="rail_start" to="rail_tunnel_in" priority="5">
        <lane id="e_rail_1_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="0.00,-2.50 5000.00,-2.50"/>
    </edge>
    <edge id="e_rail_tunnel" from="rail_tunnel_in" to="rail_tunnel_out" priority="5">
        <lane id="e_rail_tunnel_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="5000.00,-2.50 10000.00,-2.50"/>
    </edge>
    <edge id="e_rail_2" from="rail_tunnel_out" to="rail_end" priority="5">
        <lane id="e_rail_2_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="10000.00,-2.50 {length:.2f},-2.50"/>
    </edge>
    <edge id="e_rail_rev_2" from="rail_end" to="rail_tunnel_out" priority="5">
        <lane id="e_rail_rev_2_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="{length:.2f},2.50 10000.00,2.50"/>
    </edge>
    <edge id="e_rail_rev_tunnel" from="rail_tunnel_out" to="rail_tunnel_in" priority="5">
        <lane id="e_rail_rev_tunnel_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="10000.00,2.50 5000.00,2.50"/>
    </edge>
    <edge id="e_rail_rev_1" from="rail_tunnel_in" to="rail_start" priority="5">
        <lane id="e_rail_rev_1_0" index="0" speed="{speed_ms:.2f}" length="5000.00" shape="5000.00,2.50 0.00,2.50"/>
    </edge>
    <connection from="e_rail_1" to="e_rail_tunnel" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_rail_tunnel" to="e_rail_2" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_rail_rev_2" to="e_rail_rev_tunnel" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_rail_rev_tunnel" to="e_rail_rev_1" fromLane="0" toLane="0" dir="s" state="M"/>
</net>
"""
        view_xml = f"""<viewsettings>
    <scheme name="real world"/>
    <delay value="10"/>
    <viewport zoom="80" x="5000" y="0"/>
</viewsettings>
"""
        return nodes_xml, edges_xml, net_xml, view_xml, (0, length)

    else:
        # Default corridor for emergency, maritime, UAV
        length = 6000.0
        nodes_xml = f"""<nodes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/nodes_file.xsd">
    <node id="corridor_start" x="0.0" y="0.0" type="priority"/>
    <node id="corridor_mid" x="{length/2:.1f}" y="400.0" type="priority"/>
    <node id="corridor_end" x="{length:.1f}" y="800.0" type="priority"/>
</nodes>
"""
        edges_xml = f"""<edges xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/edges_file.xsd">
    <edge id="e_corr_1" from="corridor_start" to="corridor_mid" priority="3" numLanes="2" speed="{speed_ms:.1f}"/>
    <edge id="e_corr_2" from="corridor_mid" to="corridor_end" priority="3" numLanes="2" speed="{speed_ms:.1f}"/>
    <edge id="e_corr_rev_2" from="corridor_end" to="corridor_mid" priority="3" numLanes="2" speed="{speed_ms:.1f}"/>
    <edge id="e_corr_rev_1" from="corridor_mid" to="corridor_start" priority="3" numLanes="2" speed="{speed_ms:.1f}"/>
</edges>
"""
        dist1 = math.hypot(length/2, 400.0)
        dist2 = math.hypot(length/2, 400.0)
        net_xml = f"""<net version="1.20" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/net_file.xsd">
    <location netOffset="0.00,0.00" convBoundary="0.00,-10.00,{length:.2f},810.00" origBoundary="0.00,-10.00,{length:.2f},810.00" projParameter="!"/>
    <edge id="e_corr_1" from="corridor_start" to="corridor_mid" priority="3">
        <lane id="e_corr_1_0" index="0" speed="{speed_ms:.2f}" length="{dist1:.2f}" shape="0.00,-1.60 {length/2:.2f},398.40"/>
        <lane id="e_corr_1_1" index="1" speed="{speed_ms:.2f}" length="{dist1:.2f}" shape="0.00,1.60 {length/2:.2f},401.60"/>
    </edge>
    <edge id="e_corr_2" from="corridor_mid" to="corridor_end" priority="3">
        <lane id="e_corr_2_0" index="0" speed="{speed_ms:.2f}" length="{dist2:.2f}" shape="{length/2:.2f},398.40 {length:.2f},798.40"/>
        <lane id="e_corr_2_1" index="1" speed="{speed_ms:.2f}" length="{dist2:.2f}" shape="{length/2:.2f},401.60 {length:.2f},801.60"/>
    </edge>
    <edge id="e_corr_rev_2" from="corridor_end" to="corridor_mid" priority="3">
        <lane id="e_corr_rev_2_0" index="0" speed="{speed_ms:.2f}" length="{dist2:.2f}" shape="{length:.2f},804.80 {length/2:.2f},404.80"/>
        <lane id="e_corr_rev_2_1" index="1" speed="{speed_ms:.2f}" length="{dist2:.2f}" shape="{length:.2f},808.00 {length/2:.2f},408.00"/>
    </edge>
    <edge id="e_corr_rev_1" from="corridor_mid" to="corridor_start" priority="3">
        <lane id="e_corr_rev_1_0" index="0" speed="{speed_ms:.2f}" length="{dist1:.2f}" shape="{length/2:.2f},404.80 0.00,4.80"/>
        <lane id="e_corr_rev_1_1" index="1" speed="{speed_ms:.2f}" length="{dist1:.2f}" shape="{length/2:.2f},408.00 0.00,8.00"/>
    </edge>
    <connection from="e_corr_1" to="e_corr_2" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_corr_1" to="e_corr_2" fromLane="1" toLane="1" dir="s" state="M"/>
    <connection from="e_corr_rev_2" to="e_corr_rev_1" fromLane="0" toLane="0" dir="s" state="M"/>
    <connection from="e_corr_rev_2" to="e_corr_rev_1" fromLane="1" toLane="1" dir="s" state="M"/>
</net>
"""
        view_xml = f"""<viewsettings>
    <scheme name="real world"/>
    <delay value="15"/>
    <viewport zoom="120" x="{length/2:.1f}" y="400"/>
</viewsettings>
"""
        return nodes_xml, edges_xml, net_xml, view_xml, (0, length)

def _build_routes(archetype: str, veh_count: int, speed_ms: float, duration_s: int, incident_cfg: Dict[str, Any]) -> str:
    """Generates the appropriate vehicle types, routes, and vehicle flows."""
    has_incident = incident_cfg.get('enabled', False)
    incident_time = float(incident_cfg.get('trigger_time_s', 45.0))
    incident_veh_id = int(incident_cfg.get('vehicle_id', 1))

    if archetype == 'highway':
        # Platooning truck convoy
        return f"""<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="truck_leader" accel="1.8" decel="4.0" sigma="0.1" length="16.5" minGap="4.0" maxSpeed="{speed_ms:.1f}" color="0,120,255"/>
    <vType id="truck_follower" accel="2.2" decel="4.5" sigma="0.0" length="16.5" minGap="2.0" maxSpeed="{speed_ms:.1f}" color="0,200,100"/>
    <vType id="civilian_car" accel="2.6" decel="4.5" sigma="0.5" length="4.5" minGap="2.5" maxSpeed="{speed_ms*1.2:.1f}" color="200,200,200"/>

    <route id="r_highway_fwd" edges="e_fwd_1 e_fwd_2"/>
    <route id="r_highway_rev" edges="e_rev_2 e_rev_1"/>

    <!-- Platoon Convoy (Leader + Followers) -->
    <vehicle id="veh_0" type="truck_leader" route="r_highway_fwd" depart="0.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_1" type="truck_follower" route="r_highway_fwd" depart="1.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_2" type="truck_follower" route="r_highway_fwd" depart="2.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_3" type="truck_follower" route="r_highway_fwd" depart="3.0" departLane="0" departSpeed="{speed_ms:.1f}"/>

    <!-- Additional traffic flow -->
    <flow id="veh_traffic" type="civilian_car" route="r_highway_rev" begin="5" end="{duration_s}" number="{max(0, veh_count - 4)}" departLane="best" departSpeed="{speed_ms:.1f}"/>
</routes>
"""
    elif archetype == 'emergency':
        return f"""<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="ambulance" accel="3.5" decel="5.0" sigma="0.1" length="5.5" minGap="2.0" maxSpeed="{speed_ms*1.3:.1f}" color="255,0,0"/>
    <vType id="car" accel="2.4" decel="4.5" sigma="0.5" length="4.5" minGap="2.5" maxSpeed="{speed_ms:.1f}" color="0,150,220"/>

    <route id="r_corr_fwd" edges="e_corr_1 e_corr_2"/>
    <route id="r_corr_rev" edges="e_corr_rev_2 e_corr_rev_1"/>

    <!-- Priority Ambulance -->
    <vehicle id="veh_1" type="ambulance" route="r_corr_fwd" depart="0.0" departLane="1" departSpeed="{speed_ms:.1f}"/>

    <!-- Surrounding traffic -->
    <flow id="veh_fwd" type="car" route="r_corr_fwd" begin="1.0" end="{duration_s}" number="{max(1, veh_count//2)}" departLane="0" departSpeed="{speed_ms*0.9:.1f}"/>
    <flow id="veh_rev" type="car" route="r_corr_rev" begin="1.0" end="{duration_s}" number="{max(1, veh_count - veh_count//2 - 1)}" departLane="best" departSpeed="{speed_ms:.1f}"/>
</routes>
"""
    elif archetype == 'urban':
        return f"""<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="urban_car" accel="2.5" decel="4.5" sigma="0.5" length="4.2" minGap="2.0" maxSpeed="13.8" color="0,200,255"/>
    <vType id="incident_car" accel="2.0" decel="5.0" sigma="0.2" length="4.5" minGap="2.0" maxSpeed="11.1" color="255,50,0"/>

    <route id="r_perimeter_clockwise" edges="e_h_0_0_1 e_h_0_1_2 e_v_0_1_2 e_v_1_2_2 e_h_2_2_1 e_h_2_1_0 e_v_2_1_0 e_v_1_0_0"/>
    <route id="r_cross_diag" edges="e_h_1_0_1 e_h_1_1_2 e_v_1_2_2 e_v_2_1_2"/>

    <vehicle id="veh_incident" type="incident_car" route="r_cross_diag" depart="0.0" departLane="best" departSpeed="10.0"/>
    <flow id="veh_urban_1" type="urban_car" route="r_perimeter_clockwise" begin="1.0" end="{duration_s}" number="{max(1, veh_count - 1)}" departLane="best" departSpeed="8.0"/>
</routes>
"""
    elif archetype == 'rail':
        return f"""<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="frecciarossa" accel="1.2" decel="2.5" sigma="0.0" length="200.0" minGap="50.0" maxSpeed="{speed_ms:.1f}" color="200,20,20"/>

    <route id="r_rail_north_south" edges="e_rail_1 e_rail_tunnel e_rail_2"/>
    <route id="r_rail_south_north" edges="e_rail_rev_2 e_rail_rev_tunnel e_rail_rev_1"/>

    <vehicle id="veh_0" type="frecciarossa" route="r_rail_north_south" depart="0.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_1" type="frecciarossa" route="r_rail_north_south" depart="60.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_2" type="frecciarossa" route="r_rail_south_north" depart="20.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <vehicle id="veh_3" type="frecciarossa" route="r_rail_south_north" depart="80.0" departLane="0" departSpeed="{speed_ms:.1f}"/>
</routes>
"""
    else:
        # Default corridor
        return f"""<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">
    <vType id="node_unit" accel="2.0" decel="4.0" sigma="0.3" length="6.0" minGap="5.0" maxSpeed="{speed_ms:.1f}" color="0,180,180"/>

    <route id="r_corr_fwd" edges="e_corr_1 e_corr_2"/>
    <route id="r_corr_rev" edges="e_corr_rev_2 e_corr_rev_1"/>

    <flow id="veh_units_fwd" type="node_unit" route="r_corr_fwd" begin="0" end="{duration_s}" number="{veh_count//2}" departLane="0" departSpeed="{speed_ms:.1f}"/>
    <flow id="veh_units_rev" type="node_unit" route="r_corr_rev" begin="0" end="{duration_s}" number="{veh_count - veh_count//2}" departLane="best" departSpeed="{speed_ms:.1f}"/>
</routes>
"""
