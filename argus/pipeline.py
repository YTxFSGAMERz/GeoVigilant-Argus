"""
Master End-to-End Orchestrator for ARGUS GroundView Pipeline.
Runs Discovery -> Acquisition -> Street Probing -> Deduplication -> Gap-Filling -> Analytics.
"""

import os
import sys
import time
import logging
import argparse
from typing import Optional, List, Dict, Any
from argus.config import load_config, ArgusConfig
from argus.state_tracker import StateTracker
from argus.storage_guard import StorageGuard
from argus.discovery import DiscoveryEngine
from argus.acquisition import AcquisitionEngine
from argus.street_probe import StreetProbeEngine
from argus.deduplicate import DeduplicationEngine
from argus.gap_filler import GapFillerEngine
from argus.analytics import AnalyticsEngine

def setup_logging(base_dir: str):
    log_dir = os.path.join(base_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    ingest_log = os.path.join(log_dir, "ingestion.log")
    error_log = os.path.join(log_dir, "error.log")
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    ch.setFormatter(ch_fmt)
    logger.addHandler(ch)
    
    # Ingestion file handler
    fh = logging.FileHandler(ingest_log, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh_fmt = logging.Formatter("%(asctime)s [%(levelname)s] [%(name)s] %(message)s")
    fh.setFormatter(fh_fmt)
    logger.addHandler(fh)
    
    # Error file handler
    eh = logging.FileHandler(error_log, encoding="utf-8")
    eh.setLevel(logging.ERROR)
    eh.setFormatter(fh_fmt)
    logger.addHandler(eh)

def run_full_pipeline(config_path: str = "config/argus_config.yaml", max_places: Optional[int] = None):
    cfg = load_config(config_path)
    base_dir = cfg.system.base_dir
    setup_logging(base_dir)
    
    logger = logging.getLogger("ARGUS.Pipeline")
    logger.info("================================================================================")
    logger.info(">>> ARGUS GroundView: Autonomous Master Pipeline Ingestion Initialized <<<")
    logger.info("================================================================================")
    
    # 0. Storage Safety Check
    guard = StorageGuard(base_dir, cfg.system.min_free_disk_percent)
    is_safe, msg = guard.inspect_and_log("pipeline_start")
    usage = guard.get_disk_usage()
    logger.info(f"[Storage Check] Free Space: {usage['free_percent']}% ({usage['free_gb']} GB) | Safe Margin: {usage['is_safe']}")
    
    # 1. State Database Initialization
    db_path = os.path.join(base_dir, "indexes", "state_tracker.db")
    tracker = StateTracker(db_path)
    logger.info(f"[State DB] Initialized SQLite State Tracker at {db_path}")
    
    # 2. Discovery Engine Pass
    logger.info("\n--- STEP 1/6: MASTER PLACE DISCOVERY (Wikidata SPARQL & Canonical Fusion) ---")
    discovery = DiscoveryEngine(cfg, tracker)
    places = discovery.run_discovery()
    logger.info(f"[Step 1 Complete] Discovered {len(places)} canonical worldwide landmarks.")
    
    # 3. Landmark Visual Acquisition Pass (Tier 1 Wikimedia Commons)
    logger.info("\n--- STEP 2/6: TIER 1 LANDMARK IMAGE RETRIEVAL (Wikimedia Commons API) ---")
    acquisition = AcquisitionEngine(cfg, tracker)
    acquisition.run_acquisition(places, max_places=max_places, max_workers=3)
    logger.info("[Step 2 Complete] Landmark perspective acquisition finished.")
    
    # 4. Street-Level Radial Probing Pass (Tier 2 Mapillary & Tier 4 Global Streetscapes)
    logger.info("\n--- STEP 3/6: RADIAL STREET-LEVEL SPATIAL PROBING (250m -> 500m -> 1000m) ---")
    street_probe = StreetProbeEngine(cfg, tracker)
    street_probe.run_probing(places, max_places=max_places, max_workers=cfg.system.max_threads)
    logger.info("[Step 3 Complete] Radial street probing finished.")
    
    # 5. Two-Pass Deduplication & Visual Indexing Pass (SHA-256 + DCT pHash BK-Tree)
    logger.info("\n--- STEP 4/6: DEDUPLICATION & PERCEPTUAL INTEGRITY INDEXING ---")
    dedup = DeduplicationEngine(cfg, tracker)
    dedup_stats = dedup.run_deduplication_and_indexing()
    logger.info(f"[Step 4 Complete] Deduplication complete: {dedup_stats}")
    
    # 6. Closed-Loop Gap-Filling Pass
    logger.info("\n--- STEP 5/6: CLOSED-LOOP GAP-FILLING & COVERAGE SATURATION ---")
    gap_filler = GapFillerEngine(cfg, tracker)
    gap_stats = gap_filler.run_gap_filling(min_images=cfg.acquisition.min_images_per_landmark, max_iterations=2, max_places_per_iter=max_places, max_workers=cfg.system.max_threads)
    logger.info(f"[Step 5 Complete] Gap-filling complete. Coverage: {gap_stats['coverage_percent']}%")
    
    # 7. Coverage Analytics & Final Report Generation
    logger.info("\n--- STEP 6/6: ANALYTICS & FINAL REPORT COMPILATION ---")
    analytics = AnalyticsEngine(cfg, tracker)
    report_path = analytics.generate_report()
    logger.info(f"[Step 6 Complete] Final Report generated at {report_path}")
    
    summary = tracker.get_summary_stats()
    logger.info("================================================================================")
    logger.info(">>> ARGUS GroundView Pipeline Execution Successfully Finished <<<")
    logger.info(f"Landmarks Discovered: {summary['total_places']} | Landmarks with Images: {summary['places_with_images']}")
    logger.info(f"Total Visual Binaries: {summary['total_ingested_assets']} ({summary['landmark_assets']} Landmark, {summary['street_assets']} Street)")
    logger.info(f"Countries Covered: {summary['total_countries']} | Cities Covered: {summary['total_cities']}")
    logger.info(f"Storage Allocated: {summary['total_storage_mb']} MB ({summary['total_storage_gb']} GB)")
    logger.info(f"Final Report: {report_path}")
    logger.info("================================================================================")

def main():
    parser = argparse.ArgumentParser(description="ARGUS GroundView Master Ingestion Pipeline")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--max-places", type=int, default=None, help="Max places to process (default: None = all)")
    args = parser.parse_args()
    
    run_full_pipeline(args.config, max_places=args.max_places)

if __name__ == "__main__":
    main()
