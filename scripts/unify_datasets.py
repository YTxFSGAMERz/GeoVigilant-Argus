"""
ARGUS DATASET — Unified Ingestion & Multi-Source Cross-Dataset Indexer.

Consolidates all disparate geoint datasets across the repository:
1. ARGUS Landmark Dataset (3,806 places, 74,128 visual assets) [Already in state_tracker.db]
2. NUS Global Streetscapes SVI (10,000 observation points, 1,040 images)
3. Global Surveillance Camera Network (178,674 cameras with operator telemetry)
4. ALPR Inter-Agency Surveillance Sharing Networks (4,253 network links)
5. Law Enforcement & Police Precincts USA (272 precinct jurisdictions)
6. Global Metropolises (1,249 world cities)

Populates ARGUS_DATASET/indexes/state_tracker.db with dedicated tables,
foreign keys, and high-performance B-tree spatial indices.
"""

import os
import sys
import json
import time
import shutil
import sqlite3
from typing import Optional, Tuple, List, Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARGUS_DIR = os.path.join(BASE_DIR, "ARGUS_DATASET")
INDEXES_DIR = os.path.join(ARGUS_DIR, "indexes")
DB_PATH = os.path.join(INDEXES_DIR, "state_tracker.db")

STREETSCAPES_COORDS = os.path.join(ARGUS_DIR, "streetscapes", "coords.csv")
STREETSCAPES_META = os.path.join(ARGUS_DIR, "streetscapes", "metadata.json")

CAMERAS_GEOJSON = os.path.join(ARGUS_DIR, "geodata", "CAMERAS_WITH_NETWORK_DATA.geojson")
CAMERA_NETWORKS_JSON = os.path.join(ARGUS_DIR, "geodata", "camera_networks.json")
POLICE_GEOJSON = os.path.join(ARGUS_DIR, "geodata", "police_precincts_usa.geojson")
CITIES_GEOJSON = os.path.join(BASE_DIR, "static", "data", "cities.geojson")


def get_centroid(geom: Optional[Dict[str, Any]]) -> Tuple[Optional[float], Optional[float]]:
    """Calculates approximate centroid (lat, lon) from GeoJSON geometry."""
    if not geom:
        return None, None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords:
        return None, None

    pts = []
    if gtype == "Point":
        return coords[1], coords[0]
    elif gtype == "Polygon":
        for ring in coords:
            for pt in ring:
                pts.append(pt)
    elif gtype == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for pt in ring:
                    pts.append(pt)
    elif gtype in ("LineString", "MultiPoint"):
        for pt in coords:
            pts.append(pt)

    if not pts:
        return None, None

    avg_lon = sum(p[0] for p in pts) / len(pts)
    avg_lat = sum(p[1] for p in pts) / len(pts)
    return avg_lat, avg_lon


def init_unified_tables(conn: sqlite3.Connection):
    """Creates schema for unified ARGUS DATASET tables and spatial indices."""
    c = conn.cursor()

    # 1. Streetscapes SVI table
    c.execute("""
        CREATE TABLE IF NOT EXISTS streetscapes (
            id INTEGER PRIMARY KEY,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            lighting TEXT DEFAULT 'DAYLIGHT',
            weather TEXT DEFAULT 'CLEAR',
            platform TEXT DEFAULT 'STREET LEVEL',
            quality TEXT DEFAULT 'HD // GOOD',
            image_file TEXT,
            source TEXT DEFAULT 'ARGUS DATASET - Global Streetscapes SVI'
        )
    """)

    # 2. Surveillance Cameras table
    c.execute("""
        CREATE TABLE IF NOT EXISTS surveillance_cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            camera_type TEXT,
            operator TEXT,
            operator_wikidata TEXT,
            surveillance_type TEXT,
            zone TEXT,
            website TEXT,
            ref TEXT,
            source TEXT DEFAULT 'ARGUS DATASET - Global Surveillance Grid',
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
    """)

    # 3. ALPR / Surveillance Sharing Networks table
    c.execute("""
        CREATE TABLE IF NOT EXISTS camera_sharing_networks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_name TEXT,
            from_latitude REAL NOT NULL,
            from_longitude REAL NOT NULL,
            sharing_count INTEGER DEFAULT 0,
            connections_json TEXT
        )
    """)

    # 4. Law Enforcement & Police Precincts table
    c.execute("""
        CREATE TABLE IF NOT EXISTS police_precincts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            district TEXT,
            city TEXT,
            source_file TEXT,
            latitude REAL,
            longitude REAL,
            properties_json TEXT,
            geometry_json TEXT
        )
    """)

    # 5. Global Metropolises table
    c.execute("""
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            country TEXT,
            sov_a3 TEXT,
            population INTEGER DEFAULT 0,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
    """)

    conn.commit()


def ingest_streetscapes(conn: sqlite3.Connection) -> int:
    """Ingests 10,000 NUS Global Streetscapes observation points."""
    print("Ingesting Streetscapes (10k SVI)...")
    t0 = time.time()
    c = conn.cursor()

    meta_map = {}
    if os.path.exists(STREETSCAPES_META):
        with open(STREETSCAPES_META, "r", encoding="utf-8") as f:
            meta_map = json.load(f)

    rows = []
    if os.path.exists(STREETSCAPES_COORDS):
        with open(STREETSCAPES_COORDS, "r", encoding="utf-8") as f:
            idx = 0
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = [p.strip() for p in line_str.split(",")]
                if len(parts) >= 2:
                    try:
                        lat = float(parts[0])
                        lon = float(parts[1])
                        m = meta_map.get(str(idx), {})
                        rows.append((
                            idx,
                            lat,
                            lon,
                            m.get("lighting", "DAYLIGHT"),
                            m.get("weather", "CLEAR"),
                            m.get("platform", "STREET LEVEL"),
                            m.get("quality", "HD // GOOD"),
                            m.get("image_file", f"{idx}.png"),
                            m.get("source", "ARGUS DATASET - Global Streetscapes SVI")
                        ))
                        idx += 1
                    except ValueError:
                        continue

    c.execute("DELETE FROM streetscapes")
    c.executemany("""
        INSERT INTO streetscapes (id, latitude, longitude, lighting, weather, platform, quality, image_file, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"✓ Ingested {len(rows)} streetscape points in {time.time() - t0:.2f}s")
    return len(rows)


def ingest_surveillance_cameras(conn: sqlite3.Connection) -> int:
    """Ingests 178,674 surveillance camera nodes from CAMERAS_WITH_NETWORK_DATA.geojson."""
    print("Ingesting Surveillance Cameras (178k nodes)...")
    t0 = time.time()
    c = conn.cursor()

    if not os.path.exists(CAMERAS_GEOJSON):
        print(f"Warning: {CAMERAS_GEOJSON} not found!")
        return 0

    with open(CAMERAS_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    batch = []
    batch_size = 10000

    c.execute("DELETE FROM surveillance_cameras")

    insert_sql = """
        INSERT INTO surveillance_cameras (
            name, camera_type, operator, operator_wikidata,
            surveillance_type, zone, website, ref, source,
            latitude, longitude
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    count = 0
    for feat in features:
        geom = feat.get("geometry")
        if not geom or geom.get("type") != "Point":
            continue
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue

        lon, lat = coords[0], coords[1]
        props = feat.get("properties") or {}

        name = props.get("name") or props.get("ref") or f"Surveillance Node #{count + 1}"
        cam_type = props.get("camera:type") or "fixed"
        operator = props.get("operator") or "Public Safety / Municipal"
        op_wiki = props.get("operator:wikidata") or ""
        surv_type = props.get("surveillance:type") or "camera"
        zone = props.get("surveillance:zone") or props.get("surveillance") or "traffic"
        website = props.get("website") or props.get("url") or ""
        ref = props.get("ref") or ""
        src = props.get("source") or "ARGUS DATASET - Surveillance Grid"

        batch.append((
            name, cam_type, operator, op_wiki,
            surv_type, zone, website, ref, src,
            float(lat), float(lon)
        ))
        count += 1

        if len(batch) >= batch_size:
            c.executemany(insert_sql, batch)
            conn.commit()
            batch = []

    if batch:
        c.executemany(insert_sql, batch)
        conn.commit()

    print(f"✓ Ingested {count} surveillance cameras in {time.time() - t0:.2f}s")
    return count


def ingest_camera_networks(conn: sqlite3.Connection) -> int:
    """Ingests 4,253 inter-agency ALPR surveillance sharing networks."""
    print("Ingesting ALPR Surveillance Sharing Networks...")
    t0 = time.time()
    c = conn.cursor()

    if not os.path.exists(CAMERA_NETWORKS_JSON):
        print(f"Warning: {CAMERA_NETWORKS_JSON} not found!")
        return 0

    with open(CAMERA_NETWORKS_JSON, "r", encoding="utf-8") as f:
        networks = json.load(f)

    c.execute("DELETE FROM camera_sharing_networks")
    rows = []
    for item in networks:
        from_coord = item.get("from")
        if not from_coord or len(from_coord) < 2:
            continue
        from_lat, from_lon = from_coord[0], from_coord[1]
        from_name = item.get("from_name", "Unknown Agency")
        sharing_count = item.get("sharing_count", 0)
        connections_json = json.dumps(item.get("connections", []))
        rows.append((from_name, float(from_lat), float(from_lon), int(sharing_count), connections_json))

    c.executemany("""
        INSERT INTO camera_sharing_networks (from_name, from_latitude, from_longitude, sharing_count, connections_json)
        VALUES (?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"✓ Ingested {len(rows)} ALPR sharing networks in {time.time() - t0:.2f}s")
    return len(rows)


def ingest_police_precincts(conn: sqlite3.Connection) -> int:
    """Ingests 272 USA police precinct jurisdictions and calculates centroids."""
    print("Ingesting Police Precincts USA...")
    t0 = time.time()
    c = conn.cursor()

    if not os.path.exists(POLICE_GEOJSON):
        print(f"Warning: {POLICE_GEOJSON} not found!")
        return 0

    with open(POLICE_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    c.execute("DELETE FROM police_precincts")

    rows = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        lat, lon = get_centroid(geom)

        district = str(props.get("DISTRICT") or props.get("PRECINCT") or props.get("ID") or "Precinct")
        city = str(props.get("city") or "USA Law Enforcement Jurisdiction")
        source_file = str(props.get("source_file") or "police_precincts_usa.geojson")
        props_json = json.dumps(props)
        geom_json = json.dumps(geom) if geom else "{}"

        rows.append((
            district, city, source_file,
            lat, lon, props_json, geom_json
        ))

    c.executemany("""
        INSERT INTO police_precincts (
            district, city, source_file, latitude, longitude, properties_json, geometry_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"✓ Ingested {len(rows)} police precinct jurisdictions in {time.time() - t0:.2f}s")
    return len(rows)


def ingest_cities(conn: sqlite3.Connection) -> int:
    """Ingests 1,249 world metropolises from cities.geojson."""
    print("Ingesting Global Metropolises...")
    t0 = time.time()
    c = conn.cursor()

    if not os.path.exists(CITIES_GEOJSON):
        print(f"Warning: {CITIES_GEOJSON} not found!")
        return 0

    with open(CITIES_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    c.execute("DELETE FROM cities")

    rows = []
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if not coords or len(coords) < 2:
            continue

        lon, lat = coords[0], coords[1]
        name = props.get("NAME") or props.get("NAMEASCII") or "Metropolis"
        country = props.get("ADM0NAME") or props.get("SOV0NAME") or ""
        sov_a3 = props.get("SOV_A3") or props.get("ADM0_A3") or ""
        pop = int(props.get("POP_MAX") or props.get("POP_MIN") or 0)

        rows.append((name, country, sov_a3, pop, float(lat), float(lon)))

    c.executemany("""
        INSERT INTO cities (name, country, sov_a3, population, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"✓ Ingested {len(rows)} global metropolises in {time.time() - t0:.2f}s")
    return len(rows)


def build_spatial_indices(conn: sqlite3.Connection):
    """Constructs high-performance B-tree spatial indices for instantaneous queries."""
    print("Building composite B-tree spatial indices...")
    t0 = time.time()
    c = conn.cursor()

    indices = [
        ("idx_places_coords", "places(latitude, longitude)"),
        ("idx_places_cat", "places(category)"),
        ("idx_streetscapes_coords", "streetscapes(latitude, longitude)"),
        ("idx_cameras_coords", "surveillance_cameras(latitude, longitude)"),
        ("idx_cameras_operator", "surveillance_cameras(operator)"),
        ("idx_cameras_zone", "surveillance_cameras(zone)"),
        ("idx_networks_coords", "camera_sharing_networks(from_latitude, from_longitude)"),
        ("idx_precincts_coords", "police_precincts(latitude, longitude)"),
        ("idx_cities_coords", "cities(latitude, longitude)"),
        ("idx_cities_pop", "cities(population DESC)")
    ]

    for name, cols in indices:
        c.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {cols}")

    conn.commit()
    print(f"✓ Built {len(indices)} spatial and relational indices in {time.time() - t0:.2f}s")


def main():
    print("================================================================")
    print("       ARGUS DATASET — UNIFIED GEOINT INGESTION PIPELINE        ")
    print("================================================================")
    t_start = time.time()

    if not os.path.exists(DB_PATH):
        print(f"Error: Target database {DB_PATH} not found!")
        sys.exit(1)

    # Optional safety backup if not already present
    bak_path = DB_PATH + ".bak"
    if not os.path.exists(bak_path):
        print(f"Creating safety backup: {bak_path}")
        shutil.copy2(DB_PATH, bak_path)

    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. Initialize schema
        init_unified_tables(conn)

        # 2. Ingest datasets
        cnt_svi = ingest_streetscapes(conn)
        cnt_cam = ingest_surveillance_cameras(conn)
        cnt_net = ingest_camera_networks(conn)
        cnt_pol = ingest_police_precincts(conn)
        cnt_cit = ingest_cities(conn)

        # 3. Build spatial indices
        build_spatial_indices(conn)

        # 4. Summary & Verification
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM places")
        cnt_places = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM assets WHERE local_path IS NOT NULL")
        cnt_assets = c.fetchone()[0]

        total_points = cnt_places + cnt_svi + cnt_cam + cnt_net + cnt_pol + cnt_cit

        print("\n----------------------------------------------------------------")
        print("          ARGUS DATASET UNIFIED INVENTORY AUDIT                ")
        print("----------------------------------------------------------------")
        print(f"  • Verified Landmarks (ARGUS Ground Truth): {cnt_places:,} places ({cnt_assets:,} images)")
        print(f"  • Streetscapes SVI Observation Points:     {cnt_svi:,} points")
        print(f"  • Surveillance Camera Nodes:                {cnt_cam:,} cameras")
        print(f"  • ALPR Inter-Agency Sharing Networks:      {cnt_net:,} networks")
        print(f"  • Law Enforcement / Police Precincts:       {cnt_pol:,} jurisdictions")
        print(f"  • Global Metropolises:                     {cnt_cit:,} cities")
        print("----------------------------------------------------------------")
        print(f"  ★ TOTAL UNIFIED GEOINT ENTITIES:           {total_points:,} targets")
        print(f"  ★ TOTAL TIME ELAPSED:                      {time.time() - t_start:.2f}s")
        print("================================================================\n")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
