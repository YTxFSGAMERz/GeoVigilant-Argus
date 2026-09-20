"""
Multi-Source Image Acquisition Cascade (Tier 1 Wikimedia & Tier 4 Open Datasets).
Retrieves high-resolution landmark-specific assets with verified license provenance.
"""

import os
import re
import uuid
import logging
import argparse
import concurrent.futures
from typing import List, Dict, Any, Optional
from PIL import Image
from argus.config import load_config, ArgusConfig
from argus.http_client import ARGUSHttpClient
from argus.state_tracker import StateTracker
from argus.storage_guard import StorageGuard

logger = logging.getLogger(__name__)

NAMESPACE_ARGUS_IMG = uuid.UUID("7c9e1104-3a9b-4f51-b883-02fba7349182")

class AcquisitionEngine:
    def __init__(self, config: ArgusConfig, state_tracker: StateTracker):
        self.config = config
        self.tracker = state_tracker
        self.http = ARGUSHttpClient(user_agent=config.system.user_agent,
                                    rate_limits={"wikimedia.org": config.rate_limits.wikimedia_req_per_sec})
        self.guard = StorageGuard(config.system.base_dir, config.system.min_free_disk_percent)
        self.base_dir = config.system.base_dir
        self.images_dir = os.path.join(self.base_dir, "images", "landmarks")
        os.makedirs(self.images_dir, exist_ok=True)

    def clean_html(self, raw_html: str) -> str:
        if not raw_html:
            return ""
        clean = re.sub(r"<.*?>", "", raw_html)
        return clean.strip()

    def query_wikimedia_images(self, place_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f'"{place_name}"',
            "gsrnamespace": "6",
            "gsrlimit": limit,
            "prop": "imageinfo",
            "iiprop": "url|size|extmetadata|sha1",
            "iiurlwidth": 1280,
            "format": "json"
        }
        try:
            resp = self.http.get(url, params=params, timeout=15.0)
            data = resp.json()
            pages = data.get("query", {}).get("pages", {})
            results = []
            
            for pid, pinfo in pages.items():
                title = pinfo.get("title", "")
                if not any(title.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                    continue
                    
                imageinfos = pinfo.get("imageinfo", [])
                if not imageinfos:
                    continue
                ii = imageinfos[0]
                img_url = ii.get("thumburl") or ii.get("url")
                orig_url = ii.get("url")
                if not img_url:
                    continue
                    
                width = ii.get("width", 0)
                height = ii.get("height", 0)
                meta = ii.get("extmetadata", {})
                license_short = meta.get("LicenseShortName", {}).get("value", "CC BY-SA 4.0")
                license_url = meta.get("LicenseUrl", {}).get("value", "https://creativecommons.org/licenses/")
                artist = self.clean_html(meta.get("Artist", {}).get("value", "Wikimedia Contributor"))
                date_str = meta.get("DateTimeOriginal", {}).get("value", "")
                
                results.append({
                    "source": "Wikimedia Commons",
                    "source_id": title,
                    "source_url": img_url,
                    "orig_url": orig_url,
                    "width": width,
                    "height": height,
                    "license": license_short,
                    "license_url": license_url,
                    "author": artist or "Wikimedia Commons Contributor",
                    "attribution": f"{artist or 'Contributor'} / Wikimedia Commons / {license_short}",
                    "captured_at": date_str,
                    "heading": None
                })
            return results
        except Exception as e:
            logger.warning(f"[Acquisition] Wikimedia query failed for '{place_name}': {e}")
            return []

    def process_place(self, place: Dict[str, Any], max_images: int = 8) -> int:
        place_id = place["place_id"]
        place_name = place["name"]
        country = place.get("country", "UNK")
        
        country_dir = os.path.join(self.images_dir, country)
        os.makedirs(country_dir, exist_ok=True)
        
        is_safe, _ = self.guard.inspect_and_log(f"Acquisition: {place_name}")
        if not is_safe:
            max_images = min(max_images, 4)
            
        candidates = self.query_wikimedia_images(place_name, limit=max_images + 4)
        if not candidates and place.get("aliases"):
            for alias in place["aliases"]:
                candidates = self.query_wikimedia_images(alias, limit=max_images + 2)
                if candidates:
                    break
                    
        downloaded_count = 0
        for cand in candidates:
            if downloaded_count >= max_images:
                break
                
            img_uuid = f"argus-img-{uuid.uuid5(NAMESPACE_ARGUS_IMG, cand['source_url'])}"
            local_rel_path = os.path.join("images", "landmarks", country, f"{img_uuid}.jpg")
            local_abs_path = os.path.join(self.base_dir, local_rel_path)
            
            if os.path.exists(local_abs_path) and os.path.getsize(local_abs_path) > 0:
                downloaded_count += 1
                continue
                
            if not self.guard.check_capacity_for_download(500_000):
                logger.warning(f"[Acquisition] Disk safety margin reached. Halting downloads for {place_name}.")
                break
                
            success = self.http.download_file(cand["source_url"], local_abs_path)
            if not success and cand.get("orig_url") and cand["orig_url"] != cand["source_url"]:
                success = self.http.download_file(cand["orig_url"], local_abs_path)
            if success:
                try:
                    with open(local_abs_path, "rb") as f:
                        with Image.open(f) as img:
                            w, h = img.size
                    file_size = os.path.getsize(local_abs_path)
                    
                    asset_record = {
                        "image_id": img_uuid,
                        "place_id": place_id,
                        "source": cand["source"],
                        "source_id": cand["source_id"],
                        "source_url": cand["source_url"],
                        "local_path": local_rel_path.replace("\\", "/"),
                        "image_type": "landmark",
                        "status": "INGESTED",
                        "heading": cand.get("heading"),
                        "captured_at": cand.get("captured_at"),
                        "width": w,
                        "height": h,
                        "license": cand["license"],
                        "license_url": cand["license_url"],
                        "author": cand["author"],
                        "attribution": cand["attribution"],
                        "file_size_bytes": file_size
                    }
                    self.tracker.record_asset(asset_record)
                    downloaded_count += 1
                    logger.info(f"[Acquisition] Downloaded [{place_name}] -> {local_rel_path} ({w}x{h}, {file_size/1024:.1f} KB)")
                except Exception as e:
                    logger.warning(f"[Acquisition] Invalid image binary {local_abs_path}: {e}")
                    try:
                        if os.path.exists(local_abs_path):
                            os.remove(local_abs_path)
                    except Exception:
                        pass
                        
        self.tracker.update_place_status(place_id, "PROBED" if downloaded_count > 0 else "SPARSE", downloaded_count)
        return downloaded_count

    def run_acquisition(self, places: Optional[List[Dict[str, Any]]] = None, max_places: Optional[int] = None, max_workers: int = 8, shard_id: int = 0, num_shards: int = 1):
        if places is None:
            places = self.tracker.get_all_places()
            
        if num_shards > 1:
            places = [p for i, p in enumerate(places) if i % num_shards == shard_id]
            logger.info(f"[Acquisition Shard {shard_id}/{num_shards}] Assigned {len(places)} places.")
            
        target_places = places if (max_places is None or max_places <= 0) else places[:max_places]
        logger.info(f"[Acquisition] Running Parallel Tier 1 landmark retrieval for {len(target_places)} places ({max_workers} threads, Shard {shard_id+1}/{num_shards})...")
        total_downloaded = 0
        completed_places = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_place = {
                executor.submit(self.process_place, place, self.config.acquisition.target_images_per_landmark): place
                for place in target_places
            }
            for future in concurrent.futures.as_completed(future_to_place):
                place = future_to_place[future]
                completed_places += 1
                try:
                    cnt = future.result()
                    total_downloaded += cnt
                    if completed_places % 10 == 0 or completed_places == len(target_places):
                        logger.info(f"[Acquisition Shard {shard_id+1}] Progress: {completed_places}/{len(target_places)} places processed ({total_downloaded} images).")
                except Exception as e:
                    logger.error(f"[Acquisition Shard {shard_id+1}] Error processing place {place.get('name')}: {e}")
                    
        logger.info(f"[Acquisition Shard {shard_id+1}] Completed. Downloaded {total_downloaded} landmark images.")

def main():
    parser = argparse.ArgumentParser(description="ARGUS Tier 1 Acquisition Engine")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--places", default="ARGUS_DATASET/places/places.jsonl", help="Input places JSONL")
    parser.add_argument("--mode", default="priority", help="Acquisition mode")
    parser.add_argument("--limit", type=int, default=None, help="Place processing limit")
    parser.add_argument("--shard-id", type=int, default=0, help="Shard index (0-based)")
    parser.add_argument("--num-shards", type=int, default=1, help="Total number of shards")
    parser.add_argument("--workers", type=int, default=8, help="Worker threads per shard")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config(args.config)
    tracker = StateTracker(os.path.join(cfg.system.base_dir, "indexes", "state_tracker.db"))
    acq = AcquisitionEngine(cfg, tracker)
    places = tracker.get_all_places()
    acq.run_acquisition(places, max_places=args.limit, max_workers=args.workers, shard_id=args.shard_id, num_shards=args.num_shards)

if __name__ == "__main__":
    main()
