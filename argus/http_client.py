"""
Resilient HTTP Client with Token-Bucket Rate Limiting and Exponential Backoff.
"""

import os
import time
import random
import logging
import threading
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_rate: float):
        self.max_rate = max_rate
        self.interval = 1.0 / max_rate if max_rate > 0 else 0.1
        self.last_request = 0.0
        self.cooldown_until = 0.0
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            if now < self.cooldown_until:
                time.sleep(self.cooldown_until - now)
                now = time.time()
            elapsed = now - self.last_request
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
            self.last_request = time.time()

    def trigger_cooldown(self, seconds: float):
        with self._lock:
            target = time.time() + seconds
            if target > self.cooldown_until:
                self.cooldown_until = target

from requests.adapters import HTTPAdapter

class ARGUSHttpClient:
    def __init__(self, user_agent: str = "ARGUSGroundViewBot/1.0 (https://github.com/YTxFSGAMERz/GeoVigilant-Argus; contact@geovigilant.org) requests/2.31.0",
                 rate_limits: Optional[Dict[str, float]] = None):
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=64, pool_maxsize=64)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept": "application/json, text/plain, image/*, */*"
        })
        self.rate_limiters: Dict[str, RateLimiter] = {}
        
        # Calibrated optimal rate limits per second
        limits = {
            "wikidata.org": 3.0,
            "wikimedia.org": 3.0,
            "mapillary.com": 30.0,
            "openstreetcam.org": 10.0,
            "overpass-api.de": 5.0
        }
        if rate_limits:
            limits.update(rate_limits)
            
        for host, rate in limits.items():
            self.rate_limiters[host] = RateLimiter(rate)

    def _get_limiter(self, url: str) -> Optional[RateLimiter]:
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            for known_host, limiter in self.rate_limiters.items():
                if known_host in host:
                    return limiter
        except Exception:
            pass
        return None

    def request(self, method: str, url: str, max_attempts: int = 5, **kwargs) -> requests.Response:
        limiter = self._get_limiter(url)
        
        for attempt in range(max_attempts):
            if limiter:
                limiter.wait()
                
            try:
                # Default timeout 15s if not specified
                if "timeout" not in kwargs:
                    kwargs["timeout"] = 15.0
                    
                resp = self.session.request(method, url, **kwargs)
                
                # Check for rate limit or server error codes
                if resp.status_code == 429:
                    if attempt < max_attempts - 1:
                        retry_after = resp.headers.get("Retry-After")
                        try:
                            sleep_sec = float(retry_after) + random.uniform(0.5, 1.5) if retry_after else (2 ** (attempt + 1)) + random.uniform(0.5, 1.5)
                        except Exception:
                            sleep_sec = (2 ** (attempt + 1)) + random.uniform(0.5, 1.5)
                        logger.warning(f"[HTTP] Received 429 from {url}. Domain cooldown for {sleep_sec:.2f}s (Attempt {attempt+1}/{max_attempts})")
                        if limiter:
                            limiter.trigger_cooldown(sleep_sec)
                        time.sleep(sleep_sec)
                        continue
                elif resp.status_code in (500, 502, 503, 504):
                    if attempt < max_attempts - 1:
                        sleep_sec = (2 ** attempt) + random.uniform(0.1, 1.0)
                        logger.warning(f"[HTTP] Received {resp.status_code} from {url}. Backing off for {sleep_sec:.2f}s (Attempt {attempt+1}/{max_attempts})")
                        time.sleep(sleep_sec)
                        continue
                        
                resp.raise_for_status()
                return resp
                
            except (requests.exceptions.RequestException, requests.exceptions.Timeout) as exc:
                if attempt < max_attempts - 1:
                    sleep_sec = (2 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(f"[HTTP] Request error ({exc}) for {url}. Retrying in {sleep_sec:.2f}s (Attempt {attempt+1}/{max_attempts})")
                    time.sleep(sleep_sec)
                else:
                    logger.error(f"[HTTP] Final failure for {url}: {exc}")
                    raise

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def download_file(self, url: str, dest_path: str, timeout: float = 10.0, max_attempts: int = 2) -> bool:
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            resp = self.get(url, stream=True, timeout=timeout, max_attempts=max_attempts)
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=131072):
                    if chunk:
                        f.write(chunk)
            return os.path.exists(dest_path) and os.path.getsize(dest_path) > 0
        except Exception as e:
            logger.warning(f"[HTTP] Download failed for {url} -> {dest_path}: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
            return False
