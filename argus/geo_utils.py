"""
Geospatial Calculations, Coordinate Projections, and Spatial Binning for ARGUS GroundView.
"""

import math
from typing import Tuple, List, Dict, Any, Optional

def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in meters."""
    r = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    
    a = (math.sin(dphi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(dlambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c

def vincenty_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates high-precision geodesic distance on WGS-84 ellipsoid."""
    # WGS-84 ellipsoid parameters
    a = 6378137.0
    f = 1 / 298.257223563
    b = (1 - f) * a

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    l = math.radians(lon2 - lon1)
    
    u1 = math.atan((1 - f) * math.tan(phi1))
    u2 = math.atan((1 - f) * math.tan(phi2))
    sin_u1, cos_u1 = math.sin(u1), math.cos(u1)
    sin_u2, cos_u2 = math.sin(u2), math.cos(u2)

    lambda_lon = l
    for _ in range(100):
        sin_lambda = math.sin(lambda_lon)
        cos_lambda = math.cos(lambda_lon)
        sin_sigma = math.sqrt((cos_u2 * sin_lambda) ** 2 +
                              (cos_u1 * sin_u2 - sin_u1 * cos_u2 * cos_lambda) ** 2)
        if sin_sigma == 0:
            return 0.0  # Coincident points
        cos_sigma = sin_u1 * sin_u2 + cos_u1 * cos_u2 * cos_lambda
        sigma = math.atan2(sin_sigma, cos_sigma)
        sin_alpha = (cos_u1 * cos_u2 * sin_lambda) / sin_sigma
        cos2_alpha = 1 - sin_alpha ** 2
        cos2_sigma_m = cos_sigma - 2 * sin_u1 * sin_u2 / cos2_alpha if cos2_alpha != 0 else 0
        c = f / 16 * cos2_alpha * (4 + f * (4 - 3 * cos2_alpha))
        lambda_prev = lambda_lon
        lambda_lon = l + (1 - c) * f * sin_alpha * (
            sigma + c * sin_sigma * (cos2_sigma_m + c * cos_sigma * (-1 + 2 * cos2_sigma_m ** 2))
        )
        if abs(lambda_lon - lambda_prev) < 1e-12:
            break
    else:
        # Fall back to Haversine if Vincenty does not converge
        return haversine_distance_m(lat1, lon1, lat2, lon2)

    u_sq = cos2_alpha * (a ** 2 - b ** 2) / (b ** 2)
    a_val = 1 + u_sq / 16384 * (4096 + u_sq * (-768 + u_sq * (320 - 175 * u_sq)))
    b_val = u_sq / 1024 * (256 + u_sq * (-128 + u_sq * (74 - 47 * u_sq)))
    delta_sigma = b_val * sin_sigma * (
        cos2_sigma_m + b_val / 4 * (
            cos_sigma * (-1 + 2 * cos2_sigma_m ** 2) -
            b_val / 6 * cos2_sigma_m * (-3 + 4 * sin_sigma ** 2) * (-3 + 4 * cos2_sigma_m ** 2)
        )
    )
    return b * a_val * (sigma - delta_sigma)

def calculate_initial_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates compass bearing from Point 1 to Point 2 in degrees [0, 360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    
    y = math.sin(dlambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360.0) % 360.0

def get_bounding_box_meters(lat: float, lon: float, radius_m: float) -> Tuple[float, float, float, float]:
    """Returns (min_lon, min_lat, max_lon, max_lat) bounding box for radius in meters."""
    lat_delta = radius_m / 111132.0
    lon_delta = radius_m / (111319.0 * max(0.01, math.cos(math.radians(lat))))
    return (
        round(lon - lon_delta, 6),
        round(lat - lat_delta, 6),
        round(lon + lon_delta, 6),
        round(lat + lat_delta, 6)
    )

def spatial_angular_bin_key(heading: float, distance_m: float,
                             heading_bin_deg: float = 45.0,
                             distance_bin_m: float = 50.0) -> Tuple[int, int]:
    """
    Computes spatial-angular bin: Bin_key = (floor(Heading / 45deg), floor(Distance / 50m)).
    """
    h_norm = heading % 360.0
    h_bin = int(math.floor(h_norm / heading_bin_deg))
    d_bin = int(math.floor(max(0.0, distance_m) / distance_bin_m))
    return (h_bin, d_bin)

def spatial_grid_cell(lat: float, lon: float, cell_size_deg: float = 0.0003) -> str:
    """Approximate 30m grid cell for spatial deduplication."""
    lat_idx = int(math.floor(lat / cell_size_deg))
    lon_idx = int(math.floor(lon / cell_size_deg))
    return f"{lat_idx}:{lon_idx}"
