import os
import sqlite3

db_path = os.path.abspath("ARGUS_DATASET/indexes/state_tracker.db")
images_dir = os.path.abspath("ARGUS_DATASET/images")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. Investigate the 109 places with images_count = 0
cur.execute("SELECT place_id, name, country, city, category, images_count, wikipedia_url FROM places WHERE images_count = 0 OR images_count IS NULL LIMIT 20")
print("=== SAMPLE OF 109 PLACES WITH 0 IMAGES ===")
zero_places = cur.fetchall()
for p in zero_places:
    print(f"Place: {p['name']} ({p['category']}, {p['country']}) - URL: {p['wikipedia_url']}")

# 2. Check if there are assets in DB for these 109 places
zero_place_ids = [p['place_id'] for p in zero_places]
placeholders = ','.join(['?']*len(zero_place_ids))
cur.execute(f"SELECT place_id, count(*) FROM assets WHERE place_id IN ({placeholders}) GROUP BY place_id", zero_place_ids)
matched_assets = cur.fetchall()
print(f"\nAssets found in 'assets' table for sample zero-places: {len(matched_assets)}")

# 3. Check why 88,828 DB assets vs ~74,000 files on disk
# Let's map all files on disk
disk_files = {} # filename -> full_path
for root, dirs, files in os.walk(images_dir):
    for f in files:
        disk_files[f] = os.path.join(root, f)

print(f"\nTotal physical image files on disk: {len(disk_files)}")

cur.execute("SELECT image_id, place_id, source, local_path, file_size_bytes, phash, sha256 FROM assets")
all_assets = cur.fetchall()

missing_from_disk = []
present_on_disk = []
missing_by_source = {}
missing_by_place = {}

for a in all_assets:
    lpath = a['local_path']
    fname = os.path.basename(lpath)
    exists = os.path.exists(lpath) or (fname in disk_files)
    src = a['source'] or 'unknown'
    
    if exists:
        present_on_disk.append(a)
    else:
        missing_from_disk.append(a)
        missing_by_source[src] = missing_by_source.get(src, 0) + 1
        pid = a['place_id']
        missing_by_place[pid] = missing_by_place.get(pid, 0) + 1

print(f"\n=== ASSET DISK ANALYSIS ===")
print(f"Assets in DB: {len(all_assets)}")
print(f"Assets physically present on disk: {len(present_on_disk)}")
print(f"Assets recorded in DB but missing on disk: {len(missing_from_disk)}")

print("\nMissing assets by data source:")
for src, cnt in missing_by_source.items():
    print(f"  Source '{src}': {cnt} missing files")

print(f"\nNumber of places affected by missing files: {len(missing_by_place)}")

# Let's check sample missing asset records
print("\n=== SAMPLE MISSING ASSET RECORDS IN DB ===")
for a in missing_from_disk[:10]:
    print(f"  image_id: {a['image_id']} | place: {a['place_id']} | source: {a['source']} | path: {a['local_path']} | sha: {a['sha256'][:10] if a['sha256'] else 'None'} | phash: {a['phash']}")

# Check if these files were in a specific subfolder or if paths in DB point to a different directory / drive
sample_paths = [a['local_path'] for a in missing_from_disk[:10]]
print("\nSample paths recorded in DB for missing items:")
for p in sample_paths:
    print(f"  {p}")

# Check if there are files on disk not in DB
db_filenames = set(os.path.basename(a['local_path']) for a in all_assets)
orphan_files = [f for f in disk_files if f not in db_filenames]
print(f"\nFiles on disk that are NOT in DB: {len(orphan_files)}")

# Check duplicate sha256 or phash in DB
cur.execute("SELECT sha256, count(*) FROM assets WHERE sha256 IS NOT NULL GROUP BY sha256 HAVING count(*) > 1")
dup_sha = cur.fetchall()
print(f"Number of duplicate SHA256 hashes in DB: {len(dup_sha)}")

cur.execute("SELECT phash, count(*) FROM assets WHERE phash IS NOT NULL GROUP BY phash HAVING count(*) > 1")
dup_phash = cur.fetchall()
print(f"Number of duplicate pHash values in DB: {len(dup_phash)}")

conn.close()
