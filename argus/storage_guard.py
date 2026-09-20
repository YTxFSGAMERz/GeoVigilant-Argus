"""
Dynamic Storage Guard & Resource Monitor for ARGUS GroundView.
"""

import os
import shutil
import logging
import datetime
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class StorageGuard:
    def __init__(self, base_dir: str = "ARGUS_DATASET", min_free_percent: float = 20.0):
        self.base_dir = base_dir
        self.min_free_percent = min_free_percent
        self.log_file = os.path.join(self.base_dir, "logs", "resource_monitor.log")
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def get_disk_usage(self) -> Dict[str, float]:
        target = self.base_dir if os.path.exists(self.base_dir) else "."
        total, used, free = shutil.disk_usage(target)
        free_pct = (free / total) * 100.0 if total > 0 else 0.0
        used_pct = (used / total) * 100.0 if total > 0 else 0.0
        
        return {
            "total_gb": round(total / (1024 ** 3), 2),
            "used_gb": round(used / (1024 ** 3), 2),
            "free_gb": round(free / (1024 ** 3), 2),
            "free_percent": round(free_pct, 2),
            "used_percent": round(used_pct, 2),
            "is_safe": free_pct >= self.min_free_percent
        }

    def inspect_and_log(self, context: str = "periodic_check") -> Tuple[bool, str]:
        usage = self.get_disk_usage()
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        if not usage["is_safe"]:
            msg = (f"[{timestamp}] [STORAGE_GUARD WARNING] Disk free space {usage['free_percent']}% "
                   f"({usage['free_gb']} GB) is below minimum safety threshold {self.min_free_percent}%. "
                   f"Context: {context}. Switching to restricted ingestion mode.")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            logger.warning(msg)
            return False, msg
        else:
            msg = (f"[{timestamp}] [STORAGE_GUARD OK] Disk free space {usage['free_percent']}% "
                   f"({usage['free_gb']} GB). Total: {usage['total_gb']} GB. Context: {context}.")
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
            return True, msg

    def check_capacity_for_download(self, estimated_bytes: int = 1_000_000) -> bool:
        target = self.base_dir if os.path.exists(self.base_dir) else "."
        _, _, free = shutil.disk_usage(target)
        return (free - estimated_bytes) > (1024 * 1024 * 1024)
