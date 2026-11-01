import threading, time, sys, os
from werkzeug.serving import make_server
from app import create_app

PORT = 5058

class ServerThread(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.srv = make_server("127.0.0.1", PORT, app)
        self.ctx = app.app_context()
        self.ctx.push()
    def run(self): self.srv.serve_forever()
    def shutdown(self): self.srv.shutdown()

def main():
    db_path = os.path.join(os.path.dirname(__file__), "instance", "verity.db")
    app = create_app()
    server = ServerThread(app)
    server.start()
    time.sleep(1)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})  # iPhone-ish
        base = f"http://127.0.0.1:{PORT}"

        page.goto(base + "/")
        page.screenshot(path="/tmp/mobile_landing.png", full_page=True)

        page.goto(base + "/auth?mode=signup")
        page.screenshot(path="/tmp/mobile_auth.png", full_page=True)

        page.fill("#signupName", "Mobile Tester")
        page.fill("#signupEmail", "mobile@example.com")
        page.fill("#signupPassword", "testpass123")
        page.fill("#signupConfirm", "testpass123")
        page.click("#signupSubmit")
        page.wait_for_url("**/app", timeout=8000)
        page.wait_for_timeout(500)
        page.screenshot(path="/tmp/mobile_dashboard.png", full_page=True)

        page.click("[data-page='analyze']")
        page.wait_for_timeout(200)
        page.fill("#claimTextInput", "Vaccines cause infertility according to viral posts")
        page.click("#analyzeTextBtn")
        page.wait_for_selector("#analyzeResults.show", timeout=15000)
        page.screenshot(path="/tmp/mobile_analyze.png", full_page=True)

        browser.close()
    server.shutdown()
    print("mobile screenshots captured")

if __name__ == "__main__":
    main()
