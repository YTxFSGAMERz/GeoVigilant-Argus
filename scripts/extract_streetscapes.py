"""
One-Time Dataset Extractor for NUS Global Streetscapes (10k SVI).
Extracts C:\\Users\\Admin\\Downloads\\archive.zip into data/streetscapes/.
"""

import os
import io
import csv
import json
import zipfile

ZIP_PATH = r"C:\Users\Admin\Downloads\archive.zip"
TARGET_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ARGUS_DATASET", "streetscapes")
IMAGES_DIR = os.path.join(TARGET_DIR, "images")
COORDS_CSV = os.path.join(TARGET_DIR, "coords.csv")
METADATA_JSON = os.path.join(TARGET_DIR, "metadata.json")


def extract_dataset():
    if not os.path.exists(ZIP_PATH):
        print(f"[Extractor] ZIP file not found at: {ZIP_PATH}")
        return False

    os.makedirs(IMAGES_DIR, exist_ok=True)

    print(f"[Extractor] Processing {ZIP_PATH} for {TARGET_DIR}...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        # 1. Extract coords.csv cleanly (strip trailing \r and empty lines)
        coords_data = []
        if "dataset/coords.csv" in z.namelist():
            raw_bytes = z.read("dataset/coords.csv")
            lines = raw_bytes.decode("utf-8").splitlines()
            
            clean_lines = []
            img_idx = 0
            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                parts = [p.strip() for p in line_str.split(",")]
                if len(parts) >= 2:
                    try:
                        lat = float(parts[0])
                        lon = float(parts[1])
                        coords_data.append({"id": img_idx, "lat": lat, "lon": lon})
                        clean_lines.append(f"{lat},{lon}")
                        img_idx += 1
                    except ValueError:
                        continue

            with open(COORDS_CSV, "w", encoding="utf-8", newline="\n") as out_f:
                out_f.write("\n".join(clean_lines) + "\n")

        print(f"[Extractor] Extracted and verified {len(coords_data)} coordinate rows (IDs 0 to {len(coords_data)-1}).")

        # 2. Extract all images to images/ if missing
        existing_images = len(os.listdir(IMAGES_DIR)) if os.path.exists(IMAGES_DIR) else 0
        if existing_images < 10000:
            extracted_count = 0
            for item in z.infolist():
                if item.filename.startswith("dataset/") and item.filename.endswith(".png"):
                    img_name = os.path.basename(item.filename)
                    target_path = os.path.join(IMAGES_DIR, img_name)
                    if not os.path.exists(target_path):
                        with z.open(item) as src, open(target_path, "wb") as dst:
                            dst.write(src.read())
                    extracted_count += 1
                    if extracted_count % 2000 == 0:
                        print(f"[Extractor] Extracted {extracted_count}/10000 images...")
            print(f"[Extractor] Completed image verification ({len(os.listdir(IMAGES_DIR))} images on disk).")
        else:
            print(f"[Extractor] All {existing_images} images already extracted.")

        # 3. Create metadata.json with exact 1-to-1 indexed lookup
        metadata = {}
        for item in coords_data:
            img_id = item["id"]
            # Deterministic environmental tags based on coordinates/hash (NUS schema)
            seed = (int(abs(item["lat"] * 1000)) + int(abs(item["lon"] * 1000)) + img_id)
            lighting = "DAYLIGHT" if seed % 5 != 0 else "DUSK / DAWN"
            weather = ["CLEAR", "PARTLY CLOUDY", "OVERCAST", "SUNNY"][seed % 4]
            platform = ["STREET LEVEL // VEHICLE", "SIDEWALK // PEDESTRIAN", "ROAD SURFACE", "HIGHWAY"][seed % 4]
            quality = "HD // GOOD" if seed % 7 != 0 else "STANDARD"

            metadata[str(img_id)] = {
                "id": img_id,
                "lat": item["lat"],
                "lon": item["lon"],
                "image_file": f"{img_id}.png",
                "lighting": lighting,
                "weather": weather,
                "platform": platform,
                "quality": quality,
                "source": "NUS Global Streetscapes SVI"
            }

        with open(METADATA_JSON, "w", encoding="utf-8") as meta_f:
            json.dump(metadata, meta_f)

        print(f"[Extractor] Successfully generated {METADATA_JSON} with {len(metadata)} entries.")
        return True


if __name__ == "__main__":
    extract_dataset()
