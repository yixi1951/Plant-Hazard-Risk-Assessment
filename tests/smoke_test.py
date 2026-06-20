"""Playwright smoke test for the 智农 Flask web app."""
import io
import sys
import tempfile
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:7860"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"


def make_test_image(path: Path) -> None:
    img = Image.new("RGB", (256, 256), (34, 139, 34))
    img.save(path, format="PNG")


def run_smoke_test() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # --- Homepage ---
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        title = page.title()
        if "智农" not in title:
            failures.append(f"Unexpected page title: {title!r}")

        for selector in ("#upload_form", "#image_input", "#predict_btn", "#trend_chart"):
            if page.locator(selector).count() == 0:
                failures.append(f"Missing homepage element: {selector}")

        page.screenshot(path=str(SCREENSHOT_DIR / "01_homepage.png"), full_page=True)

        # --- Static pages ---
        for route, heading in [
            ("/about", "关于项目"),
            ("/faq", "常见问题"),
            ("/api", "API"),
        ]:
            page.goto(f"{BASE_URL}{route}")
            page.wait_for_load_state("networkidle")
            if heading not in page.content():
                failures.append(f"{route} missing expected text: {heading!r}")
            page.screenshot(path=str(SCREENSHOT_DIR / f"02_{route.strip('/') or 'root'}.png"), full_page=True)

        # --- API JSON endpoints ---
        page.goto(f"{BASE_URL}/api/diseases")
        page.wait_for_load_state("networkidle")
        diseases_text = page.locator("body").inner_text()
        if not diseases_text.strip().startswith("{"):
            failures.append("/api/diseases did not return JSON body")

        page.goto(f"{BASE_URL}/api/dashboard_stats")
        page.wait_for_load_state("networkidle")
        stats_text = page.locator("body").inner_text()
        if "total" not in stats_text.lower() and "count" not in stats_text.lower():
            failures.append("/api/dashboard_stats missing expected stats fields")

        # --- Upload preview flow ---
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        make_test_image(tmp_path)

        try:
            page.locator("#image_input").set_input_files(str(tmp_path))
            page.locator('button[name="action"][value="preview"]').click()
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)

            preview_visible = page.locator("#preview_img").is_visible()
            if not preview_visible:
                failures.append("Preview image not shown after upload")

            page.screenshot(path=str(SCREENSHOT_DIR / "03_after_preview.png"), full_page=True)
        finally:
            tmp_path.unlink(missing_ok=True)

        browser.close()

    if failures:
        print("SMOKE TEST FAILED:")
        for item in failures:
            print(f"  - {item}")
        sys.exit(1)

    print("SMOKE TEST PASSED")
    print(f"Screenshots saved to: {SCREENSHOT_DIR}")


if __name__ == "__main__":
    run_smoke_test()
