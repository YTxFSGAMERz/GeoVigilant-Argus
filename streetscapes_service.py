"""
ARGUS DATASET — Global Streetscapes SVI Visual Intelligence Service.

Manages the 10,000 geolocated street-level observation points within the
ARGUS DATASET suite. Provides GeoJSON generation for GPU clustering,
fast spatial indexing, image serving, and AI environmental classification.
"""

import os
import csv
import json
import math
import logging

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "ARGUS_DATASET", "streetscapes")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
COORDS_CSV = os.path.join(DATA_DIR, "coords.csv")
METADATA_JSON = os.path.join(DATA_DIR, "metadata.json")


class StreetscapesService:
    def __init__(self):
        self._initialized = False
        self._items = []              # list of dicts: {id, lat, lon}
        self._metadata_map = {}       # id -> dict
        self._geojson_cache = None    # cached FeatureCollection

    def initialize(self):
        """Loads coordinates and metadata into memory. Pre-computes GeoJSON."""
        if self._initialized:
            return True

        if not os.path.exists(COORDS_CSV):
            # Attempt one-time extraction if needed
            from scripts.extract_streetscapes import extract_dataset
            extract_dataset()

        if not os.path.exists(COORDS_CSV):
            logger.warning("[StreetscapesService] coords.csv not found at %s", COORDS_CSV)
            return False

        try:
            # 1. Load metadata if available
            if os.path.exists(METADATA_JSON):
                with open(METADATA_JSON, "r", encoding="utf-8") as f:
                    self._metadata_map = json.load(f)

            # 2. Parse coords.csv cleanly
            self._items = []
            with open(COORDS_CSV, "r", encoding="utf-8") as f:
                img_idx = 0
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    parts = [p.strip() for p in line_str.split(",")]
                    if len(parts) >= 2:
                        try:
                            lat = float(parts[0])
                            lon = float(parts[1])
                            self._items.append({"id": img_idx, "lat": lat, "lon": lon})
                            img_idx += 1
                        except ValueError:
                            continue

            # 3. Pre-compute MapLibre GeoJSON FeatureCollection
            features = []
            for item in self._items:
                img_id = item["id"]
                meta = self._metadata_map.get(str(img_id), {})
                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [item["lon"], item["lat"]]
                    },
                    "properties": {
                        "id": img_id,
                        "lat": item["lat"],
                        "lon": item["lon"],
                        "lighting": meta.get("lighting", "DAYLIGHT"),
                        "weather": meta.get("weather", "CLEAR"),
                        "platform": meta.get("platform", "STREET LEVEL"),
                        "quality": meta.get("quality", "HD // GOOD"),
                    }
                })

            self._geojson_cache = {
                "type": "FeatureCollection",
                "features": features
            }

            self._initialized = True
            logger.info("[StreetscapesService] Initialized with %d observation points.", len(self._items))
            return True

        except Exception as exc:
            logger.error("[StreetscapesService] Initialization failed: %s", exc, exc_info=True)
            return False

    def get_geojson(self):
        """Returns the pre-computed GeoJSON FeatureCollection of all 10k points."""
        if not self._initialized:
            self.initialize()
        return self._geojson_cache or {"type": "FeatureCollection", "features": []}

    def get_image_path(self, image_id: int):
        """Returns the absolute file path or Hugging Face CDN URL of an image."""
        img_path = os.path.join(IMAGES_DIR, f"{image_id}.png")
        if os.path.exists(img_path):
            return img_path
        # Cloud CDN fallback from Hugging Face Dataset
        hf_repo = os.environ.get("ARGUS_HF_DATASET", "YTxFSGAMERz/ARGUS_DATASET")
        return f"https://huggingface.co/datasets/{hf_repo}/resolve/main/data/streetscapes/images/{image_id}.png"

    def get_metadata(self, image_id: int):
        """Returns full metadata for a specific observation point."""
        if not self._initialized:
            self.initialize()

        meta = self._metadata_map.get(str(image_id))
        if meta:
            return meta

        if 0 <= image_id < len(self._items):
            item = self._items[image_id]
            return {
                "id": image_id,
                "lat": item["lat"],
                "lon": item["lon"],
                "image_file": f"{image_id}.png",
                "lighting": "DAYLIGHT",
                "weather": "CLEAR",
                "platform": "STREET LEVEL",
                "quality": "HD // GOOD",
                "source": "ARGUS DATASET - Street Level SVI"
            }
        return None

    def get_nearby(self, lat: float, lon: float, radius_km: float = 50.0, limit: int = 50):
        """Returns observation points within radius_km (using Haversine distance)."""
        if not self._initialized:
            self.initialize()

        results = []
        # Approximate degree box filter first for performance
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))

        for item in self._items:
            if abs(item["lat"] - lat) > lat_delta or abs(item["lon"] - lon) > lon_delta:
                continue

            # Exact Haversine
            d = self._haversine(lat, lon, item["lat"], item["lon"])
            if d <= radius_km:
                meta = self.get_metadata(item["id"]) or item
                results.append({**meta, "distance_km": round(d, 2)})

        results.sort(key=lambda x: x["distance_km"])
        return results[:limit]

    def get_statistics(self):
        """Returns dataset overview statistics."""
        if not self._initialized:
            self.initialize()
        return {
            "total_observations": len(self._items),
            "dataset_source": "ARGUS DATASET - Street Level SVI (10K Sample)",
            "coverage_type": "Global Geolocated SVI",
            "attributes": ["lighting", "weather", "platform", "quality", "coordinates"],
            "status": "ONLINE" if self._initialized else "OFFLINE"
        }

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Global singleton instance
streetscapes_service = StreetscapesService()
