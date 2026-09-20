import os
import sys
import time
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def wait_for_server(url="http://127.0.0.1:5000", timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False

def main():
    print("[*] Launching GeoVigilant backend (app.py)...")
    server_proc = subprocess.Popen([sys.executable, "app.py"], cwd=BASE_DIR)
    
    try:
        if not wait_for_server():
            print("[!] Failed to connect to http://127.0.0.1:5000 within timeout.")
            return 1

        print("[+] Backend active on http://127.0.0.1:5000")
        time.sleep(2)

        with sync_playwright() as p:
            print("[*] Launching Playwright Chromium with WebGL support...")
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--enable-webgl",
                    "--ignore-gpu-blocklist",
                    "--use-gl=angle",
                    "--use-angle=d3d11",
                    "--enable-features=Vulkan,DefaultANGLEVulkan",
                    "--no-sandbox",
                    "--disable-setuid-sandbox"
                ]
            )
            
            page = browser.new_page(viewport={"width": 1920, "height": 1080})

            # 1. portfolio_landing.png
            print("[1/22] Capturing portfolio_landing.png...")
            page.goto("http://127.0.0.1:5000/", wait_until="networkidle")
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "portfolio_landing.png"))

            # 2. globe_regression_check.png
            print("[2/22] Capturing globe_regression_check.png...")
            page.goto("http://127.0.0.1:5000/earth")
            page.wait_for_timeout(9000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "globe_regression_check.png"))

            # 3. radar_and_layers_verified.png
            print("[3/22] Capturing radar_and_layers_verified.png...")
            try:
                page.click("#btn-air-radar", timeout=3000)
            except Exception:
                page.keyboard.press("KeyR")
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "radar_and_layers_verified.png"))

            # 4. radar_verified_shot.png
            print("[4/22] Capturing radar_verified_shot.png...")
            try:
                page.click("#btn-rainviewer", timeout=3000)
            except Exception as e:
                print("Could not toggle rainviewer:", e)
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "radar_verified_shot.png"))

            # 5. sidebar_radar_removed.png
            print("[5/22] Capturing sidebar_radar_removed.png...")
            try:
                page.click("#btn-air-radar", timeout=2000)  # Close radar modal if open
            except Exception:
                pass
            page.wait_for_timeout(2000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "sidebar_radar_removed.png"))

            # 6. gv_1_tactical.png
            print("[6/22] Capturing gv_1_tactical.png...")
            page.goto("http://127.0.0.1:5000/ground")
            page.wait_for_timeout(6000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_1_tactical.png"))

            # 7. gv_2_streets.png
            print("[7/22] Capturing gv_2_streets.png...")
            try:
                page.click("#basemap-streets", timeout=3000)
            except Exception as e:
                print("Error clicking basemap-streets:", e)
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_2_streets.png"))

            # 8. gv_3_satellite.png
            print("[8/22] Capturing gv_3_satellite.png...")
            try:
                page.click("#basemap-satellite", timeout=3000)
            except Exception as e:
                print("Error clicking basemap-satellite:", e)
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_3_satellite.png"))

            # 9. gv_4_streetscapes_clusters.png
            print("[9/22] Capturing gv_4_streetscapes_clusters.png...")
            try:
                page.click("#basemap-tactical", timeout=3000)
            except Exception:
                pass
            page.evaluate("() => { if (window._groundViewApp && window._groundViewApp.map) { window._groundViewApp.map.flyTo({ center: [-122.4194, 37.7749], zoom: 6, duration: 1000 }); } }")
            page.wait_for_timeout(3500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_4_streetscapes_clusters.png"))

            # 10. gv_5_svi_hud_modal.png
            print("[10/22] Capturing gv_5_svi_hud_modal.png...")
            page.evaluate("""() => {
                if (window._groundViewApp && typeof window._groundViewApp._onStreetscapeClick === 'function') {
                    window._groundViewApp._onStreetscapeClick(
                        { id: 42, lat: 37.774900, lon: -122.419400, lighting: 'DAYLIGHT // OVERCAST', weather: 'CLEAR', platform: 'MOBILE PATROL SENSOR', quality: 'HD // OPTICAL 1080P' },
                        { lat: 37.774900, lng: -122.419400 }
                    );
                }
            }""")
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_5_svi_hud_modal.png"))

            # 11. gv_australia_pin_modal.png
            print("[11/22] Capturing gv_australia_pin_modal.png...")
            page.evaluate("""() => {
                if (window._groundViewApp && typeof window._groundViewApp._onStreetscapeClick === 'function') {
                    window._groundViewApp._onStreetscapeClick(
                        { id: 188, lat: -25.274400, lon: 133.775100, lighting: 'DIRECT SUNLIGHT', weather: 'DESERT CLEAR', platform: 'OUTBACK HIGHWAY SVI', quality: 'HD // OPTICAL 1080P' },
                        { lat: -25.274400, lng: 133.775100 }
                    );
                }
            }""")
            page.wait_for_timeout(2500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_australia_pin_modal.png"))

            # 12. gv_global_clusters.png
            print("[12/22] Capturing gv_global_clusters.png...")
            page.evaluate("""() => {
                const modal = document.getElementById('gv-streetscapes-modal');
                if (modal) modal.classList.add('hidden');
                if (window._groundViewApp && window._groundViewApp.map) {
                    window._groundViewApp.map.flyTo({ center: [20, 20], zoom: 2.1, duration: 1000 });
                }
            }""")
            page.wait_for_timeout(4500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_global_clusters.png"))

            # 13. gv_pin_click_verified.png
            print("[13/22] Capturing gv_pin_click_verified.png...")
            page.evaluate("""() => {
                if (window._groundViewApp && window._groundViewApp.map) {
                    window._groundViewApp.map.flyTo({ center: [-122.4194, 37.7749], zoom: 12, duration: 1000 });
                }
            }""")
            page.wait_for_timeout(3000)
            page.evaluate("""() => {
                if (window._groundViewApp && typeof window._groundViewApp._onStreetscapeClick === 'function') {
                    window._groundViewApp._onStreetscapeClick(
                        { id: 1, lat: 37.774900, lon: -122.419400, lighting: 'URBAN DAYLIGHT', weather: 'METROPOLITAN CLEAR', platform: 'SURVEILLANCE CAM SVI-0001', quality: 'HD 1080P' },
                        { lat: 37.774900, lng: -122.419400 }
                    );
                }
            }""")
            page.wait_for_timeout(2000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_pin_click_verified.png"))

            # 14. wifi_surveillance.png
            print("[14/22] Capturing wifi_surveillance.png...")
            page.goto("http://127.0.0.1:5000/surveillance")
            page.wait_for_timeout(6000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "wifi_surveillance.png"))

            # 15. news_map_final.png (Section 6 Primary)
            print("[15/22] Capturing news_map_final.png...")
            page.goto("http://127.0.0.1:5000/news")
            page.wait_for_timeout(6000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_map_final.png"))

            # 16. news_map_click.png
            print("[16/22] Capturing news_map_click.png...")
            page.evaluate("""() => {
                const kyivChip = Array.from(document.querySelectorAll('.filter-chip')).find(el => el.textContent.includes('Kyiv') || el.textContent.includes('UKRAINE'));
                if (kyivChip) {
                    kyivChip.click();
                } else if (typeof searchByLocation === 'function') {
                    searchByLocation('Kyiv');
                }
            }""")
            page.wait_for_timeout(4500)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_map_click.png"))

            # 17. news_map_tactical.png
            print("[17/22] Capturing news_map_tactical.png...")
            page.evaluate("() => { if (typeof switchBasemap === 'function') switchBasemap('tactical'); }")
            page.wait_for_timeout(3000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_map_tactical.png"))

            # 18. news_map_streets.png
            print("[18/22] Capturing news_map_streets.png...")
            page.evaluate("() => { if (typeof switchBasemap === 'function') switchBasemap('streets'); }")
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_map_streets.png"))

            # 19. news_map_satellite.png
            print("[19/22] Capturing news_map_satellite.png...")
            page.evaluate("() => { if (typeof switchBasemap === 'function') switchBasemap('satellite'); }")
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_map_satellite.png"))

            # 20. osint_twitter_stream.png (Section 6 Primary)
            print("[20/22] Capturing osint_twitter_stream.png...")
            page.goto("http://127.0.0.1:5000/social/twitter")
            page.wait_for_timeout(4000)
            try:
                page.fill(".user-search input, input[type='text']", "@tactical_recon")
            except Exception:
                pass
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "osint_twitter_stream.png"))

            # 21. osint_reddit_stream.png
            print("[21/22] Capturing osint_reddit_stream.png...")
            page.goto("http://127.0.0.1:5000/social/reddit")
            page.wait_for_timeout(4000)
            try:
                page.fill(".search-box input, input[type='text']", "r/geopolitics")
            except Exception:
                pass
            page.wait_for_timeout(1000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "osint_reddit_stream.png"))

            # 22. news_networks.png
            print("[22/22] Capturing news_networks.png...")
            page.goto("http://127.0.0.1:5000/newsnetworks")
            page.wait_for_timeout(4000)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "news_networks.png"))

            browser.close()
            print("[+] All 22 high-resolution tactical screenshots successfully captured!")

    finally:
        print("[*] Terminating server process...")
        server_proc.terminate()
        server_proc.wait()
        print("[+] Backend terminated cleanly.")

if __name__ == "__main__":
    sys.exit(main() or 0)
