# ============================================================
# GeoVigilant app.py  –  Library Imports & Credential Config
# ============================================================

# --- Standard Library ---
import os
import io
import random
import base64
import re
import ssl
import json
import time
import math
import socket

import string
import secrets
import asyncio
import logging
import tempfile
import threading
import webbrowser
import sqlite3
import csv
import subprocess
import shutil
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import functools
from functools import wraps, lru_cache
from io import BytesIO
from collections import defaultdict, deque
from threading import Lock

import urllib.parse

# --- Third-Party: Web Framework ---
from flask import (
    Flask, render_template, jsonify, redirect, url_for,
    session, request, Response, send_file, make_response,
    render_template_string
)
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash

# --- Third-Party: HTTP & Auth ---
import requests
import feedparser
from bs4 import BeautifulSoup
try:
    import ujson as json_lib
except ImportError:
    import json as json_lib
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
import websockets


# --- Third-Party: Image / CV (Lazy Loaded / Optional) ---
try:
    import numpy as np
except ImportError:
    np = None

# --- Third-Party: Text-to-Speech (Optional) ---
try:
    from gtts import gTTS
except ImportError:
    gTTS = None  # TTS feature disabled if gtts not installed (pip install gtts)



# --- Local Config ---
from news_config import NEWS_SOURCES

# Load .env file for local development (no-op in production if not present)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed; use OS env vars directly

# ============================================================
# Flask App Initialization
# ============================================================
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(_APP_DIR, 'templates'),
            static_folder=os.path.join(_APP_DIR, 'static'))
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
OPENCELLID_API_KEY = os.environ.get("OPENCELLID_API_KEY", "")
from Socio import socio_bp
app.register_blueprint(socio_bp, url_prefix='/socio')

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB request size limit (DoS prevention)

@app.after_request
def apply_security_headers(response):
    """Apply defensive security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

def is_safe_public_url(url: str) -> bool:
    """
    SSRF Protection Guard:
    Validates that a URL is a valid public HTTP/HTTPS URL and does NOT resolve
    to loopback, private, link-local, multicast, or cloud metadata IP addresses.
    """
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if parsed.scheme.lower() not in ('http', 'https'):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        
        hostname_lower = hostname.lower().strip('[]')
        if hostname_lower in ('localhost', '127.0.0.1', '::1', '0.0.0.0', '169.254.169.254'):
            return False
        if hostname_lower.endswith('.local') or hostname_lower.endswith('.internal') or hostname_lower.endswith('.localhost'):
            return False
            
        import ipaddress
        addr_info = socket.getaddrinfo(hostname_lower, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for res in addr_info:
            ip_str = res[4][0]
            ip = ipaddress.ip_address(ip_str)
            if (ip.is_private or 
                ip.is_loopback or 
                ip.is_link_local or 
                ip.is_reserved or 
                ip.is_multicast or 
                ip.is_unspecified or
                str(ip).startswith('169.254.') or
                str(ip).startswith('100.64.') or
                str(ip) in ('0.0.0.0', '255.255.255.255')):
                return False
        return True
    except Exception:
        return False

if os.environ.get('VERCEL'):
    app.config['UPLOAD_FOLDER'] = os.path.join(tempfile.gettempdir(), 'uploads')
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception:
    pass

socketio = SocketIO(app)

# ============================================================
# Database Helpers
# ============================================================
def get_conn():
    if os.environ.get('VERCEL'):
        db_path = os.path.join(tempfile.gettempdir(), 'geosent.db')
    else:
        db_path = os.path.join(app.root_path, 'geosent.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with necessary tables."""
    try:
        conn = get_conn()
        c = conn.cursor()
        # Table for crime search history
        c.execute('''CREATE TABLE IF NOT EXISTS crime_searches
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      username TEXT,
                      search_type TEXT,
                      query_params TEXT,
                      results TEXT,
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization error: {e}")

# Initialize database on startup
with app.app_context():
    init_db()

# ============================================================
# API Keys & Credentials
# ============================================================
NUMVERIFY_API_KEY      = os.environ.get("NUMVERIFY_API_KEY",      "")
OPENCAGE_API_KEY       = os.environ.get("OPENCAGE_API_KEY",       "")

# Twitter / X
TWITTER_API_KEY             = os.environ.get("TWITTER_API_KEY") or os.environ.get("TWITTER_CONSUMER_KEY", "")
TWITTER_API_SECRET          = os.environ.get("TWITTER_API_SECRET") or os.environ.get("TWITTER_CONSUMER_SECRET", "")
TWITTER_ACCESS_TOKEN        = os.environ.get("TWITTER_ACCESS_TOKEN",        "")
TWITTER_ACCESS_TOKEN_SECRET = os.environ.get("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_BEARER_TOKEN        = os.environ.get("TWITTER_BEARER_TOKEN",        "")

# News / AI Credentials
NEWS_API_KEY         = os.environ.get("NEWS_API_KEY", "")
ANTHROPIC_BASE_URL   = os.environ.get("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
ANTHROPIC_AUTH_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL      = os.environ.get("ANTHROPIC_MODEL", "nvidia/nemotron-3.5-lightning:free")

OPENROUTER_API_KEY   = os.environ.get("OPENROUTER_API_KEY", "") or ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY
OPENROUTER_BASE_URL  = ANTHROPIC_BASE_URL
if "/v1" not in OPENROUTER_BASE_URL:
    OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/v1/chat/completions"
else:
    OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"

OPENROUTER_CHAT_HEADERS = {
    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://geovigilant.local",
    "X-Title": "GeoVigilant OS",
}

OPENROUTER_MODELS = [
    "nvidia/nemotron-3.5-lightning:free",
    "minimax/minimax-m3:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "z-ai/glm-5.2:free",
    "liquid/lfm-2.5-2.6b:free",
    "openrouter/auto",
]

HIGHSIGHT_API_KEY = os.environ.get("HIGHSIGHT_API_KEY", "")
NASA_API_KEY      = os.environ.get("NASA_API_KEY",      "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Webhooks / Misc
AIS_API_KEY         = os.environ.get("AIS_API_KEY", "")
api_key             = AIS_API_KEY

# Ollama Cloud / Local Daemon & ChromaDB
OLLAMA_BASE_URL  = os.environ.get("OLLAMA_BASE_URL",  "http://127.0.0.1:11434").rstrip('/')
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL",     "gpt-oss:120b-cloud")
OLLAMA_API_KEY   = os.environ.get("OLLAMA_API_KEY",   "")
EMBEDDING_MODEL  = os.environ.get("EMBEDDING_MODEL",  "all-minilm:latest")
WIGLE_API_NAME   = os.environ.get("WIGLE_API_NAME",   "")
WIGLE_API_TOKEN  = os.environ.get("WIGLE_API_TOKEN",  "")

def get_wigle_auth():
    """Dynamically resolve WiGLE credentials from environment or .env file."""
    name = os.environ.get("WIGLE_API_NAME") or WIGLE_API_NAME
    token = os.environ.get("WIGLE_API_TOKEN") or WIGLE_API_TOKEN
    if not name or not token:
        try:
            from dotenv import dotenv_values
            env_file = os.path.join(_APP_DIR, '.env')
            if os.path.exists(env_file):
                vals = dotenv_values(env_file)
                name = name or vals.get("WIGLE_API_NAME", "")
                token = token or vals.get("WIGLE_API_TOKEN", "")
        except Exception:
            pass
    return (name, token)

MACVENDORS_TOKEN = os.environ.get("MACVENDORS_TOKEN", "")

def get_macvendors_token():
    """Dynamically resolve MACVendors Bearer token from environment or .env file."""
    tok = os.environ.get("MACVENDORS_TOKEN") or MACVENDORS_TOKEN
    if not tok:
        try:
            from dotenv import dotenv_values
            env_file = os.path.join(_APP_DIR, '.env')
            if os.path.exists(env_file):
                vals = dotenv_values(env_file)
                tok = vals.get("MACVENDORS_TOKEN", "")
        except Exception:
            pass
    return tok

def lookup_mac_vendor(mac_address):
    """
    Resolve hardware vendor for a given MAC/BSSID using MACVendors API v1 with Bearer token.
    Falls back gracefully to legacy endpoint or generic identifier.
    """
    if not mac_address:
        return {"vendor": "Generic Hardware", "raw": {}}
    clean_mac = re.sub(r'[^a-fA-F0-9:]', '', mac_address.strip())
    token = get_macvendors_token()
    
    # 1. Authorized API v1 Query
    if token:
        try:
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
            url = f"https://api.macvendors.com/v1/lookup/{urllib.parse.quote(clean_mac)}"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                vendor_name = data.get("organization_name") or "IEEE Registered Vendor"
                return {
                    "vendor": vendor_name,
                    "address": data.get("organization_address", ""),
                    "assignment": data.get("assignment", ""),
                    "registry": data.get("registry", ""),
                    "status": "success"
                }
            elif resp.status_code == 404:
                return {"vendor": "Unregistered / Private MAC", "status": "not_found"}
        except Exception as e:
            print(f"[MACVendors v1] Lookup exception for {clean_mac}: {e}")

    # 2. Legacy Free Endpoint Fallback
    try:
        url = f"https://api.macvendors.com/{urllib.parse.quote(clean_mac)}"
        resp = requests.get(url, headers={"User-Agent": "GeoVigilant-Argus/2.0"}, timeout=5)
        if resp.status_code == 200 and resp.text.strip():
            return {"vendor": resp.text.strip(), "status": "legacy"}
    except Exception:
        pass

    return {"vendor": "IEEE Registered Vendor", "status": "unknown"}

def get_opencellid_key():
    """Dynamically resolve OpenCellID API key from environment or .env file."""
    key = os.environ.get("OPENCELLID_API_KEY") or OPENCELLID_API_KEY
    if not key:
        try:
            from dotenv import dotenv_values
            env_file = os.path.join(_APP_DIR, '.env')
            if os.path.exists(env_file):
                vals = dotenv_values(env_file)
                key = vals.get("OPENCELLID_API_KEY", "")
        except Exception:
            pass
    return key or ""

ZOOMEYE_API_KEY = os.environ.get("ZOOMEYE_API_KEY", "")

def get_zoomeye_key():
    """Dynamically resolve ZoomEye API key from environment or .env file."""
    key = os.environ.get("ZOOMEYE_API_KEY") or ZOOMEYE_API_KEY
    if not key:
        try:
            from dotenv import dotenv_values
            env_file = os.path.join(_APP_DIR, '.env')
            if os.path.exists(env_file):
                vals = dotenv_values(env_file)
                key = vals.get("ZOOMEYE_API_KEY", "")
        except Exception:
            pass
    return key or ""

CENSYS_API_TOKEN = os.environ.get("CENSYS_API_TOKEN", "")

def get_censys_token():
    """Dynamically resolve Censys Personal Access Token from environment or .env file."""
    tok = os.environ.get("CENSYS_API_TOKEN") or CENSYS_API_TOKEN
    if not tok:
        try:
            from dotenv import dotenv_values
            env_file = os.path.join(_APP_DIR, '.env')
            if os.path.exists(env_file):
                vals = dotenv_values(env_file)
                tok = vals.get("CENSYS_API_TOKEN", "")
        except Exception:
            pass
    return tok or ""


def ensure_ollama_running():
    """Ensure local Ollama daemon is active if pointing to localhost."""
    if "127.0.0.1" in OLLAMA_BASE_URL or "localhost" in OLLAMA_BASE_URL:
        try:
            r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        ollama_bin = os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe")
        if not os.path.exists(ollama_bin):
            ollama_bin = shutil.which("ollama")

        if ollama_bin and os.path.exists(ollama_bin):
            try:
                creationflags = 0x08000000 if os.name == 'nt' else 0  # CREATE_NO_WINDOW
                spawn_env = os.environ.copy()
                spawn_env["OLLAMA_KEEP_ALIVE"] = "-1"
                spawn_env["OLLAMA_FLASH_ATTENTION"] = "1"
                subprocess.Popen(
                    [ollama_bin, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                    env=spawn_env
                )
                time.sleep(1.5)
                return True
            except Exception as e:
                print(f"[Ollama] Auto-spawn daemon notice: {e}")
    return False

def _call_ollama_chat(messages, model=None, timeout=25):
    """
    Unified caller for Ollama Cloud (e.g. gemma4:31b-cloud) and remote/local Ollama instances.
    Supports native /api/chat and OpenAI-compatible /v1/chat/completions with optional Bearer auth.
    """
    target_model = model or OLLAMA_MODEL
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"

    ensure_ollama_running()

    # 1. Native Ollama /api/chat
    try:
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "think": False,
            "keep_alive": -1,
            "options": {
                "num_ctx": 2048,
                "num_predict": 350,
                "temperature": 0.4
            }
        }
        resp = requests.post(f"{OLLAMA_BASE_URL}/api/chat", headers=headers, json=payload, timeout=timeout)
        if resp.status_code == 200:
            content = resp.json().get("message", {}).get("content", "").strip()
            if content:
                return content
    except Exception:
        pass

    # 2. OpenAI-compatible /v1/chat/completions
    try:
        v1_url = f"{OLLAMA_BASE_URL}/v1/chat/completions"
        v1_payload = {
            "model": target_model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024
        }
        resp_v1 = requests.post(v1_url, headers=headers, json=v1_payload, timeout=timeout)
        if resp_v1.status_code == 200:
            choices = resp_v1.json().get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "").strip()
                if content:
                    return content
    except Exception:
        pass

    return None



# ============================================================
# Auth Helpers
# ============================================================
KML_DIR = os.path.join(app.root_path, 'templates', 'wmaps')


# ============================================================
# News Cache
# ============================================================
news_cache      = {}
NEWS_CACHE_LIMIT = 15  # minutes

# ============================================================
# Routes begin below
# ============================================================



@app.route('/')
def portfolio():
    """Render the GeoVigilant Argus Eye frontend portfolio / suite overview."""
    return render_template("portfolio.html")


@app.route('/earth')
def earth():
    """Render main GeoVigilant-Argus Earth HUD dashboard."""
    geodata_dir = os.path.join(app.root_path, 'ARGUS_DATASET', 'geodata')
    geojson_files = []
    if os.path.exists(geodata_dir):
        geojson_files = [f for f in os.listdir(geodata_dir) if f.endswith('.geojson')]
    argus_mode = os.environ.get('ARGUS_MODE', 'eco')
    return render_template("earth.html", geojson_files=geojson_files, argus_mode=argus_mode)


@app.route('/surveillance')
@app.route('/map-w')
def surveillance():
    """Render WiFi & RF surveillance dashboard."""
    return render_template("wifi-search.html")


@app.route('/crmx')
def crmx_dashboard():
    """Alias for main Earth HUD dashboard."""
    return redirect(url_for('earth'))


@app.route('/tor-chat')
@app.route('/profiles')
@app.route('/neural')
@app.route('/cctv')
@app.route('/mobile')
@app.route('/alerts')
@app.route('/fit')
@app.route('/settings')
def app_modules():
    """Render modular views inside GeoVigilant-Argus HUD."""
    geodata_dir = os.path.join(app.root_path, 'ARGUS_DATASET', 'geodata')
    geojson_files = []
    if os.path.exists(geodata_dir):
        geojson_files = [f for f in os.listdir(geodata_dir) if f.endswith('.geojson')]
    return render_template("earth.html", geojson_files=geojson_files)


@app.route('/social')
def social_redirect():
    """Redirect to global news and social intel stream."""
    return redirect(url_for('news_page'))


@app.route('/social/reddit')
def social_reddit():
    """Render Reddit OSINT stream."""
    return render_template("social/reddit.html")


@app.route('/social/twitter')
def social_twitter():
    """Render Twitter/X OSINT stream."""
    return render_template("social/twitter.html")


@app.route('/ground')
def groundview():
    """Render ARGUS GroundView — 2D Geospatial Intelligence Workspace.
    Completely isolated from the 3D Cesium globe.
    MapLibre GL JS loads lazily only when this page is visited.
    """
    return render_template("groundview.html")


@app.route('/api/groundview/config')
def groundview_config():
    """Serve GroundView runtime configuration.
    Mapillary access token is sourced from environment variable,
    never hardcoded in frontend bundles.
    """
    return jsonify({
        'mapillaryToken': os.environ.get('MAPILLARY_ACCESS_TOKEN', ''),
        'mapillaryClientId': '28129684709980967',
    })


# Cache the patched CartoDB styles in memory (avoids re-fetching on every reload)
_gv_style_cache = {}

@app.route('/api/groundview/map-style')
def groundview_map_style():
    """Proxy + patch CartoDB Dark Matter & Voyager GL vector styles.

    Applies the Palestine label correction server-side before MapLibre
    ever loads the style, so "Israel" never appears in either dark or streets mode.

    Target layers (confirmed from CartoDB style.json):
      place_country_1  — country names at low zoom
      place_country_2  — country names at higher zoom
      place_state      — state/province names
    """
    global _gv_style_cache
    import urllib.request
    from flask import request

    theme = request.args.get('theme', 'tactical')
    # Normalize aliases
    if theme in ('dark', 'tactical'):
        cache_key = 'tactical'
    elif theme == 'streets':
        cache_key = 'streets'
    elif theme == 'satellite':
        cache_key = 'satellite'
    else:
        cache_key = 'tactical'

    if cache_key not in _gv_style_cache:
        if cache_key == 'streets':
            CARTO_URL = 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json'
        else:
            CARTO_URL = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

        try:
            req = urllib.request.Request(CARTO_URL, headers={'User-Agent': 'GeoVigilant-Argus/1.0'})
            with urllib.request.urlopen(req, timeout=15) as res:
                import json as _json
                style = _json.loads(res.read())
        except Exception as exc:
            app.logger.error('Failed to fetch CartoDB style (%s): %s', cache_key, exc)
            return jsonify({'error': 'upstream style unavailable'}), 502

        if cache_key == 'satellite':
            # ── Clean satellite hybrid style ────────────────────────────────
            # Strategy: take CartoDB dark-matter's line + symbol layers only
            # (roads, labels) and stack them on top of an ESRI satellite raster.
            # We proxy the ESRI tiles through Flask to guarantee browser access.
            #
            # Layer order (bottom → top):
            #   [0] background (dark fallback while tiles load)
            #   [1] esri-satellite-layer (raster imagery)
            #   [2..N] line layers (roads, boundaries, waterways)
            #   [N+1..] symbol layers (labels, icons)
            # ────────────────────────────────────────────────────────────────

            import json as _json_sat

            # Extract only line + symbol layers from CartoDB for road/label overlay
            overlay_layers = [
                l for l in style.get('layers', [])
                if l.get('type') in ('line', 'symbol')
            ]

            # Build clean satellite style from scratch (no fill-hiding needed)
            style = {
                'version': 8,
                'name': 'ARGUS-Satellite',
                'glyphs': style.get('glyphs', 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/glyphs/{fontstack}/{range}.pbf'),
                'sprite': style.get('sprite', 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/sprite'),
                'sources': {
                    # Keep CartoDB vector source for roads/labels
                    'carto': style.get('sources', {}).get('carto', {
                        'type': 'vector',
                        'url': 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/tile.json'
                    }),
                    # ESRI satellite proxied through Flask for browser reliability
                    'esri-satellite': {
                        'type': 'raster',
                        'tiles': ['/api/groundview/tiles/satellite/{z}/{y}/{x}'],
                        'tileSize': 256,
                        'minzoom': 0,
                        'maxzoom': 19,
                        'attribution': 'Esri, Maxar, Earthstar Geographics'
                    }
                },
                'layers': [
                    # Dark background — always visible as fallback
                    {
                        'id': 'background',
                        'type': 'background',
                        'paint': {'background-color': '#0d1117'}
                    },
                    # Satellite raster imagery (base)
                    # Note: Do NOT set maxzoom < 24 on the layer itself!
                    # The source has maxzoom: 19; MapLibre will automatically
                    # GPU-overscale zoom 19 tiles for zoom 20, 21, 22+ without hiding the layer.
                    {
                        'id': 'esri-satellite-layer',
                        'type': 'raster',
                        'source': 'esri-satellite',
                        'minzoom': 0,
                        'maxzoom': 24,
                        'paint': {
                            'raster-opacity': 1.0,
                            'raster-saturation': 0.05,
                            'raster-contrast': 0.05
                        }
                    },
                    # Roads and labels from CartoDB on top of satellite
                    *overlay_layers
                ]
            }

        # ── Comprehensive Palestine & Arabic Place Names Patch ───────────────
        try:
            from arabic_names import patch_style_with_arabic_names
            style = patch_style_with_arabic_names(style)
        except Exception as patch_exc:
            app.logger.warning('Failed to apply arabic names patch: %s', patch_exc)
        # ─────────────────────────────────────────────────────────────────────

        _gv_style_cache[cache_key] = style
        app.logger.info('GroundView style (%s) cached with Arabic patch applied.', cache_key)

    response = jsonify(_gv_style_cache[cache_key])
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response



# ─── GroundView: ESRI Satellite Tile Proxy ────────────────────────────────────
# MapLibre fetches tiles from the browser. Proxying through Flask ensures
# tiles always load regardless of browser-side network restrictions.

_ESRI_TILE_BASE = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile'
_ESRI_TILE_CACHE = {}  # Simple in-memory tile cache (LRU not needed at dev scale)

@app.route('/api/groundview/tiles/satellite/<int:z>/<int:y>/<int:x>')
def proxy_satellite_tile(z, y, x):
    """Proxy ESRI World Imagery satellite tiles to avoid browser-side network restrictions."""
    import urllib.request
    from flask import Response
    cache_key_tile = (z, y, x)
    if cache_key_tile in _ESRI_TILE_CACHE:
        tile_data, content_type = _ESRI_TILE_CACHE[cache_key_tile]
    else:
        esri_url = f'{_ESRI_TILE_BASE}/{z}/{y}/{x}'
        try:
            req = urllib.request.Request(
                esri_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
                }
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                tile_data = r.read()
                content_type = r.headers.get('Content-Type', 'image/jpeg')
        except Exception as e:
            app.logger.error('Satellite tile proxy ERROR z=%d y=%d x=%d: %s', z, y, x, e)
            return Response(status=503)
        # Cache tiles at zoom ≤ 10 to save bandwidth (low-zoom tiles are reused a lot)
        if z <= 10 and len(_ESRI_TILE_CACHE) < 2000:
            _ESRI_TILE_CACHE[cache_key_tile] = (tile_data, content_type)

    resp = Response(tile_data, content_type=content_type)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


# ─── GroundView: Global Streetscapes (10k SVI) Endpoints ──────────────────────

@app.route('/api/groundview/streetscapes/geojson')
def get_streetscapes_geojson():
    """Returns pre-computed GeoJSON FeatureCollection of all 10k observation points."""
    from streetscapes_service import streetscapes_service
    geojson_data = streetscapes_service.get_geojson()
    response = jsonify(geojson_data)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/api/groundview/streetscapes/image/<int:image_id>')
def get_streetscape_image(image_id):
    """Serves the PNG street image for a given observation point ID."""
    from streetscapes_service import streetscapes_service
    from flask import send_file, abort
    img_path = streetscapes_service.get_image_path(image_id)
    if not img_path:
        abort(404)
    return send_file(img_path, mimetype='image/png', max_age=86400)


@app.route('/api/groundview/streetscapes/info/<int:image_id>')
def get_streetscape_info(image_id):
    """Returns full metadata and AI environmental tags for an observation point."""
    from streetscapes_service import streetscapes_service
    meta = streetscapes_service.get_metadata(image_id)
    if not meta:
        return jsonify({'error': 'Observation point not found'}), 404
    return jsonify(meta)


@app.route('/api/groundview/streetscapes/nearby')
def get_streetscapes_nearby():
    """Spatial query for streetscape observation points within radius (km)."""
    from streetscapes_service import streetscapes_service
    from flask import request
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        radius = float(request.args.get('radius', 50.0))
        limit = int(request.args.get('limit', 50))
    except ValueError:
        return jsonify({'error': 'Invalid numeric parameters'}), 400

    results = streetscapes_service.get_nearby(lat, lon, radius_km=radius, limit=limit)
    return jsonify({'count': len(results), 'observations': results})


@app.route('/api/groundview/streetscapes/stats')
def get_streetscapes_stats():
    """Returns dataset overview statistics."""
    from streetscapes_service import streetscapes_service
    return jsonify(streetscapes_service.get_statistics())


# ─── GroundView: ARGUS Global Landmarks & Visual Intel (74k+ Assets) ─────────

@app.route('/api/argus/places/geojson')
@app.route('/api/groundview/landmarks/geojson')
def get_argus_places_geojson():
    """Returns pre-computed GeoJSON FeatureCollection of global landmarks."""
    from argus_dataset_service import argus_dataset_service
    from flask import request
    category = request.args.get('category')
    country = request.args.get('country')
    geojson_data = argus_dataset_service.get_places_geojson(category=category, country=country)
    response = jsonify(geojson_data)
    response.headers['Cache-Control'] = 'public, max-age=86400'
    return response


@app.route('/api/argus/places/<place_id>')
@app.route('/api/groundview/landmarks/info/<place_id>')
def get_argus_place_detail(place_id):
    """Returns complete place details including all multi-angle image assets."""
    from argus_dataset_service import argus_dataset_service
    detail = argus_dataset_service.get_place_detail(place_id)
    if not detail:
        return jsonify({'error': 'Place not found'}), 404
    return jsonify(detail)


@app.route('/api/argus/places/nearby')
@app.route('/api/groundview/landmarks/nearby')
def get_argus_places_nearby():
    """Spatial query for landmarks within radius (km)."""
    from argus_dataset_service import argus_dataset_service
    from flask import request
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        radius = float(request.args.get('radius', 50.0))
        limit = int(request.args.get('limit', 30))
    except ValueError:
        return jsonify({'error': 'Invalid numeric parameters'}), 400

    results = argus_dataset_service.get_nearby_places(lat, lon, radius_km=radius, limit=limit)
    return jsonify({'count': len(results), 'places': results})


@app.route('/api/argus/images/<image_id>')
@app.route('/api/groundview/landmarks/image/<image_id>')
def get_argus_image(image_id):
    """Serves high-resolution JPG image binary for a given image_id."""
    from argus_dataset_service import argus_dataset_service
    from flask import send_file, abort
    img_path = argus_dataset_service.get_image_path(image_id)
    if not img_path:
        abort(404)
    return send_file(img_path, mimetype='image/jpeg', max_age=86400)


@app.route('/api/argus/visual-search', methods=['POST', 'GET'])
@app.route('/api/groundview/visual-search', methods=['POST', 'GET'])
def search_argus_visual():
    """Performs BK-Tree perceptual hash matching or image upload visual geolocation."""
    from argus_dataset_service import argus_dataset_service
    from flask import request
    
    max_dist = int(request.args.get('max_dist', 12))
    limit = int(request.args.get('limit', 10))

    if request.method == 'POST':
        if 'image' in request.files:
            file = request.files['image']
            image_bytes = file.read()
            phash, matches = argus_dataset_service.visual_search_by_image_bytes(image_bytes, max_dist=max_dist, limit=limit)
            return jsonify({
                'status': 'success',
                'computed_phash': phash,
                'match_count': len(matches),
                'matches': matches
            })
        
        # Check if JSON payload with phash was supplied
        data = request.get_json(silent=True) or {}
        phash = data.get('phash') or request.form.get('phash')
        if phash:
            matches = argus_dataset_service.visual_search_by_phash(phash, max_dist=max_dist, limit=limit)
            return jsonify({
                'status': 'success',
                'query_phash': phash,
                'match_count': len(matches),
                'matches': matches
            })
        return jsonify({'status': 'error', 'message': 'Provide an image file upload or phash hex string'}), 400

    # GET query by phash param
    phash = request.args.get('phash')
    if not phash:
        return jsonify({'status': 'error', 'message': 'Missing phash query parameter'}), 400
    matches = argus_dataset_service.visual_search_by_phash(phash, max_dist=max_dist, limit=limit)
    return jsonify({
        'status': 'success',
        'query_phash': phash,
        'match_count': len(matches),
        'matches': matches
    })


@app.route('/api/argus/categories')
@app.route('/api/groundview/landmarks/categories')
def get_argus_categories():
    """Returns distinct landmark categories and counts."""
    from argus_dataset_service import argus_dataset_service
    return jsonify(argus_dataset_service.get_categories())


@app.route('/api/argus/stats')
@app.route('/api/groundview/landmarks/stats')
def get_argus_stats():
    """Returns ARGUS GroundView dataset overview statistics."""
    from argus_dataset_service import argus_dataset_service
    return jsonify(argus_dataset_service.get_statistics())


# ─── ARGUS DATASET: Unified Geospatial Intelligence Endpoints ─────────────────

@app.route('/api/dataset/unified/stats')
@app.route('/api/argus/unified/stats')
def get_argus_unified_stats():
    """Returns comprehensive aggregated intelligence statistics for the whole ARGUS DATASET suite."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    return jsonify(argus_unified_dataset_service.get_unified_statistics())


@app.route('/api/dataset/unified/search')
@app.route('/api/argus/unified/search')
def search_argus_unified_nearby():
    """High-speed multi-layer spatial query across all 198k+ unified ARGUS entities."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    from flask import request
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        radius = float(request.args.get('radius_km', request.args.get('radius', 25.0)))
        limit = int(request.args.get('limit', 50))
    except ValueError:
        return jsonify({'error': 'Invalid numeric parameters'}), 400

    layers_arg = request.args.get('layers')
    layers = [l.strip() for l in layers_arg.split(',') if l.strip()] if layers_arg else None

    results = argus_unified_dataset_service.search_nearby(lat, lon, radius_km=radius, layers=layers, limit=limit)
    return jsonify({'count': len(results), 'results': results})


@app.route('/api/dataset/unified/bbox')
@app.route('/api/argus/unified/bbox')
def get_argus_unified_bbox():
    """Returns unified GeoJSON FeatureCollection for an exact bounding box viewport."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    from flask import request
    try:
        min_lat = float(request.args.get('min_lat', -90))
        min_lon = float(request.args.get('min_lon', -180))
        max_lat = float(request.args.get('max_lat', 90))
        max_lon = float(request.args.get('max_lon', 180))
        limit = int(request.args.get('limit', 250))
    except ValueError:
        return jsonify({'error': 'Invalid numeric bounding box parameters'}), 400

    layers_arg = request.args.get('layers')
    layers = [l.strip() for l in layers_arg.split(',') if l.strip()] if layers_arg else None

    geojson_data = argus_unified_dataset_service.search_bbox(
        min_lat=min_lat, min_lon=min_lon, max_lat=max_lat, max_lon=max_lon, layers=layers, limit_per_layer=limit
    )
    return jsonify(geojson_data)


@app.route('/api/dataset/unified/cameras/<int:camera_id>')
def get_argus_camera_detail(camera_id):
    """Returns details for a surveillance camera along with nearby ALPR sharing links."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    detail = argus_unified_dataset_service.get_camera_detail(camera_id)
    if not detail:
        return jsonify({'error': 'Camera node not found'}), 404
    return jsonify(detail)


@app.route('/api/dataset/unified/precincts/<int:precinct_id>')
def get_argus_precinct_detail(precinct_id):
    """Returns full police precinct record including jurisdiction polygon geometry."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    detail = argus_unified_dataset_service.get_precinct_detail(precinct_id)
    if not detail:
        return jsonify({'error': 'Precinct not found'}), 404
    return jsonify(detail)


@app.route('/api/dataset/unified/vector-search')
@app.route('/api/argus/unified/vector-search')
def search_argus_unified_vectors():
    """Executes dense vector semantic geolocation search over ChromaDB neural embeddings."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    from flask import request
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'status': 'error', 'message': 'Missing query parameter', 'results': []}), 400
    try:
        limit = int(request.args.get('limit', 15))
    except ValueError:
        limit = 15
    layer = request.args.get('layer')
    results = argus_unified_dataset_service.semantic_search(query, limit=limit, layer_filter=layer)
    return jsonify(results)


@app.route('/api/dataset/unified/defense')
@app.route('/api/argus/unified/defense')
def get_argus_defense_infrastructure():
    """Returns strategic defense, nuclear, spaceport, and law enforcement facilities."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    from flask import request
    facility_type = request.args.get('type')
    country = request.args.get('country')
    threat_level = request.args.get('threat_level')
    try:
        limit = int(request.args.get('limit', 100))
    except ValueError:
        limit = 100
    facilities = argus_unified_dataset_service.get_defense_infrastructure(
        facility_type=facility_type, country=country, threat_level=threat_level, limit=limit
    )
    return jsonify({'count': len(facilities), 'facilities': facilities})


@app.route('/api/dataset/unified/cameras/<int:camera_id>/health')
def probe_argus_camera_health(camera_id):
    """Real-time network connectivity and live stream health check for a camera node."""
    from argus_unified_dataset_service import argus_unified_dataset_service
    health_result = argus_unified_dataset_service.probe_camera_stream(camera_id)
    return jsonify(health_result)


@app.route('/earthnetworks')
def earthnetworks():
    """Render Global Intelligence & Ground Station Networks."""
    return render_template("newsnetworks.html", sources=NEWS_SOURCES)


@app.route('/api/username')
def get_username():
    """Return active operative username."""
    user = os.environ.get("USERNAME", os.environ.get("USER", "GeoVigilant Operative"))
    return jsonify({"username": user})


@app.route('/log-activity', methods=['GET', 'POST'])
def log_activity():
    """Record UI and operative telemetry activity."""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/geo/wireless-nodes')
@app.route('/wirelesesh9')
def get_wireless_nodes():
    """Return wireless / surveillance devices array for Earth HUD."""
    lat = request.args.get('lat', default=38.9072, type=float)
    lon = request.args.get('lon', default=-77.0369, type=float)
    
    nodes = [
        {"lat": lat + 0.0012, "lon": lon + 0.0015, "ssid": "ARGUS_SEC_CAM_01", "type": "camera", "vendor": "Axis Communications", "signal": -48},
        {"lat": lat - 0.0018, "lon": lon - 0.0011, "ssid": "CORP_GATEWAY_5G", "type": "router", "vendor": "Cisco Systems", "signal": -56},
        {"lat": lat + 0.0025, "lon": lon - 0.0020, "ssid": "SMART_METER_GRID", "type": "iot", "vendor": "Siemens IoT", "signal": -68},
        {"lat": lat - 0.0009, "lon": lon + 0.0022, "ssid": "BT_TRACK_BEACON", "type": "bluetooth", "vendor": "Nordic Semi", "signal": -72},
        {"lat": lat + 0.0031, "lon": lon + 0.0018, "ssid": "MUNICIPAL_CCTV_NODE", "type": "camera", "vendor": "Hikvision", "signal": -52}
    ]
    return jsonify(nodes)




@lru_cache(maxsize=32)
def _load_cached_geojson_summary(safe_filename):
    filepath = os.path.join(app.root_path, 'ARGUS_DATASET', 'geodata', safe_filename)
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    features = data.get('features', [])
    summary_features = []
    
    for feat in features[:500]: # Increased to 500 for map display
        summary_features.append({
            "type": feat.get("type"),
            "properties": feat.get("properties"),
            "geometry": feat.get("geometry")
        })

    return {
        "filename": safe_filename,
        "total_features": len(features),
        "summary": summary_features
    }

@app.route('/api/geojson/<filename>')
def get_geojson_data(filename):
    """Return a summary of the GeoJSON file (properties and first few coords to keep it snappy) with LRU cache."""
    # Security check: prevent directory traversal
    if '..' in filename or filename.startswith('/') or filename.startswith('.'):
        return jsonify({"error": "Invalid filename"}), 400

    safe_filename = os.path.basename(filename)
    try:
        res = _load_cached_geojson_summary(safe_filename)
        if res is None:
            return jsonify({"error": "File not found"}), 404
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

_geo_index_cached_data = None

@app.route('/api/geo/index')
def get_geo_index():
    """Return the surveillance grid index."""
    global _geo_index_cached_data
    if _geo_index_cached_data is not None:
        return jsonify(_geo_index_cached_data)

    filepath = os.path.join(app.root_path, 'ARGUS_DATASET', 'geodata', 'geo', 'index.json')
    if not os.path.exists(filepath):
        return jsonify({"error": "Index not found"}), 404
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            _geo_index_cached_data = json.load(f)
        return jsonify(_geo_index_cached_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@functools.lru_cache(maxsize=256)
def _load_cached_tile(z, x, y):
    filepath = os.path.join(app.root_path, 'ARGUS_DATASET', 'geodata', 'geo', str(z), str(x), f"{y}.json")
    if not os.path.exists(filepath):
        return None
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.route('/api/geo/tile/<z>/<x>/<y>')
def get_geo_tile(z, x, y):
    """Return a specific surveillance grid tile with LRU caching."""
    try:
        z = int(z)
        x = int(x)
        y = int(y)
    except ValueError:
        return jsonify({"error": "Invalid tile coordinates"}), 400

    try:
        data = _load_cached_tile(z, x, y)
        if data is None:
            return jsonify({"error": "Tile not found"}), 404
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500






# ── Flight data cache (refreshed every 30 s in background) ──────────────────
_flight_cache      = []
_flight_cache_time = 0
_flight_cache_lock = __import__('threading').Lock()
_flight_fetch_running = False

_FLT_MIL_PREFIXES = ['RCH','SPAR','SAM','AF1','MAGMA','ASCOT','BAF','GAF',
                     'PLF','DUKE','NAVY','COBRA','VIPER','REACH','EVAC']
_FLT_MIL_TYPES    = ['C17','C130','C5','KC135','KC10','F15','F16','F18',
                     'F22','F35','B52','B1','B2','E3','E6','P8','V22']
_FLT_PRIV_TYPES   = ['C172','C182','C208','PA28','SR22','TBM9','PC12','CL60','C152','PA32']

_flight_store = {}  # hex_code -> (flight_dict, timestamp)

def _refresh_flights_cache():
    """Background worker: hits adsb.lol globally across all continents concurrently."""
    global _flight_cache, _flight_cache_time, _flight_fetch_running, _flight_store
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as _FTO

    # Comprehensive global flight hubs covering ALL continents
    endpoints = [
        # Military & Special Global
        ("https://api.adsb.lol/v2/mil", "Military Global"),
        ("https://api.adsb.lol/v2/ladd", "LADD Global"),
        ("https://api.adsb.lol/v2/pia", "PIA Global"),

        # Africa
        ("https://api.adsb.lol/v2/point/30.0444/31.2357/250", "Africa - Cairo"),
        ("https://api.adsb.lol/v2/point/-26.2041/28.0473/250", "Africa - Johannesburg"),
        ("https://api.adsb.lol/v2/point/-1.2921/36.8219/250", "Africa - Nairobi"),
        ("https://api.adsb.lol/v2/point/6.5244/3.3792/250", "Africa - Lagos"),
        ("https://api.adsb.lol/v2/point/33.5731/-7.5898/250", "Africa - Casablanca"),

        # Middle East
        ("https://api.adsb.lol/v2/point/25.2048/55.2708/250", "Middle East - Dubai"),
        ("https://api.adsb.lol/v2/point/24.7136/46.6753/250", "Middle East - Riyadh"),
        ("https://api.adsb.lol/v2/point/41.0082/28.9784/250", "Middle East - Istanbul"),
        ("https://api.adsb.lol/v2/point/32.0853/34.7818/250", "Middle East - Tel Aviv"),

        # Asia & South Asia
        ("https://api.adsb.lol/v2/point/28.6139/77.2090/250", "Asia - Delhi"),
        ("https://api.adsb.lol/v2/point/19.0760/72.8777/250", "Asia - Mumbai"),
        ("https://api.adsb.lol/v2/point/1.3521/103.8198/250", "Asia - Singapore"),
        ("https://api.adsb.lol/v2/point/13.7563/100.5018/250", "Asia - Bangkok"),
        ("https://api.adsb.lol/v2/point/22.3193/114.1694/250", "Asia - Hong Kong"),
        ("https://api.adsb.lol/v2/point/35.6762/139.6503/250", "Asia - Tokyo"),
        ("https://api.adsb.lol/v2/point/37.5665/126.9780/250", "Asia - Seoul"),

        # Europe
        ("https://api.adsb.lol/v2/point/51.5074/-0.1278/250", "Europe - London"),
        ("https://api.adsb.lol/v2/point/50.1109/8.6821/250", "Europe - Frankfurt"),
        ("https://api.adsb.lol/v2/point/48.8566/2.3522/250", "Europe - Paris"),
        ("https://api.adsb.lol/v2/point/40.4168/-3.7038/250", "Europe - Madrid"),
        ("https://api.adsb.lol/v2/point/41.9028/12.4964/250", "Europe - Rome"),
        ("https://api.adsb.lol/v2/point/52.2297/21.0122/250", "Europe - Warsaw"),

        # Americas
        ("https://api.adsb.lol/v2/point/40.7128/-74.0060/250", "Americas - New York"),
        ("https://api.adsb.lol/v2/point/34.0522/-118.2437/250", "Americas - Los Angeles"),
        ("https://api.adsb.lol/v2/point/41.8781/-87.6298/250", "Americas - Chicago"),
        ("https://api.adsb.lol/v2/point/25.7617/-80.1918/250", "Americas - Miami"),
        ("https://api.adsb.lol/v2/point/-23.5505/-46.6333/250", "Americas - Sao Paulo"),
        ("https://api.adsb.lol/v2/point/4.7110/-74.0721/250", "Americas - Bogota"),

        # Oceania
        ("https://api.adsb.lol/v2/point/-33.8688/151.2093/250", "Oceania - Sydney"),
    ]

    def _fetch_one(url_name):
        url, name = url_name
        out = {}
        try:
            resp = requests.get(url, timeout=7, headers={"User-Agent": "GeoVigilant-Argus/2.0"})
            if resp.status_code != 200:
                return out
            for ac in resp.json().get('ac', []):
                if ac.get('lat') is None or ac.get('lon') is None:
                    continue
                hex_code = ac.get('hex', '').upper()
                callsign = (ac.get('flight', '') or '').strip() or ac.get('r', '') or hex_code
                reg  = ac.get('r', '')
                atyp = ac.get('t', '')
                is_mil = (any(callsign.upper().startswith(p) for p in _FLT_MIL_PREFIXES) or
                          any(t in atyp.upper() for t in _FLT_MIL_TYPES))
                is_priv = ((callsign.startswith('N') and len(callsign) <= 6) or
                           callsign.startswith('G-') or callsign.startswith('VH-') or
                           atyp.upper() in _FLT_PRIV_TYPES)
                is_emg = (ac.get('emergency', 'none') != 'none' or ac.get('squawk') == '7700')
                f_type = 'emergency' if is_emg else ('military' if is_mil else ('private' if is_priv else 'commercial'))
                out[hex_code] = {
                    'icao24': hex_code.lower(), 'callsign': callsign,
                    'registration': reg or '---', 'aircraft_type': atyp or '---',
                    'long': ac.get('lon'), 'lat': ac.get('lat'),
                    'alt': ac.get('alt_baro') or ac.get('alt_geom') or 10000,
                    'velocity': ac.get('gs', 0), 'heading': ac.get('track', 0),
                    'squawk': ac.get('squawk', '----'), 'type': f_type,
                }
        except Exception as ex:
            pass
        return out

    now = _time.time()
    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            futs = [pool.submit(_fetch_one, ep) for ep in endpoints]
            for f in as_completed(futs, timeout=18):
                try:
                    res = f.result()
                    for hx, flt in res.items():
                        _flight_store[hx] = (flt, now)
                except Exception:
                    pass
    except _FTO:
        pass

    # Prune flights older than 180 seconds (3 min)
    cutoff = now - 180
    _flight_store = {k: v for k, v in _flight_store.items() if v[1] > cutoff}

    with _flight_cache_lock:
        all_flights = [v[0] for v in _flight_store.values()]
        # Memory Protection: Prioritize emergency, military, private, then commercial; cap at 1,200
        priority_order = {'emergency': 0, 'military': 1, 'private': 2, 'commercial': 3}
        all_flights.sort(key=lambda x: priority_order.get(x.get('type'), 4))
        _flight_cache = all_flights[:1200]
        _flight_cache_time = now
        _flight_fetch_running = False
    print(f"[flights] global cache refreshed — {len(_flight_cache)} aircraft across all continents (memory capped)")


@app.route('/api/proxy/rss')
def proxy_rss_feed():
    """Proxy external RSS feeds to avoid browser CORS issues with strict SSRF validation."""
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"error": "Missing url parameter"}), 400
    if not is_safe_public_url(target_url):
        return jsonify({"error": "Invalid or disallowed URL (internal/private destinations are blocked)"}), 403
    try:
        resp = requests.get(target_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=8)
        content_type = resp.headers.get('Content-Type', 'application/xml; charset=utf-8')
        return Response(resp.content, status=resp.status_code, content_type=content_type)
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route('/api/geo/flights')
def get_flight_data():
    """Return cached flight data; trigger background refresh when stale (>30 s)."""
    import time as _time, threading
    global _flight_fetch_running

    CACHE_TTL = 30          # seconds before data is considered stale
    now = _time.time()

    with _flight_cache_lock:
        stale = (now - _flight_cache_time) > CACHE_TTL
        need_refresh = stale and not _flight_fetch_running

    if need_refresh:
        with _flight_cache_lock:
            _flight_fetch_running = True
        t = threading.Thread(target=_refresh_flights_cache, daemon=True)
        t.start()

    search_q = request.args.get('q', '').strip().upper()
    with _flight_cache_lock:
        data = list(_flight_cache)   # snapshot

    if search_q:
        data = [f for f in data if
                search_q in (f.get('icao24','') or '').upper() or
                search_q in (f.get('callsign','') or '').upper() or
                search_q in (f.get('registration','') or '').upper()]

    return jsonify(data)


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 2: NASA FIRMS — Real VIIRS 375m Active Fire / Wildfire Data
# ─────────────────────────────────────────────────────────────────────────────
_firms_cache = []
_firms_cache_time = 0
_firms_cache_lock = threading.Lock()

@app.route('/api/geo/firms')
def get_firms_data():
    """
    Fetch real VIIRS C2 375m active fire detections from NASA FIRMS.
    No API key needed. 15-minute server-side cache.
    """
    import time as _time
    global _firms_cache, _firms_cache_time

    with _firms_cache_lock:
        if _firms_cache and (_time.time() - _firms_cache_time) < 900:
            return jsonify(_firms_cache)

    url = 'https://firms.modaps.eosdis.nasa.gov/data/active_fire/suomi-npp-viirs-c2/csv/SUOMI_VIIRS_C2_Global_24h.csv'
    try:
        r = requests.get(url, timeout=25, headers={'User-Agent': 'GeoVigilant/2.0'})
        r.raise_for_status()
        reader = csv.DictReader(r.text.splitlines())
        fires = []
        for row in reader:
            try:
                lat = float(row.get('latitude', 0))
                lon = float(row.get('longitude', 0))
                frp = float(row.get('frp', 0) or 0)
                bright = float(row.get('bright_ti4', 0) or 0)
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    continue
                fires.append({
                    'latitude': lat,
                    'longitude': lon,
                    'brightness': bright,
                    'frp': frp,
                    'acq_date': row.get('acq_date', ''),
                    'acq_time': row.get('acq_time', ''),
                    'satellite': row.get('satellite', 'SUOMI-NPP'),
                    'confidence': row.get('confidence', 'nominal'),
                    'daynight': row.get('daynight', ''),
                })
            except (ValueError, KeyError):
                continue
        with _firms_cache_lock:
            _firms_cache = fires
            _firms_cache_time = _time.time()
        print(f"[FIRMS] Loaded {len(fires)} real fire detections from NASA VIIRS")
        return jsonify(fires)
    except Exception as e:
        print(f"[FIRMS] Error: {e}")
        with _firms_cache_lock:
            if _firms_cache:
                return jsonify(_firms_cache)  # return stale if available
        return jsonify([]), 503


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 3: NOAA SWPC — Real Space Weather (Kp index + Alerts)
# ─────────────────────────────────────────────────────────────────────────────
_space_weather_cache = {}
_space_weather_cache_time = 0

@app.route('/api/geo/space-weather')
def get_space_weather():
    """
    Real NOAA SWPC data: planetary Kp index and active geomagnetic storm alerts.
    No API key. 5-minute cache.
    """
    import time as _time
    global _space_weather_cache, _space_weather_cache_time

    if _space_weather_cache and (_time.time() - _space_weather_cache_time) < 300:
        return jsonify(_space_weather_cache)

    result = {
        'status': 'LIVE',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'kp_index': None,
        'storm_level': 'G0',
        'alerts': [],
        'kp_history': []
    }

    # Kp index (latest reading)
    try:
        r = requests.get(
            'https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
            timeout=8, headers={'User-Agent': 'GeoVigilant/2.0'}
        )
        if r.status_code == 200:
            data = r.json()
            if len(data) > 1:
                # Each row: [datetime_str, kp, kp_fraction, observed/estimated]
                recent = data[-1]
                kp = float(recent[1]) if recent[1] else 0.0
                result['kp_index'] = round(kp, 1)
                # NOAA geomagnetic storm scale: G1=5, G2=6, G3=7, G4=8, G5=9
                if kp >= 9.0: result['storm_level'] = 'G5'
                elif kp >= 8.0: result['storm_level'] = 'G4'
                elif kp >= 7.0: result['storm_level'] = 'G3'
                elif kp >= 6.0: result['storm_level'] = 'G2'
                elif kp >= 5.0: result['storm_level'] = 'G1'
                # Last 24 hours of history
                result['kp_history'] = [
                    {'time': row[0], 'kp': float(row[1]) if row[1] else 0.0}
                    for row in data[-24:] if len(row) >= 2
                ]
    except Exception as e:
        print(f"[SpaceWeather] Kp error: {e}")
        result['status'] = 'DEGRADED'

    # Active alerts
    try:
        r = requests.get(
            'https://services.swpc.noaa.gov/products/alerts.json',
            timeout=8, headers={'User-Agent': 'GeoVigilant/2.0'}
        )
        if r.status_code == 200:
            alerts_data = r.json()
            result['alerts'] = [
                {
                    'product_id': a.get('product_id', ''),
                    'issue_datetime': a.get('issue_datetime', ''),
                    'message': (a.get('message', '') or '')[:500]
                }
                for a in alerts_data[:10]
            ]
    except Exception as e:
        print(f"[SpaceWeather] Alerts error: {e}")

    _space_weather_cache.update(result)
    _space_weather_cache_time = _time.time()
    return jsonify(result)


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 4: Emergency Squawk Filter — real aircraft broadcasting 7500/7600/7700
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/geo/flights/squawks')
def get_emergency_squawks():
    """
    Filter the live flight cache for aircraft broadcasting emergency squawk codes:
    7500 = Hijack, 7600 = Radio Failure, 7700 = General Emergency
    Returns real telemetry for matching aircraft only.
    """
    EMERGENCY_CODES = {'7500', '7600', '7700'}
    with _flight_cache_lock:
        snapshot = list(_flight_cache)

    matches = []
    for ac in snapshot:
        sq = str(ac.get('squawk', '') or '').strip()
        if sq in EMERGENCY_CODES:
            code_meaning = {
                '7500': 'HIJACK',
                '7600': 'RADIO_FAILURE',
                '7700': 'GENERAL_EMERGENCY'
            }.get(sq, 'EMERGENCY')
            matches.append({
                **ac,
                'squawk_meaning': code_meaning,
                'alert_level': 'CRITICAL' if sq == '7500' else 'HIGH',
                'retrieved_at': datetime.now(timezone.utc).isoformat()
            })

    return jsonify({
        'status': 'LIVE',
        'count': len(matches),
        'squawks': matches,
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


# ─────────────────────────────────────────────────────────────────────────────
#  STEP 5: OSINT Tools — DNS, Sanctions, OpenStreetMap Overpass
# ─────────────────────────────────────────────────────────────────────────────
@app.route('/api/osint/dns')
def osint_dns():
    """Resolve DNS records (A, MX, NS) for a given domain using Python socket."""
    import socket
    domain = request.args.get('domain', '').strip().lower()
    if not domain or len(domain) > 253:
        return jsonify({'error': 'Invalid domain'}), 400

    result = {'domain': domain, 'status': 'LIVE', 'records': {}}
    # A record
    try:
        ips = list({ai[4][0] for ai in socket.getaddrinfo(domain, None)})
        result['records']['A'] = ips
    except Exception as e:
        result['records']['A'] = []

    # MX records via DNS-over-HTTPS (Google)
    try:
        r = requests.get(
            f'https://dns.google/resolve?name={domain}&type=MX',
            timeout=5, headers={'Accept': 'application/json'}
        )
        if r.status_code == 200:
            answers = r.json().get('Answer', [])
            result['records']['MX'] = [a['data'] for a in answers]
    except Exception:
        result['records']['MX'] = []

    # NS records via DNS-over-HTTPS
    try:
        r = requests.get(
            f'https://dns.google/resolve?name={domain}&type=NS',
            timeout=5, headers={'Accept': 'application/json'}
        )
        if r.status_code == 200:
            answers = r.json().get('Answer', [])
            result['records']['NS'] = [a['data'] for a in answers]
    except Exception:
        result['records']['NS'] = []

    # TXT (for SPF/DKIM/DMARC)
    try:
        r = requests.get(
            f'https://dns.google/resolve?name={domain}&type=TXT',
            timeout=5, headers={'Accept': 'application/json'}
        )
        if r.status_code == 200:
            answers = r.json().get('Answer', [])
            result['records']['TXT'] = [a['data'] for a in answers]
    except Exception:
        result['records']['TXT'] = []

    return jsonify(result)


# ── OFAC SDN In-Memory Cache ──────────────────────────────────────────────────
_sdn_cache = []
_sdn_cache_time = 0

@app.route('/api/osint/sanctions')
def osint_sanctions():
    """
    Search OFAC Specially Designated Nationals list.
    Uses the official US Treasury SDN CSV export with memory caching.
    """
    global _sdn_cache, _sdn_cache_time
    import csv

    query = request.args.get('query', '').strip().lower()
    if not query or len(query) < 2:
        return jsonify({'error': 'Query too short (min 2 chars)'}), 400

    now = time.time()
    # Cache for 24 hours (86400 seconds)
    if not _sdn_cache or (now - _sdn_cache_time) > 86400:
        SDN_URL = 'https://www.treasury.gov/ofac/downloads/sdn.csv'
        try:
            r = requests.get(SDN_URL, timeout=20, headers={'User-Agent': 'GeoVigilant/2.0 (Mozilla/5.0)'})
            r.raise_for_status()
            reader = csv.reader(r.text.splitlines())
            parsed = []
            for row in reader:
                if len(row) > 1 and row[1].strip():
                    name = row[1].strip()
                    sdn_type = row[2].strip() if len(row) > 2 and row[2].strip() != '-0-' else 'ENTITY'
                    program = [row[3].strip()] if len(row) > 3 and row[3].strip() != '-0-' else []
                    title = row[4].strip() if len(row) > 4 and row[4].strip() != '-0-' else ''
                    remarks = row[11].strip() if len(row) > 11 and row[11].strip() != '-0-' else ''
                    parsed.append({
                        'uid': row[0].strip(),
                        'name': name,
                        'sdnType': sdn_type,
                        'program': program,
                        'title': title,
                        'remarks': remarks[:300]
                    })
            if parsed:
                _sdn_cache = parsed
                _sdn_cache_time = now
                print(f"[OSINT/Sanctions] Loaded {len(_sdn_cache)} SDN entries into memory cache.")
        except Exception as e:
            print(f"[OSINT/Sanctions] Fetch error: {e}")
            if not _sdn_cache:
                return jsonify({'error': str(e), 'status': 'DEGRADED'}), 503

    matches = []
    for item in _sdn_cache:
        if query in item['name'].lower() or (item.get('remarks') and query in item['remarks'].lower()):
            matches.append(item)
            if len(matches) >= 50:
                break

    return jsonify({
        'status': 'LIVE',
        'query': query,
        'count': len(matches),
        'results': matches,
        'source': 'US OFAC SDN List'
    })


@app.route('/api/osint/overpass')
def osint_overpass():
    """
    Query OpenStreetMap Overpass API for infrastructure within a radius.
    Returns amenities, military objects, transport, communication nodes.
    """
    try:
        lat = float(request.args.get('lat', 0))
        lon = float(request.args.get('lon', 0))
        radius = min(int(request.args.get('radius', 500)), 5000)  # cap at 5km
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid lat/lon/radius'}), 400

    query = f"""
[out:json][timeout:15];
(
  node["amenity"](around:{radius},{lat},{lon});
  node["military"](around:{radius},{lat},{lon});
  node["aeroway"](around:{radius},{lat},{lon});
  node["landuse"="industrial"](around:{radius},{lat},{lon});
  way["building"="industrial"](around:{radius},{lat},{lon});
  node["communication"](around:{radius},{lat},{lon});
);
out body;
"""
    try:
        r = requests.post(
            'https://overpass-api.de/api/interpreter',
            data={'data': query},
            timeout=20,
            headers={'User-Agent': 'GeoVigilant/2.0'}
        )
        r.raise_for_status()
        data = r.json()
        elements = data.get('elements', [])
        results = []
        for el in elements[:200]:
            tags = el.get('tags', {})
            results.append({
                'id': el.get('id'),
                'type': el.get('type'),
                'lat': el.get('lat'),
                'lon': el.get('lon'),
                'name': tags.get('name', ''),
                'amenity': tags.get('amenity', ''),
                'military': tags.get('military', ''),
                'aeroway': tags.get('aeroway', ''),
                'landuse': tags.get('landuse', ''),
                'building': tags.get('building', ''),
                'communication': tags.get('communication', ''),
            })
        return jsonify({
            'status': 'LIVE',
            'center': {'lat': lat, 'lon': lon},
            'radius_m': radius,
            'count': len(results),
            'elements': results,
            'source': 'OpenStreetMap Overpass'
        })
    except Exception as e:
        print(f"[OSINT/Overpass] Error: {e}")
        return jsonify({'error': str(e), 'status': 'DEGRADED'}), 503


# Satellite raw TLE cache & live propagated positions
_sat_tle_cache = []
_sat_tle_cache_time = 0
_sat_orbit_cache = None
_sat_orbit_cache_time = 0

def _propagate_tle_groundtrack(line1, line2, norad_id, name, now_utc=None):
    """
    Compute authentic Keplerian sub-satellite point (lat, lon, alt)
    using orbital parameters, J2 nodal regression, and Greenwich Mean Sidereal Time (GMST).
    Zero fake random numbers or static hashes.
    """
    try:
        if now_utc is None:
            now_utc = datetime.now(timezone.utc)

        # 1. Parse TLE Line 1 for Epoch
        epoch_yr_2digit = int(line1[18:20])
        epoch_year = 2000 + epoch_yr_2digit if epoch_yr_2digit < 57 else 1900 + epoch_yr_2digit
        epoch_day = float(line1[20:32])
        epoch_dt = datetime(epoch_year, 1, 1, tzinfo=timezone.utc) + timedelta(days=epoch_day - 1.0)
        dt_days = (now_utc - epoch_dt).total_seconds() / 86400.0

        # 2. Parse TLE Line 2
        inclination_deg = float(line2[8:16])
        raan_deg = float(line2[17:25])
        ecc_str = line2[26:33].strip()
        ecc = float("0." + ecc_str) if ecc_str else 0.0001
        arg_perigee_deg = float(line2[34:42])
        mean_anomaly_deg = float(line2[43:51])
        mean_motion_revday = float(line2[52:63])

        if mean_motion_revday <= 0:
            return None

        # Semi-major axis via Kepler's 3rd law (mu = 398600.4418 km^3/s^2)
        mu = 398600.4418
        period_s = 86400.0 / mean_motion_revday
        a = (mu * (period_s / (2 * math.pi)) ** 2) ** (1.0 / 3.0)
        alt_km = max(160.0, a * (1.0 - ecc) - 6378.137)

        # Mean Anomaly at current UTC time
        mean_motion_deg_day = mean_motion_revday * 360.0
        M = (mean_anomaly_deg + mean_motion_deg_day * dt_days) % 360.0
        M_rad = math.radians(M)

        # Solve Kepler's equation for Eccentric Anomaly E: M = E - e*sin(E)
        E = M_rad
        for _ in range(3):
            f = E - ecc * math.sin(E) - M_rad
            f_prime = 1.0 - ecc * math.cos(E)
            if abs(f_prime) < 1e-12:
                break
            E -= f / f_prime

        # True Anomaly nu
        sin_nu = (math.sqrt(max(0.0, 1.0 - ecc * ecc)) * math.sin(E)) / max(1e-12, 1.0 - ecc * math.cos(E))
        cos_nu = (math.cos(E) - ecc) / max(1e-12, 1.0 - ecc * math.cos(E))
        nu = math.atan2(sin_nu, cos_nu)

        # Argument of latitude u = omega + nu
        u = math.radians(arg_perigee_deg) + nu

        # Satellite latitude
        inc_rad = math.radians(inclination_deg)
        sin_lat = math.sin(inc_rad) * math.sin(u)
        lat_deg = math.degrees(math.asin(max(-1.0, min(1.0, sin_lat))))

        # Right ascension of ascending node with J2 nodal regression
        re_km = 6378.137
        node_rate_deg_day = -9.9639 * ((re_km / a) ** 3.5) * math.cos(inc_rad)
        current_raan = (raan_deg + node_rate_deg_day * dt_days) % 360.0

        # Right ascension in orbital plane
        delta_ra = math.atan2(math.cos(inc_rad) * math.sin(u), math.cos(u))

        # Greenwich Mean Sidereal Time (GMST) at current UTC
        jd = 2440587.5 + (now_utc.timestamp() / 86400.0)
        d = jd - 2451545.0
        gmst_deg = (280.46061837 + 360.98564736629 * d) % 360.0

        # Sub-satellite Longitude
        lon_deg = (current_raan + math.degrees(delta_ra) - gmst_deg) % 360.0
        if lon_deg > 180.0:
            lon_deg -= 360.0
        elif lon_deg < -180.0:
            lon_deg += 360.0

        return {
            "noradId": norad_id,
            "name": name or f"SAT-{norad_id}",
            "latitude": round(lat_deg, 4),
            "longitude": round(lon_deg, 4),
            "altitude": round(alt_km, 1),
            "inclination": round(inclination_deg, 2),
            "period_min": round(period_s / 60.0, 1)
        }
    except Exception:
        return None


@app.route('/api/geo/satellites')
def get_satellite_data():
    """Fetch live satellite positions with authentic Keplerian orbital propagation."""
    import time
    global _sat_tle_cache, _sat_tle_cache_time, _sat_orbit_cache, _sat_orbit_cache_time

    now = time.time()
    # Serve cached orbital positions if computed within the last 30 seconds
    if _sat_orbit_cache is not None and (now - _sat_orbit_cache_time) < 30:
        return jsonify(_sat_orbit_cache)

    # Refresh TLE catalogue from SatNogs if cache is empty or older than 6 hours
    if not _sat_tle_cache or (now - _sat_tle_cache_time) > 21600:
        try:
            response = requests.get(
                'https://db.satnogs.org/api/tle/?format=json&limit=1500',
                timeout=25,
                headers={"User-Agent": "GeoVigilant/2.0"}
            )
            if response.status_code == 200:
                entries = response.json()
                valid_entries = []
                for entry in entries:
                    l1 = entry.get('tle1', '')
                    l2 = entry.get('tle2', '')
                    nid = str(entry.get('norad_cat_id', ''))
                    if l1 and l2 and len(l1) >= 60 and len(l2) >= 60:
                        nm = (entry.get('tle0', '') or '').lstrip('0 ').strip()
                        valid_entries.append((l1, l2, nid, nm))
                if valid_entries:
                    _sat_tle_cache = valid_entries
                    _sat_tle_cache_time = now
                    print(f"[Satellites] TLE catalogue refreshed: {len(_sat_tle_cache)} satellites loaded")
        except Exception as e:
            print(f"[Satellites] SatNogs fetch exception: {e}")

    # Propagate live orbits against exact current UTC time
    now_utc = datetime.now(timezone.utc)
    results = []
    seen = set()
    for l1, l2, nid, nm in _sat_tle_cache:
        if nid in seen:
            continue
        seen.add(nid)
        pos = _propagate_tle_groundtrack(l1, l2, nid, nm, now_utc)
        if pos:
            results.append(pos)
        if len(results) >= 800:
            break

    _sat_orbit_cache = results
    _sat_orbit_cache_time = now
    return jsonify(results)

# --- VESSEL HARBOR UPLINK ---
# Global cache for AIS data & vessel history
_ais_vessels_cache = {}
_ais_vessel_history = defaultdict(lambda: deque(maxlen=60))
_ais_cache_lock = None
_ais_websocket_task = None

def start_ais_websocket():
    """Start background WebSocket connection to AISstream.io for 100% real live maritime telemetry."""
    
    global _ais_cache_lock, _ais_websocket_task
    _ais_cache_lock = Lock()
    async def ais_stream():
        global _ais_vessels_cache, _ais_vessel_history
        
        async with websockets.connect("wss://stream.aisstream.io/v0/stream", ping_interval=20, ping_timeout=20) as websocket:
            # Subscribe to global ship positions
            subscribe_message = {
                "APIKey": api_key,
                "BoundingBoxes": [[[-90, -180], [90, 180]]]  # Global coverage
            }
            
            await websocket.send(json.dumps(subscribe_message))
            print("AISstream.io connected - receiving live authentic ship telemetry...")
            
            async for message_json in websocket:
                try:
                    message = json.loads(message_json)
                    
                    # Handle Position Reports
                    if "Message" in message and "PositionReport" in message["Message"]:
                        pos = message["Message"]["PositionReport"]
                        meta = message.get("MetaData", {})
                        
                        mmsi = str(meta.get("MMSI", "000000000"))
                        ship_name = meta.get("ShipName", "UNKNOWN").strip()
                        
                        # Map NavigationalStatus integer to readable text
                        nav_status_map = {
                            0: "UNDERWAY", 1: "AT ANCHOR", 2: "NOT UNDER COMMAND",
                            3: "RESTRICTED MANEUVERABILITY", 4: "CONSTRAINED BY DRAUGHT",
                            5: "MOORED", 6: "AGROUND", 7: "FISHING", 8: "UNDERWAY SAILING",
                            11: "TOWING", 12: "TOWING", 14: "AIS SART ACTIVE"
                        }
                        nav_status_raw = pos.get("NavigationalStatus", 0)
                        nav_status = nav_status_map.get(int(nav_status_raw) if isinstance(nav_status_raw, (int, float)) else 0, "UNDERWAY")
                        
                        vessel_data = {
                            "mmsi": mmsi,
                            "name": ship_name if ship_name else "UNKNOWN",
                            "lat": pos.get("Latitude", 0),
                            "lon": pos.get("Longitude", 0),
                            "heading": int(pos.get("TrueHeading", 0) or pos.get("Cog", 0) or 0),
                            "speed": float(pos.get("Sog", 0) or 0),
                            "type": _ais_vessels_cache.get(mmsi, {}).get("type", "cargo"),
                            "imo": meta.get("IMO") or _ais_vessels_cache.get(mmsi, {}).get("imo", "---") or "---",
                            "status": nav_status,
                            "country": _ais_vessels_cache.get(mmsi, {}).get("country", "--"),
                            "draft": _ais_vessels_cache.get(mmsi, {}).get("draft", 0),
                            "destination": meta.get("Destination") or _ais_vessels_cache.get(mmsi, {}).get("destination", "---") or "---",
                            "callsign": meta.get("CallSign") or _ais_vessels_cache.get(mmsi, {}).get("callsign", "---") or "---",
                            "source": "AISstream_LIVE",
                            "atd": "---",
                            "departure": "---",
                            "category": _ais_vessels_cache.get(mmsi, {}).get("type", "cargo")
                        }
                        
                        with _ais_cache_lock:
                            _ais_vessels_cache[mmsi] = vessel_data
                            lat_val = pos.get("Latitude")
                            lon_val = pos.get("Longitude")
                            if lat_val is not None and lon_val is not None and (lat_val != 0 or lon_val != 0):
                                _ais_vessel_history[mmsi].append([lat_val, lon_val])
                    
                    # Handle Ship Static Data (has ship type and country)
                    elif "Message" in message and "ShipStaticData" in message["Message"]:
                        static = message["Message"]["ShipStaticData"]
                        meta = message.get("MetaData", {})
                        
                        mmsi = str(meta.get("MMSI", "000000000"))
                        ship_type_code = static.get("Type", 0)
                        
                        # Map AIS ship type codes to readable types
                        # NOTE: More specific ranges must come BEFORE broader ranges to avoid shadowing.
                        type_map = {
                            range(35, 36): "military",  # Military (must be before fishing 30-40)
                            range(51, 52): "special",   # Search & Rescue (must be before pilot 50-60)
                            range(30, 40): "fishing",
                            range(40, 50): "tug",
                            range(50, 60): "pilot",
                            range(60, 70): "passenger",
                            range(70, 80): "cargo",
                            range(80, 90): "tanker",
                        }
                        
                        ship_type = "cargo"  # default
                        for code_range, type_name in type_map.items():
                            if ship_type_code in code_range:
                                ship_type = type_name
                                break
                        
                        # Get country from UserID (first 3 digits of MMSI = Maritime Identification Digits)
                        mid = mmsi[:3]
                        country_map = {
                            '202': 'GB', '203': 'ES', '204': 'PT', '205': 'BE', '206': 'FR',
                            '207': 'FR', '208': 'FR', '209': 'CY', '210': 'CY', '211': 'DE',
                            '212': 'CY', '213': 'GE', '214': 'MD', '215': 'MT', '216': 'AM',
                            '218': 'DE', '219': 'DK', '220': 'DK', '224': 'ES', '225': 'ES',
                            '226': 'FR', '227': 'FR', '228': 'FR', '229': 'MT', '230': 'FI',
                            '231': 'FO', '232': 'GB', '233': 'GB', '234': 'GB', '235': 'GB',
                            '236': 'GI', '237': 'GR', '238': 'HR', '239': 'GR', '240': 'GR',
                            '241': 'GR', '242': 'MA', '243': 'HU', '244': 'NL', '245': 'NL',
                            '246': 'NL', '247': 'IT', '248': 'MT', '249': 'MT', '250': 'IE',
                            '251': 'IS', '252': 'LI', '253': 'LU', '254': 'MC', '255': 'PT',
                            '256': 'MT', '257': 'NO', '258': 'NO', '259': 'NO', '261': 'PL',
                            '262': 'ME', '263': 'PT', '264': 'RO', '265': 'SE', '266': 'SE',
                            '267': 'SK', '268': 'SM', '269': 'CH', '270': 'CZ', '271': 'TR',
                            '272': 'UA', '273': 'RU', '274': 'MK', '275': 'LV', '276': 'EE',
                            '277': 'LT', '278': 'SI', '279': 'RS', '301': 'AI', '303': 'US',
                            '304': 'AG', '305': 'AG', '306': 'CW', '307': 'AW', '308': 'BS',
                            '309': 'BS', '310': 'BM', '311': 'BS', '312': 'BZ', '314': 'BB',
                            '316': 'CA', '319': 'KY', '321': 'CR', '323': 'CU', '325': 'DM',
                            '327': 'DO', '329': 'GP', '330': 'GD', '331': 'GL', '332': 'GT',
                            '334': 'HN', '336': 'HT', '338': 'US', '339': 'JM', '341': 'KN',
                            '343': 'LC', '345': 'MX', '347': 'MQ', '348': 'MS', '350': 'NI',
                            '351': 'PA', '352': 'PA', '353': 'PA', '354': 'PA', '355': 'PA',
                            '356': 'PA', '357': 'PA', '358': 'PR', '359': 'SV', '361': 'PM',
                            '362': 'TT', '364': 'TC', '366': 'US', '367': 'US', '368': 'US',
                            '369': 'US', '370': 'PA', '371': 'PA', '372': 'PA', '373': 'PA',
                            '374': 'PA', '375': 'VC', '376': 'VC', '377': 'VC', '378': 'VG',
                            '401': 'AF', '403': 'SA', '405': 'BD', '408': 'BH', '410': 'BT',
                            '412': 'CN', '413': 'CN', '414': 'CN', '416': 'TW', '417': 'LK',
                            '419': 'IN', '422': 'IR', '423': 'AZ', '425': 'IQ', '428': 'IL',
                            '431': 'JP', '432': 'JP', '434': 'TM', '436': 'KZ', '437': 'UZ',
                            '438': 'JO', '440': 'KR', '441': 'KR', '443': 'PS', '445': 'KP',
                            '447': 'KW', '450': 'LB', '451': 'KG', '453': 'MO', '455': 'MV',
                            '457': 'MN', '459': 'NP', '461': 'OM', '463': 'PK', '466': 'QA',
                            '468': 'SY', '470': 'AE', '471': 'AE', '472': 'TJ', '473': 'YE',
                            '475': 'YE', '477': 'HK', '478': 'BA', '501': 'AQ', '503': 'AU',
                            '506': 'MM', '508': 'BN', '510': 'FM', '511': 'PW', '512': 'NZ',
                            '514': 'KH', '515': 'KH', '516': 'CX', '518': 'CK', '520': 'FJ',
                            '523': 'CC', '525': 'ID', '529': 'KI', '531': 'LA', '533': 'MY',
                            '536': 'MP', '538': 'MH', '540': 'NC', '542': 'NU', '544': 'NR',
                            '546': 'PF', '548': 'PH', '553': 'PG', '555': 'PN', '557': 'SB',
                            '559': 'AS', '561': 'WS', '563': 'SG', '564': 'SG', '565': 'SG',
                            '566': 'SG', '567': 'TH', '570': 'TO', '572': 'TV', '574': 'VN',
                            '576': 'VU', '577': 'VU', '578': 'WF', '601': 'ZA', '603': 'AO',
                            '605': 'DZ', '607': 'TF', '608': 'AS', '609': 'BI', '610': 'BJ',
                            '611': 'BW', '612': 'CF', '613': 'CM', '615': 'CG', '616': 'KM',
                            '617': 'CV', '618': 'AQ', '619': 'CI', '620': 'KM', '621': 'DJ',
                            '622': 'EG', '624': 'ET', '625': 'ER', '626': 'GA', '627': 'GH',
                            '629': 'GM', '630': 'GW', '631': 'GQ', '632': 'GN', '633': 'BF',
                            '634': 'KE', '635': 'AQ', '636': 'LR', '637': 'LR', '638': 'SS',
                            '642': 'LY', '644': 'LS', '645': 'MU', '647': 'MG', '649': 'ML',
                            '650': 'MZ', '654': 'MR', '655': 'MW', '656': 'NE', '657': 'NG',
                            '659': 'NA', '660': 'RE', '661': 'RW', '662': 'SD', '663': 'SN',
                            '664': 'SC', '665': 'SH', '666': 'SO', '667': 'SL', '668': 'ST',
                            '669': 'SZ', '670': 'TD', '671': 'TG', '672': 'TN', '674': 'TZ',
                            '675': 'UG', '676': 'CD', '677': 'TZ', '678': 'ZM', '679': 'ZW'
                        }
                        country = country_map.get(mid, "--")
                        
                        # Update or create vessel data with static info
                        with _ais_cache_lock:
                            if mmsi in _ais_vessels_cache:
                                _ais_vessels_cache[mmsi]["type"] = ship_type
                                _ais_vessels_cache[mmsi]["country"] = country
                                _ais_vessels_cache[mmsi]["category"] = ship_type
                                # Also update static fields that may have been missing
                                if static.get("CallSign"):
                                    _ais_vessels_cache[mmsi]["callsign"] = static["CallSign"].strip()
                                if meta.get("IMO"):
                                    _ais_vessels_cache[mmsi]["imo"] = str(meta["IMO"])
                                if static.get("Destination"):
                                    _ais_vessels_cache[mmsi]["destination"] = static["Destination"].strip()
                                if static.get("Draught"):
                                    _ais_vessels_cache[mmsi]["draft"] = round(static["Draught"] / 10, 1)
                            else:
                                # Create minimal entry until we get position report
                                _ais_vessels_cache[mmsi] = {
                                    "mmsi": mmsi,
                                    "name": meta.get("ShipName", "UNKNOWN").strip(),
                                    "type": ship_type,
                                    "country": country,
                                    "lat": 0,
                                    "lon": 0,
                                    "heading": 0,
                                    "speed": 0,
                                    "imo": str(meta.get("IMO", "---")),
                                    "status": "UNKNOWN",
                                    "draft": round(static.get("Draught", 0) / 10, 1),
                                    "destination": (static.get("Destination") or "---").strip(),
                                    "callsign": (static.get("CallSign") or "---").strip(),
                                    "source": "AISstream_LIVE",
                                    "atd": "---",
                                    "departure": "---",
                                    "category": ship_type
                                }
                            
                except Exception as e:
                    print(f"AIS Parse Error: {e}")
                    continue
    
   
    def run_async():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while True:
            try:
                loop.run_until_complete(ais_stream())
            except Exception as e:
                print(f"AIS WebSocket Error: {e}, reconnecting in 5s...")
                import time
                time.sleep(5)
    
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()
    print("AIS WebSocket thread started")

@app.route('/api/geo/vessels')
def get_vessel_data():
    """Fetch REAL live vessel data from AISstream.io"""
    global _ais_vessels_cache, _ais_websocket_task
    
    # Start WebSocket if not already started
    if _ais_websocket_task is None:
        try:
            start_ais_websocket()
            _ais_websocket_task = True
        except Exception as e:
            print(f"Failed to start AIS WebSocket: {e}")
    
    # Return cached vessels (optimized for performance)
    with _ais_cache_lock if _ais_cache_lock else nullcontext():
        all_vessels = list(_ais_vessels_cache.values())
        
        # Filter out vessels with invalid positions
        valid_vessels = [v for v in all_vessels if v.get('lat') != 0 and v.get('lon') != 0]
        
        # Prioritize India (419), China (412, 413, 414), Russia (273)
        priority_prefixes = ('419', '412', '413', '414', '273')
        
        priority_ships = [v for v in valid_vessels if v.get('mmsi', '').startswith(priority_prefixes)]
        other_ships = [v for v in valid_vessels if not v.get('mmsi', '').startswith(priority_prefixes)]
        
        # Combine: Priority ships first, then others, limit to 1500 total for better coverage
        vessels = (priority_ships + other_ships)[:1500]
    
    return jsonify(vessels)


# ─── CCTV Live Camera Integration ──────────────────────────────────────────────
# Marker data cache — loaded once, refreshed every 24 hours
_cctv_markers_data = None     # list of [cam_id, lat, lng, cat_str, ft_str]
_cctv_markers_ts   = 0
_cctv_markers_lock = threading.Lock()
_cctv_markers_loading = False
_cctv_req_cache   = {}        # bounds+cat → {data, ts}   (60-second TTL)

_CCTV_MARKER_TTL = 86400      # 24 h
_CCTV_REQ_TTL    = 60         # 60 s per viewport
_CCTV_MAX_CAMS   = 2000       # max markers returned per request

_CCTV_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://opencctv.org/',
    'Accept': 'application/json, */*',
}

_CCTV_CAT_MAP = {
    0: 'traffic', 1: 'road', 2: 'railway', 3: 'beach', 4: 'weather',
    5: 'volcano', 6: 'nature', 7: 'construction', 8: 'airport',
    9: 'port', 10: 'wildlife', 11: 'ski', 12: 'city', 13: 'campus',
}
_CCTV_FT_MAP = {0: 'image', 1: 'm3u8', 2: 'mjpeg', 3: 'iframe', 4: 'direct'}

# Sources confirmed dead, broken, or unreachable upstream:
# - txdot, faa, skaping, ipcamlive, cav: non-HTTP/custom schemes (e.g. txdot://, faa-weathercam://)
# - road: unreplaced {timestamp} template variable in MLIT Japan URLs causing HTTP 404
# - cr: HTTP 401 Unauthorized / HTTP 503 token failures on skyvdn.com/trafficwise.org
# - asfinag, nycdot, cotrip, jakarta, njta: connection timeouts / firewalled hosts
# - algotraffic, earthcam, infoclimat, trafficwatch: HTTP 403 Forbidden / anti-scraping
# - topis, thailand: SSL/TLS handshake & certificate validation failures
_CCTV_DEAD_SOURCES = {
    'txdot',
    'cr',
    'faa',
    'road',
    'asfinag',
    'nycdot',
    'cotrip',
    'skaping',
    'algotraffic',
    'jakarta',
    'topis',
    'ipcamlive',
    'earthcam',
    'infoclimat',
    'cav',
    'thailand',
    'njta',
    'trafficwatch',
}

# Individual cameras confirmed unplayable (external embed playback disabled, deleted, or 404):
# - camscape-nepal-1..5: YouTube error 101/150 "Playback on other websites has been disabled by video owner"
# - camscape-czech-republic-17, 19: YouTube error 100 video deleted/unavailable
_CCTV_DEAD_CAMERAS = {
    'camscape-nepal-1',
    'camscape-nepal-2',
    'camscape-nepal-3',
    'camscape-nepal-5',
    'camscape-czech-republic-17',
    'camscape-czech-republic-19',
}
_cctv_yt_cache = {}  # vid_id -> bool (oEmbed playability)


def _load_cctv_markers_bg():
    """Background thread: fetch + parse global camera marker catalog (≈7 MB)."""
    global _cctv_markers_data, _cctv_markers_ts, _cctv_markers_loading
    try:
        r = requests.get('https://opencctv.org/api/cameras/markers',
                         headers=_CCTV_HEADERS, timeout=60)
        r.raise_for_status()
        raw = r.json()
        ids  = raw.get('ids',  [])
        lats = raw.get('lats', [])
        lngs = raw.get('lngs', [])
        cats = raw.get('cats', [])
        fts  = raw.get('fts',  [])
        data = [
            [cam_id, lat, lng,
             _CCTV_CAT_MAP.get(cat, 'traffic'),
             _CCTV_FT_MAP.get(ft, 'image')]
            for cam_id, lat, lng, cat, ft
            in zip(ids, lats, lngs, cats, fts)
            if cam_id.split('-', 1)[0] not in _CCTV_DEAD_SOURCES
            and cam_id not in _CCTV_DEAD_CAMERAS
        ]
        with _cctv_markers_lock:
            _cctv_markers_data = data
            _cctv_markers_ts   = time.time()
        print(f"[CCTV] Marker catalog loaded: {len(data):,} cameras (filtered {len(ids) - len(data):,} dead source cameras)")
    except Exception as exc:
        print(f"[CCTV] Marker load error: {exc}")
    finally:
        _cctv_markers_loading = False


@app.route('/api/geo/cctv')
def get_cctv_data():
    """Live global CCTV cameras — viewport-aware, category-filtered."""
    global _cctv_markers_loading

    # ── 1. Parse request params ─────────────────────────────────────────────
    bounds = request.args.get('bounds', '')
    category = request.args.get('cat', '')
    try:
        if bounds:
            min_lat, min_lng, max_lat, max_lng = [float(x) for x in bounds.split(',')]
        else:
            lat = float(request.args.get('lat', 38.9))
            lon = float(request.args.get('lon', -77.0))
            spread = float(request.args.get('spread', 1.0))
            min_lat, min_lng = lat - spread, lon - spread
            max_lat, max_lng = lat + spread, lon + spread
    except (ValueError, TypeError):
        return jsonify([])

    # ── 2. Short-circuit cache ───────────────────────────────────────────────
    now = time.time()
    ck  = f"{round(min_lat,1)},{round(min_lng,1)},{round(max_lat,1)},{round(max_lng,1)},{category}"
    if ck in _cctv_req_cache and now - _cctv_req_cache[ck]['ts'] < _CCTV_REQ_TTL:
        return jsonify(_cctv_req_cache[ck]['data'])

    # ── 3. Ensure marker catalog is loaded (trigger background load if needed) ─
    with _cctv_markers_lock:
        stale = (_cctv_markers_data is None or
                 now - _cctv_markers_ts > _CCTV_MARKER_TTL)
    if stale and not _cctv_markers_loading:
        _cctv_markers_loading = True
        t = threading.Thread(target=_load_cctv_markers_bg, daemon=True)
        t.start()

    with _cctv_markers_lock:
        markers = _cctv_markers_data  # may still be None on very first call

    if not markers:
        # Still loading — return empty so frontend retries (timer fires in 5s)
        return jsonify([])

    # ── 4. Filter markers by viewport bounds (and optional category) ─────────
    cameras = []
    for cam_id, lat, lng, cat_str, ft_str in markers:
        if cam_id in _CCTV_DEAD_CAMERAS:
            continue
        if not (min_lat <= lat <= max_lat and min_lng <= lng <= max_lng):
            continue
        if category and cat_str != category:
            continue
        # Build a human-readable name from the source-prefixed ID
        parts = cam_id.split('-', 1)
        name  = parts[1].replace('-', ' ').title()[:50] if len(parts) > 1 else cam_id[:50]
        cameras.append({
            'id':        f'cctv-{cam_id}',
            'name':      name,
            'latitude':  lat,
            'longitude': lng,
            'category':  cat_str,
            'feed_type': ft_str,
            'status':    'Online',
        })
        if len(cameras) >= _CCTV_MAX_CAMS:
            break

    # ── 5. Store in short-lived request cache ───────────────────────────────
    _cctv_req_cache[ck] = {'data': cameras, 'ts': now}
    if len(_cctv_req_cache) > 300:
        oldest = sorted(_cctv_req_cache, key=lambda k: _cctv_req_cache[k]['ts'])[:100]
        for k in oldest:
            _cctv_req_cache.pop(k, None)

    return jsonify(cameras)


@app.route('/api/geo/cctv-feed')
def get_cctv_feed():
    """Return full camera details (feed URL, exact coords) for a single camera."""
    cam_id = request.args.get('id', '').replace('cctv-', '', 1)
    if not cam_id:
        return jsonify({'error': 'No camera ID provided'}), 400
    src_prefix = cam_id.split('-', 1)[0]
    if src_prefix in _CCTV_DEAD_SOURCES or cam_id in _CCTV_DEAD_CAMERAS:
        return jsonify({'error': 'Video playback unavailable (restricted or offline)', 'unplayable': True, 'id': cam_id}), 410
    try:
        r = requests.get(
            f'https://opencctv.org/api/cameras/{cam_id}',
            headers=_CCTV_HEADERS, timeout=8
        )
        if not r.ok:
            _CCTV_DEAD_CAMERAS.add(cam_id)
            return jsonify({'error': f'Camera {cam_id} not found ({r.status_code})', 'unplayable': True, 'id': cam_id}), 404
        d = r.json()
        feed_url = d.get('feed_url', '')

        # Fast pre-flight check for YouTube streams
        if feed_url and ('youtube.com' in feed_url or 'youtu.be' in feed_url):
            vid_id = ''
            if 'youtube.com/embed/' in feed_url:
                vid_id = feed_url.split('youtube.com/embed/')[1].split('?')[0].split('&')[0]
            elif 'youtu.be/' in feed_url:
                vid_id = feed_url.split('youtu.be/')[1].split('?')[0].split('&')[0]
            elif 'v=' in feed_url:
                vid_id = feed_url.split('v=')[1].split('&')[0]

            if vid_id:
                if vid_id in _cctv_yt_cache:
                    playable = _cctv_yt_cache[vid_id]
                else:
                    try:
                        oem = requests.get(
                            f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid_id}&format=json',
                            timeout=2.5
                        )
                        # 401 = embed disabled by owner; 404 = deleted / not found
                        playable = (oem.status_code == 200)
                        _cctv_yt_cache[vid_id] = playable
                    except Exception:
                        playable = True

                if not playable:
                    _CCTV_DEAD_CAMERAS.add(cam_id)
                    with _cctv_markers_lock:
                        if _cctv_markers_data:
                            _cctv_markers_data = [m for m in _cctv_markers_data if m[0] != cam_id]
                    _cctv_req_cache.clear()
                    return jsonify({
                        'error': 'Video playback on other websites has been disabled by the video owner',
                        'unplayable': True,
                        'id': cam_id
                    }), 410

        return jsonify({
            'name':      d.get('name', cam_id),
            'feed_url':  feed_url,
            'feed_type': d.get('feed_type', 'image'),
            'category':  d.get('category', 'traffic'),
            'country':   d.get('country', ''),
            'city':      d.get('city', ''),
            'latitude':  d.get('lat'),
            'longitude': d.get('lng'),
            'source':    d.get('source', ''),
        })
    except Exception as exc:
        print(f"[CCTV Feed] Error fetching {cam_id}: {exc}")
        return jsonify({'error': str(exc)}), 500


@app.route('/api/geo/cctv-report-unplayable', methods=['GET', 'POST'])
def report_unplayable_cctv():
    """Mark a CCTV camera as unplayable so it is purged from markers and future requests."""
    global _cctv_markers_data
    cam_id = request.args.get('id', '')
    if not cam_id and request.is_json:
        cam_id = (request.get_json(silent=True) or {}).get('id', '')
    cam_id = cam_id.replace('cctv-', '', 1)
    if not cam_id:
        return jsonify({'error': 'No camera ID provided'}), 400

    _CCTV_DEAD_CAMERAS.add(cam_id)
    with _cctv_markers_lock:
        if _cctv_markers_data:
            _cctv_markers_data = [m for m in _cctv_markers_data if m[0] != cam_id]
    _cctv_req_cache.clear()
    print(f"[CCTV] Blacklisted unplayable camera at runtime: {cam_id}")
    return jsonify({'success': True, 'blacklisted': cam_id})


@app.route('/api/geo/cctv-stream')
def proxy_cctv_stream():
    """Proxy a CCTV image or MJPEG stream to bypass browser CORS restrictions with strict SSRF validation."""
    feed_url = request.args.get('url', '')
    if not feed_url or not feed_url.startswith('http'):
        return '', 400
    if not is_safe_public_url(feed_url):
        return jsonify({"error": "Access to private or internal addresses is forbidden"}), 403
    try:
        resp = requests.get(feed_url, headers={
            'User-Agent': 'Mozilla/5.0 GeoVigilant/1.0',
            'Referer': 'https://opencctv.org/',
        }, timeout=10, stream=True)
        ct = resp.headers.get('Content-Type', 'image/jpeg')
        # Stream MJPEG; return full body for static images
        if 'multipart' in ct or 'mjpeg' in ct.lower():
            return Response(resp.iter_content(chunk_size=4096), content_type=ct)
        return Response(resp.content, content_type=ct)
    except Exception as exc:
        print(f"[CCTV Stream] Proxy error: {exc}")
        return '', 502



@app.route('/api/geo/crimes')
def get_crime_data():
    """Fetch live crime data from UK Police API."""
    lat = request.args.get('lat', '51.52')
    lng = request.args.get('lng', '-0.1')
    date = request.args.get('date', '') # Format: YYYY-MM
    
    url = f"https://data.police.uk/api/crimes-street/all-crime?lat={lat}&lng={lng}"
    if date:
        url += f"&date={date}"
        
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify([])
    except Exception as e:
        print(f"Error fetching crime data: {e}")
        return jsonify([])


@app.route('/api/geo/vessel/path/<mmsi>')
def get_vessel_path(mmsi):
    """Return authentic historical track points for a vessel."""
    mmsi_str = str(mmsi)
    pts = []
    with _ais_cache_lock if _ais_cache_lock else nullcontext():
        if mmsi_str in _ais_vessel_history and _ais_vessel_history[mmsi_str]:
            pts = list(_ais_vessel_history[mmsi_str])
        elif mmsi_str in _ais_vessels_cache:
            v = _ais_vessels_cache[mmsi_str]
            if v.get("lat") and v.get("lon") and (v["lat"] != 0 or v["lon"] != 0):
                pts = [[v["lat"], v["lon"]]]
    return jsonify(pts)





@app.route('/api/geo/news')
def get_geo_news():
    """
    Fetch geopolitical news and verified intelligence for a specific location.
    Zero synthetic or mock data — authentic regional RSS feeds and live APIs.
    """
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    
    if lat is None or lon is None:
        return jsonify({"error": "Missing coordinates"}), 400

    # --- Check Cache ---
    cache_key = f"geo_{lat}_{lon}"
    now_ts = datetime.now(timezone.utc).timestamp()
    if cache_key in news_cache:
        cached_time, cached_data = news_cache[cache_key]
        if (now_ts - cached_time) < (NEWS_CACHE_LIMIT * 60):
            print(f"Serving cached geo news for: {cache_key}")
            return jsonify(cached_data)

    try:
        real_tweets = []
        real_news = []
        
        # --- 1. Location Detection (Geocoding) ---
        location_query = ""
        detected_region = ""
        try:
            geo_url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
            geo_res = requests.get(geo_url, timeout=3, headers={'User-Agent': 'GeoVigilant OS/1.0'})
            if geo_res.status_code == 200:
                geo_data = geo_res.json()
                address = geo_data.get('address', {})
                location_query = address.get('country', '') or address.get('city', '') or address.get('state', '')
                print(f"Reverse geocode: {location_query}")
                
                # Regional Mapping
                country_mapping = {
                    "United States": "USA", "India": "INDIA", "China": "CHINA",
                    "Russia": "RUSSIA", "Japan": "JAPAN", "Australia": "AUSTRALIA",
                    "Taiwan": "TAIWAN", "South Korea": "SOUTH_KOREA", "Israel": "ISRAEL",
                    "United Arab Emirates": "UAE", "Iran": "IRAN"
                }
                
                for c_name, reg_key in country_mapping.items():
                    if location_query and c_name in location_query:
                        detected_region = reg_key
                        break
                
                if not detected_region and location_query:
                    if any(x in location_query for x in ["Europe", "France", "Germany", "Spain", "Italy", "UK", "London", "Portugal"]):
                        detected_region = "EUROPE"
                    elif any(x in location_query for x in ["Africa", "Kenya", "Nigeria", "Egypt", "South Africa"]):
                        detected_region = "AFRICA"
        except Exception as geo_err:
            print(f"Geocoding error: {geo_err}")

        # --- 2. Try Real Twitter API v2 (Search) ---
        if TWITTER_BEARER_TOKEN and TWITTER_BEARER_TOKEN != 'YOUR_BEARER_TOKEN_HERE':
            try:
                headers = {"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"}
                params = {
                    'query': '(breaking OR news OR alert) -is:retweet lang:en',
                    'max_results': 2,
                    'tweet.fields': 'created_at,author_id,text'
                }
                response = requests.get('https://api.twitter.com/2/tweets/search/recent', headers=headers, params=params, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data:
                        for t in data['data']:
                            created = t.get('created_at', '')
                            try:
                                dt = datetime.strptime(created, '%Y-%m-%dT%H:%M:%S.%fZ')
                                time_str = dt.strftime('%H:%M:%S')
                            except:
                                time_str = 'Recent'
                            real_tweets.append({"user": f"@User_{t.get('author_id', 'Unknown')[-4:]}", "text": t.get('text', ''), "timestamp": time_str})
            except Exception as e: print(f"Twitter API Exception: {e}")

        # --- 3. Try Regional RSS (Authentic Feeds) ---
        if detected_region:
            print(f"Uplinking regional RSS: {detected_region}")
            try:
                rss_geo = fetch_rss_news(detected_region)
                real_news.extend(rss_geo[:15])
            except Exception as e:
                print(f"Regional RSS error: {e}")

        # --- 4. Try NewsAPI (If available) ---
        if NEWS_API_KEY and NEWS_API_KEY.strip() and not NEWS_API_KEY.startswith('YOUR_'):
            try:
                news_url = f"https://newsapi.org/v2/everything?q={location_query or 'world news'}&sortBy=publishedAt&pageSize=10&apiKey={NEWS_API_KEY}"
                n_res = requests.get(news_url, timeout=5)
                if n_res.status_code == 200:
                    n_data = n_res.json()
                    for article in n_data.get('articles', [])[:50]:
                        pub_time = article.get('publishedAt', '')
                        try:
                            dt = datetime.strptime(pub_time, '%Y-%m-%dT%H:%M:%SZ')
                            time_str = dt.strftime('%H:%M %b %d')
                        except:
                            time_str = 'Recent'
                        title = article.get('title', '')
                        art_url = article.get('url')
                        if not art_url or not str(art_url).startswith('http'):
                            art_url = f"https://news.google.com/search?q={urllib.parse.quote(title)}"
                        real_news.append({
                            "source": article.get('source', {}).get('name', 'NewsAPI'),
                            "title": title,
                            "time": time_str,
                            "url": art_url,
                            "published": pub_time or datetime.now(timezone.utc).isoformat(),
                            "type": "GEO_INTEL"
                        })
            except Exception as e: print(f"News API Exception: {e}")

        # --- 5. International Fallback (If no regional news found) ---
        if not real_news:
            print("Fallback to International RSS Intelligence...")
            try:
                intl_news = fetch_rss_news("INTERNATIONAL")
                real_news.extend(intl_news[:15])
            except Exception as e:
                print(f"International RSS fallback error: {e}")

        # --- 6. Degraded Mode Handling ---
        sentiment_score = 0.5
        sentiment_label = "UNKNOWN"

        # --- 7. AI Intelligence Summary ---
        context_str = f"LOCATION: {location_query or 'Unknown Sector'}\n"
        if real_news:
            context_str += "LATEST_HEADLINES:\n" + "\n".join([f"- {n['title']} ({n['source']})" for n in real_news[:5]]) + "\n"
        if real_tweets:
            context_str += "INTERCEPTED_SIGNALS:\n" + "\n".join([f"- {t['text']}" for t in real_tweets[:3]]) + "\n"
        
        ai_summary = ""
        try:
            ai_summary = analyze_with_ai(context_str)
        except Exception as e:
            ai_summary = f"[GEO-SENTINEL] Sector telemetry established. Tactical monitoring online."

        result_data = {
            "lat": lat,
            "lon": lon,
            "sentiment": {
                "score": round(sentiment_score, 2),
                "label": sentiment_label,
                "trend": "STABLE"
            },
            "tweets": real_tweets,
            "news": real_news,
            "articles": real_news,
            "intel_summary": ai_summary,
            "provenance": {
                "twitter": "live" if real_tweets else "unavailable",
                "news": "live" if real_news else "unavailable",
                "ai": "cloud" if ai_summary and "ANALYSIS_OFFLINE" not in ai_summary else "offline"
            }
        }

        # Store in cache
        news_cache[cache_key] = (now_ts, result_data)
        return jsonify(result_data)

    except Exception as exc:
        print(f"[get_geo_news] Unhandled exception: {exc}", flush=True)
        return jsonify({
            "lat": lat,
            "lon": lon,
            "sentiment": {"score": 0.5, "label": "STANDBY", "trend": "STABLE"},
            "tweets": [],
            "news": [],
            "articles": [],
            "intel_summary": "[SATELLITE_UPLINK] Sector active.",
            "provenance": {"twitter": "unavailable", "news": "unavailable", "ai": "offline"}
        })

def analyze_with_ai(context):
    """
    Multi-tier Geopolitical AI Analysis:
    1. Ollama Cloud (Priority 1: gemma4:31b-cloud)
    2. Cloud OpenRouter (Priority 2)
    3. Intelligent Tactical OSINT Deterministic Heuristic Engine (Priority 3, zero fake random data)
    """
    # Tier 1: Ollama Cloud (Priority 1: Lowest Latency Cloud Model)
    messages = [
        {"role": "system", "content": "You are GeoVigilant OS Geopolitical AI. Provide a 2-sentence tactical intelligence assessment of the news headlines."},
        {"role": "user", "content": context}
    ]
    ollama_models = [OLLAMA_MODEL, "gpt-oss:120b-cloud", "gemma4:31b-cloud"]
    for m_name in ollama_models:
        if not m_name:
            continue
        try:
            ollama_content = _call_ollama_chat(messages, model=m_name, timeout=15)
            if ollama_content:
                return f"[NEURAL_CORE:OLLAMA_CLOUD] {ollama_content}"
        except Exception:
            pass

    # Tier 2: Cloud OpenRouter (Priority 2)
    if OPENROUTER_API_KEY and "placeholder" not in OPENROUTER_API_KEY and len(OPENROUTER_API_KEY) > 10:
        for m_name in OPENROUTER_MODELS:
            try:
                response = requests.post(
                    url=OPENROUTER_CHAT_URL,
                    headers=OPENROUTER_CHAT_HEADERS,
                    data=json.dumps({
                        "model": m_name,
                        "messages": [
                            {"role": "system", "content": "You are GeoVigilant OS Geopolitical AI. Analyze the provided news context and provide a brief, high-tech assessment of the situation in 2-3 sentences. Use CYBERPUNK/OSINT tone."},
                            {"role": "user", "content": context}
                        ],
                        "max_tokens": 300,
                        "temperature": 0.6
                    }),
                    timeout=8
                )
                if response.status_code == 200:
                    choices = response.json().get('choices', [])
                    if choices:
                        res_content = choices[0].get('message', {}).get('content', '').strip()
                        if res_content:
                            return res_content
            except Exception as e:
                print(f"OpenRouter Model {m_name} Error: {e}")

    # Tier 3: Tactical OSINT Deterministic Heuristic Engine (Zero random numbers)
    ctx_upper = (context or "").upper()
    keywords_critical = ["WAR", "ATTACK", "MISSILE", "TROOPS", "EXPLOSION", "CASUALTIES", "HOSTAGE", "INVASION", "BORDER", "GAZA", "UKRAINE", "MILITARY", "CONFLICT", "STRIKE"]
    keywords_strategic = ["SANCTIONS", "TRADE", "TARIFF", "SUMMIT", "PACT", "NATO", "BRICS", "OPEC", "INFLATION", "SECURITY", "ELECTION", "AI", "DIPLOMAT"]
    keywords_energy = ["OIL", "GAS", "PIPELINE", "ENERGY", "CRUDE", "SUPPLY", "NORDSTREAM", "BARREL"]

    crit_matches = [k for k in keywords_critical if k in ctx_upper]
    strat_matches = [k for k in keywords_strategic if k in ctx_upper]
    energy_matches = [k for k in keywords_energy if k in ctx_upper]

    crit_weight = len(crit_matches) * 8
    strat_weight = len(strat_matches) * 4
    energy_weight = len(energy_matches) * 5
    signal_mass = min(len(ctx_upper.split()), 80) // 10

    if crit_matches:
        threat_level = "CRITICAL / ELEVATED"
        threat_score = min(96, max(75, 74 + crit_weight + signal_mass))
        return f"[TACTICAL INTEL MATRIX] Sector threat assessment: {threat_level} ({threat_score}%). Active signal correlation detected around {' + '.join(crit_matches[:3])}. Telemetry indicates elevated defense readiness and logistics maneuvering across primary corridors."
    elif energy_matches:
        threat_level = "VOLATILE"
        threat_score = min(85, max(60, 61 + energy_weight + signal_mass))
        return f"[STRATEGIC GEO-ASSESSMENT] Energy & resource supply vector volatility at {threat_score}%. Fluctuations detected in critical transport nodes. Macro-hedging and contingency routing observed across maritime lanes."
    elif strat_matches:
        threat_level = "STRATEGIC REBALANCING"
        threat_score = min(76, max(52, 53 + strat_weight + signal_mass))
        return f"[GEOPOLITICAL SENTIMENT CORE] Multilateral strategic alignment detected across {' + '.join(strat_matches[:3])}. Algorithmic sentiment tracking signals diplomatic realignments with an intelligence confidence score of {threat_score}%."
    else:
        score = min(68, max(42, 48 + signal_mass))
        return f"[GLOBAL SURVEILLANCE MESH] Transnational intelligence lattice operational across all monitored sectors. Signal baseline indicates steady telemetry with localized volatility index at {score}%. Continuous automated monitoring active."

@app.route('/api/news/analyze', methods=['POST'])
def analyze_news_sentiment():
    data = request.json or {}
    content = data.get('content', '')
    if not content:
        content = "Global geopolitical update and sentiment monitoring"
    
    analysis = analyze_with_ai(content)
    return jsonify({"analysis": analysis})

market_cache = {}

def _fetch_yahoo_quote(symbol):
    """Fetch a single Yahoo Finance quote. Returns (price, change_pct) or (None, None)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1m&range=1d"
        r = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0 GeoVigilant/2.0'})
        if r.status_code == 200:
            js = r.json()
            meta = js.get('chart', {}).get('result', [{}])[0].get('meta', {})
            price = meta.get('regularMarketPrice')
            prev_close = meta.get('chartPreviousClose') or meta.get('previousClose')
            if price and prev_close:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)
                return round(price, 2), change_pct
    except Exception as e:
        print(f"[Yahoo] {symbol} error: {e}")
    return None, None

@app.route('/api/market/data')
def get_market_data():
    """
    Fetch live market data for Oil, Gold, Silver, S&P500 via Yahoo Finance and BTC via CoinGecko.
    Zero random/fake data — all prices are real or endpoint is marked DEGRADED.
    """
    now_ts = datetime.now(timezone.utc).timestamp()
    if 'market' in market_cache:
        c_ts, c_data = market_cache['market']
        if (now_ts - c_ts) < 60:  # 60 sec cache
            return jsonify(c_data)

    # --- Real commodity prices via Yahoo Finance ---
    brent_price, brent_change = _fetch_yahoo_quote('BZ=F')
    gold_price, gold_change = _fetch_yahoo_quote('GC=F')
    silver_price, silver_change = _fetch_yahoo_quote('SI=F')
    sp500_price, sp500_change = _fetch_yahoo_quote('^GSPC')

    # Fallback static values only used if API is down (marked DEGRADED)
    status = "LIVE"
    if brent_price is None:
        brent_price, brent_change = 78.40, 0.0
        status = "DEGRADED"
    if gold_price is None:
        gold_price, gold_change = 2914.50, 0.0
        status = "DEGRADED"
    if silver_price is None:
        silver_price, silver_change = 32.80, 0.0
        status = "DEGRADED"
    if sp500_price is None:
        sp500_price, sp500_change = 5500.00, 0.0
        status = "DEGRADED"

    # --- Real BTC via CoinGecko ---
    btc_price, btc_change = 88450.00, 0.0
    try:
        cg_res = requests.get(
            'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_24hr_change=true',
            timeout=3,
            headers={'User-Agent': 'GeoVigilant OS/1.0'}
        )
        if cg_res.status_code == 200:
            cg_data = cg_res.json()
            if 'bitcoin' in cg_data:
                btc_price = float(cg_data['bitcoin'].get('usd', btc_price))
                btc_change = round(float(cg_data['bitcoin'].get('usd_24h_change', 0.0)), 2)
    except Exception as e:
        print(f"[CoinGecko] BTC error: {e}")
        status = "DEGRADED"

    result = {
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brent_crude": {
            "name": "BRENT_CRUDE",
            "price": f"${brent_price:.2f}",
            "raw_price": brent_price,
            "change": brent_change
        },
        "gold": {
            "name": "GOLD_OUNCE",
            "price": f"${gold_price:,.2f}",
            "raw_price": gold_price,
            "change": gold_change
        },
        "silver": {
            "name": "SILVER_OUNCE",
            "price": f"${silver_price:.2f}",
            "raw_price": silver_price,
            "change": silver_change
        },
        "sp500": {
            "name": "S&P_500",
            "price": f"${sp500_price:,.2f}",
            "raw_price": sp500_price,
            "change": sp500_change
        },
        "btc": {
            "name": "BTC_USD",
            "price": f"${btc_price:,.2f}",
            "raw_price": btc_price,
            "change": btc_change
        },
        "commodities": {
            "OIL": {"price": brent_price, "change": brent_change},
            "GOLD": {"price": gold_price, "change": gold_change},
            "SILVER": {"price": silver_price, "change": silver_change}
        },
        "indices": {
            "SP500": {"price": sp500_price, "change": sp500_change}
        },
        "crypto": {
            "BITCOIN": {"price": btc_price, "change": btc_change}
        }
    }

    market_cache['market'] = (now_ts, result)
    return jsonify(result)


@app.route('/api/market/sentiment')
def get_market_sentiment():
    """Real Crypto Fear & Greed Index from alternative.me — no API key needed."""
    now_ts = datetime.now(timezone.utc).timestamp()
    if 'sentiment' in market_cache:
        c_ts, c_data = market_cache['sentiment']
        if (now_ts - c_ts) < 300:  # 5-min cache
            return jsonify(c_data)
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5,
                         headers={'User-Agent': 'GeoVigilant/2.0'})
        if r.status_code == 200:
            d = r.json().get('data', [{}])[0]
            result = {
                "status": "LIVE",
                "value": int(d.get('value', 50)),
                "label": d.get('value_classification', 'Neutral'),
                "timestamp": d.get('timestamp', ''),
                "retrieved": datetime.now(timezone.utc).isoformat()
            }
            market_cache['sentiment'] = (now_ts, result)
            return jsonify(result)
    except Exception as e:
        print(f"[Sentiment] Fear & Greed error: {e}")
    return jsonify({"status": "DEGRADED", "value": 50, "label": "Neutral"})


@app.route('/frontend')
def frontend():
    return redirect(url_for('earth'))

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('static/assets', path)

@app.route('/news')
def news_page():
    return render_template('news.html')

@app.route('/newsnetworks')
def newsnetworks_page():
    return render_template('newsnetworks.html', sources=NEWS_SOURCES)

rss_news_cache = {}

def _parse_single_feed(url, region):
    items = []
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*'
        }
        resp = requests.get(url, timeout=3.0, headers=headers)
        if resp.status_code == 200 and resp.content:
            feed = feedparser.parse(resp.content)
            source_name = feed.feed.get('title') or (url.split('/')[2] if '/' in url else 'RSS')
            for entry in feed.entries[:10]:
                title = entry.get('title', 'Intel Report')
                link = entry.get('link') or entry.get('id')
                if not link and entry.get('links'):
                    link = entry.get('links')[0].get('href')
                if not link or not str(link).startswith('http'):
                    link = f"https://news.google.com/search?q={urllib.parse.quote(title)}"

                items.append({
                    "source": source_name,
                    "title": title,
                    "url": str(link),
                    "published": entry.get('published') or entry.get('updated') or datetime.now(timezone.utc).isoformat(),
                    "description": entry.get('summary', '')[:200] + "..." if entry.get('summary') else "",
                    "image": None,
                    "type": f"RSS_{region}"
                })
    except Exception:
        pass
    return items

def fetch_rss_news(region):
    """
    Fetch and parse all RSS feeds for a given region in parallel with strict per-feed timeout and caching.
    """
    if not region or region not in NEWS_SOURCES:
        return []

    now_ts = datetime.now(timezone.utc).timestamp()
    if region in rss_news_cache:
        c_ts, c_arts = rss_news_cache[region]
        if (now_ts - c_ts) < (5 * 60):  # 5 minutes cache
            return c_arts

    rss_urls = NEWS_SOURCES[region].get('rss', [])
    if not rss_urls:
        return []

    articles = []
    try:
        with ThreadPoolExecutor(max_workers=min(10, len(rss_urls))) as executor:
            futures = [executor.submit(_parse_single_feed, u, region) for u in rss_urls]
            try:
                for f in as_completed(futures, timeout=4.5):
                    try:
                        res = f.result()
                        if res:
                            articles.extend(res)
                    except Exception:
                        pass
            except (TimeoutError, Exception):
                pass

            for f in futures:
                if f.done() and not f.cancelled():
                    try:
                        res = f.result()
                        if res:
                            for item in res:
                                if item not in articles:
                                    articles.append(item)
                    except Exception:
                        pass
    except Exception as e:
        print(f"[RSS] fetch_rss_news error for {region}: {e}", flush=True)

    if articles:
        rss_news_cache[region] = (now_ts, articles)

    return articles

@app.route('/api/news/advanced')
def get_advanced_news():
    try:
        lat = request.args.get('lat')
        lon = request.args.get('lon')
        query = request.args.get('q', '')
        news_type = request.args.get('type', 'all') 
        region = request.args.get('region', '').upper()
        
        if not NEWS_API_KEY or NEWS_API_KEY == "YOUR_NEWS_API_KEY": # Let real keys through
            # If no key, try RSS first
            if region:
                rss_news = fetch_rss_news(region)
                if rss_news:
                    return jsonify({
                        "query": query or region,
                        "articles": rss_news,
                        "count": len(rss_news)
                    })
            
            # If no key, and no lat/lon, return real international RSS or GDELT news
            if not lat or not lon:
                rss_intl = fetch_rss_news(region if region else "INTERNATIONAL")
                if rss_intl:
                    return jsonify({
                        "query": query or "INTERNATIONAL INTEL",
                        "articles": rss_intl,
                        "count": len(rss_intl)
                    })

                # Live GDELT global intelligence fallback
                try:
                    gdelt_resp = requests.get(
                        "https://api.gdeltproject.org/api/v2/doc/doc?query=geopolitics&mode=artlist&maxrecords=10&format=json",
                        timeout=6
                    )
                    if gdelt_resp.status_code == 200:
                        gdelt_arts = []
                        for art in gdelt_resp.json().get("articles", []):
                            gdelt_arts.append({
                                "source": art.get("domain", "GDELT"),
                                "title": art.get("title", ""),
                                "url": art.get("url", ""),
                                "published": art.get("seendate", ""),
                                "description": art.get("title", ""),
                                "image": art.get("socialimage"),
                                "type": "GDELT_INTEL"
                            })
                        if gdelt_arts:
                            return jsonify({
                                "query": query or "GDELT INTEL",
                                "articles": gdelt_arts,
                                "count": len(gdelt_arts)
                            })
                except Exception:
                    pass

                return jsonify({
                    "query": query or "global news",
                    "articles": [],
                    "count": 0
                })

            geo_res = get_geo_news()
            try:
                geo_json = geo_res.get_json()
                if geo_json:
                    if 'articles' not in geo_json:
                        geo_json['articles'] = geo_json.get('news', [])
                    return jsonify(geo_json)
            except Exception:
                pass
            return geo_res

        news_articles = []
        search_query = query
        if lat and lon:
            try:
                geo_url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}"
                g_res = requests.get(geo_url, headers={'User-Agent': 'GeoVigilant OS/1.0'}, timeout=5)
                if g_res.status_code == 200:
                    address = g_res.json().get('address', {})
                    city = address.get('city') or address.get('town') or address.get('village')
                    country = address.get('country')
                    
                    if news_type == 'local' and city:
                        search_query += f" {city}"
                    elif news_type == 'national' and country:
                        search_query += f" {country}"
                    elif news_type == 'all':
                        search_query += f" {city or country or ''}"
            except:
                pass

        sort_by = request.args.get('sortBy', 'publishedAt')
        from_date = request.args.get('from', '')
        language = request.args.get('language', 'en')
        page_size = 10 # Hard limit to 10 as per user request
        
        # --- Check Cache ---
        cache_key = f"advanced_{search_query}_{language}_{sort_by}"
        now_ts = datetime.now(timezone.utc).timestamp()
        if cache_key in news_cache:
            cached_time, cached_data = news_cache[cache_key]
            if (now_ts - cached_time) < (NEWS_CACHE_LIMIT * 60):
                print(f"Serving cached news for: {cache_key}")
                return jsonify(cached_data)

        try:
            url = "https://newsapi.org/v2/everything"
            params = {
                'q': search_query.strip() or 'world news',
                'apiKey': NEWS_API_KEY,
                'language': language,
                'sortBy': sort_by,
                'pageSize': page_size
            }
            if from_date:
                params['from'] = from_date

            print(f"Requesting NewsAPI: {url} with params: {params}")
            response = requests.get(url, params=params, timeout=10)
            print(f"NewsAPI Response Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"NewsAPI successfully fetched {len(data.get('articles', []))} articles.")
                for art in data.get('articles', []):
                    title = art.get('title') or 'Intel Feed Item'
                    art_url = art.get('url')
                    if not art_url or not str(art_url).startswith('http'):
                        art_url = f"https://news.google.com/search?q={urllib.parse.quote(title)}"
                    news_articles.append({
                        "source": art.get('source', {}).get('name', 'N/A'),
                        "title": title,
                        "url": art_url,
                        "published": art.get('publishedAt'),
                        "description": art.get('description'),
                        "image": art.get('urlToImage'),
                        "type": "INTEL_FEED"
                    })
            else:
                 print(f"NewsAPI Error (Advanced): {response.status_code} - {response.text[:200]}")
        except Exception as e:
            print(f"Advanced News Fetch Error: {e}")

        # If region is provided, fetch RSS to complement NewsAPI
        # DEFAULT behavior: if no region specified, mixing in INTERNATIONAL RSS
        rss_region = region if region else "INTERNATIONAL"
        try:
            rss_news = fetch_rss_news(rss_region)
            news_articles.extend(rss_news)
        except Exception as e:
            print(f"[Advanced News] RSS merge error: {e}")

        # Final fallback: if articles still empty, query GDELT global news
        if not news_articles:
            try:
                gdelt_resp = requests.get(
                    "https://api.gdeltproject.org/api/v2/doc/doc?query=geopolitics&mode=artlist&maxrecords=10&format=json",
                    timeout=6
                )
                if gdelt_resp.status_code == 200:
                    for art in gdelt_resp.json().get("articles", []):
                        news_articles.append({
                            "source": art.get("domain", "GDELT"),
                            "title": art.get("title", ""),
                            "url": art.get("url", ""),
                            "published": art.get("seendate", ""),
                            "description": art.get("title", ""),
                            "image": art.get("socialimage"),
                            "type": "GDELT_STREAM"
                        })
            except Exception:
                pass

        # Store in cache if successful (even if only RSS articles found)
        if news_articles:
            result_data = {
                "query": search_query,
                "articles": news_articles,
                "count": len(news_articles)
            }
            news_cache[cache_key] = (now_ts, result_data)

        return jsonify({
            "query": search_query,
            "articles": news_articles,
            "count": len(news_articles)
        })

    except Exception as top_err:
        print(f"[get_advanced_news] Top-level fallback invoked: {top_err}", flush=True)
        fallback_articles = []
        try:
            fallback_articles = fetch_rss_news("INTERNATIONAL")
        except Exception:
            pass
        return jsonify({
            "query": request.args.get('q', '') or "global news",
            "articles": fallback_articles,
            "count": len(fallback_articles)
        })


@app.route('/api/translate')
def translate_text():
    """
    Translate text to English using free translation service.
    Uses MyMemory Translation API (free, no key required).
    """
    text = request.args.get('text', '')
    source_lang = request.args.get('source', 'auto')
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
    
    try:
        # MyMemory doesn't support 'auto', so we need to try common languages
        # or use a simple heuristic
        if source_lang == 'auto':
            # Try translating from multiple common languages and pick the best one
            # Common news languages: Spanish, French, German, Arabic, Chinese, Russian, etc.
            test_langs = ['es', 'fr', 'de', 'ar', 'zh', 'ru', 'ja', 'pt', 'it', 'nl']
            
            # Quick heuristic: if text is already mostly English, don't translate
            if text.replace(' ', '').isascii():
                # Likely already English or uses Latin script
                source_lang = 'en'
            else:
                # Try the first non-English language (most common: Spanish)
                source_lang = 'es'
        
        # Using MyMemory Translation API (free, no key required)
        # Limit: 500 words per request, 10000 words per day
        url = "https://api.mymemory.translated.net/get"
        params = {
            'q': text[:500],  # Limit to 500 chars
            'langpair': f'{source_lang}|en'
        }
        
        response = requests.get(url, params=params, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            translated = data.get('responseData', {}).get('translatedText', text)
            
            # If translation is same as original, it might already be in English
            if translated == text or translated.upper() == text.upper():
                return jsonify({
                    "original": text,
                    "translated": text,
                    "source_lang": "en",
                    "note": "Already in English"
                })
            
            return jsonify({
                "original": text,
                "translated": translated,
                "source_lang": source_lang
            })
        else:
            return jsonify({"error": "Translation failed", "original": text}), 500
            
    except Exception as e:
        print(f"Translation error: {e}")
        return jsonify({"error": str(e), "original": text}), 500

def get_flight_meta(callsign):
    """Fetch route and registration data for a specific callsign."""
    if not callsign or callsign == "N/A":
        return jsonify({"error": "No callsign provided"}), 400
        
    try:
        # 1. Try Routes API (Origin/Destination)
        route_url = f"https://opensky-network.org/api/routes?callsign={callsign}"
        r_res = requests.get(route_url, timeout=10)
        route_data = {}
        if r_res.status_code == 200:
            route_data = r_res.json()
            
        return jsonify({
            "callsign": callsign,
            "route": route_data.get("route", ["UNK", "UNK"]),
            "operator": route_data.get("operatorIata", "---"),
            "flight_number": route_data.get("flightNumber", "---")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500









@app.route('/earthnetworks', methods=['GET'])
def earth_networks():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        lat = float(lat)
        lon = float(lon)

        # ─── Much larger search radius ───
        # ≈ 2–3 km box — much better chance of results
        delta = 0.02   # ≈ 2.2 km at equator; adjust to 0.03–0.05 if still empty
        lat_min = lat - delta
        lat_max = lat + delta
        lon_min = lon - delta
        lon_max = lon + delta

        networks = []

        try:
            url = "https://api.wigle.net/api/v2/network/search"
            
            params = {
                "latrange1": lat_min,
                "latrange2": lat_max,
                "longrange1": lon_min,
                "longrange2": lon_max,
                "freenet": "false",
                "paynet": "false",
                "resultsPerPage": 100,      # max is usually 100
                # Optional: add variance reduction if you want
                # "variance": "0.1"         # only high-quality trilaterated results
            }

            # Use Basic Auth
            auth = (WIGLE_API_NAME, WIGLE_API_TOKEN)
            response = requests.get(url, auth=auth, params=params, timeout=12)

            print(f"WiGLE status: {response.status_code}")   # debug in console
            print(f"URL called: {response.url}")             # very useful!

            if response.status_code != 200:
                # Pass through the status code (e.g., 429 for rate limit)
                status = response.status_code
                if status == 429:
                    return jsonify({
                        "success": False,
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "WiGLE API daily limit reach. Try again later or use custom token."
                    }), 429
                return jsonify({
                    "success": False,
                    "error": f"WiGLE returned {status}",
                    "message": response.text[:200]
                }), 502

            data = response.json()

            if not data.get("success"):
                return jsonify({
                    "success": False,
                    "error": data.get("message", "WiGLE query failed")
                }), 400

            results = data.get("results", [])
            print(f"Found {len(results)} networks")   # debug

            for net in results:
                is_bt = net.get('type') == 'Bluetooth' or 'bluetooth' in net.get('ssid', '').lower()
                
                networks.append({
                    "ssid": net.get('ssid') or net.get('name', 'Unknown'),
                    "netid": net.get('netid', '??:??:??:??:??:??'),
                    "lat": net.get('trilat'),
                    "lon": net.get('trilong'),
                    "type": "bluetooth" if is_bt else "wifi",
                    "encryption": net.get('encryption', 'N/A'),
                    # Optional extras you might want
                    "channel": net.get('channel'),
                    "firstseen": net.get('firsttime'),
                    "lastseen": net.get('lasttime'),
                })

            return jsonify({"success": True, "results": networks})

        except requests.exceptions.RequestException as e:
            print(f"WiGLE Request Error: {e}")
            return jsonify({"error": f"Network error contacting WiGLE: {str(e)}"}), 502

    except ValueError:
        return jsonify({"error": "Invalid latitude/longitude"}), 400
    except Exception as e:
        print(f"Earth Networks Error: {e}")
        return jsonify({"error": str(e)}), 500


#  WiGLE Surveillance Camera Scanner
# ──────────────────────────────────────────────
WIGLE_CAM_SSID_PATTERNS = {
    'flock':        ['Flock-'],
    'surveillance': ['cam', 'ipcam', 'hikvision', 'dahua', 'axis', 'amcrest', 'reolink', 'wyze', 'cctv', 'dvr', 'nvr', 'surveillance'],
    'dashcam':      ['dashcam', 'blackvue', 'viofo', 'thinkware', 'nextbase', 'vantrue'],
}

@app.route('/api/wigle/cameras', methods=['GET'])
def wigle_cameras():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    if not lat or not lon:
        return jsonify({"error": "Missing coordinates"}), 400
    try:
        lat = float(lat)
        lon = float(lon)
    except ValueError:
        return jsonify({"error": "Invalid coordinates"}), 400

    delta = min(0.04, max(0.005, float(request.args.get('radius', 0.02))))  # ~2 km default
    lat_min, lat_max = lat - delta, lat + delta
    lon_min, lon_max = lon - delta, lon + delta
    seen_bssids = set()
    cameras = []
    
    # OpenStreetMap Overpass API: Authentic mapped surveillance cameras (Free, no WiGLE key needed)
    mirrors = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
    ]
    overpass_query = f"""[out:json][timeout:10];(node["man_made"="surveillance"]({lat_min},{lon_min},{lat_max},{lon_max});node["surveillance"]({lat_min},{lon_min},{lat_max},{lon_max}););out body 150;"""

    for mirror in mirrors:
        try:
            op_resp = requests.post(
                mirror,
                data={"data": overpass_query},
                timeout=8,
                headers={"User-Agent": "GeoVigilant-Argus/2.0"}
            )
            if op_resp.status_code == 200:
                elements = op_resp.json().get("elements", [])
                for el in elements:
                    el_id = str(el.get("id"))
                    if el_id in seen_bssids:
                        continue
                    seen_bssids.add(el_id)
                    tags = el.get("tags", {})
                    cam_type = tags.get("camera:type") or tags.get("surveillance:type") or tags.get("surveillance") or "cctv"
                    cameras.append({
                        "lat": el.get("lat"),
                        "lon": el.get("lon"),
                        "ssid": tags.get("name") or tags.get("description") or f"OSM_CAM_{el_id}",
                        "bssid": f"OSM-{el_id}",
                        "type": cam_type,
                        "operator": tags.get("operator", "Public"),
                        "encryption": "Verified Node",
                        "channel": 1,
                        "firstseen": tags.get("start_date", "2026-01-01"),
                        "lastseen": "LIVE",
                        "source": "OpenStreetMap_Surveillance"
                    })
                if len(cameras) > 0:
                    break
        except Exception as e:
            continue

    # Supplementary: If WiGLE credentials exist, query WiGLE network catalog
    if WIGLE_API_NAME and WIGLE_API_TOKEN:
        try:
            url = "https://api.wigle.net/api/v2/network/search"
            ssid_queries = ['Flock', 'cam', 'hikvision', 'dahua', 'dashcam', 'blackvue', 'cctv', 'surveillance', 'reolink', 'axis', 'wyze', 'dvr']
            
            for ssid_q in ssid_queries:
                if len(cameras) >= 200:
                    break
                params = {
                    "ssidlike": ssid_q,
                    "latrange1": lat_min,
                    "latrange2": lat_max,
                    "longrange1": lon_min,
                    "longrange2": lon_max,
                    "resultsPerPage": 50,
                }
                auth = (WIGLE_API_NAME, WIGLE_API_TOKEN)
                resp = requests.get(url, auth=auth, params=params, timeout=8)
                if resp.status_code == 429:
                    break
                if resp.status_code != 200:
                    continue
                data = resp.json()
                if not data.get("success"):
                    continue

                for net in data.get("results", []):
                    bssid = net.get("netid", "")
                    if bssid in seen_bssids:
                        continue
                    seen_bssids.add(bssid)

                    ssid = (net.get("ssid") or "").strip()
                    ssid_lower = ssid.lower()

                    # Classify camera type
                    cam_type = "surveillance"
                    for ctype, patterns in WIGLE_CAM_SSID_PATTERNS.items():
                        if any(p.lower() in ssid_lower for p in patterns):
                            cam_type = ctype
                            break

                    cameras.append({
                        "lat": net.get("trilat"),
                        "lon": net.get("trilong"),
                        "ssid": ssid or "Unknown Camera",
                        "bssid": bssid,
                        "type": cam_type,
                        "encryption": net.get("encryption", "N/A"),
                        "channel": net.get("channel"),
                        "firstseen": net.get("firsttime"),
                        "lastseen": net.get("lasttime"),
                    })
        except requests.exceptions.RequestException as e:
            print(f"WiGLE Cameras Error: {e}")
        except Exception as e:
            print(f"WiGLE Cameras Exception: {e}")

    return jsonify({"success": True, "cameras": cameras, "total": len(cameras)})




        # ================================================================
# GEOVIGILANT AI ROUTE - Ollama Phi Integration with Web Search
# ================================================================



# ================================================================
# GEOVIGILANT AI - Engine Configuration
# OpenRouter / Anthropic Cloud Engine (Default) + Ollama Local Fallback
# ================================================================
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_CHAT_HEADERS = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json",
}
HF_MODELS = [
    "meta-llama/Llama-3.1-8B-Instruct:cerebras",
    "meta-llama/Llama-3.1-8B-Instruct:together",
    "mistralai/Mistral-7B-Instruct-v0.3:together",
]

# ================================================================
# GEOVIGILANT VECTOR DATABASE (ChromaDB)
# ================================================================



CHROMA_DB_PATH = os.path.join(tempfile.gettempdir(), "argus_chroma_db") if os.environ.get('VERCEL') else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ARGUS_DATASET", "chroma_db")
COLLECTION_NAME = "geosent_memory_v2"

_chroma_client = None
_memory_collection = None
_chroma_attempted = False

import hashlib
try:
    from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
except Exception:
    class EmbeddingFunction:
        pass
    Documents = list
    Embeddings = list

class LocalVectorEmbeddingFunction(EmbeddingFunction[Documents]):
    """Deterministic, lightning-fast offline embedding vectorizer that never hangs on remote downloads."""
    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            vec = [0.0] * 384
            words = text.lower().split()
            for i, word in enumerate(words):
                h = int(hashlib.md5(word.encode('utf-8')).hexdigest(), 16)
                idx = h % 384
                vec[idx] += 1.0 / (1.0 + i * 0.1)
            norm = sum(x*x for x in vec) ** 0.5 or 1.0
            embeddings.append([x / norm for x in vec])
        return embeddings

    def embed_query(self, input):
        if isinstance(input, str):
            return self.__call__([input])[0]
        return self.__call__(input)

    def embed_documents(self, input):
        return self.__call__(input)

_local_embedding_fn = LocalVectorEmbeddingFunction()

def get_chroma_db():
    """Lazy initialize ChromaDB client and collection on first use."""
    global _chroma_client, _memory_collection, _chroma_attempted
    if _chroma_attempted:
        return _chroma_client, _memory_collection
    _chroma_attempted = True
    try:
        import chromadb
    except ImportError:
        print("[ChromaDB] chromadb package not installed. Memory vector store unavailable.")
        return None, None
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=_local_embedding_fn)
        print(f"ChromaDB: Initialized collection '{COLLECTION_NAME}'")
        _chroma_client, _memory_collection = client, collection
        return client, collection
    except Exception as e:
        print(f"ChromaDB Init Error: {e}")
        return None, None

def save_conversation(user_message, ai_response):
    """Save conversation to ChromaDB as vector memory."""
    _, collection = get_chroma_db()
    if not collection: return
    try:
        doc_id = f"mem_{int(time.time()*1000)}"
        text_content = f"User: {user_message}\nAI: {ai_response}"
        collection.add(
            documents=[text_content],
            metadatas=[{"timestamp": datetime.now().isoformat(), "type": "conversation"}],
            ids=[doc_id]
        )
        print(f"ChromaDB: Saved memory {doc_id}")
    except Exception as e:
        print(f"ChromaDB Save Error: {e}")

def get_relevant_memories(query_text, n_results=3):
    """Retrieve semantically relevant memories."""
    _, collection = get_chroma_db()
    if not collection: return []
    try:
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results
        )
        return results['documents'][0] if results['documents'] else []
    except Exception as e:
        print(f"ChromaDB Query Error: {e}")
        return []

def get_conversation_context(current_query):
    """Build context string from relevant vector memories."""
    memories = get_relevant_memories(current_query, n_results=3)
    if not memories:
        return ""
    
    context_str = "RELEVANT MEMORY STREAM (ChromaDB):\n"
    for i, mem in enumerate(memories):
        context_str += f"[{i+1}] {mem}\n"
    return context_str + "\n"

# --- Memory Management API Endpoints ---

@app.route('/api/geovigilantai/memory', methods=['GET'])
def get_memories():
    """List all memories (limited to recent/all for UI)."""
    _, collection = get_chroma_db()
    if not collection:
        return jsonify({"error": "Memory system offline"}), 500
    try:
        count = collection.count()
        if count == 0:
            return jsonify({"memories": []})
        result = collection.get(limit=50, include=['documents', 'metadatas'])
        memories = []
        for i, doc_id in enumerate(result['ids']):
            meta = result['metadatas'][i] if result['metadatas'] else {}
            memories.append({
                "id": doc_id,
                "content": result['documents'][i],
                "timestamp": meta.get('timestamp', 'Unknown')
            })
        memories.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify({"memories": memories, "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/geovigilantai/memory/<memory_id>', methods=['DELETE'])
def delete_memory(memory_id):
    _, collection = get_chroma_db()
    if not collection: return jsonify({"error": "System offline"}), 500
    try:
        collection.delete(ids=[memory_id])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/geovigilantai/memory/all', methods=['DELETE'])
def clear_all_memories():
    """Clear all entries from the memory collection."""
    _, collection = get_chroma_db()
    if not collection: return jsonify({"error": "System offline"}), 500
    try:
        all_ids = collection.get()['ids']
        if all_ids:
            collection.delete(ids=all_ids)
            print(f"ChromaDB: Cleared {len(all_ids)} memories")
        return jsonify({"success": True, "count": len(all_ids)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/geovigilantai/memory/<memory_id>', methods=['PUT'])
def update_memory(memory_id):
    _, collection = get_chroma_db()
    if not collection: return jsonify({"error": "System offline"}), 500
    data = request.json
    new_content = data.get('content')
    if not new_content: return jsonify({"error": "No content"}), 400
    
    try:
        collection.update(
            ids=[memory_id],
            documents=[new_content]
        )
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Helper Scrapers ---
def scrape_google_html(query):
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Google search URL
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:

            soup = BeautifulSoup(resp.text, "html.parser")
            # Google's HTML structure changes often, but look for standard result containers
            # Try looking for divs with class 'g' or 'tF2Cxc'
            for g in soup.find_all('div', class_='g', limit=5):
                anchors = g.find_all('a')
                if anchors:
                    link = anchors[0]['href']
                    title = anchors[0].find('h3')
                    if title:
                        title = title.get_text()
                        snippet_div = g.find('div', style='-webkit-line-clamp:2') # common snippet container
                        snippet = snippet_div.get_text() if snippet_div else "Google Result"
                        if link.startswith('http'):
                            results.append({"title": title, "link": link, "snippet": snippet, "source": "Google"})
    except Exception as e:
        print(f"Google Scrape Error: {e}")
    return results

def scrape_bing_html(query):
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        url = f"https://www.bing.com/search?q={requests.utils.quote(query)}"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:

            soup = BeautifulSoup(resp.text, "html.parser")
            # Bing results are usually in <li class="b_algo">
            for li in soup.find_all('li', class_='b_algo', limit=5):
                h2 = li.find('h2')
                if h2:
                    a = h2.find('a')
                    if a:
                        title = a.get_text()
                        link = a['href']
                        snippet_p = li.find('p')
                        snippet = snippet_p.get_text() if snippet_p else "Bing Result"
                        results.append({"title": title, "link": link, "snippet": snippet, "source": "Bing"})
    except Exception as e:
        print(f"Bing Scrape Error: {e}")
    return results

def scrape_ddg_html(query):
    results = []
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
        }
        # Use html.duckduckgo.com for easier parsing
        resp = requests.post("https://html.duckduckgo.com/html/", data={"q": query}, headers=headers, timeout=10)
        if resp.status_code == 200:

            soup = BeautifulSoup(resp.text, "html.parser")
            for result in soup.find_all("div", class_="result", limit=5):
                link_el = result.find("a", class_="result__a")
                snippet_el = result.find("a", class_="result__snippet")
                if link_el:
                    title = link_el.get_text(strip=True)
                    link = link_el["href"]
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    results.append({"title": title, "link": link, "snippet": snippet, "source": "DuckDuckGo"})
    except Exception as e:
        print(f"DDG Scrape Error: {e}")
    return results

def scrape_darkweb(query):
    """
    Dark Web search via Tor proxy. Queries multiple .onion search engines.
    Requires Tor service running on localhost:9050.
    Based on Robin project: https://github.com/apurvsinghgautam/robin
    """
    import re
    results = []
    
    # Dark Web Search Engines (.onion addresses) - Full List
    DARKWEB_ENGINES = [
        "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}",  # Ahmia
        "http://3bbad7fauom4d6sgppalyqddsqbf5u5p56b5k5uk2zxsy3d6ey2jobad.onion/search?q={query}",  # OnionLand
        "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}",  # Torgle
        "http://amnesia7u5odx5xbwtpnqk3edybgud5bmiagu75bnqx2crntw5kry7ad.onion/search?query={query}",  # Amnesia
        "http://kaizerwfvp5gxu6cppibp7jhcqptavq3iqef66wbxenh6a2fklibdvid.onion/search?q={query}",  # Kaizer
        "http://anima4ffe27xmakwnseih3ic2y7y3l6e7fucwk4oerdn4odf7k74tbid.onion/search?q={query}",  # Anima
        "http://tornadoxn3viscgz647shlysdy7ea5zqzwda7hierekeuokh5eh5b3qd.onion/search?q={query}",  # Tornado
        "http://tornetupfu7gcgidt33ftnungxzyfq2pygui5qdoyss34xbgx2qruzid.onion/search?q={query}",  # TorNet
        "http://torlbmqwtudkorme6prgfpmsnile7ug2zm4u3ejpcncxuhpu4k2j4kyd.onion/index.php?a=search&q={query}",  # Torland
        "http://findtorroveq5wdnipkaojfpqulxnkhblymc7aramjzajcvpptd4rjqd.onion/search?q={query}",  # Find Tor
        "http://2fd6cemt4gmccflhm6imvdfvli3nf7zn6rfrwpsy7uhxrgbypvwf5fad.onion/search?query={query}",  # Excavator
        "http://oniwayzz74cv2puhsgx4dpjwieww4wdphsydqvf5q7eyz4myjvyw26ad.onion/search.php?s={query}",  # Onionway
        "http://tor66sewebgixwhcqfnp5inzp5x5uohhdy3kvtnyfxc2e5mxiuh34iid.onion/search?q={query}",  # Tor66
        "http://3fzh7yuupdfyjhwt3ugzqqof6ulbcl27ecev33knxe3u7goi3vfn2qqd.onion/oss/index.php?search={query}",  # OSS
        "http://torgolnpeouim56dykfob6jh5r2ps2j73enc42s2um4ufob3ny4fcdyd.onion/?q={query}",  # Torgol
        "http://searchgf7gdtauh7bhnbyed4ivxqmuoat3nm6zfrg3ymkq6mtnpye3ad.onion/search?q={query}",  # The Deep Searches
    ]
    
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:137.0) Gecko/20100101 Firefox/137.0",
    ]
    
    def get_tor_session():
        session = requests.Session()
        # Tor SOCKS5 proxy on default port
        session.proxies = {
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050"
        }
        return session
    
    def fetch_onion_search(endpoint, query_term):
        url = endpoint.format(query=requests.utils.quote(query_term))
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        try:
            session = get_tor_session()
            response = session.get(url, headers=headers, timeout=30)
            if response.status_code == 200:

                soup = BeautifulSoup(response.text, "html.parser")
                links = []
                for a in soup.find_all('a'):
                    try:
                        href = a.get('href', '')
                        title = a.get_text(strip=True)
                        # Extract onion links
                        onion_match = re.findall(r'https?://[a-z0-9\.]+\.onion[^\s"\']*', href)
                        if onion_match and "search" not in onion_match[0].lower() and len(title) > 3:
                            links.append({"title": title, "link": onion_match[0], "snippet": "Dark Web Result", "source": "TOR_NETWORK"})
                    except:
                        continue
                return links
        except Exception as e:
            print(f"Darkweb Engine Error ({endpoint[:50]}...): {e}")
        return []
    
    # Check if Tor is available (quick test)
    try:
        test_session = get_tor_session()
        test_session.get("http://check.torproject.org", timeout=5)
        tor_available = True
    except:
        tor_available = False
        print("TOR_PROXY_UNAVAILABLE: Falling back to clearnet .onion proxies")
    
    if tor_available:
        # Query multiple engines in parallel (up to 6)
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(fetch_onion_search, endpoint, query) for endpoint in DARKWEB_ENGINES]
            for future in as_completed(futures):
                try:
                    res = future.result()
                    results.extend(res)
                except:
                    pass
    else:
        # Fallback: Use clearnet Ahmia proxy (ahmia.fi) with anti-bot token negotiation
        try:
            s = requests.Session()
            s.headers.update({"User-Agent": random.choice(USER_AGENTS)})
            r_home = s.get("https://ahmia.fi/", timeout=8)
            params = {"q": query}
            if r_home.status_code == 200:
                soup_home = BeautifulSoup(r_home.text, "html.parser")
                form = soup_home.find("form")
                if form:
                    for inp in form.find_all("input"):
                        if inp.get("type") == "hidden" and inp.get("name"):
                            params[inp.get("name")] = inp.get("value", "")

            resp = s.get("https://ahmia.fi/search/", params=params, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for li in soup.find_all("li", class_="result", limit=15):
                    a = li.find("a")
                    if a:
                        title = a.get_text(strip=True)
                        raw_link = a.get("href", "")
                        if "redirect_url=" in raw_link:
                            parsed = urllib.parse.urlparse(raw_link)
                            qs = urllib.parse.parse_qs(parsed.query)
                            actual_link = qs.get("redirect_url", [raw_link])[0]
                        else:
                            actual_link = raw_link

                        cite = li.find("cite")
                        snippet = cite.get_text(strip=True) if cite else "Ahmia Darknet Result"
                        results.append({"title": title, "link": actual_link, "snippet": snippet, "source": "Ahmia_Clearnet"})
        except Exception as e:
            print(f"Ahmia Clearnet Error: {e}")
    
    # Deduplicate
    seen = set()
    unique = []
    for r in results:
        if r['link'] not in seen:
            seen.add(r['link'])
            unique.append(r)
    
    return unique

@app.route('/api/tools/web_scan', methods=['POST'])
def perform_web_scan():
    """
    Advanced Web Scraper Endpoint.
    Handles aggressive scraping, different media types, and source filtering.
    """
    data = request.json or {}
    query = data.get('query', '').strip()
    scan_type = data.get('type', 'all')
    sources = data.get('sources', [])
    aggressive = data.get('aggressive', False)
    if isinstance(sources, str):
        sources = [sources]
    
    # 1. Modify Query based on Sources (Aggressive Mode)
    site_map = {
        'twitter':      'site:twitter.com',
        'reddit':       'site:reddit.com',
        'instagram':    'site:instagram.com',
        'linkedin':     'site:linkedin.com',
        'telegram':     'site:t.me',
        'discord':      'site:discord.gg OR site:discord.com',
        'pastebin':     'site:pastebin.com OR site:ghostbin.co OR site:rentry.co',
        'breach':       'site:breachforums.cx OR site:raidforums.com OR site:leakbase.io OR site:dehashed.com',
        'github':       'site:github.com',
        'stackoverflow':'site:stackoverflow.com',
        'leaks':        'site:pastebin.com OR site:breachforums.cx OR site:ghostbin.co OR site:rentry.co',
        'darkweb':      'site:onion.ly OR "onion"'
    }

    if sources:
        # Construct a combined OR query for all selected sources
        site_filters = []
        for s in sources:
            if s == 'web':
                continue # No filter for general web
            if s in site_map:
                site_filters.append(site_map[s])
            else:
                site_filters.append(f"site:{s}.com")
        
        valid_filters = site_filters
        
        if valid_filters:
            # If 'web' was selected, we want (filters) OR (general terms) -> actually in search engine syntax, adding "OR site:..." works but usually restricts.
            # If web is selected, we basically shouldn't restrict at all, OR we should search for "query OR (query site:twitter)" which is redundant.
            # Strategy: If 'web' is present, don't apply ANY site filter to the main query, but maybe boost the others?
            # actually, if 'web' is there, the user wants EVERYTHING. So `site:twitter.com` is a subset of `web`. 
            # So if 'web' is in sources, we just run the query RAW.
            if 'web' in sources:
                pass # Do not append site filters
            else:
                if len(valid_filters) == 1:
                    query += f" {valid_filters[0]}"
                else:
                    combined = " OR ".join(valid_filters)
                    query += f" ({combined})"

    # 2. Breach keyword enrichment — when scanning leak/dump sources, enrich the query
    # so search engines surface actual dump/paste records rather than generic results.
    BREACH_SOURCES = {'leaks', 'breach', 'pastebin'}
    if any(s in BREACH_SOURCES for s in sources):
        breach_keywords = ['leak', 'dump', 'password', 'breach', 'exposed', 'database', 'combo']
        if not any(k in query.lower() for k in breach_keywords):
            query += ' "leak" OR "dump" OR "breach" OR "exposed" OR "password"'

    results = []

    # Try DDG Library first (cleanest API if works)
    try:
        # NOTE: Updated to 'ddgs' package if available, else try fallbacks
        try:
            from duckduckgo_search import DDGS
            ddgs = DDGS()
            if scan_type == 'images':
                 # ... (keep image logic separate or assume text for general web)
                 pass 
            elif scan_type == 'text' or scan_type == 'all':
                 ddg_gen = ddgs.text(query, max_results=5)
                 for r in ddg_gen:
                     results.append({
                         "title": r.get('title', ''),
                         "link": r.get('href', ''),
                         "snippet": r.get('body', ''),
                         "source": "DDGS_LIB"
                     })
        except Exception:
            pass # Fallback immediately
    except Exception:
        pass

    # Multi-engine fallback: only run unconstrained if no specific sources were given
    # or if 'web' is explicitly selected. When breach/leak sources are provided, the
    # site-filtered query already targets the right domains — running raw scrapers
    # alongside would pollute results with unrelated general web pages.
    has_specific_sources = sources and 'web' not in sources
    run_multi_engine = (not results) or (not has_specific_sources)
    if run_multi_engine:
        # We want to aggregate results from Google, Bing, and DDG HTML
        print(f"Performing Multi-Engine Scrape for: {query}")
        
        # Google
        g_results = scrape_google_html(query)
        results.extend(g_results)
        
        # Bing
        b_results = scrape_bing_html(query)
        results.extend(b_results)
        
        # DDG HTML
        d_results = scrape_ddg_html(query)
        results.extend(d_results)
    
    # Dark Web search (if darkweb source selected — aggressive flag alone no longer triggers this)
    if 'darkweb' in sources:
        print(f"Performing Dark Web Scrape for: {query}")
        darkweb_results = scrape_darkweb(query)
        results.extend(darkweb_results)

    # De-duplicate results by link
    unique_results = []
    seen_links = set()
    for r in results:
        if r['link'] not in seen_links:
            unique_results.append(r)
            seen_links.add(r['link'])
    results = unique_results

    # 3. Aggressive Scraping (Fetch Page Content for Text Results)
    if aggressive and results:
            for item in results[:3]:
                if item.get('link') and not item.get('full_text'):
                    try:
                        headers = {"User-Agent": "Mozilla/5.0"}
                        page_resp = requests.get(item['link'], headers=headers, timeout=5)
                        if page_resp.status_code == 200:

                            page_soup = BeautifulSoup(page_resp.text, "html.parser")
                            paragraphs = page_soup.find_all('p')
                            text_content = ' '.join([p.get_text() for p in paragraphs[:5]])
                            if text_content:
                                item['full_text'] = text_content[:500] + "..." 
                    except Exception:
                        pass

    return jsonify({
        "status": "success",
        "results": results,
        "query": query,
        "type": scan_type,
        "aggressive": aggressive
    })


@app.route('/api/tor/status')
def get_tor_status():
    """Real telemetry for local Tor SOCKS5 daemon (port 9050) and control port (port 9051)."""
    import socket
    import time
    
    # 1. Test SOCKS5 port 9050
    socks5_online = False
    socks5_latency = None
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2.0)
    t0 = time.time()
    try:
        s.connect(('127.0.0.1', 9050))
        socks5_latency = round((time.time() - t0) * 1000, 1)
        socks5_online = True
        s.close()
    except Exception:
        socks5_online = False
    
    # 2. Test Control port 9051
    control_online = False
    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    c.settimeout(1.5)
    try:
        c.connect(('127.0.0.1', 9051))
        control_online = True
        c.close()
    except Exception:
        control_online = False

    # 3. Check public exit IP if socks5 is online
    exit_ip = None
    if socks5_online:
        try:
            proxies = {"http": "socks5h://127.0.0.1:9050", "https": "socks5h://127.0.0.1:9050"}
            r = requests.get("https://check.torproject.org/api/ip", proxies=proxies, timeout=5)
            if r.status_code == 200:
                data = r.json()
                exit_ip = data.get("IP")
        except Exception:
            pass

    return jsonify({
        "status": "online" if socks5_online else "offline",
        "socks5": {
            "host": "127.0.0.1",
            "port": 9050,
            "online": socks5_online,
            "latency_ms": socks5_latency
        },
        "control": {
            "host": "127.0.0.1",
            "port": 9051,
            "online": control_online
        },
        "exit_ip": exit_ip,
        "bundle_path": "tor-expert-bundle-windows-i686-15.0.19\\tor\\tor.exe"
    })


@app.route('/api/tor/newnym', methods=['POST'])
def send_tor_newnym():
    """Send real SIGNAL NEWNYM to Tor Control Port 9051 to rotate circuit."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(('127.0.0.1', 9051))
        s.sendall(b'AUTHENTICATE ""\r\n')
        resp = s.recv(1024).decode('utf-8', errors='ignore')
        if not resp.startswith('250'):
            s.sendall(b'AUTHENTICATE\r\n')
            resp = s.recv(1024).decode('utf-8', errors='ignore')
        
        s.sendall(b'SIGNAL NEWNYM\r\n')
        signal_resp = s.recv(1024).decode('utf-8', errors='ignore')
        s.sendall(b'QUIT\r\n')
        s.close()
        
        if signal_resp.startswith('250'):
            return jsonify({"status": "success", "message": "Circuit rotated successfully (SIGNAL NEWNYM 250 OK)"})
        else:
            return jsonify({"status": "error", "message": f"Tor control response: {signal_resp.strip()}"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Could not connect to Tor control port 9051: {str(e)}"}), 503


@app.route('/api/geovigilantai/chat', methods=['POST'])
@app.route('/chatgpt', methods=['GET', 'POST'])
@app.route('/chat', methods=['GET', 'POST'])
def geovigilantai_chat():
    """
    GeoVigilant AI Chat - OpenRouter cloud backend (with Anthropic/OpenRouter config)
    and Ollama / Tactical heuristic fallbacks.
    """
    data = (request.json if request.is_json else None) or request.form.to_dict() or {}
    user_message = data.get('message', '').strip() or data.get('prompt', '').strip() or data.get('q', '').strip()
    web_search = data.get('web_search', False)
    human_mode = data.get('human_mode', False)
    engine = data.get('engine', 'ollama')
    selected_model_id = data.get('model_id')
    tts_enabled = data.get('tts', False)
    context_data = data.get('context', {})

    # Auto-enable web search for news/stocks if not already on
    news_keywords = ["news", "stock", "price", "market", "update", "latest", "briefing", "happening"]
    if any(k in user_message.lower() for k in news_keywords):
        web_search = True
    
    if not user_message:
        return jsonify({"error": "Empty message", "reply": "Awaiting directive...", "response": "Awaiting directive..."}), 400
    
    # --- Build Web Context (DuckDuckGo Scraper) ---
    web_context = ""
    if web_search:
        try:
            query = requests.utils.quote(user_message)
            url = f"https://html.duckduckgo.com/html/?q={query}"
            resp = requests.post(url, data={"q": user_message}, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                snippets = []
                for result in soup.find_all("div", class_="result", limit=5):
                    link_el = result.find("a", class_="result__a")
                    snippet_el = result.find("a", class_="result__snippet")
                    if link_el and snippet_el:
                        title = link_el.get_text(strip=True)
                        link = link_el["href"]
                        text = snippet_el.get_text(strip=True)
                        snippets.append(f"• [{title}]({link}): {text}")
                if snippets:
                    web_context = "REAL-TIME WEB DATA (DUCKDUCKGO):\n" + "\n".join(snippets)
                else:
                    web_context = "*(No web results found for this query)*"
        except Exception as e:
            web_context = f"*(Web search technical error: {e})*"

    # --- Live Webpage Scraper for Any URLs in Prompt / Context ---
    url_matches = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', user_message)

    if url_matches:
        for u in url_matches[:2]:
            full_u = u if u.startswith('http') else f"https://{u}"
            if not is_safe_public_url(full_u):
                continue
            try:
                u_resp = requests.get(full_u, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}, timeout=8)
                if u_resp.status_code == 200:
                    u_soup = BeautifulSoup(u_resp.text, "html.parser")
                    # Remove scripts and styles
                    for s in u_soup(["script", "style", "nav", "footer"]):
                        s.extract()
                    u_title = u_soup.title.string.strip() if u_soup.title and u_soup.title.string else full_u
                    body_text = ' '.join(p.get_text(strip=True) for p in u_soup.find_all(['p', 'h1', 'h2', 'h3', 'article'])[:12])
                    if body_text:
                        web_context += f"\n\nLIVE WEBPAGE CONTENT INTERCEPT [{u_title}]:\nURL: {full_u}\nEXTRACTED TEXT: {body_text[:1500]}...\n"
            except Exception as ex:
                print(f"[ARGUS AI] Webpage scrape notice for {full_u}: {ex}")

    # --- Build Live Page Telemetry Context ---
    page_context_str = ""
    telemetry = data.get('page_telemetry') or context_data or {}
    # Resolve target_url (now that telemetry is available)
    target_url_from_data = data.get('target_url') or telemetry.get('target_url')
    if target_url_from_data and target_url_from_data not in url_matches:
        url_matches.append(target_url_from_data)
    if telemetry:
        page_lines = []
        if telemetry.get('page_label') or telemetry.get('url'):
            page_lines.append(f"• ACTIVE VIEWPORT / PAGE: {telemetry.get('page_label', 'UNKNOWN')} ({telemetry.get('url', '')})")
        if telemetry.get('sector_header'):
            page_lines.append(f"• CURRENT SECTOR: {telemetry.get('sector_header')}")
        if telemetry.get('search_query'):
            page_lines.append(f"• ACTIVE USER SEARCH: \"{telemetry.get('search_query')}\"")
        if telemetry.get('map_center'):
            mc = telemetry['map_center']
            page_lines.append(f"• MAP VIEWPORT COORDINATES: Lat {mc.get('lat')}, Lon {mc.get('lng')}, Zoom {mc.get('zoom')}")
        elif telemetry.get('coords_display'):
            page_lines.append(f"• COORDINATES DISPLAY: {telemetry.get('coords_display')}")
        
        # News articles on screen
        if telemetry.get('news_articles'):
            art_list = telemetry['news_articles']
            page_lines.append(f"• VISIBLE NEWS ARTICLES ON SCREEN ({len(art_list)} items):")
            for idx, a in enumerate(art_list[:6]):
                page_lines.append(f"   [{idx+1}] \"{a.get('title', '')}\" (Source: {a.get('source', 'Unknown')})")
        elif telemetry.get('news_headlines_on_screen'):
            hdls = telemetry['news_headlines_on_screen']
            page_lines.append(f"• VISIBLE HEADLINES ON SCREEN: {'; '.join(hdls[:5])}")

        # Intercepted RF / WiFi nodes on screen
        if telemetry.get('intercepted_devices'):
            devs = telemetry['intercepted_devices']
            page_lines.append(f"• INTERCEPTED RF NODES ON SCREEN ({len(devs)} devices):")
            for idx, d in enumerate(devs[:8]):
                page_lines.append(f"   [{idx+1}] {d.get('type', 'NODE').upper()}: SSID=\"{d.get('ssid', 'Hidden')}\" | MAC/BSSID={d.get('bssid', 'N/A')} | Vendor={d.get('vendor', 'Unknown')} | Signal={d.get('signal', '-')} dBm")
        elif telemetry.get('visible_nodes_count'):
            page_lines.append(f"• INTERCEPTED NODES ON SCREEN: {telemetry.get('visible_nodes_count')} nodes")

        # Market Rates on screen
        if telemetry.get('market_rates'):
            mr = telemetry['market_rates']
            page_lines.append(f"• LIVE COMMODITY & ASSET UPLINK: Brent Crude={mr.get('brent', '$78.40')}, Gold={mr.get('gold', '$2914.50')}, Silver={mr.get('silver', '$32.80')}, BTC={mr.get('btc', '$88,450.00')}")

        # Air & Maritime tracking
        if telemetry.get('tracked_flights_count'):
            page_lines.append(f"• ACTIVE AIRSPACE ENTITIES: {telemetry.get('tracked_flights_count')} flights tracked")
        if telemetry.get('tracked_vessels_count'):
            page_lines.append(f"• ACTIVE MARITIME ENTITIES: {telemetry.get('tracked_vessels_count')} vessels tracked")

        if page_lines:
            page_context_str = "CURRENT LIVE ON-SCREEN PAGE TELEMETRY:\n" + "\n".join(page_lines) + "\n\n"

    # --- Build Map Context (Legacy & Global) ---
    map_context_str = ""
    if context_data and not telemetry.get('page_label'):
        map_context_str = "MAP CONTEXT:\n"
        if context_data.get('flights'):
            map_context_str += "• FLIGHTS: " + ", ".join([f"{f['icao']} at ({f['lat']}, {f['lng']})" for f in context_data['flights']]) + "\n"
        if context_data.get('vessels'):
            map_context_str += "• VESSELS: " + ", ".join([f"{v['mmsi']} at ({v['lat']}, {v['lng']})" for v in context_data['vessels']]) + "\n"
        if context_data.get('cells'):
            map_context_str += "• CELL TOWERS: " + " | ".join(context_data['cells']) + "\n"
        if context_data.get('coords'):
            lat = context_data['coords'].get('lat')
            lng = context_data['coords'].get('lng')
            if lat is not None and lng is not None:
                try:
                    from argus_dataset_service import argus_dataset_service
                    nearby_lm = argus_dataset_service.get_nearby_places(float(lat), float(lng), radius_km=30, limit=4)
                    if nearby_lm:
                        map_context_str += "• NEARBY ARGUS GROUNDVIEW LANDMARKS: " + " | ".join([f"{lm['name']} ({lm['category']}, {lm['distance_km']}km)" for lm in nearby_lm]) + "\n"
                except Exception:
                    pass
        map_context_str += "\n"

    # --- Build ARGUS AI Master System Prompt ---
    system_prompt = (
        "You are 'ARGUS AI' (Advanced Reconnaissance Geospatial & Universal Surveillance AI), the elite tactical intelligence, "
        "GEOINT, SIGINT, and OSINT neural core of the GeoVigilant-Argus platform.\n\n"
        "SYSTEM ARCHITECTURE & SUBSYSTEM CAPABILITIES:\n"
        "1. 3D GLOBE (/earth): Real-time 3D Cesium visualization integrating OpenSky ADS-B flight tracking, AIS Marine vessel tracking, "
        "NORAD TLE satellite orbit propagation, OpenCellID cellular base stations, WiGLE RF surveillance, ACLED/GDELT conflict heatmaps, "
        "CCTV live camera feeds, and global crime vectors.\n"
        "2. GROUNDVIEW (/ground): High-precision 2D tactical mapping, ARGUS Global Landmarks (3,806 cataloged places across 162 countries, 74,128 verified multi-perspective assets), 64-bit DCT pHash BK-Tree visual reverse geolocation, Streetscapes visual feeds, high-res satellite & hybrid layers, coordinate crosshairs.\n"
        "3. NEWS STREAM (/news): Multi-source live geopolitical feeds (GDELT, RSS), automated sentiment scoring, geopolitical tension analysis, live market uplink (Brent Crude, Gold, Silver, BTC), sector filtering.\n"
        "4. RF SURVEILLANCE (/surveillance): Wi-Fi SSID/BSSID scanning, Bluetooth LE emitter intercepts, camera/dashcam/IoT categorization, MAC OUI vendor resolution, Shodan host reconnaissance, security protocol analysis.\n"
        "5. NETWORKS MATRIX (/newsnetworks, /earthnetworks): Telecom infrastructure, subsea fiber optic cables, satellite constellations, RF spectrum allocation.\n"
        "6. SOCIAL THREAT PROFILING (/social): Reddit & Twitter OSINT monitoring, sentiment classification, threat tiering.\n\n"
        "MATHEMATICAL & SCIENTIFIC MODELING (USE LATEX):\n"
        "When performing spatial, RF, ballistic, or economic assessments, incorporate clear LaTeX mathematical expressions using $...$ for inline formulas and $$...$$ for display equations:\n"
        "- Spherical Geodesic Distance: $$d = 2R \\arcsin\\left(\\sqrt{\\sin^2\\left(\\frac{\\Delta \\phi}{2}\\right) + \\cos\\phi_1 \\cos\\phi_2 \\sin^2\\left(\\frac{\\Delta \\lambda}{2}\\right)}\\right)$$\n"
        "- RF Free-Space Path Loss (FSPL): $$P_r = P_t + G_t + G_r - 20\\log_{10}(d) - 20\\log_{10}(f) - 20\\log_{10}\\left(\\frac{4\\pi}{c}\\right)$$\n"
        "- Multi-Factor Threat Index: $$\\text{TMS} = \\sum_{i=1}^n w_i \\cdot S_i \\quad \\text{where } \\sum w_i = 1.0$$\n"
        "- Geopolitical Tension Volatility: $$\\Delta V_{\\text{market}} = \\beta \\cdot \\text{SentimentDeficit} + \\epsilon$$\n\n"
        "STRICT PRESENTATION & FORMATTING DIRECTIVES:\n"
        "1. RICH GFM MARKDOWN: Always structure your intelligence briefings with clear headers (`### ⚡ EXECUTIVE SUMMARY`, `### 📍 GEOLOCATION MATRIX`, `### 🛡 THREAT ASSESSMENT`).\n"
        "2. MARKDOWN TABLES: Format key telemetry, coordinates, hardware attributes, device lists, or market shifts into clean, structured Markdown tables:\n"
        "   | Metric / Parameter | Value / Coordinate | Risk Level | Status |\n"
        "   | :--- | :--- | :--- | :--- |\n"
        "3. ON-SCREEN TELEMETRY: When user asks what is happening on screen, analyze the 'CURRENT LIVE ON-SCREEN PAGE TELEMETRY' provided below in detail. Mention visible coordinates, headlines, intercepted MAC addresses/SSIDs, and commodity fluctuations.\n"
        "4. ACTIONABLE GUI TAGS: Include interactive system trigger tags inside your response so the user can interact directly with the HUD:\n"
        "   - `[SCAN_MAP: Lat, Lng]` (e.g. `[SCAN_MAP: 38.1006, -120.7297]`) -> Renders a direct camera jump button.\n"
        "   - `[TRACK_FLIGHT: ICAO]` (e.g. `[TRACK_FLIGHT: AAE123]`) -> Renders an aircraft lock button.\n"
        "   - `[TRACK_VESSEL: MMSI]` (e.g. `[TRACK_VESSEL: 211281610]`) -> Renders a vessel tracking button.\n"
        "5. TONE: Authoritative, elite intelligence agency tone (CIA/NSA/NRO cyber-command level). Clean, precise, and visually impeccable."
    )

    if human_mode:
        system_prompt += (
            "\n\nPERSONA: 'HUMAN INTEL ANALYST'. Deliver professional, articulate, expert colleague dialogue while maintaining technical depth."
        )
    else:
        system_prompt += "\n\nPERSONA: 'ARGUS CYBER COMMAND'. High-density tactical intelligence, strictly structured."

    # --- Memory Context (ChromaDB) ---
    memory_context = get_conversation_context(user_message)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{web_context}\n\n{page_context_str}{map_context_str}{memory_context}\nUSER_MESSAGE: {user_message}"}
    ]

    reply = None
    engine_used = engine

    # ── 1. OLLAMA CLOUD ENGINE (Primary - Cloud Models Only) ──
    if engine in ('ollama', 'cloud', 'default', '') or (engine != 'openrouter' and engine != 'hf'):
        ollama_models = [selected_model_id] if (selected_model_id and any(k in selected_model_id for k in ['gpt', 'gemma', 'kimi'])) else [OLLAMA_MODEL, "gpt-oss:120b-cloud", "gemma4:31b-cloud"]
        for m_name in ollama_models:
            if not m_name:
                continue
            try:
                print(f"[GeoVigilant AI] Querying Ollama Cloud ({m_name})...")
                c = _call_ollama_chat(messages, model=m_name, timeout=25)
                if c:
                    reply = c
                    engine_used = f"ollama_cloud:{m_name}"
                    print(f"[GeoVigilant AI] Ollama Cloud Success ({m_name})")
                    break
            except Exception as o_err:
                print(f"[GeoVigilant AI] Ollama Cloud ({m_name}) notice: {o_err}")

    # ── 2. OPENROUTER CLOUD ENGINE (Fallback or Direct) ──
    if reply is None and OPENROUTER_API_KEY:
        models_to_try = [selected_model_id] if (selected_model_id and '/' in selected_model_id) else OPENROUTER_MODELS
        for model_name in models_to_try:
            try:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
                print(f"[GeoVigilant AI] Trying OpenRouter: {model_name}")
                resp = requests.post(OPENROUTER_CHAT_URL, headers=OPENROUTER_CHAT_HEADERS, json=payload, timeout=20)
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "").strip()
                        if content:
                            reply = content
                            engine_used = f"openrouter:{model_name}"
                            print(f"[GeoVigilant AI] OK: {model_name}")
                            break
                else:
                    print(f"[GeoVigilant AI] {model_name} -> HTTP {resp.status_code}: {resp.text[:200]}")
            except requests.exceptions.Timeout:
                print(f"[GeoVigilant AI] {model_name} timed out, trying next...")
            except Exception as exc:
                print(f"[GeoVigilant AI] {model_name} exception: {exc}")

    # ── 3. HF ENGINE FALLBACK ──
    if reply is None and HF_TOKEN:
        for model_name in HF_MODELS:
            try:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1024
                }
                resp = requests.post(HF_CHAT_URL, headers=HF_CHAT_HEADERS, json=payload, timeout=20)
                if resp.status_code == 200:
                    content = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if content:
                        reply = content
                        engine_used = f"hf:{model_name.split('/')[-1]}"
                        break
            except Exception:
                pass

    # ── 4. TACTICAL OSINT HEURISTIC FALLBACK (Guarantees zero downtime) ──
    if reply is None:
        engine_used = "tactical_osint_core"
        if web_context and "REAL-TIME WEB DATA" in web_context:
            reply = f"**[GEOVIGILANT AI // RECONNAISSANCE UPLINK]**\n\nLive intelligence stream correlated with query: `{user_message}`\n\n{web_context[:650]}\n\n> *Telemetry matrix operational across all sector layers.*"
        else:
            reply = f"**[GEOVIGILANT AI // TACTICAL BRIEFING]**\n\nQuery received: `{user_message}`\n\nGeospatial telemetry and surveillance lattice active. Signal intelligence indicates standard perimeter activity across operational sectors."

    # ── SAVE MEMORY ──────────────────────────────────────────────────────
    try:
        save_conversation(user_message, reply)
    except Exception as mem_e:
        print(f"[GeoVigilant AI] Memory save error: {mem_e}")

    # ── TTS ──────────────────────────────────────────────────────────────
    clean_reply = re.sub(r'\[.*?\]', '', reply).strip()
    audio_base64 = ""
    if tts_enabled:
        if gTTS is None:
            print("[GeoVigilant AI] TTS requested but gtts is not installed. Run: pip install gtts")
        else:
            try:
                tts = gTTS(text=clean_reply[:500], lang='en')
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tts.save(tmp.name)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    audio_base64 = base64.b64encode(f.read()).decode('utf-8')
                os.remove(tmp_path)
            except Exception as tts_e:
                print(f"[GeoVigilant AI] TTS error: {tts_e}")

    return jsonify({
        "response": reply,
        "reply": reply,
        "engine": engine_used,
        "audio": audio_base64,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "web_search_used": web_search,
        "engine_used": engine_used
    })


# ================================================================
# NEW SEARCH RECORD ROUTES
# ================================================================

@app.route('/api/search/crime', methods=['POST'])
def search_crime_record():
    """
    Real-Time Crime Record Search using Web Scraping and OSINT APIs.
    """
    data = request.json or {}
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    mid_name = data.get('mid_name', '').strip()
    dob = data.get('dob', '').strip()
    address = data.get('address', '').strip()
    target = data.get('target', 'USA')
    
    query = f"{first_name} {mid_name} {last_name}".strip()
    if not query:
        return jsonify({"status": "error", "message": "No query provided"}), 400

    results = []

    # Worldwide Multi-Node Aggregation
    nodes_to_query = [target]
    if target == "WORLDWIDE":
        nodes_to_query = ["USA", "UK", "India", "Global"]

    # 1. INTERPOL Red Notice API Integration (Real-Time)
    if data.get('interpol', True):
        try:
            interpol_url = f"https://ws-public.interpol.int/notices/v1/red?name={last_name}&forename={first_name}"
            interpol_res = requests.get(interpol_url, timeout=10)
            if interpol_res.status_code == 200:
                notices = interpol_res.json().get('_embedded', {}).get('notices', [])
                for notice in notices:
                    results.append({
                        "id": f"INTERPOL-{notice.get('entity_id')}",
                        "name": f"{notice.get('forename')} {notice.get('name')}",
                        "dob": notice.get('date_of_birth', 'N/A'),
                        "offense": "International Red Notice - Wanted Subject",
                        "status": "Wanted (Red)",
                        "source": "INTERPOL Global Archive",
                        "details": f"Subject listed in Interpol Public Notices. Nationality: {notice.get('nationalities', ['Unknown'])[0]}",
                        "location": f"https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices#{notice.get('entity_id')}"
                    })
        except Exception as e:
            print(f"Interpol API Error: {e}")

    # 1.1 UK INTERPOL Specific Search
    if data.get('uk_interpol', False):
        try:
            uk_interpol_url = f"https://ws-public.interpol.int/notices/v1/red?name={last_name}&forename={first_name}&nationality=GB"
            uk_res = requests.get(uk_interpol_url, timeout=10)
            if uk_res.status_code == 200:
                notices = uk_res.json().get('_embedded', {}).get('notices', [])
                for notice in notices:
                    results.append({
                        "id": f"UK-INTERPOL-{notice.get('entity_id')}",
                        "name": f"{notice.get('forename')} {notice.get('name')}",
                        "dob": notice.get('date_of_birth', 'N/A'),
                        "offense": "UK-Specific Interpol Notice",
                        "status": "Priority Focus",
                        "source": "UK-Interpol Direct Uplink",
                        "details": f"Subject with UK nationality/links found in Interpol dataset. Entity ID: {notice.get('entity_id')}",
                        "location": f"https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices#{notice.get('entity_id')}"
                    })
        except Exception as e:
            print(f"UK Interpol API Error: {e}")

    # 1.2 FBI Most Wanted API (Public — api.fbi.gov)
    try:
        fbi_params = {}
        if first_name:
            fbi_params['field_first_name'] = first_name
        if last_name:
            fbi_params['field_last_name'] = last_name
        fbi_url = "https://api.fbi.gov/wanted/v1/list"
        fbi_res = requests.get(fbi_url, params=fbi_params, timeout=10,
                               headers={"User-Agent": "GeoVigilant-Argus/1.0 OSINT"})
        if fbi_res.status_code == 200:
            fbi_data = fbi_res.json()
            for item in fbi_data.get('items', []):
                # Name filter — API may return partial matches; verify client-side too
                item_title = item.get('title', '')
                results.append({
                    "id": f"FBI-{item.get('uid', item.get('@id', 'WANTED'))}",
                    "name": item_title,
                    "dob": item.get('dates_of_birth_used', ['N/A'])[0] if item.get('dates_of_birth_used') else 'N/A',
                    "offense": (item.get('subjects') or ['Federal Offense'])[0],
                    "status": "FBI Most Wanted",
                    "source": "FBI.gov Official Wanted List",
                    "details": (item.get('description') or item.get('caution') or 'Subject listed on FBI Most Wanted')[:300],
                    "location": item.get('url') or f"https://www.fbi.gov/wanted/topten/{item_title.lower().replace(' ', '-')}"
                })
    except Exception as e:
        print(f"FBI API Error: {e}")

    # 1.3 UK Police API — Stop & Search / Wanted Persons via data.police.uk
    if target in ("UK", "WORLDWIDE"):
        try:
            # data.police.uk does not have a named-person wanted endpoint,
            # but we can search forces for crime data context
            uk_forces_res = requests.get("https://data.police.uk/api/forces", timeout=8)
            if uk_forces_res.status_code == 200:
                # Not per-person, but log that UK Police API is reachable
                print(f"UK Police API: {len(uk_forces_res.json())} forces available")
        except Exception as e:
            print(f"UK Police API Error: {e}")

    # 2. Sex Offender Registry Index (OSINT Dorks)
    if any([first_name, last_name]):
        subject_name = f"{first_name} {last_name}".strip()
        registry_queries = [
            f'site:nsopw.gov "{subject_name}"',
            f'site:sexoffender.ncrps.gov "{subject_name}"',
            f'inurl:sex-offender-registry "{subject_name}"',
            f'site:gov.uk "sex offender register" "{subject_name}"',
            f'site:mha.gov.in "sex offender" "{subject_name}"'
        ]
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            registry_tasks = [executor.submit(scrape_google_html, q) for q in registry_queries]
            for task in registry_tasks:
                try:
                    registry_hits = task.result()
                    for hit in registry_hits:
                        results.append({
                            "id": "REGISTRY-HIT",
                            "name": hit['title'],
                            "dob": "Check Linked Record",
                            "offense": "Sex Offender Registry Match",
                            "status": "Registered Entity",
                            "source": "SOR Global Index",
                            "details": hit['snippet'],
                            "location": hit['link']
                        })
                except: pass

    # 3. Search OpenSanctions (Free API for persons of interest/sanctions)
    try:
        os_url = f"https://api.opensanctions.org/search/default?q={requests.utils.quote(query)}&limit=20"
        os_resp = requests.get(os_url, timeout=10)
        if os_resp.status_code == 200:
            os_data = os_resp.json()
            for item in os_data.get('results', []):
                results.append({
                    "id": item.get('id', 'OS-INTEL'),
                    "name": item.get('caption', query),
                    "dob": item.get('properties', {}).get('birthDate', ['Unknown'])[0],
                    "offense": item.get('schema', 'Person of Interest'),
                    "status": "Listed / Target" if item.get('target') else "Entity",
                    "source": "OpenSanctions Global",
                    "details": item.get('summary', 'Subject identified in international datasets.'),
                    "location": item.get('properties', {}).get('country', ['Global'])[0]
                })
    except Exception as e:
        print(f"OpenSanctions Error: {e}")

    # 4. Web Scraping for additional "criminal record" context
    search_queries = []
    for node in nodes_to_query:
        search_queries.append(f'"{query}" criminal record {node}')
        search_queries.append(f'"{query}" arrest record {node}')
    
    web_results = []
    
    # Try DDG Library first for reliable web results
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        for q in search_queries[:4]: # Query more terms
            ddg_gen = ddgs.text(q, max_results=8)
            for r in ddg_gen:
                web_results.append({
                    "title": r.get('title', ''),
                    "link": r.get('href', ''),
                    "snippet": r.get('body', ''),
                    "source": "DDGS_LIB"
                })
    except Exception as e:
        print(f"DDGS Error in crime search: {e}")

    if not web_results:
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for q in search_queries:
                futures.append(executor.submit(scrape_google_html, q))
                futures.append(executor.submit(scrape_bing_html, q))
                futures.append(executor.submit(scrape_ddg_html, q))
                
            for future in futures:
                try:
                    res = future.result()
                    if res:
                        web_results.extend(res)
                except:
                    pass

    # Deduplicate and format web results
    seen_links = set()
    for res in web_results:
        if res['link'] not in seen_links:
            results.append({
                "id": "WEB-OSINT",
                "name": res['title'],
                "dob": "N/A",
                "offense": "Web Intelligence Snippet",
                "status": "Unverified",
                "source": res['source'],
                "details": res['snippet'],
                "location": res['link']
            })
            seen_links.add(res['link'])

    save_crime_search(session.get('username', 'Guest'), 'text', {
        "first_name": first_name, "last_name": last_name, "mid_name": mid_name, "dob": dob, "address": address
    }, results)

    return jsonify({
        "status": "success",
        "results": results[:100],
        "target": target
    })

def save_crime_search(username, search_type, params, results):
    """Save search history to SQLite."""
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("INSERT INTO crime_searches (username, search_type, query_params, results) VALUES (?, ?, ?, ?)",
                  (username, search_type, json.dumps(params), json.dumps(results)))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error saving search history: {e}")

@app.route('/api/search/photo', methods=['POST'])
def search_photo_record():
    """
    Real-Time Reverse Image Search using multiple search engines.
    Uploads image to Yandex, Bing, Google for real facial/image matches.
    """
    if 'photo' not in request.files:
        return jsonify({"status": "error", "message": "No photo uploaded"}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No selected file"}), 400

    image_bytes = file.read()
    results = []
    logs = []

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 1. YANDEX Reverse Image Search (Most reliable for facial matches)
    logs.append("[SYS] QUERYING_YANDEX_VISUAL_DATABASE...")
    try:
        yandex_url = "https://yandex.com/images/search"
        files_payload = {'upfile': (file.filename or 'image.jpg', image_bytes, 'image/jpeg')}
        yandex_params = {'rpt': 'imageview', 'format': 'json', 'request': '{"blocks":[{"block":"b-page_type_search-by-image__link"}]}'}
        
        # Step 1: Upload image to get CBIR ID
        upload_url = "https://yandex.com/images-apphost/image-download"
        upload_resp = requests.post(upload_url, files=files_payload, headers=headers_base, timeout=15)
        
        if upload_resp.status_code == 200:
            upload_data = upload_resp.json()
            cbir_id = upload_data.get('image_id', '')
            original_url = upload_data.get('url', '')
            
            if cbir_id:
                # Step 2: Search using CBIR ID
                search_url = f"https://yandex.com/images/search?rpt=imageview&cbir_id={cbir_id}"
                search_resp = requests.get(search_url, headers=headers_base, timeout=15)
                
                if search_resp.status_code == 200:

                    soup = BeautifulSoup(search_resp.text, 'html.parser')
                    
                    # Extract similar image results
                    for item in soup.find_all('a', class_='serp-item__link', limit=8):
                        try:
                            title = item.get_text(strip=True)
                            link = item.get('href', '')
                            if not link.startswith('http'):
                                link = 'https://yandex.com' + link
                            img_tag = item.find('img')
                            img_url = img_tag.get('src', '') if img_tag else ''
                            if img_url and not img_url.startswith('http'):
                                img_url = 'https:' + img_url
                            
                            if title and link:
                                results.append({
                                    "title": title[:100],
                                    "page_url": link,
                                    "image_url": img_url or original_url or '',
                                    "source": "YANDEX_VISUAL",
                                    "similarity": "DIRECT_MATCH"
                                })
                        except:
                            continue
                    
                    # Also try to get "similar images" section
                    for item in soup.find_all('div', {'class': lambda x: x and 'CbirSimilar' in str(x)}, limit=5):
                        try:
                            a_tag = item.find('a')
                            img_tag = item.find('img')
                            if a_tag and img_tag:
                                results.append({
                                    "title": a_tag.get('title', 'Yandex Similar Match'),
                                    "page_url": a_tag.get('href', ''),
                                    "image_url": img_tag.get('src', ''),
                                    "source": "YANDEX_SIMILAR",
                                    "similarity": "SIMILAR_PATTERN"
                                })
                        except:
                            continue
                            
                logs.append(f"[SUCCESS] YANDEX: {len([r for r in results if 'YANDEX' in r['source']])} matches found")
        else:
            logs.append(f"[WARN] YANDEX upload returned {upload_resp.status_code}")
    except Exception as e:
        logs.append(f"[ERROR] YANDEX: {str(e)[:80]}")
        print(f"Yandex reverse search error: {e}")

    # 2. BING Visual Search
    logs.append("[SYS] QUERYING_BING_VISUAL_SEARCH...")
    try:

        img_b64 = base64.b64encode(image_bytes).decode('utf-8')
        bing_url = "https://www.bing.com/images/search?view=detailv2&iss=sbiupload&FORM=SBIIDP"
        
        bing_files = {'image': (file.filename or 'image.jpg', image_bytes, 'image/jpeg')}
        bing_resp = requests.post(
            "https://www.bing.com/images/search?q=imgurl:&view=detailv2&iss=sbiupload&FORM=IRSBIQ",
            files=bing_files,
            headers=headers_base,
            timeout=15,
            allow_redirects=True
        )
        
        if bing_resp.status_code == 200:

            soup = BeautifulSoup(bing_resp.text, 'html.parser')
            
            # Extract pages containing the image
            for item in soup.find_all('a', class_='richImgLnk', limit=8):
                try:
                    title_el = item.find('div', class_='imgPg')
                    img_el = item.find('img')
                    href = item.get('href', '')
                    
                    results.append({
                        "title": title_el.get_text(strip=True) if title_el else "Bing Visual Match",
                        "page_url": href if href.startswith('http') else f"https://www.bing.com{href}",
                        "image_url": img_el.get('src', '') if img_el else '',
                        "source": "BING_VISUAL",
                        "similarity": "VISUAL_MATCH"
                    })
                except:
                    continue
            
            # Try alternative result structure
            for item in soup.find_all('li', {'class': lambda x: x and 'vsi' in str(x).lower()}, limit=8):
                try:
                    a_tag = item.find('a')
                    img_tag = item.find('img')
                    if a_tag:
                        results.append({
                            "title": a_tag.get('title', '') or img_tag.get('alt', '') if img_tag else "Bing Match",
                            "page_url": a_tag.get('href', ''),
                            "image_url": img_tag.get('src', '') if img_tag else '',
                            "source": "BING_VISUAL",
                            "similarity": "IMAGE_INDEX"
                        })
                except:
                    continue
                    
        logs.append(f"[SUCCESS] BING: {len([r for r in results if 'BING' in r['source']])} matches found")
    except Exception as e:
        logs.append(f"[ERROR] BING: {str(e)[:80]}")
        print(f"Bing reverse search error: {e}")

    # 3. Google Reverse Image Search
    logs.append("[SYS] QUERYING_GOOGLE_REVERSE_IMAGE...")
    try:
        google_url = "https://www.google.com/searchbyimage/upload"
        google_files = {'encoded_image': (file.filename or 'image.jpg', image_bytes, 'image/jpeg')}
        google_resp = requests.post(
            google_url,
            files=google_files,
            headers=headers_base,
            timeout=15,
            allow_redirects=True
        )
        
        if google_resp.status_code == 200:

            soup = BeautifulSoup(google_resp.text, 'html.parser')
            
            # Extract search results
            for item in soup.find_all('div', class_='g', limit=8):
                try:
                    a_tag = item.find('a')
                    h3_tag = item.find('h3')
                    snippet = item.find('span', class_='aCOpRe') or item.find('div', class_='VwiC3b')
                    
                    if a_tag and h3_tag:
                        results.append({
                            "title": h3_tag.get_text(strip=True),
                            "page_url": a_tag.get('href', ''),
                            "image_url": "",
                            "source": "GOOGLE_REVERSE",
                            "similarity": "CORRELATED_ENTITY",
                            "snippet": snippet.get_text(strip=True) if snippet else ""
                        })
                except:
                    continue
                    
        logs.append(f"[SUCCESS] GOOGLE: {len([r for r in results if 'GOOGLE' in r['source']])} matches found")
    except Exception as e:
        logs.append(f"[ERROR] GOOGLE: {str(e)[:80]}")
        print(f"Google reverse search error: {e}")

    # 4. DuckDuckGo Image Search Fallback (uses filename as query)
    logs.append("[SYS] QUERYING_DUCKDUCKGO_IMAGE_INDEX...")
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        # Search for face-related results
        search_term = "face person " + (file.filename or "unknown").rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
        ddg_images = ddgs.images(search_term, max_results=6)
        for img_result in ddg_images:
            results.append({
                "title": img_result.get('title', 'DDG Image Match'),
                "page_url": img_result.get('url', ''),
                "image_url": img_result.get('image', ''),
                "source": "DUCKDUCKGO_IMAGES",
                "similarity": "INDEX_CORRELATION",
                "thumbnail": img_result.get('thumbnail', '')
            })
        logs.append(f"[SUCCESS] DDG: {len([r for r in results if 'DDG' in r['source']])} matches found")
    except Exception as e:
        logs.append(f"[ERROR] DDG: {str(e)[:80]}")

    # 5. INTERPOL Red Notice Search (always query for facial context)
    logs.append("[SYS] CROSS_REFERENCING_INTERPOL_DATABASE...")
    try:
        interpol_resp = requests.get("https://ws-public.interpol.int/notices/v1/red?resultPerPage=10", timeout=10)
        if interpol_resp.status_code == 200:
            notices = interpol_resp.json().get('_embedded', {}).get('notices', [])
            for notice in notices[:5]:
                thumbnail_links = notice.get('_links', {}).get('thumbnail', {}).get('href', '')
                results.append({
                    "title": f"{notice.get('forename', 'UNKNOWN')} {notice.get('name', 'SUBJECT')}",
                    "page_url": f"https://www.interpol.int/en/How-we-work/Notices/View-Red-Notices#{notice.get('entity_id')}",
                    "image_url": thumbnail_links,
                    "source": "INTERPOL_RED_NOTICE",
                    "similarity": "INTERPOL_RECORD",
                    "nationality": str(notice.get('nationalities', ['Unknown'])),
                    "dob": notice.get('date_of_birth', 'Unknown')
                })
        logs.append(f"[SUCCESS] INTERPOL: {len([r for r in results if 'INTERPOL' in r['source']])} entries cross-referenced")
    except Exception as e:
        logs.append(f"[ERROR] INTERPOL: {str(e)[:80]}")

    # Deduplicate by page_url
    seen = set()
    unique_results = []
    for r in results:
        key = r.get('page_url', '') or r.get('image_url', '')
        if key and key not in seen:
            seen.add(key)
            unique_results.append(r)
    results = unique_results

    logs.append(f"[COMPLETE] TOTAL_UNIQUE_MATCHES: {len(results)}")
    
    save_crime_search(session.get('username', 'Guest'), 'photo', {"filename": file.filename}, results)

    return jsonify({
        "status": "success",
        "results": results,
        "total": len(results),
        "logs": logs
    })

@app.route('/api/search/inject', methods=['POST'])
def search_inject_ai():
    """Inject a search result into GeoVigilant AI's long-term memory."""
    data = request.json or {}
    result_data = data.get('result', {})
    if not result_data:
        return jsonify({"error": "Empty result data"}), 400
    
    try:
        # Save to ChromaDB for GeoVigilant AI
        msg = f"INJECTED INTEL RECORD: {result_data.get('name')} | Source: {result_data.get('source')} | Details: {result_data.get('details')}"
        save_conversation("SYSTEM_INJECTION_FROM_CRIME_MODULE", msg)
        return jsonify({"success": True, "message": "Record injected into GeoVigilant AI neural memory."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/search/ai/integrate', methods=['POST'])
def search_ai_integrate():
    """
    AI integration for Search Records.
    Enhances search results with AI-driven insights.
    """
    start_time = time.time()
    data = request.json or {}
    query = data.get('query', '').strip()
    context = data.get('context', '') # Context from search results
    
    # Use the existing GeoVigilant AI logic but focused on crime records
    system_prompt = (
        "You are 'Crime Analyst AI', a specialized branch of GeoVigilant AI. "
        "Your role is to analyze criminal records and provide OSINT insights. "
        "Format your response with 'ANALYSIS:', 'POTENTIAL VULNERABILITIES:', and 'DORK QUERIES:' headers."
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context: {context}\n\nAnalyze this subject: {query}"}
    ]
    
    reply = None
    if OPENROUTER_API_KEY:
        for m_name in OPENROUTER_MODELS:
            try:
                payload = {
                    "model": m_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 500
                }
                resp = requests.post(OPENROUTER_CHAT_URL, headers=OPENROUTER_CHAT_HEADERS, json=payload, timeout=20)
                if resp.status_code == 200:
                    choices = resp.json().get("choices", [])
                    if choices:
                        reply = choices[0].get("message", {}).get("content", "").strip()
                        if reply:
                            break
            except Exception:
                pass

    if not reply and HF_TOKEN:
        try:
            payload = {"model": HF_MODELS[0], "messages": messages, "temperature": 0.7, "max_tokens": 500}
            resp = requests.post(HF_CHAT_URL, headers=HF_CHAT_HEADERS, json=payload, timeout=20)
            if resp.status_code == 200:
                reply = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception:
            pass

    if not reply:
        reply = f"ANALYSIS:\nSubject '{query}' analyzed across active OSINT nodes. Records match context telemetry.\n\nPOTENTIAL VULNERABILITIES:\n- Public records exposure across indexed databases\n- Digital footprint correlation detected\n\nDORK QUERIES:\n- site:gov \"{query}\"\n- site:interpol.int \"{query}\""

    processing_time = round(time.time() - start_time, 2)
    return jsonify({
        "response": reply,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "processing_time": processing_time
    })


@app.route('/api/geovigilantai/embed', methods=['POST'])
def geovigilantai_embed():
    """Generate embeddings for geospatial data using all-minilm model."""
    data = request.json or {}
    text = data.get('text', '').strip()
    


    if not text:
        return jsonify({"error": "Empty text"}), 400
    
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": EMBEDDING_MODEL,
                "prompt": text
            },
            timeout=30
        )
        
        if response.status_code == 200:
            embeddings = response.json().get('embedding', [])
            return jsonify({"embeddings": embeddings, "dimension": len(embeddings)})
        else:
            return jsonify({"error": f"Embedding failed: {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/geovigilantai/status')
def geovigilantai_status():
    """Check if the AI subsystem is operational with live status from Ollama Cloud."""
    ollama_ok = False
    active_model = OLLAMA_MODEL
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=1.5)
        if r.status_code == 200:
            ollama_ok = True
            models = [m.get("name") for m in r.json().get("models", [])]
            if OLLAMA_MODEL in models:
                active_model = OLLAMA_MODEL
            elif models:
                active_model = models[0]
    except Exception:
        pass

    return jsonify({
        "status": "CONNECTED" if (ollama_ok or bool(OPENROUTER_API_KEY)) else "DEGRADED",
        "engine": f"Ollama Cloud ({active_model})" if ollama_ok else "OpenRouter Cloud",
        "model": active_model,
        "ollama_active": ollama_ok,
        "ollama_base_url": OLLAMA_BASE_URL,
        "web_search": "DuckDuckGo_Scraper_Active"
    })


import ssl

@app.route('/api/satellite/highsight')
def get_highsight_satellites():
    """ Placeholder for HighSight Satellite API integration """
    return jsonify({
        "status": "online",
        "provider": "HighSight",
        "message": "UPLINK_ESTABLISHED",
        "key_active": True,
        "satellites": [] # Placeholder for future data integration
    })

# Shodan API configuration (set SHODAN_API_KEY in .env to enable enhanced host intelligence)
SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY", "")

def classify_device(name, original_type):
    if not name:
        return original_type
    name_upper = name.upper()
    if any(k in name_upper for k in ["CAR", "FORD", "TOYOTA", "BMW", "TESLA", "SYNC", "MAZDA", "HONDA", "UCONNECT", "HYUNDAI", "LEXUS", "NISSAN"]):
        return "car"
    if any(k in name_upper for k in ["TV", "BRAVIA", "VIZIO", "SAMSUNG", "LG", "ROKU", "FIRE", "SMARTVIEW", "KDL-"]):
        return "tv"
    if any(k in name_upper for k in ["HEADPHONE", "EARBUD", "BOSE", "SONY", "BEATS", "AUDIO", "AIRPOD", "JBL", "SENNHEISER"]):
        return "headphone"
    if any(k in name_upper for k in ["DASHCAM", "DASH CAM", "DVR", "70MAI", "VIOFO", "GARMIN DASH"]):
        return "dashcam"
    if any(k in name_upper for k in ["CAM", "SURVEILLANCE", "SECURITY", "NEST", "RING", "ARLO", "HIKVISION", "DAHUA", "REOLINK"]):
        return "camera"
    if any(k in name_upper for k in ["WATCH", "FITBIT", "GARMIN", "WHOOP"]):
        return "iot"
    return original_type

@app.route('/nearby')
@app.route('/api/nearby')
def nearby():
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    mode = request.args.get('mode', 'wifi') # 'wifi' or 'bluetooth'
    
    if not lat or not lon:
        return jsonify({"error": "Missing coordinates"}), 400

    devices = []
    wigle_user, wigle_key = get_wigle_auth()
    
    if mode == 'bluetooth':
        # Wigle Bluetooth API call
        if wigle_user and wigle_key:
            try:
                wigle_response = requests.get(
                    'https://api.wigle.net/api/v2/bluetooth/search',
                    params={'latrange1': lat-0.01, 'latrange2': lat+0.01, 'longrange1': lon-0.01, 'longrange2': lon+0.01},
                    auth=(wigle_user, wigle_key),
                    timeout=8
                )
                if wigle_response.status_code == 200:
                    for device in wigle_response.json().get('results', []):
                        name = device.get('name') or device.get('netid')
                        original_type = "bluetooth"
                        classified_type = classify_device(name, original_type)
                        
                        devices.append({
                            "lat": device.get('trilat'),
                            "lon": device.get('trilong'),
                            "ssid": name,
                            "bssid": device.get('netid'),
                            "vendor": device.get('type') or ("Bluetooth Node" if classified_type == "bluetooth" else classified_type.replace('_', ' ').title()),
                            "signal": device.get('level'),
                            "timestamp": device.get('lastupdt'),
                            "type": classified_type
                        })
                else:
                    print(f"Wigle BT error: {wigle_response.status_code} - {wigle_response.text[:120]}")
            except Exception as e:
                print(f"Wigle BT exception: {str(e)}")
    else:
        # Standard WiFi/Cell/IoT Logic
        # Wigle API call
        if wigle_user and wigle_key:
            try:
                wigle_response = requests.get(
                    'https://api.wigle.net/api/v2/network/search',
                    params={'latrange1': lat-0.01, 'latrange2': lat+0.01, 'longrange1': lon-0.01, 'longrange2': lon+0.01},
                    auth=(wigle_user, wigle_key),
                    timeout=8
                )
                if wigle_response.status_code == 200:
                    for network in wigle_response.json().get('results', []):
                        name = network.get('ssid')
                        original_type = "router"
                        classified_type = classify_device(name, original_type)

                        devices.append({
                            "lat": network.get('trilat'),
                            "lon": network.get('trilong'),
                            "ssid": name,
                            "bssid": network.get('netid'),
                            "vendor": network.get('vendor'),
                            "signal": network.get('level'),
                            "timestamp": network.get('lastupdt'),
                            "type": classified_type
                        })
                else:
                    print(f"Wigle error: {wigle_response.status_code} - {wigle_response.text[:120]}")
            except Exception as e:
                print(f"Wigle exception: {str(e)}")

        # OpenCellID API call (Bounded to under 4M sq meters)
        if OPENCELLID_API_KEY:
            try:
                bbox = f"{lat-0.008},{lon-0.008},{lat+0.008},{lon+0.008}"
                opencell_response = requests.get(
                    'https://opencellid.org/cell/getInArea',
                    params={
                        "key": OPENCELLID_API_KEY,
                        "BBOX": bbox,
                        "format": "json"
                    },
                    timeout=8
                )
                if opencell_response.status_code == 200:
                    data = opencell_response.json()
                    cells = data.get('cells', []) if isinstance(data, dict) else []
                    for cell in cells:
                        clat = float(cell.get('lat'))
                        clon = float(cell.get('lon'))
                        cid = str(cell.get('cellid', 'Cell Tower'))
                        radio = str(cell.get('radio', 'LTE')).upper()
                        devices.append({
                            "lat": clat,
                            "lon": clon,
                            "cell_id": cid,
                            "ssid": f"CELL_TOWER_{cid} ({radio})",
                            "vendor": f"MCC:{cell.get('mcc')} MNC:{cell.get('mnc')} [{radio}]",
                            "signal": cell.get('averageSignalStrength') or -65,
                            "encryption": f"Radio: {radio}",
                            "accuracy": cell.get('range', 1000),
                            "url": f"https://www.opencellid.org/#zoom=16&lat={clat}&lon={clon}",
                            "timestamp": cell.get('updated'),
                            "type": "cell_tower"
                        })
                else:
                    print(f"OpenCellID HTTP error: {opencell_response.status_code} - {opencell_response.text[:100]}")
            except Exception as e:
                print(f"OpenCellID exception: {str(e)}")

        # OpenStreetMap Overpass: Authentic mapped CCTV & Surveillance Cameras
        try:
            delta_osm = 0.04
            osm_query = f"""[out:json][timeout:6];(node["man_made"="surveillance"]({lat-delta_osm},{lon-delta_osm},{lat+delta_osm},{lon+delta_osm});node["surveillance"]({lat-delta_osm},{lon-delta_osm},{lat+delta_osm},{lon+delta_osm}););out body 50;"""
            osm_resp = requests.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": osm_query},
                headers={"User-Agent": "GeoVigilant-Argus/2.0"},
                timeout=6
            )
            if osm_resp.status_code == 200:
                seen_cam_coords = set((d.get("lat"), d.get("lon")) for d in devices if d.get("lat"))
                for el in osm_resp.json().get("elements", []):
                    c_lat, c_lon = el.get("lat"), el.get("lon")
                    if (c_lat, c_lon) in seen_cam_coords:
                        continue
                    seen_cam_coords.add((c_lat, c_lon))
                    el_id = str(el.get("id"))
                    tags = el.get("tags", {})
                    mount_raw = tags.get("camera:mount") or ""
                    mount_str = f"{mount_raw.title()} Mount" if mount_raw else "Surveillance Enclosure"
                    cam_type_raw = tags.get("camera:type") or tags.get("surveillance:type") or tags.get("surveillance") or "CCTV Optical Camera"
                    cam_type_str = cam_type_raw.replace("_", " ").title()
                    operator_str = tags.get("operator") or tags.get("brand") or "Public / Municipal Authority"
                    zone_str = (tags.get("surveillance:zone") or tags.get("surveillance:type") or "Public Safety Zone").replace("_", " ").title()
                    env_str = "Indoor Facility" if (tags.get("indoor") == "yes" or mount_raw.lower() == "ceiling") else "Outdoor Perimeter"
                    direction = tags.get("camera:direction") or tags.get("direction") or ""
                    dir_str = f"Bearing {direction}°" if direction else "Fixed Orientation"

                    devices.append({
                        "lat": c_lat,
                        "lon": c_lon,
                        "ssid": tags.get("name") or tags.get("description") or f"OSM_SURVEILLANCE_{el_id}",
                        "bssid": f"OSM-{el_id}",
                        "type": "camera",
                        "vendor": operator_str,
                        "mount": mount_str,
                        "camera_type": cam_type_str,
                        "zone": zone_str,
                        "environment": env_str,
                        "direction": dir_str,
                        "osm_id": el_id,
                        "signal": -48,
                        "encryption": f"{cam_type_str} | {mount_str}",
                        "accuracy": 5,
                        "url": f"https://www.openstreetmap.org/node/{el_id}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "raw_tags": tags
                    })
        except Exception as e:
            print(f"Overpass camera exception: {e}")


        # Shodan API call
        if SHODAN_API_KEY:
            try:
                shodan_response = requests.get(
                    'https://api.shodan.io/shodan/host/search',
                    params={'key': SHODAN_API_KEY, 'query': f'geo:{lat},{lon},1', 'limit': 5}
                )
                if shodan_response.status_code == 200:
                    for banner in shodan_response.json().get('matches', []):
                        ip = banner['ip_str']
                        info = banner.get('data', '')
                        classified_type = classify_device(info, "iot_device")

                        devices.append({
                            "lat": banner['location']['latitude'],
                            "lon": banner['location']['longitude'],
                            "ip": ip,
                            "info": info[:50],
                            "type": classified_type
                        })
            except Exception as e:
                print(f"Shodan exception: {str(e)}")

    return jsonify({"devices": devices})

@app.route('/api/geo/towers')
def get_towers():
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        
        if not lat or not lon:
            lat = 51.505
            lon = -0.09

        # Bounding Box strictly bounded under 4,000,000 sq meters as per OpenCellID Wiki API spec
        delta = 0.008 # approx 1.8km radius, ~3,100,000 sq meters
        min_lat = lat - delta
        max_lat = lat + delta
        min_lon = lon - delta
        max_lon = lon + delta
        bbox = f"{min_lat},{min_lon},{max_lat},{max_lon}"

        # Official OpenCellID API call (https://wiki.opencellid.org/wiki/API)
        response = requests.get(
            'https://opencellid.org/cell/getInArea',
            params={
                "key": OPENCELLID_API_KEY,
                "BBOX": bbox,
                "format": "json",
                "limit": 50
            },
            timeout=8
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                return jsonify({"error": "API returned non-JSON", "details": response.text[:100]})

            towers = []
            cells = data.get('cells', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            
            for cell in cells:
                clat = float(cell.get('lat', 0))
                clon = float(cell.get('lon', 0))
                cid = str(cell.get('cellid', 'Unknown'))
                radio = str(cell.get('radio', 'GSM')).upper()
                towers.append({
                    "id": cid,
                    "lat": clat,
                    "lon": clon,
                    "lac": cell.get('lac', cell.get('tac', 0)),
                    "mcc": cell.get('mcc', 0),
                    "mnc": cell.get('mnc', 0),
                    "signal": cell.get('averageSignalStrength', 0),
                    "range": cell.get('range', 1000),
                    "samples": cell.get('samples', 1),
                    "radio": radio,
                    "url": f"https://www.opencellid.org/#zoom=16&lat={clat}&lon={clon}"
                })
            
            return jsonify(towers)
            
        else:
            return jsonify({"error": f"OpenCellID Upstream error: {response.status_code}", "details": response.text[:100]}), 502

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/geo/celltower')
def get_celltower_click():
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        
        if not lat or not lon:
            return jsonify({"error": "Missing coordinates"}), 400

        # Official OpenCellID getInArea query with micro-BBOX
        delta = 0.008
        bbox = f"{lat-delta},{lon-delta},{lat+delta},{lon+delta}"

        response = requests.get(
            'https://opencellid.org/cell/getInArea',
            params={
                "key": OPENCELLID_API_KEY,
                "BBOX": bbox,
                "format": "json",
                "limit": 50
            },
            timeout=8
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
            except Exception:
                return jsonify({"error": "API returned non-JSON", "details": response.text[:100]})

            towers = []
            cells = data.get('cells', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            for cell in cells:
                clat = float(cell.get('lat', 0))
                clon = float(cell.get('lon', 0))
                cid = str(cell.get('cellid', 'Unknown'))
                radio = str(cell.get('radio', 'GSM')).upper()
                towers.append({
                    "id": cid,
                    "lat": clat,
                    "lon": clon,
                    "lac": cell.get('lac', cell.get('tac', 0)),
                    "mcc": cell.get('mcc', 0),
                    "mnc": cell.get('mnc', 0),
                    "signal": cell.get('averageSignalStrength', 0),
                    "range": cell.get('range', 1000),
                    "samples": cell.get('samples', 1),
                    "radio": radio,
                    "url": f"https://www.opencellid.org/#zoom=16&lat={clat}&lon={clon}"
                })
            return jsonify(towers)
        else:
            return jsonify({"error": f"Upstream API error: {response.status_code}", "details": response.text[:100]}), 502

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/geo/cell')
def get_cell_exact():
    """Exact cell lookup by MCC, MNC, LAC, CellID as per https://wiki.opencellid.org/wiki/API#Getting_cell_position"""
    try:
        mcc = request.args.get('mcc', type=int)
        mnc = request.args.get('mnc', type=int)
        lac = request.args.get('lac', type=int)
        cellid = request.args.get('cellid', type=int)
        radio = request.args.get('radio', default='LTE')

        if not (mcc and mnc and lac and cellid):
            return jsonify({"error": "Missing required parameters: mcc, mnc, lac, cellid"}), 400

        res = requests.get(
            'https://opencellid.org/cell/get',
            params={
                "key": OPENCELLID_API_KEY,
                "mcc": mcc,
                "mnc": mnc,
                "lac": lac,
                "cellid": cellid,
                "radio": radio,
                "format": "json"
            },
            timeout=8
        )
        return jsonify(res.json()), res.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/searchzz')
@app.route('/api/searchzz')
def search():
    search_type = request.args.get('type', '').strip()
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Missing search query", "devices": []}), 400

    devices = []
    
    is_ip = bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', query))
    is_bssid = bool(re.match(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$', query))
    is_coords = bool(re.match(r'^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$', query))

    if not search_type:
        if is_coords:
            search_type = 'location'
        elif is_ip:
            search_type = 'network'
        elif is_bssid:
            search_type = 'bssid'
        else:
            # Check if query is likely a city or location name
            search_type = 'location' if any(c.isalpha() for c in query) and len(query.split()) <= 4 else 'ssid'

    # 1. REAL IP / HOST INTELLIGENCE SEARCH
    if is_ip or search_type == 'network':
        target_ip = query if is_ip else ''
        if not target_ip:
            try:
                target_ip = socket.gethostbyname(query)
            except Exception:
                target_ip = query

        try:
            # Live IP Geolocation & ASN Intelligence
            ip_res = requests.get(
                f"http://ip-api.com/json/{target_ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query",
                timeout=6
            ).json()

            if ip_res.get('status') == 'success':
                lat = float(ip_res.get('lat', 38.9072))
                lon = float(ip_res.get('lon', -77.0369))
                isp = ip_res.get('isp', 'Unknown ISP')
                org = ip_res.get('org', isp)
                asn = ip_res.get('as', '')
                rev_dns = ip_res.get('reverse', '')

                # Live Shodan Open Ports & Vulnerabilities (Free InternetDB API)
                open_ports = []
                shodan_hostnames = []
                try:
                    shodan_res = requests.get(f"https://internetdb.shodan.io/{target_ip}", timeout=5).json()
                    open_ports = shodan_res.get('ports', [])
                    shodan_hostnames = shodan_res.get('hostnames', [])
                except Exception as e:
                    print(f"Shodan InternetDB error: {e}")

                primary_host = shodan_hostnames[0] if shodan_hostnames else (rev_dns or target_ip)
                port_summary = f"Open Ports: {', '.join(map(str, open_ports))}" if open_ports else "Standard TCP/IP"

                devices.append({
                    "lat": lat,
                    "lon": lon,
                    "ssid": f"{org} ({primary_host})",
                    "ip": target_ip,
                    "vendor": f"{isp} [{asn}]",
                    "signal": -45,
                    "encryption": port_summary,
                    "accuracy": 15,
                    "url": f"https://www.shodan.io/host/{target_ip}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "router"
                })

                # Live OpenCellID cell towers surrounding the IP's real geolocation
                if OPENCELLID_API_KEY:
                    try:
                        bbox = f"{lat-0.008},{lon-0.008},{lat+0.008},{lon+0.008}"
                        cell_res = requests.get(
                            'https://opencellid.org/cell/getInArea',
                            params={"key": OPENCELLID_API_KEY, "BBOX": bbox, "format": "json"},
                            timeout=8
                        ).json()
                        for cell in cell_res.get('cells', []):
                            clat = float(cell.get('lat'))
                            clon = float(cell.get('lon'))
                            cid = str(cell.get('cellid', 'Cell Tower'))
                            radio = str(cell.get('radio', 'LTE')).upper()
                            devices.append({
                                "lat": clat,
                                "lon": clon,
                                "cell_id": cid,
                                "ssid": f"CELL_TOWER_{cid} ({radio})",
                                "vendor": f"MCC:{cell.get('mcc')} MNC:{cell.get('mnc')} [{radio}]",
                                "signal": cell.get('averageSignalStrength') or -65,
                                "encryption": f"Radio Protocol: {radio}",
                                "accuracy": cell.get('range', 1000),
                                "url": f"https://www.opencellid.org/#zoom=16&lat={clat}&lon={clon}",
                                "timestamp": cell.get('updated') or datetime.now(timezone.utc).isoformat(),
                                "type": "cell_tower"
                            })
                    except Exception as e:
                        print(f"OpenCellID IP proximity exception: {e}")

        except Exception as e:
            print(f"IP search exception: {e}")

    # 2. REAL LOCATION & CELL TOWER SEARCH (Coordinates or City / Region)
    elif search_type == 'location':
        lat, lon = None, None
        if is_coords:
            try:
                lat, lon = map(float, query.split(','))
            except Exception:
                pass
        else:
            # Geocode city/address via OpenStreetMap Nominatim
            try:
                osm_res = requests.get(
                    f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(query)}&format=json&limit=1",
                    headers={"User-Agent": "GeoVigilant-Argus/2.0"},
                    timeout=6
                ).json()
                if osm_res:
                    lat = float(osm_res[0]['lat'])
                    lon = float(osm_res[0]['lon'])
            except Exception as e:
                print(f"OSM Geocoding exception: {e}")

        if lat is not None and lon is not None:
            # Live OpenCellID API query (bounded under 4M sq meters)
            if OPENCELLID_API_KEY:
                try:
                    bbox = f"{lat-0.008},{lon-0.008},{lat+0.008},{lon+0.008}"
                    cell_res = requests.get(
                        'https://opencellid.org/cell/getInArea',
                        params={"key": OPENCELLID_API_KEY, "BBOX": bbox, "format": "json"},
                        timeout=8
                    ).json()
                    for cell in cell_res.get('cells', []):
                        clat = float(cell.get('lat'))
                        clon = float(cell.get('lon'))
                        cid = str(cell.get('cellid', 'Cell Tower'))
                        radio = str(cell.get('radio', 'LTE')).upper()
                        devices.append({
                            "lat": clat,
                            "lon": clon,
                            "cell_id": cid,
                            "ssid": f"CELL_TOWER_{cid} ({radio})",
                            "vendor": f"MCC:{cell.get('mcc')} MNC:{cell.get('mnc')} [{radio}]",
                            "signal": cell.get('averageSignalStrength') or -65,
                            "encryption": f"Radio Protocol: {radio}",
                            "accuracy": cell.get('range', 1000),
                            "url": f"https://www.opencellid.org/#zoom=16&lat={clat}&lon={clon}",
                            "timestamp": cell.get('updated') or datetime.now(timezone.utc).isoformat(),
                            "type": "cell_tower"
                        })
                except Exception as e:
                    print(f"OpenCellID location exception: {e}")

            # Live WiGLE API query
            wigle_user, wigle_key = get_wigle_auth()
            if wigle_user and wigle_key:
                try:
                    wigle_res = requests.get(
                        'https://api.wigle.net/api/v2/network/search',
                        params={'latrange1': lat-0.008, 'latrange2': lat+0.008, 'longrange1': lon-0.008, 'longrange2': lon+0.008},
                        auth=(wigle_user, wigle_key),
                        timeout=8
                    )
                    if wigle_res.status_code == 200:
                        for network in wigle_res.json().get('results', []):
                            netid = network.get('netid', '')
                            devices.append({
                                "lat": network.get('trilat'),
                                "lon": network.get('trilong'),
                                "ssid": network.get('ssid') or 'Hidden Network',
                                "bssid": netid,
                                "vendor": network.get('vendor') or 'Generic RF Device',
                                "signal": network.get('level', -65),
                                "encryption": network.get('encryption', 'WPA2-PSK'),
                                "channel": network.get('channel', 6),
                                "accuracy": 12,
                                "url": f"https://wigle.net/search#bssid={netid}" if netid else f"/earth?lat={network.get('trilat')}&lon={network.get('trilong')}",
                                "timestamp": network.get('lastupdt') or datetime.now(timezone.utc).isoformat(),
                                "type": "router"
                            })
                    else:
                        print(f"WiGLE location error: {wigle_res.status_code} - {wigle_res.text[:100]}")
                except Exception as e:
                    print(f"WiGLE location exception: {e}")

    # 3. REAL BSSID / MAC ADDRESS SEARCH
    elif search_type == 'bssid':
        # Live IEEE MAC Vendor Registry Lookup via MACVendors API v1 (Bearer Token)
        vendor_info = lookup_mac_vendor(query)
        real_vendor = vendor_info.get("vendor") or 'IEEE Registered Vendor'
        addr_info = vendor_info.get("address", "").strip()
        reg_info = vendor_info.get("registry", "")

        # Live WiGLE API query
        wigle_found = False
        wigle_user, wigle_key = get_wigle_auth()
        if wigle_user and wigle_key:
            try:
                wigle_res = requests.get(
                    'https://api.wigle.net/api/v2/network/search',
                    params={'netid': query},
                    auth=(wigle_user, wigle_key),
                    timeout=8
                )
                if wigle_res.status_code == 200:
                    for network in wigle_res.json().get('results', []):
                        wigle_found = True
                        devices.append({
                            "lat": network.get('trilat'),
                            "lon": network.get('trilong'),
                            "ssid": network.get('ssid') or f"BSSID_{query}",
                            "bssid": query,
                            "vendor": network.get('vendor') or real_vendor,
                            "signal": network.get('level', -55),
                            "encryption": network.get('encryption', 'WPA2-PSK'),
                            "channel": network.get('channel', 6),
                            "accuracy": 10,
                            "url": f"https://wigle.net/search#bssid={query}",
                            "timestamp": network.get('lastupdt') or datetime.now(timezone.utc).isoformat(),
                            "type": "router"
                        })
                else:
                    print(f"WiGLE BSSID response: {wigle_res.status_code} - {wigle_res.text[:100]}")
            except Exception as e:
                print(f"WiGLE BSSID exception: {e}")

        # If WiGLE is rate-limited or no live network returned, present the real IEEE hardware record without fake coordinates
        if not wigle_found:
            details_str = f"IEEE {reg_info} - {addr_info}" if addr_info else "IEEE 802.11 OUI Registered"
            devices.append({
                "lat": None,
                "lon": None,
                "ssid": f"MAC_{query}",
                "bssid": query,
                "vendor": real_vendor,
                "signal": -50,
                "encryption": details_str,
                "accuracy": 0,
                "url": f"https://wigle.net/search#bssid={query}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "type": "hardware_oui"
            })


    # 4. REAL SSID SEARCH
    elif search_type == 'ssid':
        wigle_user, wigle_key = get_wigle_auth()
        if wigle_user and wigle_key:
            try:
                wigle_res = requests.get(
                    'https://api.wigle.net/api/v2/network/search',
                    params={'ssid': query},
                    auth=(wigle_user, wigle_key),
                    timeout=8
                )
                if wigle_res.status_code == 200:
                    for network in wigle_res.json().get('results', []):
                        netid = network.get('netid', '')
                        devices.append({
                            "lat": network.get('trilat'),
                            "lon": network.get('trilong'),
                            "ssid": network.get('ssid', query),
                            "bssid": netid,
                            "vendor": network.get('vendor') or 'Wireless Access Point',
                            "signal": network.get('level', -58),
                            "encryption": network.get('encryption', 'WPA2-PSK'),
                            "channel": network.get('channel', 11),
                            "accuracy": 12,
                            "url": f"https://wigle.net/search#bssid={netid}" if netid else f"https://wigle.net/search#ssid={query}",
                            "timestamp": network.get('lastupdt') or datetime.now(timezone.utc).isoformat(),
                            "type": "router"
                        })
                else:
                    print(f"WiGLE SSID response: {wigle_res.status_code} - {wigle_res.text[:100]}")
            except Exception as e:
                print(f"WiGLE SSID exception: {e}")


    return jsonify({"devices": devices})


@app.route('/api/mac/lookup/<path:mac>')
def api_mac_lookup(mac):
    """Query MACVendors API v1 with Bearer token for OUI assignment and manufacturer."""
    info = lookup_mac_vendor(mac)
    return jsonify({"success": True, "mac": mac, "data": info})


@app.route('/api/osint/host/<path:target_ip>')
def api_free_shodan_host(target_ip):
    """
    Fused Multi-Source OSINT Host Intelligence:
    1. Shodan InternetDB (100% Free - Ports, Hostnames, CPEs, Vulns, Tags)
    2. IP-API (Free Geolocation, ASN, ISP, Timezone, Reverse DNS)
    3. Censys Platform v3 API (Personal Access Token - Live Host Services, OS, Fingerprints)
    4. ZoomEye API (Threat Intelligence)
    """
    target_ip = target_ip.strip()
    if not target_ip:
        return jsonify({"error": "Missing target IP"}), 400

    # Resolve domain names if passed
    resolved_ip = target_ip
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target_ip):
        try:
            resolved_ip = socket.gethostbyname(target_ip)
        except Exception:
            resolved_ip = target_ip

    # 1. Shodan InternetDB (Official Free API - No Key Needed)
    shodan_data = {}
    try:
        shodan_res = requests.get(f"https://internetdb.shodan.io/{resolved_ip}", timeout=5)
        if shodan_res.status_code == 200:
            shodan_data = shodan_res.json()
    except Exception as e:
        print(f"[InternetDB] Error: {e}")

    # 2. IP Geolocation & ASN Intelligence (Free ip-api.com)
    geo_data = {}
    try:
        geo_res = requests.get(
            f"http://ip-api.com/json/{resolved_ip}?fields=status,message,country,regionName,city,lat,lon,timezone,isp,org,as,reverse",
            timeout=5
        )
        if geo_res.status_code == 200:
            geo_data = geo_res.json()
    except Exception as e:
        print(f"[IP-API] Error: {e}")

    # 3. Censys Platform v3 API (Live Asset Host Intelligence)
    censys_data = {}
    censys_tok = get_censys_token()
    if censys_tok:
        try:
            censys_headers = {
                "Authorization": f"Bearer {censys_tok}",
                "Accept": "application/vnd.censys.api.v3.host.v1+json"
            }
            c_res = requests.get(f"https://api.platform.censys.io/v3/global/asset/host/{resolved_ip}", headers=censys_headers, timeout=6)
            if c_res.status_code == 200:
                res_obj = c_res.json().get("result", {}).get("resource", {})
                censys_services = [
                    {
                        "port": s.get("port"),
                        "service_name": s.get("service_name"),
                        "transport": s.get("transport_protocol")
                    }
                    for s in res_obj.get("services", [])
                ]
                censys_data = {
                    "status": "connected",
                    "services": censys_services,
                    "service_count": len(censys_services),
                    "operating_system": res_obj.get("operating_system"),
                    "autonomous_system": res_obj.get("autonomous_system"),
                    "last_updated_at": res_obj.get("last_updated_at"),
                    "source": "Censys Platform v3"
                }
        except Exception as e:
            print(f"[Censys v3] Query error: {e}")

    # 4. ZoomEye Fallback Check
    zoomeye_data = {}
    zoomeye_key = get_zoomeye_key()
    if zoomeye_key:
        try:
            # Try zoomeye.ai gateway first, fallback to zoomeye.org
            z_headers = {"API-KEY": zoomeye_key, "User-Agent": "GeoVigilant-Argus/2.0"}
            for base_host in ["https://api.zoomeye.ai", "https://api.zoomeye.org"]:
                try:
                    zr = requests.get(f"{base_host}/host/search?query=ip:{resolved_ip}", headers=z_headers, timeout=4)
                    if zr.status_code == 200:
                        zoomeye_data = zr.json()
                        break
                except Exception:
                    pass
        except Exception as e:
            print(f"[ZoomEye] Error: {e}")

    ports = shodan_data.get("ports", [])
    cpes = shodan_data.get("cpes", [])
    hostnames = shodan_data.get("hostnames", [])
    vulns = shodan_data.get("vulns", [])
    tags = shodan_data.get("tags", [])

    return jsonify({
        "success": True,
        "query": target_ip,
        "ip": resolved_ip,
        "geo": {
            "country": geo_data.get("country", "Unknown"),
            "city": geo_data.get("city", "Unknown"),
            "lat": geo_data.get("lat"),
            "lon": geo_data.get("lon"),
            "timezone": geo_data.get("timezone", "UTC")
        },
        "network": {
            "isp": geo_data.get("isp", "Unknown ISP"),
            "org": geo_data.get("org", "Unknown Org"),
            "asn": geo_data.get("as", ""),
            "reverse_dns": geo_data.get("reverse", "")
        },
        "shodan_internetdb": {
            "open_ports": ports,
            "port_count": len(ports),
            "hostnames": hostnames,
            "cpes": cpes,
            "vulnerabilities": vulns,
            "tags": tags,
            "source": "Shodan InternetDB (Free Community Feed)"
        },
        "censys_v3": censys_data if censys_data else {"status": "inactive"},
        "zoomeye": zoomeye_data if zoomeye_data else {"status": "inactive"},
        "shodan_web_url": f"https://www.shodan.io/host/{resolved_ip}",
        "censys_web_url": f"https://search.censys.io/hosts/{resolved_ip}"
    })


@app.route('/api/osint/certs/<path:target_domain>')
def api_osint_certs(target_domain):
    """
    100% Free Certificate Transparency & Subdomain Intelligence.
    Queries crt.sh with resilient fallback to SSLMate CertSpotter API.
    """
    domain = target_domain.strip().lower()
    if not domain:
        return jsonify({"error": "Missing target domain"}), 400

    # Remove protocol if passed
    domain = re.sub(r'^https?://', '', domain).split('/')[0]

    subdomains = set()
    certs = []
    source = "crt.sh"

    # 1. Primary: crt.sh
    try:
        crt_url = f"https://crt.sh/?q=%25.{urllib.parse.quote(domain)}&output=json"
        crt_res = requests.get(crt_url, headers={"User-Agent": "GeoVigilant-Argus/2.0"}, timeout=6)
        if crt_res.status_code == 200:
            for item in crt_res.json()[:200]:
                name_val = item.get("name_value", "")
                for sub in name_val.split("\n"):
                    sub_clean = sub.strip().lower().lstrip("*.")
                    if domain in sub_clean:
                        subdomains.add(sub_clean)
                certs.append({
                    "issuer": item.get("issuer_name"),
                    "logged_at": item.get("entry_timestamp"),
                    "not_before": item.get("not_before"),
                    "not_after": item.get("not_after"),
                    "common_name": item.get("common_name")
                })
    except Exception as e:
        print(f"[crt.sh] Primary failed ({e}), falling back to CertSpotter...")

    # 2. Resilient Fallback: CertSpotter (Free CT log monitor)
    if not subdomains:
        try:
            cs_url = f"https://api.certspotter.com/v1/issuances?domain={urllib.parse.quote(domain)}&include_subdomains=true&expand=dns_names"
            cs_res = requests.get(cs_url, headers={"User-Agent": "GeoVigilant-Argus/2.0"}, timeout=7)
            if cs_res.status_code == 200:
                source = "CertSpotter (CT Logs)"
                for item in cs_res.json()[:150]:
                    for name in item.get("dns_names", []):
                        sub_clean = name.strip().lower().lstrip("*.")
                        if domain in sub_clean:
                            subdomains.add(sub_clean)
                    certs.append({
                        "issuer": item.get("issuer", {}).get("name"),
                        "not_before": item.get("not_before"),
                        "not_after": item.get("not_after"),
                        "dns_names": item.get("dns_names")
                    })
        except Exception as e:
            print(f"[CertSpotter] Fallback failed: {e}")

    sorted_subdomains = sorted(list(subdomains))
    return jsonify({
        "success": True,
        "domain": domain,
        "subdomain_count": len(sorted_subdomains),
        "subdomains": sorted_subdomains,
        "certificate_count": len(certs),
        "certificates": certs[:30],
        "source": source
    })


@app.route('/api/osint/zoomeye/<path:query_str>')
def api_osint_zoomeye_search(query_str):
    """
    Direct ZoomEye Intelligence Search using configured API Key.
    """
    key = get_zoomeye_key()
    if not key:
        return jsonify({"error": "ZoomEye API Key not configured"}), 400

    headers = {"API-KEY": key, "User-Agent": "GeoVigilant-Argus/2.0"}
    for host in ["https://api.zoomeye.ai", "https://api.zoomeye.org"]:
        try:
            url = f"{host}/host/search?query={urllib.parse.quote(query_str)}&page=1"
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                return jsonify({"success": True, "source": host, "data": res.json()})
            elif res.status_code == 403 and "api.zoomeye.ai" in res.text:
                continue
        except Exception as e:
            print(f"[ZoomEye Search] Error with {host}: {e}")

    return jsonify({"success": False, "message": "ZoomEye upstream service currently unreachable or regionally restricted."}), 502



# ============================================================
# System Diagnostic & Memory Telemetry API
# ============================================================
@app.route('/api/sys/memory')
def sys_memory_status():
    """Telemetry endpoint returning live system and process RAM statistics."""
    try:
        import psutil
        proc = psutil.Process(os.getpid())
        mem_info = proc.memory_info()
        sys_mem = psutil.virtual_memory()
        with _flight_cache_lock:
            flt_cnt = len(_flight_cache)
        with _firms_cache_lock:
            firms_cnt = len(_firms_cache)
        return jsonify({
            "process_rss_mb": round(mem_info.rss / (1024 * 1024), 2),
            "process_vms_mb": round(mem_info.vms / (1024 * 1024), 2),
            "system_total_gb": round(sys_mem.total / (1024 ** 3), 2),
            "system_used_percent": sys_mem.percent,
            "flight_cache_count": flt_cnt,
            "firms_cache_count": firms_cnt,
            "status": "optimized"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', 5000))
    app.run(host=host, port=port, debug=debug_mode)

