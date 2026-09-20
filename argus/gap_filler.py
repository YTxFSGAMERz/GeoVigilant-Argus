"""
Closed-Loop Gap-Filling Engine for ARGUS GroundView.
Identifies sparse places, calculates coverage tiers,
and executes iterative multi-source gap-filling passes.
"""

import os
import json
import logging
import argparse
import concurrent.futures
from typing import List, Dict, Any, Optional
from argus.config import load_config, ArgusConfig
from argus.state_tracker import StateTracker
from argus.acquisition import AcquisitionEngine
from argus.street_probe import StreetProbeEngine

logger = logging.getLogger(__name__)

class GapFillerEngine:
    def __init__(self, config: ArgusConfig, state_tracker: StateTracker):
        self.config = config
        self.tracker = state_tracker
        self.acq_engine = AcquisitionEngine(config, state_tracker)
        self.street_engine = StreetProbeEngine(config, state_tracker)
        self.base_dir = config.system.base_dir
        self.coverage_dir = os.path.join(self.base_dir, "places", "coverage")
        os.makedirs(self.coverage_dir, exist_ok=True)

    def assess_coverage(self) -> Dict[str, Any]:
        """Calculates global coverage tiers across all discovered landmarks."""
        places = self.tracker.get_all_places()
        
        tier_zero = []     # 0 images
        tier_low = []      # 1-4 images
        tier_target = []   # 5-9 images
        tier_optimal = []  # 10+ images
        
        country_counts: Dict[str, Dict[str, int]] = {}
        category_counts: Dict[str, Dict[str, int]] = {}
        
        for p in places:
            cnt = p.get("images_count", 0)
            pid = p["place_id"]
            country = p.get("country", "UNK")
            category = p.get("category", "landmark")
            
            # Tiers
            if cnt == 0:
                tier_zero.append(p)
            elif 1 <= cnt < 5:
                tier_low.append(p)
            elif 5 <= cnt < 10:
                tier_target.append(p)
            else:
                tier_optimal.append(p)
                
            # Country coverage
            if country not in country_counts:
                country_counts[country] = {"total_places": 0, "covered_places": 0, "total_images": 0}
            country_counts[country]["total_places"] += 1
            if cnt > 0:
                country_counts[country]["covered_places"] += 1
            country_counts[country]["total_images"] += cnt
            
            # Category coverage
            if category not in category_counts:
                category_counts[category] = {"total_places": 0, "covered_places": 0, "total_images": 0}
            category_counts[category]["total_places"] += 1
            if cnt > 0:
                category_counts[category]["covered_places"] += 1
            category_counts[category]["total_images"] += cnt

        # Export coverage JSONs
        with open(os.path.join(self.coverage_dir, "country_coverage.json"), "w", encoding="utf-8") as f:
            json.dump(country_counts, f, indent=2)
            
        with open(os.path.join(self.coverage_dir, "category_coverage.json"), "w", encoding="utf-8") as f:
            json.dump(category_counts, f, indent=2)

        total = len(places)
        return {
            "total_places": total,
            "zero_coverage_count": len(tier_zero),
            "low_coverage_count": len(tier_low),
            "target_met_count": len(tier_target),
            "optimal_count": len(tier_optimal),
            "coverage_percent": round(((total - len(tier_zero)) / total * 100.0), 2) if total > 0 else 0.0,
            "tier_zero_places": tier_zero,
            "tier_low_places": tier_low
        }

    def _remediate_single_place(self, p: Dict[str, Any], min_images: int) -> int:
        name = p["name"]
        curr_cnt = p.get("images_count", 0)
        needed = min_images - curr_cnt
        if needed <= 0:
            return 0
            
        # 1. Broaden landmark image acquisition
        acq_cnt = self.acq_engine.process_place(p, max_images=needed + 2)
        
        # 2. Broaden street probe with widened 1km radius if still below threshold
        current_assets = self.tracker.get_assets_for_place(p["place_id"])
        if len(current_assets) < min_images:
            street_cnt = self.street_engine.probe_place_radially(p, target_count=min_images)
            acq_cnt += street_cnt
            
        return 1 if acq_cnt > 0 else 0

    def run_gap_filling(self, min_images: int = 5, max_iterations: int = 2, max_places_per_iter: Optional[int] = None, max_workers: int = 16):
        logger.info(f"[GapFiller] Initializing High-Speed parallel gap-filling loop (Target min images: {min_images}, Max iterations: {max_iterations}, Workers: {max_workers})...")
        
        for iteration in range(1, max_iterations + 1):
            assessment = self.assess_coverage()
            zero_places = assessment["tier_zero_places"]
            low_places = assessment["tier_low_places"]
            all_target = zero_places + low_places
            target_candidates = all_target if (max_places_per_iter is None or max_places_per_iter <= 0) else all_target[:max_places_per_iter]
            
            logger.info(f"[GapFiller] Iteration {iteration}/{max_iterations}: "
                        f"Zero-coverage: {len(zero_places)}, Low-coverage: {len(low_places)}. "
                        f"Targeting {len(target_candidates)} priority entities in parallel...")
            
            if not target_candidates:
                logger.info("[GapFiller] All accessible landmark coverage targets satisfied!")
                break
                
            remediated_count = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(self._remediate_single_place, p, min_images) for p in target_candidates]
                for f in concurrent.futures.as_completed(futures):
                    try:
                        remediated_count += f.result()
                    except Exception as e:
                        logger.error(f"[GapFiller] Remediation error: {e}")
                    
            logger.info(f"[GapFiller] Iteration {iteration} finished. Remediated coverage for {remediated_count} places.")
            
        final_assessment = self.assess_coverage()
        logger.info(f"[GapFiller] Final Global Coverage: {final_assessment['coverage_percent']}% "
                    f"({final_assessment['total_places'] - final_assessment['zero_coverage_count']}/{final_assessment['total_places']} places covered).")
        return final_assessment

def main():
    parser = argparse.ArgumentParser(description="ARGUS Gap-Filling Engine")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--min-images", type=int, default=5, help="Minimum images per landmark")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max gap filling iterations")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config(args.config)
    tracker = StateTracker(os.path.join(cfg.system.base_dir, "indexes", "state_tracker.db"))
    engine = GapFillerEngine(cfg, tracker)
    engine.run_gap_filling(min_images=args.min_images, max_iterations=args.max_iterations)

if __name__ == "__main__":
    main()
