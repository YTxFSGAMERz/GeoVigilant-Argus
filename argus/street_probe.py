"""
Radial Street-Level Spatial Probing Engine (Tier 2 Mapillary, Tier 3 KartaView, Tier 4 Global Streetscapes).
Probes surrounding geographic space (250m -> 500m -> 1000m) with viewpoint angular diversity.
"""

import os
import uuid
import math
import shutil
import logging
import argparse
import concurrent.futures
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
from argus.config import load_config, ArgusConfig
from argus.http_client import ARGUSHttpClient
from argus.state_tracker import StateTracker
from argus.storage_guard import StorageGuard
from argus.geo_utils import (
    get_bounding_box_meters, vincenty_distance_m,
    calculate_initial_bearing, spatial_angular_bin_key
)

logger = logging.getLogger(__name__)

NAMESPACE_ARGUS_IMG = uuid.UUID("7c9e1104-3a9b-4f51-b883-02fba7349182")

class StreetProbeEngine:
    def __init__(self, config: ArgusConfig, state_tracker: StateTracker):
        self.config = config
        self.tracker = state_tracker
        self.http = ARGUSHttpClient(user_agent=config.system.user_agent,
                                    rate_limits={"mapillary.com": config.rate_limits.mapillary_req_per_sec,
                                                 "openstreetcam.org": config.rate_limits.kartaview_req_per_sec})
        self.guard = StorageGuard(config.system.base_dir, config.system.min_free_disk_percent)
        self.base_dir = config.system.base_dir
        self.street_images_dir = os.path.join(self.base_dir, "images", "street")
        os.makedirs(self.street_images_dir, exist_ok=True)
        
        self.local_streetscapes = self._init_local_streetscapes()

    def _init_local_streetscapes(self):
        try:
            from streetscapes_service import streetscapes_service
            streetscapes_service.initialize()
            return streetscapes_service
        except Exception as e:
            logger.info(f"[StreetProbe] Local streetscapes service initialization info: {e}")
            return None

    def query_mapillary_radial(self, lat: float, lon: float, radius_m: float, limit: int = 15) -> List[Dict[str, Any]]:
        token = self.config.tokens.mapillary_access_token
        if not token:
            return []
            
        min_lon, min_lat, max_lon, max_lat = get_bounding_box_meters(lat, lon, min(radius_m, 400.0))
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        
        url = "https://graph.mapillary.com/images"
        params = {
            "access_token": token,
            "fields": "id,geometry,compass_angle,captured_at,thumb_1024_url,thumb_2048_url",
            "bbox": bbox,
            "limit": limit
        }
        
        try:
            resp = self.http.get(url, params=params, timeout=3.0, max_attempts=1)
            data = resp.json()
            items = data.get("data", [])
            results = []
            
            for it in items:
                img_id = it.get("id")
                geom = it.get("geometry", {})
                coords = geom.get("coordinates", [])
                if len(coords) < 2:
                    continue
                c_lon, c_lat = coords[0], coords[1]
                thumb_url = it.get("thumb_2048_url") or it.get("thumb_1024_url")
                if not thumb_url:
                    continue
                    
                heading = it.get("compass_angle")
                if heading is None:
                    heading = calculate_initial_bearing(c_lat, c_lon, lat, lon)
                    
                dist_m = vincenty_distance_m(c_lat, c_lon, lat, lon)
                captured_at_ts = it.get("captured_at")
                
                results.append({
                    "source": "Mapillary API v4",
                    "source_id": str(img_id),
                    "source_url": thumb_url,
                    "lat": c_lat,
                    "lon": c_lon,
                    "heading": heading,
                    "distance_m": dist_m,
                    "captured_at": str(captured_at_ts) if captured_at_ts else None,
                    "license": "CC BY-SA 4.0",
                    "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
                    "author": "Mapillary Contributor",
                    "attribution": f"Mapillary Contributor #{img_id} / Mapillary / CC BY-SA 4.0"
                })
            return results
        except Exception as e:
            logger.debug(f"[StreetProbe] Mapillary query failed for ({lat}, {lon}) r={radius_m}m: {e}")
            return []

    def query_local_streetscapes_radial(self, lat: float, lon: float, radius_m: float, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.local_streetscapes:
            return []
            
        radius_km = radius_m / 1000.0
        nearby = self.local_streetscapes.get_nearby(lat, lon, radius_km=radius_km, limit=limit)
        results = []
        
        for it in nearby:
            img_id = it["id"]
            local_src_path = self.local_streetscapes.get_image_path(img_id)
            if not local_src_path or not os.path.exists(local_src_path):
                continue
                
            c_lat = it["lat"]
            c_lon = it["lon"]
            dist_m = vincenty_distance_m(c_lat, c_lon, lat, lon)
            heading = calculate_initial_bearing(c_lat, c_lon, lat, lon)
            
            results.append({
                "source": "Global Streetscapes",
                "source_id": f"NUS-SVI-{img_id}",
                "source_url": f"local://ARGUS_DATASET/streetscapes/images/{img_id}.png",
                "local_source_file": local_src_path,
                "lat": c_lat,
                "lon": c_lon,
                "heading": heading,
                "distance_m": dist_m,
                "captured_at": None,
                "license": "Open Research License",
                "license_url": "https://github.com/nus-ual/global-streetscapes",
                "author": "NUS Urban Analytics Lab",
                "attribution": "NUS Urban Analytics Lab / Global Streetscapes Dataset / CC BY-NC 4.0"
            })
        return results

    def probe_place_radially(self, place: Dict[str, Any], target_count: int = 8) -> int:
        place_id = place["place_id"]
        place_name = place["name"]
        lat = place["latitude"]
        lon = place["longitude"]
        country = place.get("country", "UNK")
        
        country_dir = os.path.join(self.street_images_dir, country)
        os.makedirs(country_dir, exist_ok=True)
        
        radii = self.config.acquisition.radial_steps_meters
        retained_bins: Dict[Tuple[int, int], Dict[str, Any]] = {}
        downloaded_count = 0
        
        for r_m in radii:
            if len(retained_bins) >= target_count:
                break
                
            candidates = self.query_mapillary_radial(lat, lon, radius_m=r_m, limit=10)
            
            # Tier 4: Global Streetscapes fallback / complement
            if len(candidates) < 2:
                local_cands = self.query_local_streetscapes_radial(lat, lon, radius_m=r_m, limit=6)
                candidates.extend(local_cands)
                
            for cand in candidates:
                bin_k = spatial_angular_bin_key(cand["heading"], cand["distance_m"], heading_bin_deg=45.0, distance_bin_m=50.0)
                if bin_k not in retained_bins:
                    retained_bins[bin_k] = cand
                    if len(retained_bins) >= target_count:
                        break

        for bin_k, cand in retained_bins.items():
            img_uuid = f"argus-img-{uuid.uuid5(NAMESPACE_ARGUS_IMG, cand['source_url'])}"
            local_rel_path = os.path.join("images", "street", country, f"{img_uuid}.jpg")
            local_abs_path = os.path.join(self.base_dir, local_rel_path)
            
            if os.path.exists(local_abs_path) and os.path.getsize(local_abs_path) > 0:
                downloaded_count += 1
                continue
                
            if not self.guard.check_capacity_for_download(500_000):
                logger.warning(f"[StreetProbe] Disk margin limit reached. Stopping probe for {place_name}.")
                break
                
            success = False
            if cand.get("local_source_file") and os.path.exists(cand["local_source_file"]):
                try:
                    with Image.open(cand["local_source_file"]) as img:
                        img.convert("RGB").save(local_abs_path, "JPEG", quality=90)
                    success = True
                except Exception as e:
                    logger.warning(f"[StreetProbe] Local conversion failed: {e}")
            else:
                success = self.http.download_file(cand["source_url"], local_abs_path)
                
            if success and os.path.exists(local_abs_path):
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
                        "image_type": "street",
                        "status": "INGESTED",
                        "heading": round(cand["heading"], 2),
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
                    logger.info(f"[StreetProbe] [{place_name}] Street View (Heading: {cand['heading']:.1f}°, Dist: {cand['distance_m']:.0f}m) -> {local_rel_path}")
                except Exception as e:
                    logger.warning(f"[StreetProbe] Corrupted street image {local_abs_path}: {e}")
                    try:
                        if os.path.exists(local_abs_path):
                            os.remove(local_abs_path)
                    except Exception:
                        pass
                        
        return downloaded_count

    def run_probing(self, places: Optional[List[Dict[str, Any]]] = None, max_places: Optional[int] = None, max_workers: int = 16, shard_id: int = 0, num_shards: int = 1):
        if places is None:
            places = self.tracker.get_all_places()
            
        if num_shards > 1:
            places = [p for i, p in enumerate(places) if i % num_shards == shard_id]
            logger.info(f"[StreetProbe Shard {shard_id}/{num_shards}] Assigned {len(places)} places.")
            
        target_places = places if (max_places is None or max_places <= 0) else places[:max_places]
        logger.info(f"[StreetProbe] Running Parallel street views probing for {len(target_places)} landmarks ({max_workers} threads, Shard {shard_id+1}/{num_shards})...")
        total_street_images = 0
        completed_places = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_place = {
                executor.submit(self.probe_place_radially, place, 6): place
                for place in target_places
            }
            for future in concurrent.futures.as_completed(future_to_place):
                place = future_to_place[future]
                completed_places += 1
                try:
                    cnt = future.result()
                    total_street_images += cnt
                    if completed_places % 10 == 0 or completed_places == len(target_places):
                        logger.info(f"[StreetProbe Shard {shard_id+1}] Progress: {completed_places}/{len(target_places)} places probed ({total_street_images} street assets).")
                except Exception as e:
                    logger.error(f"[StreetProbe Shard {shard_id+1}] Error probing {place.get('name')}: {e}")
                    
        logger.info(f"[StreetProbe Shard {shard_id+1}] Probing complete. Total street images: {total_street_images}.")

def main():
    parser = argparse.ArgumentParser(description="ARGUS Radial Street Probing")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--radii", nargs="+", type=int, default=[250, 500, 1000], help="Radial steps in meters")
    parser.add_argument("--limit", type=int, default=None, help="Max places to probe")
    parser.add_argument("--shard-id", type=int, default=0, help="Shard index (0-based)")
    parser.add_argument("--num-shards", type=int, default=1, help="Total number of shards")
    parser.add_argument("--workers", type=int, default=16, help="Worker threads per shard")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config(args.config)
    tracker = StateTracker(os.path.join(cfg.system.base_dir, "indexes", "state_tracker.db"))
    probe = StreetProbeEngine(cfg, tracker)
    places = tracker.get_all_places()
    probe.run_probing(places, max_places=args.limit, max_workers=args.workers, shard_id=args.shard_id, num_shards=args.num_shards)

if __name__ == "__main__":
    main()
