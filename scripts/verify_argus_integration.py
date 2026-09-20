import os
import sys
import io

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

print("=" * 70)
print("🔍 VERIFYING ARGUS GROUNDVIEW INTEGRATION IN GEOVIGILANT-ARGUS")
print("=" * 70)

# 1. Test Backend Flask Client
try:
    from app import app
    client = app.test_client()
    print("✓ Flask application loaded successfully.")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"✗ Failed to import Flask app: {e}")
    sys.exit(1)

# Test /api/argus/stats
resp = client.get('/api/argus/stats')
assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
stats = resp.get_json()
print(f"✓ /api/argus/stats: {stats['total_places']} places, {stats['total_images']} assets ({stats['total_size_gb']} GB), {stats['unique_countries']} countries, {stats.get('bktree_indexed_images', 0)} indexed in BK-Tree")

# Test /api/argus/categories
resp = client.get('/api/argus/categories')
assert resp.status_code == 200
categories = resp.get_json()
print(f"✓ /api/argus/categories: {len(categories)} distinct categories found ({', '.join([c['id'] for c in categories[:5]])}...)")

# Test /api/argus/places/geojson
resp = client.get('/api/argus/places/geojson')
assert resp.status_code == 200
geojson = resp.get_json()
features = geojson.get('features', [])
assert len(features) > 0, "Expected features > 0"
print(f"✓ /api/argus/places/geojson: {len(features)} GeoJSON features generated")

# Test /api/argus/places/geojson?category=
first_cat = categories[0]['id']
resp = client.get(f'/api/argus/places/geojson?category={first_cat}')
assert resp.status_code == 200
filtered_features = resp.get_json().get('features', [])
print(f"✓ /api/argus/places/geojson?category={first_cat}: {len(filtered_features)} filtered features")

# Test /api/argus/places/<id>
first_place_id = features[0]['properties']['place_id']
resp = client.get(f'/api/argus/places/{first_place_id}')
assert resp.status_code == 200
place_detail = resp.get_json()
assert 'name' in place_detail and 'images' in place_detail
print(f"✓ /api/argus/places/{first_place_id}: '{place_detail['name']}' with {len(place_detail['images'])} images")

# Test /api/argus/places/nearby
lat = features[0]['geometry']['coordinates'][1]
lon = features[0]['geometry']['coordinates'][0]
resp = client.get(f'/api/argus/places/nearby?lat={lat}&lon={lon}&radius_km=100')
assert resp.status_code == 200
nearby = resp.get_json()
print(f"✓ /api/argus/places/nearby: {len(nearby)} nearby places found around ({lat:.2f}, {lon:.2f})")

# Test /api/argus/images/<id>
if place_detail['images']:
    first_image_id = place_detail['images'][0]['image_id']
    resp = client.get(f'/api/argus/images/{first_image_id}')
    assert resp.status_code == 200
    assert resp.content_type in ['image/jpeg', 'image/png', 'image/webp']
    print(f"✓ /api/argus/images/{first_image_id}: image stream verified ({len(resp.data)} bytes, {resp.content_type})")

# Test /api/argus/visual-search via POST with raw image
from argus_dataset_service import argus_dataset_service
sample_img_path = argus_dataset_service.get_image_path(first_image_id)
if sample_img_path and os.path.exists(sample_img_path):
    with open(sample_img_path, 'rb') as f:
        img_bytes = f.read()
    
    data = {
        'image': (io.BytesIO(img_bytes), 'query.jpg')
    }
    resp = client.post('/api/argus/visual-search?max_dist=10&limit=5', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    search_result = resp.get_json()
    matches = search_result.get('matches', [])
    assert len(matches) > 0, "Expected at least 1 match for existing image"
    print(f"✓ /api/argus/visual-search: query pHash {search_result['computed_phash']} matched {len(matches)} targets (Top match: '{matches[0]['place_name']}' - Hamming: {matches[0]['hamming_distance']})")

# 2. Check Static Frontend Bundles
assert os.path.exists('static/js/groundview-main.js'), "static/js/groundview-main.js missing"
assert os.path.exists('static/js/globe-main.js'), "static/js/globe-main.js missing"
print("✓ Static Vite bundles verified on disk.")

print("=" * 70)
print("🎯 ALL ARGUS GROUNDVIEW INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
print("=" * 70)
