import os
import sys
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import jinja2
from news_config import NEWS_SOURCES

def build_newsnetworks():
    t_path = os.path.join(ROOT_DIR, 'templates', 'newsnetworks.html')
    with open(t_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace url_for with static paths
    content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"/static/\1", content)
    
    template = jinja2.Template(content)
    rendered = template.render(sources=NEWS_SOURCES)
    
    out_path = os.path.join(ROOT_DIR, 'newsnetworks.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"[Build] newsnetworks.html generated successfully ({len(rendered)} bytes).")

def build_wifi_search():
    t_path = os.path.join(ROOT_DIR, 'templates', 'wifi-search.html')
    with open(t_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace url_for with static paths
    content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"/static/\1", content)

    out_path = os.path.join(ROOT_DIR, 'wifi-search.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[Build] wifi-search.html generated successfully ({len(content)} bytes).")

def build_news():
    r_path = os.path.join(ROOT_DIR, 'news.html')
    with open(r_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace url_for with static paths
    content = re.sub(r"\{\{\s*url_for\('static',\s*filename='([^']+)'\)\s*\}\}", r"/static/\1", content)

    with open(r_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    t_path = os.path.join(ROOT_DIR, 'templates', 'news.html')
    with open(t_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"[Build] news.html updated and synced to templates/news.html ({len(content)} bytes).")

if __name__ == "__main__":
    build_newsnetworks()
    build_wifi_search()
    build_news()
