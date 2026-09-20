"""
Two-Pass Deduplication & Visual Verification Engine.
Pass 1: Cryptographic SHA-256 integrity verification.
Pass 2: Perceptual Hash (DCT pHash) indexed via BK-Tree with heading & temporal gating.
"""

import os
import csv
import json
import pickle
import hashlib
import logging
import argparse
import datetime
import numpy as np
import scipy.fftpack
from PIL import Image
from typing import List, Dict, Any, Tuple, Optional
from argus.config import load_config, ArgusConfig
from argus.state_tracker import StateTracker

logger = logging.getLogger(__name__)

def compute_sha256(filepath: str) -> str:
    """Calculates SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def compute_dct_phash(image: Image.Image, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    """Calculates 64-bit DCT perceptual hash as a 16-char hexadecimal string."""
    img = image.convert("L").resize((hash_size * highfreq_factor, hash_size * highfreq_factor), Image.Resampling.LANCZOS)
    pixels = np.asarray(img, dtype=np.float32)
    dct = scipy.fftpack.dct(scipy.fftpack.dct(pixels, axis=0), axis=1)
    dctlowfreq = dct[:hash_size, :hash_size]
    med = np.median(dctlowfreq)
    diff = dctlowfreq > med
    bit_str = "".join("1" if b else "0" for b in diff.flatten())
    hash_int = int(bit_str, 2)
    return f"{hash_int:016x}"

def hamming_distance(hash1_hex: str, hash2_hex: str) -> int:
    """Computes Hamming distance between two 16-character hexadecimal pHashes."""
    try:
        val1 = int(hash1_hex, 16)
        val2 = int(hash2_hex, 16)
        xor_val = val1 ^ val2
        return xor_val.bit_count()
    except Exception:
        return 64

class BKTreeNode:
    def __init__(self, item: Dict[str, Any]):
        self.item = item
        self.children: Dict[int, 'BKTreeNode'] = {}

class BKTree:
    """BK-Tree metric index for fast discrete distance queries."""
    def __init__(self):
        self.root: Optional[BKTreeNode] = None
        self.size: int = 0

    def insert(self, item: Dict[str, Any]):
        if not self.root:
            self.root = BKTreeNode(item)
            self.size = 1
            return

        curr = self.root
        phash = item["phash"]
        while True:
            d = hamming_distance(phash, curr.item["phash"])
            if d in curr.children:
                curr = curr.children[d]
            else:
                curr.children[d] = BKTreeNode(item)
                self.size += 1
                break

    def query(self, phash: str, max_dist: int) -> List[Tuple[int, Dict[str, Any]]]:
        results = []
        if not self.root:
            return results

        def _search(node: BKTreeNode):
            d = hamming_distance(phash, node.item["phash"])
            if d <= max_dist:
                results.append((d, node.item))

            low = max(0, d - max_dist)
            high = d + max_dist
            for dist_k, child in node.children.items():
                if low <= dist_k <= high:
                    _search(child)

        _search(self.root)
        return results

class DeduplicationEngine:
    def __init__(self, config: ArgusConfig, state_tracker: StateTracker):
        self.config = config
        self.tracker = state_tracker
        self.base_dir = config.system.base_dir
        self.meta_dir = os.path.join(self.base_dir, "metadata")
        self.index_dir = os.path.join(self.base_dir, "indexes")
        os.makedirs(self.meta_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)
        
        self.bktree = BKTree()
        self.bktree_path = os.path.join(self.index_dir, "phash_bktree.index")

    def run_deduplication_and_indexing(self) -> Dict[str, int]:
        logger.info("[Deduplicate] Running two-pass deduplication & perceptual integrity indexing...")
        
        with self.tracker._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM assets WHERE status = 'INGESTED'")
            rows = [dict(r) for r in cur.fetchall()]

        logger.info(f"[Deduplicate] Scanning {len(rows)} ingested image assets...")
        
        import concurrent.futures
        
        def process_single_asset(asset: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            local_rel = asset.get("local_path", "")
            local_abs = os.path.join(self.base_dir, local_rel)
            
            if not os.path.exists(local_abs) or os.path.getsize(local_abs) == 0:
                return None

            sha = compute_sha256(local_abs)
            asset["sha256"] = sha

            try:
                with open(local_abs, "rb") as f:
                    with Image.open(f) as img:
                        ph = compute_dct_phash(img)
                        w, h = img.size
                asset["phash"] = ph
                asset["width"] = w
                asset["height"] = h
                return asset
            except Exception as e:
                logger.warning(f"[Deduplicate] Failed to decode {local_abs}: {e}")
                return None

        logger.info(f"[Deduplicate] Computing hashes across {len(rows)} images using 16 worker threads...")
        hashed_assets: List[Dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            results = executor.map(process_single_asset, rows)
            for r in results:
                if r is not None:
                    hashed_assets.append(r)

        logger.info(f"[Deduplicate] Building BK-Tree and filtering duplicates across {len(hashed_assets)} valid images...")
        sha256_seen: Dict[str, str] = {}
        verified_assets: List[Dict[str, Any]] = []
        pruned_exact_count = 0
        pruned_visual_count = 0

        for asset in hashed_assets:
            sha = asset["sha256"]
            local_rel = asset.get("local_path", "")
            local_abs = os.path.join(self.base_dir, local_rel)

            if sha in sha256_seen:
                pruned_exact_count += 1
                try:
                    os.remove(local_abs)
                except Exception:
                    pass
                continue
            sha256_seen[sha] = asset["image_id"]

            ph = asset.get("phash")
            if not ph:
                continue

            neighbors = self.bktree.query(ph, max_dist=self.config.acquisition.phash_hamming_threshold)
            keep_file = True
            
            for dist, neighbor in neighbors:
                heading_diff = 180.0
                if asset.get("heading") is not None and neighbor.get("heading") is not None:
                    heading_diff = abs(asset["heading"] - neighbor["heading"])
                    if heading_diff > 180.0:
                        heading_diff = 360.0 - heading_diff

                days_diff = 1000
                if asset.get("captured_at") and neighbor.get("captured_at"):
                    try:
                        d1 = datetime.datetime.fromisoformat(asset["captured_at"].replace("Z", "+00:00"))
                        d2 = datetime.datetime.fromisoformat(neighbor["captured_at"].replace("Z", "+00:00"))
                        days_diff = abs((d1 - d2).days)
                    except Exception:
                        days_diff = 1000

                if heading_diff <= self.config.acquisition.heading_difference_threshold_deg and \
                   days_diff <= self.config.acquisition.temporal_difference_threshold_days:
                    keep_file = False
                    pruned_visual_count += 1
                    try:
                        os.remove(local_abs)
                    except Exception:
                        pass
                    break

            if keep_file:
                self.bktree.insert(asset)
                verified_assets.append(asset)

        with open(self.bktree_path, "wb") as bf:
            pickle.dump(self.bktree, bf)

        logger.info(f"[Deduplicate] Bulk persisting {len(verified_assets)} verified assets to database...")
        self.tracker.bulk_record_assets(verified_assets)
        self._write_metadata_files(verified_assets)
        
        logger.info(f"[Deduplicate] Completed. Retained {len(verified_assets)} verified images. "
                    f"Pruned: {pruned_exact_count} exact byte duplicates, {pruned_visual_count} perceptual duplicates.")
        
        return {
            "retained": len(verified_assets),
            "pruned_exact": pruned_exact_count,
            "pruned_visual": pruned_visual_count
        }

    def _write_metadata_files(self, assets: List[Dict[str, Any]]):
        images_jsonl = os.path.join(self.meta_dir, "images.jsonl")
        images_csv = os.path.join(self.meta_dir, "images.csv")
        licenses_csv = os.path.join(self.meta_dir, "licenses.csv")
        sources_csv = os.path.join(self.meta_dir, "sources.csv")
        
        with open(images_jsonl, "w", encoding="utf-8") as jf:
            for a in assets:
                jf.write(json.dumps(a, ensure_ascii=False) + "\n")
                
        fields = ["image_id", "place_id", "source", "source_id", "source_url",
                  "local_path", "image_type", "heading",
                  "captured_at", "width", "height", "license", "license_url",
                  "author", "attribution", "sha256", "phash", "file_size_bytes"]
        with open(images_csv, "w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for a in assets:
                writer.writerow(a)

        lic_counts: Dict[str, Dict[str, Any]] = {}
        for a in assets:
            lic = a.get("license", "CC BY-SA 4.0")
            if lic not in lic_counts:
                lic_counts[lic] = {"license": lic, "count": 0, "url": a.get("license_url", "")}
            lic_counts[lic]["count"] += 1
            
        with open(licenses_csv, "w", encoding="utf-8", newline="") as lf:
            writer = csv.DictWriter(lf, fieldnames=["license", "count", "url"])
            writer.writeheader()
            for row in lic_counts.values():
                writer.writerow(row)

        src_counts: Dict[str, Dict[str, Any]] = {}
        for a in assets:
            src = a.get("source", "Unknown")
            if src not in src_counts:
                src_counts[src] = {"source": src, "downloaded_images": 0, "total_bytes": 0}
            src_counts[src]["downloaded_images"] += 1
            src_counts[src]["total_bytes"] += a.get("file_size_bytes", 0)

        with open(sources_csv, "w", encoding="utf-8", newline="") as sf:
            writer = csv.DictWriter(sf, fieldnames=["source", "downloaded_images", "total_bytes"])
            writer.writeheader()
            for row in src_counts.values():
                writer.writerow(row)

def main():
    parser = argparse.ArgumentParser(description="ARGUS Two-Pass Deduplication & Visual Indexing")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--verify-sha256", action="store_true", default=True, help="Verify SHA256")
    parser.add_argument("--verify-phash", action="store_true", default=True, help="Verify pHash")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config(args.config)
    tracker = StateTracker(os.path.join(cfg.system.base_dir, "indexes", "state_tracker.db"))
    dedup = DeduplicationEngine(cfg, tracker)
    stats = dedup.run_deduplication_and_indexing()
    print(f"Deduplication complete: {stats}")

if __name__ == "__main__":
    main()
