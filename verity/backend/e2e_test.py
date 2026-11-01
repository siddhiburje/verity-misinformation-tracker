"""
End-to-end browser test using Playwright + a real Flask dev server
running in a background thread (same process, so it dies with the
test — no cross-process/cross-call lifecycle issues).
"""
import threading
import time
import sys
from werkzeug.serving import make_server

from app import create_app

PORT = 5057


class ServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.srv = make_server("127.0.0.1", PORT, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.srv.serve_forever()

    def shutdown(self):
        self.srv.shutdown()


def main():
    import os
    db_path = os.path.join(os.path.dirname(__file__), "instance", "verity.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    app = create_app()
    server = ServerThread(app)
    server.start()
    time.sleep(1)

    from playwright.sync_api import sync_playwright

    failures = []

    def check(label, condition):
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {label}")
        if not condition:
            failures.append(label)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: console_errors.append(str(exc)))

        base = f"http://127.0.0.1:{PORT}"

        # --- 1. Landing page ---
        page.goto(base + "/")
        check("landing page loads", page.title().startswith("Verity"))
        check("landing has Start tracking CTA", page.locator("text=Start tracking").first.is_visible())
        page.screenshot(path="/tmp/shot_landing.png", full_page=True)

        # --- 2. Navigate to signup ---
        page.click("text=Start tracking >> nth=0")
        page.wait_for_url("**/auth*")
        check("auth page shows signup mode from query param", page.locator("#signupForm").is_visible())
        page.screenshot(path="/tmp/shot_auth_signup.png", full_page=True)

        # --- 3. Sign up ---
        page.fill("#signupName", "Playwright Tester")
        page.fill("#signupEmail", "playwright@example.com")
        page.fill("#signupPassword", "testpass123")
        page.fill("#signupConfirm", "testpass123")
        page.click("#signupSubmit")
        page.wait_for_url("**/app", timeout=8000)
        check("signup redirects to dashboard", "/app" in page.url)
        page.wait_for_timeout(500)
        page.screenshot(path="/tmp/shot_dashboard_overview.png", full_page=True)

        check("sidebar shows user name", "Playwright" in page.locator("#userName").inner_text())
        stat_claims = page.locator("#statClaims").inner_text()
        check("overview stats loaded (non-placeholder)", stat_claims != "–" and stat_claims != "")

        # --- 4. Analyze a claim (text) ---
        page.click("[data-page='analyze']")
        page.wait_for_timeout(200)
        page.fill("#claimTextInput", "New reports claim the vaccine causes infertility in young women across the country.")
        page.click("#analyzeTextBtn")
        page.wait_for_selector("#analyzeResults.show", timeout=15000)
        check("analyze results rendered", page.locator("#analyzeResults .result-title").is_visible())
        narrative = page.locator("#analyzeResults .narrative-badge").inner_text()
        check("narrative badge populated", len(narrative) > 0)
        check("graph svg rendered", page.locator("#analyzeResults .graph-container svg").count() > 0)
        check("timeline rows rendered", page.locator("#analyzeResults .timeline-row").count() > 0)
        check("keyword tags rendered", page.locator("#analyzeResults .kw-list .tag").count() > 0)
        page.screenshot(path="/tmp/shot_analyze_result.png", full_page=True)

        # click a graph node & a timeline row to exercise interactivity
        svg_node = page.locator("#analyzeResults .graph-container svg circle").first
        if svg_node.count() > 0:
            svg_node.click(force=True)
        page.locator("#analyzeResults .timeline-row").first.click()
        check("timeline row can be selected (active class present)",
              "active-row" in (page.locator("#analyzeResults .timeline-row.active-row").first.get_attribute("class") or ""))

        # --- 4b. Analyze a claim (image / OCR) ---
        page.click("button[data-input='image']")
        page.wait_for_timeout(200)

        import io
        from PIL import Image as PILImage, ImageDraw, ImageFont
        img = PILImage.new("RGB", (900, 160), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
        except Exception:
            font = ImageFont.load_default()
        draw.text((20, 20), "BREAKING: new claim about election fraud", fill="black", font=font)
        draw.text((20, 70), "spreads rapidly across social media", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        page.set_input_files("#imageFileInput", files=[{
            "name": "screenshot.png", "mimeType": "image/png", "buffer": buf.getvalue(),
        }])
        check("image preview shown after selecting a file", page.locator("#imagePreviewBox").is_visible())
        page.click("#analyzeImageBtn")
        page.wait_for_selector("#analyzeResults.show", timeout=20000)
        ocr_text = page.locator(".ocr-preview").inner_text() if page.locator(".ocr-preview").count() else ""
        check("OCR extracted text is shown to the user", "election" in ocr_text.lower() or "claim" in ocr_text.lower())
        check("image analysis produced a result graph", page.locator("#analyzeResults .graph-container svg").count() > 0)
        page.screenshot(path="/tmp/shot_image_analyze.png", full_page=True)

        # reject a bad file extension
        page.click("#imageClearBtn")
        page.set_input_files("#imageFileInput", files=[{
            "name": "notes.txt", "mimeType": "text/plain", "buffer": b"not an image",
        }])
        page.wait_for_timeout(300)
        check("unsupported image extension shows a clear error", page.locator("#analyzeError.show").is_visible())

        # --- 5. Import dataset (paste-as-file via TXT format) ---
        page.click("[data-page='import']")
        page.wait_for_timeout(200)
        page.click("button[data-format='text']")
        page.set_input_files("#datasetFileInput", files=[{
            "name": "claims.txt",
            "mimeType": "text/plain",
            "buffer": b"Voting machines were hacked to flip votes\nMail ballots were destroyed by officials\n",
        }])
        page.wait_for_selector("#datasetPreviewBox", state="visible", timeout=5000)
        check("dataset preview shows parsed rows", page.locator("#datasetPreviewTable table").is_visible())
        page.click("#datasetAnalyzeBtn")
        page.wait_for_selector("#datasetSummaryBox", state="visible", timeout=15000)
        ds_count = page.locator("#dsCount").inner_text()
        check("dataset analysis summary populated", ds_count == "2")
        page.screenshot(path="/tmp/shot_import_result.png", full_page=True)

        # --- 6. News tracker (no API key -> offline fallback banner) ---
        page.click("[data-page='news']")
        page.wait_for_timeout(200)
        page.fill("#newsQueryInput", "election fraud")
        page.click("#newsTrackBtn")
        page.wait_for_selector("#newsResults", state="visible", timeout=15000)
        banner_text = page.locator("#newsBanner").inner_text()
        check("news banner shown with honest offline warning", "NEWSAPI_KEY" in banner_text or "offline" in banner_text.lower())
        check("news graph rendered", page.locator("#newsGraphContainer svg").count() > 0)
        page.screenshot(path="/tmp/shot_news_result.png", full_page=True)

        # --- 7. History ---
        page.click("[data-page='history']")
        page.wait_for_timeout(500)
        check("history shows entries", page.locator(".history-row").count() > 0)
        page.locator(".history-row").first.click()
        page.wait_for_timeout(800)
        page.screenshot(path="/tmp/shot_history.png", full_page=True)

        # --- 8. Logout flow ---
        page.click("[data-page='overview']")
        page.click("#logoutBtn")
        page.wait_for_url("**/auth", timeout=5000)
        check("logout redirects to /auth", "/auth" in page.url)

        # --- 9. Protected route redirect when logged out ---
        page.goto(base + "/app")
        page.wait_for_url("**/auth*", timeout=5000)
        check("visiting /app while logged out redirects to /auth", "/auth" in page.url)

        # --- 10. Login flow ---
        page.goto(base + "/auth")
        page.fill("#loginEmail", "playwright@example.com")
        page.fill("#loginPassword", "testpass123")
        page.click("#loginSubmit")
        page.wait_for_url("**/app", timeout=8000)
        check("login redirects to dashboard", "/app" in page.url)

        # --- Wrong password ---
        page.click("#logoutBtn")
        page.wait_for_url("**/auth", timeout=5000)
        page.fill("#loginEmail", "playwright@example.com")
        page.fill("#loginPassword", "wrongpassword")
        page.click("#loginSubmit")
        page.wait_for_timeout(600)
        check("wrong password shows error alert", page.locator("#formAlert.show").is_visible())

        browser.close()

    server.shutdown()

    print("\n--- Console/page errors captured during test ---")
    # Filter out expected/benign noise: this sandbox blocks the Google
    # Fonts CDN with an invalid cert (harmless font fallback), and the
    # intentional wrong-password test deliberately triggers a 401 that
    # the browser logs as a console error even though the app handles
    # it correctly (already asserted above via the visible alert).
    benign_markers = ["ERR_CERT_AUTHORITY_INVALID", "401 (UNAUTHORIZED)"]
    real_errors = [e for e in console_errors if e.strip() and not any(m in e for m in benign_markers)]
    for e in real_errors:
        print(" -", e)
    check("no unexpected JS console/page errors during full flow", len(real_errors) == 0)

    print(f"\n{'='*50}\n{len(failures)} FAILURE(S)\n{'='*50}")
    for f in failures:
        print(" -", f)

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
