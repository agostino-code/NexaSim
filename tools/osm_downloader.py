#!/usr/bin/env python3
"""
NexaSim OpenStreetMap (OSM) Downloader & Geographic Cache Manager
Horizon Europe NexaSphere Research Project

Downloads real road networks via OpenStreetMap Overpass API for a given bounding box
and caches the resulting .osm XML files locally using SHA256 hashing.
"""

import os
import sys
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = REPO_ROOT / 'scenarios' / 'cache' / 'osm'

OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

def compute_bbox_hash(bbox: List[float]) -> str:
    """Computes a unique SHA256 identifier for a given [min_lon, min_lat, max_lon, max_lat]."""
    bbox_str = f"{bbox[0]:.6f}_{bbox[1]:.6f}_{bbox[2]:.6f}_{bbox[3]:.6f}"
    return hashlib.sha256(bbox_str.encode('utf-8')).hexdigest()[:16]

def build_overpass_query(bbox: List[float]) -> str:
    """
    Builds Overpass QL query to download driveable highways, railways, and junctions.
    bbox format: [min_lon, min_lat, max_lon, max_lat]
    Overpass expects (min_lat, min_lon, max_lat, max_lon).
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    query = f"""
    [out:xml][timeout:60];
    (
      way["highway"~"motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|unclassified|service"]({min_lat},{min_lon},{max_lat},{max_lon});
      way["railway"~"rail|highspeed"]({min_lat},{min_lon},{max_lat},{max_lon});
    );
    (._;>;);
    out body;
    """
    return query.strip()

def download_osm_bbox(
    bbox: List[float],
    output_path: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    force_download: bool = False
) -> Path:
    """
    Retrieves OpenStreetMap XML for bounding box [min_lon, min_lat, max_lon, max_lat].
    Uses local cache if available unless force_download is True.
    """
    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    bbox_hash = compute_bbox_hash(bbox)
    cached_file = cache_dir / f"osm_{bbox_hash}.osm"

    if cached_file.exists() and cached_file.stat().st_size > 1024 and not force_download:
        print(f"[OSM Downloader] Using cached OSM data: {cached_file.name}")
        if output_path and Path(output_path) != cached_file:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copyfile(cached_file, output_path)
            return Path(output_path).resolve()
        return cached_file.resolve()

    query = build_overpass_query(bbox)
    data = urllib.parse.urlencode({'data': query}).encode('utf-8')

    success = False
    for server in OVERPASS_SERVERS:
        try:
            print(f"[OSM Downloader] Querying Overpass API ({server}) for bbox {bbox}...")
            req = urllib.request.Request(
                server,
                data=data,
                headers={'User-Agent': 'NexaSim-Simulator/1.0 (Horizon Europe NexaSphere)'}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                content = resp.read()
                if b'<osm' in content and b'</osm>' in content:
                    with open(cached_file, 'wb') as f:
                        f.write(content)
                    print(f"[OSM Downloader] Successfully downloaded and cached ({len(content)//1024} KB)")
                    success = True
                    break
        except Exception as e:
            print(f"[OSM Downloader] Server {server} failed: {e}")

    if not success:
        if cached_file.exists() and cached_file.stat().st_size > 0:
            print(f"[OSM Downloader] Warning: Network fetch failed, falling back to existing cache.")
            return cached_file.resolve()
        raise RuntimeError(f"Failed to fetch OpenStreetMap data for bbox {bbox} from all servers.")

    if output_path and Path(output_path) != cached_file:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copyfile(cached_file, output_path)
        return Path(output_path).resolve()

    return cached_file.resolve()

if __name__ == '__main__':
    # Test bounding box (Stelvio Pass snippet)
    test_bbox = [10.4500, 46.5200, 10.4850, 46.5500]
    out = download_osm_bbox(test_bbox)
    print(f"Result file: {out}")
