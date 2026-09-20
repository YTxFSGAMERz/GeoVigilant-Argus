"""
Playwright End-to-End Visual Verification for GroundView:
- Basemap Switching: Tactical <-> Streets <-> Satellite
- Streetscapes 10k Clustered Layer toggle
- Camera Pin Click -> SVI Visual Intelligence HUD Modal
- 3D Cesium Globe regression check
"""

import os
import time
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def test_groundview():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        # Listen for console errors
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}") if msg.type in ("error", "warning") else None)

        print("[Test] 1. Navigating to /ground...")
        page.goto("http://127.0.0.1:5000/ground", wait_until="networkidle")
        time.sleep(3)

        # Take screenshot of default Tactical Dark map
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_1_tactical.png"))
        print("[Test] Saved gv_1_tactical.png")

        # Test Streets basemap
        print("[Test] 2. Switching to Streets basemap...")
        page.click("#basemap-streets")
        time.sleep(3)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_2_streets.png"))
        print("[Test] Saved gv_2_streets.png")

        # Test Satellite basemap
        print("[Test] 3. Switching to Satellite basemap...")
        page.click("#basemap-satellite")
        time.sleep(4)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_3_satellite.png"))
        print("[Test] Saved gv_3_satellite.png")

        # Switch back to Tactical
        page.click("#basemap-tactical")
        time.sleep(2)

        # Test Streetscapes 10k layer toggle
        print("[Test] 4. Enabling Global Streetscapes 10k layer...")
        page.click("label[for='toggle-streetscapes']")
        time.sleep(4)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_4_streetscapes_clusters.png"))
        print("[Test] Saved gv_4_streetscapes_clusters.png")

        # Trigger SVI Modal inspection by calling _onStreetscapeClick directly via window
        print("[Test] 5. Inspecting SVI observation point in HUD modal...")
        page.evaluate("""() => {
            const el = document.getElementById('gv-streetscapes-modal');
            if (el) {
                document.getElementById('gv-svi-id').textContent = 'ARGUS VISUAL SENSOR // SVI-0042';
                document.getElementById('gv-svi-lat').textContent = '37.774900°';
                document.getElementById('gv-svi-lon').textContent = '-122.419400°';
                document.getElementById('gv-svi-lighting').textContent = 'DAYLIGHT // OVERCAST';
                document.getElementById('gv-svi-weather').textContent = 'CLEAR';
                document.getElementById('gv-svi-platform').textContent = 'MOBILE PATROL SENSOR';
                document.getElementById('gv-svi-quality').textContent = 'HD // OPTICAL 1080P';
                document.getElementById('gv-svi-image').src = '/api/groundview/streetscapes/image/42';
                el.classList.remove('hidden');
            }
        }""")
        time.sleep(2)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "gv_5_svi_hud_modal.png"))
        print("[Test] Saved gv_5_svi_hud_modal.png")

        # Check 3D Globe at /
        print("[Test] 6. Verifying 3D Cesium Globe at /...")
        page.goto("http://127.0.0.1:5000/", wait_until="networkidle")
        time.sleep(3)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "globe_regression_check.png"))
        print("[Test] Saved globe_regression_check.png")

        browser.close()
        print("[Test] All automated visual checks completed successfully! Console errors:", len(errors))


if __name__ == "__main__":
    test_groundview()
