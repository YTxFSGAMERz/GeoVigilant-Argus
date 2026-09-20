import os
import sqlite3

db_path = os.path.abspath("ARGUS_DATASET/indexes/state_tracker.db")
images_dir = os.path.abspath("ARGUS_DATASET/images")

print(f"Connecting to {db_path}...")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# 1. List all tables and schemas
print("\n--- TABLES IN DATABASE ---")
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cur.fetchall()]
for t in tables:
    cur.execute(f"SELECT count(*) FROM {t}")
    cnt = cur.fetchone()[0]
    print(f"Table '{t}': {cnt} rows")

# 2. Check asset statuses
print("\n--- ASSET STATUS BREAKDOWN ---")
try:
    cur.execute("SELECT status, count(*) FROM assets GROUP BY status")
    for row in cur.fetchall():
        print(f"Status '{row[0]}': {row[1]}")
except Exception as e:
    print(f"Error querying asset status: {e}")

# 3. Check places breakdown (how many have images, how many don't)
print("\n--- PLACES IMAGE COUNT STATS ---")
cur.execute("""
    SELECT 
        COUNT(*) as total_places,
        SUM(CASE WHEN images_count > 0 THEN 1 ELSE 0 END) as places_with_images,
        SUM(CASE WHEN images_count = 0 OR images_count IS NULL THEN 1 ELSE 0 END) as places_with_zero_images
    FROM places
""")
row = cur.fetchone()
print(f"Total Places: {row['total_places']}")
print(f"Places with images > 0: {row['places_with_images']}")
print(f"Places with images = 0: {row['places_with_zero_images']}")

# 4. Check asset local_path null vs non-null vs disk existence
print("\n--- ASSET DISK EXISTENCE AUDIT ---")
cur.execute("SELECT count(*) FROM assets WHERE local_path IS NULL OR local_path = ''")
null_paths = cur.fetchone()[0]
cur.execute("SELECT count(*) FROM assets WHERE local_path IS NOT NULL AND local_path != ''")
non_null_paths = cur.fetchone()[0]
print(f"Assets with local_path IS NULL / empty: {null_paths}")
print(f"Assets with local_path recorded: {non_null_paths}")

# Check sample of missing files or error fields
cur.execute("PRAGMA table_info(assets)")
columns = [col[1] for col in cur.fetchall()]
print(f"Asset columns: {columns}")

if 'error' in columns or 'error_message' in columns or 'failure_reason' in columns:
    err_col = 'error' if 'error' in columns else ('error_message' if 'error_message' in columns else 'failure_reason')
    cur.execute(f"SELECT {err_col}, count(*) FROM assets WHERE {err_col} IS NOT NULL AND {err_col} != '' GROUP BY {err_col} LIMIT 10")
    print(f"\n--- ERROR BREAKDOWN in {err_col} ---")
    for r in cur.fetchall():
        print(f"{r[0]}: {r[1]}")

# 5. Check if files on disk match DB
disk_files = set()
for root, dirs, files in os.walk(images_dir):
    for f in files:
        disk_files.add(f)

print(f"\nTotal files on disk in images/: {len(disk_files)}")

# Check how many DB assets exist on disk
cur.execute("SELECT id, local_path FROM assets WHERE local_path IS NOT NULL AND local_path != ''")
assets_db = cur.fetchall()
found_on_disk = 0
missing_on_disk = 0
missing_samples = []

for a in assets_db:
    lpath = a['local_path']
    fname = os.path.basename(lpath)
    # Check absolute or relative or basename in disk_files
    if os.path.exists(lpath) or fname in disk_files:
        found_on_disk += 1
    else:
        missing_on_disk += 1
        if len(missing_samples) < 10:
            missing_samples.append((a['id'], lpath))

print(f"DB Assets found on disk: {found_on_disk}")
print(f"DB Assets missing on disk: {missing_on_disk}")
if missing_samples:
    print("Sample missing assets in DB:")
    for mid, mpath in missing_samples:
        print(f"  ID: {mid} -> Expected: {mpath}")

# Check if there are other log tables or history
for t in tables:
    if 'log' in t.lower() or 'history' in t.lower() or 'task' in t.lower() or 'state' in t.lower():
        print(f"\nSample from table '{t}':")
        cur.execute(f"SELECT * FROM {t} LIMIT 5")
        for r in cur.fetchall():
            print(dict(r))

conn.close()
