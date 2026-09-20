import os
import sqlite3

db_path = os.path.abspath("ARGUS_DATASET/indexes/state_tracker.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- INSPECTING MISSING ASSETS (14,873 records) ---")
cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN sha256 IS NULL THEN 1 ELSE 0 END) as null_sha,
        SUM(CASE WHEN phash IS NULL THEN 1 ELSE 0 END) as null_phash,
        SUM(CASE WHEN width IS NULL THEN 1 ELSE 0 END) as null_width,
        SUM(CASE WHEN file_size_bytes IS NULL OR file_size_bytes = 0 THEN 1 ELSE 0 END) as zero_bytes
    FROM assets 
    WHERE sha256 IS NULL OR sha256 = ''
""")
row = cur.fetchone()
print(f"Total with null sha256: {row['total']}")
print(f"Null pHash: {row['null_phash']}")
print(f"Null width/height: {row['null_width']}")
print(f"Zero file size: {row['zero_bytes']}")

cur.execute("""
    SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN sha256 IS NOT NULL THEN 1 ELSE 0 END) as valid_sha,
        SUM(CASE WHEN phash IS NOT NULL THEN 1 ELSE 0 END) as valid_phash
    FROM assets 
    WHERE sha256 IS NOT NULL AND sha256 != ''
""")
row2 = cur.fetchone()
print(f"\nTotal with valid sha256: {row2['total']}")
print(f"Valid pHash: {row2['valid_phash']}")

# Check why Wikimedia or Mapillary URLs failed
cur.execute("SELECT source, source_url FROM assets WHERE sha256 IS NULL LIMIT 10")
print("\nSample source URLs for un-downloaded items:")
for r in cur.fetchall():
    print(f"  [{r['source']}] {r['source_url']}")

conn.close()
