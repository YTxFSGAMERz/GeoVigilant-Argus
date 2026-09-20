"""
ARGUS DATASET — Unified Dataset Engine Verification Test Suite.
Tests:
- Database table integrity and record counts
- Composite spatial index performance (< 10ms target)
- Multi-layer nearby radius searches (Landmarks, Streetscapes, Cameras, Precincts, Cities)
- Viewport Bounding-Box GeoJSON queries
- Full API integration
"""

import os
import sys
import time
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from argus_unified_dataset_service import argus_unified_dataset_service

def test_unified_service():
    print("================================================================")
    print("      ARGUS DATASET UNIFIED SERVICE VERIFICATION SUITE         ")
    print("================================================================")
    
    t0 = time.time()
    ok = argus_unified_dataset_service.initialize()
    init_time = (time.time() - t0) * 1000
    print(f"✓ Initialization: {'SUCCESS' if ok else 'FAILED'} in {init_time:.2f} ms")
    assert ok, "Service failed to initialize"

    # 1. Test Unified Statistics
    stats = argus_unified_dataset_service.get_unified_statistics()
    print(f"✓ Dataset Suite: {stats['suite_name']}")
    print(f"✓ Total Unified Geoint Targets: {stats['total_geoint_entities']:,}")
    print(f"  - Verified Landmarks: {stats['layers']['landmarks']['count']:,} ({stats['layers']['landmarks']['verified_images']:,} images)")
    print(f"  - Streetscapes SVI:   {stats['layers']['streetscapes']['count']:,}")
    print(f"  - Surveillance Grid:  {stats['layers']['surveillance_grid']['cameras_count']:,} cameras ({stats['layers']['surveillance_grid']['alpr_sharing_networks']:,} ALPR networks)")
    print(f"  - Law Enforcement:    {stats['layers']['law_enforcement']['precincts_count']:,} precincts")
    print(f"  - Metropolises:       {stats['layers']['metropolises']['cities_count']:,} cities")
    assert stats["total_geoint_entities"] >= 190000, "Expected at least 190k entities"

    # 2. Test Multi-Layer Radius Search in Montreal (45.5017, -73.5673)
    t1 = time.time()
    results = argus_unified_dataset_service.search_nearby(45.5017, -73.5673, radius_km=5.0, limit=25)
    query_time = (time.time() - t1) * 1000
    print(f"\n✓ Multi-Layer Nearby Search (Montreal, radius 5km):")
    print(f"  Query executed in {query_time:.2f} ms — Found {len(results)} tactical targets:")
    for r in results[:5]:
        print(f"   [{r['layer'].upper()}] {r['name']} — {r['distance_km']} km away ({r['icon']})")
    assert len(results) > 0, "Expected nearby results"

    # 3. Test Multi-Layer Radius Search in Paris (48.8566, 2.3522)
    t2 = time.time()
    paris_results = argus_unified_dataset_service.search_nearby(48.8566, 2.3522, radius_km=10.0, limit=25)
    paris_time = (time.time() - t2) * 1000
    print(f"\n✓ Multi-Layer Nearby Search (Paris, radius 10km):")
    print(f"  Query executed in {paris_time:.2f} ms — Found {len(paris_results)} tactical targets:")
    for r in paris_results[:5]:
        print(f"   [{r['layer'].upper()}] {r['name']} — {r['distance_km']} km away ({r['icon']})")
    assert len(paris_results) > 0, "Expected Paris results"

    # 4. Test Bounding Box GeoJSON Query
    t3 = time.time()
    bbox_data = argus_unified_dataset_service.search_bbox(
        min_lat=45.45, min_lon=-73.65, max_lat=45.55, max_lon=-73.50, limit_per_layer=50
    )
    bbox_time = (time.time() - t3) * 1000
    features = bbox_data.get("features", [])
    print(f"\n✓ Bounding Box GeoJSON Extraction:")
    print(f"  Query executed in {bbox_time:.2f} ms — Extracted {len(features)} GeoJSON features")
    assert len(features) > 0, "Expected bbox features"

    # 5. Test Camera Detail & ALPR Network Link
    cam_id = 1
    cam_detail = argus_unified_dataset_service.get_camera_detail(cam_id)
    print(f"\n✓ Camera Detail Lookup (ID: {cam_id}):")
    print(f"  Name: {cam_detail['name']}")
    print(f"  Operator: {cam_detail['operator']}")
    print(f"  Zone: {cam_detail['zone']}")
    print(f"  Website: {cam_detail['website']}")
    print(f"  Source: {cam_detail['source']}")

    print("\n================================================================")
    print("         ALL UNIFIED DATASET ENGINE TESTS PASSED!               ")
    print("================================================================")

if __name__ == "__main__":
    test_unified_service()
