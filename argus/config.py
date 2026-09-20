"""
Configuration loader and schema validator for ARGUS GroundView.
"""

import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

@dataclass
class SystemConfig:
    max_threads: int = 16
    min_free_disk_percent: float = 20.0
    user_agent: str = "ARGUS-GroundView-Bot/1.0 (Research Ingestion Engine; mailto:argus@geovigilant.org)"
    base_dir: str = "ARGUS_DATASET"

@dataclass
class DiscoveryConfig:
    wikidata_endpoint: str = "https://query.wikidata.org/sparql"
    overpass_endpoint: str = "https://overpass-api.de/api/interpreter"
    h3_resolution: int = 10
    spatial_dedup_radius_m: float = 35.0
    sample_limit_per_category: int = 60

@dataclass
class AcquisitionConfig:
    target_images_per_landmark: int = 15
    min_images_per_landmark: int = 5
    radial_steps_meters: List[int] = field(default_factory=lambda: [250, 500, 1000])
    phash_hamming_threshold: int = 10
    heading_difference_threshold_deg: float = 30.0
    temporal_difference_threshold_days: int = 90
    max_download_workers: int = 8

@dataclass
class RateLimitsConfig:
    wikimedia_req_per_sec: float = 20.0
    mapillary_req_per_sec: float = 10.0
    kartaview_req_per_sec: float = 2.0

@dataclass
class TokensConfig:
    mapillary_access_token: str = ""

@dataclass
class ArgusConfig:
    system: SystemConfig = field(default_factory=SystemConfig)
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    acquisition: AcquisitionConfig = field(default_factory=AcquisitionConfig)
    rate_limits: RateLimitsConfig = field(default_factory=RateLimitsConfig)
    tokens: TokensConfig = field(default_factory=TokensConfig)

def load_config(config_path: Optional[str] = None) -> ArgusConfig:
    if config_path is None:
        config_path = os.path.join("config", "argus_config.yaml")
    
    if not os.path.exists(config_path):
        return ArgusConfig()
    
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    
    sys_data = raw.get("system", {})
    disc_data = raw.get("discovery", {})
    acq_data = raw.get("acquisition", {})
    rl_data = raw.get("rate_limits", {})
    tok_data = raw.get("tokens", {})
    env_token = os.environ.get("MAPILLARY_ACCESS_TOKEN")
    if env_token:
        tok_data["mapillary_access_token"] = env_token
    
    return ArgusConfig(
        system=SystemConfig(**{k: v for k, v in sys_data.items() if k in SystemConfig.__annotations__}),
        discovery=DiscoveryConfig(**{k: v for k, v in disc_data.items() if k in DiscoveryConfig.__annotations__}),
        acquisition=AcquisitionConfig(**{k: v for k, v in acq_data.items() if k in AcquisitionConfig.__annotations__}),
        rate_limits=RateLimitsConfig(**{k: v for k, v in rl_data.items() if k in RateLimitsConfig.__annotations__}),
        tokens=TokensConfig(**{k: v for k, v in tok_data.items() if k in TokensConfig.__annotations__})
    )
