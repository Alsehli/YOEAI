"""Exercise both desktop direction layers in Chromium without loading AI models."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            for edition in ("source", "editions/lite/source"):
                server = ThreadingHTTPServer(
                    ("127.0.0.1", 0), partial(Quiet, directory=str(ROOT / edition))
                )
                threading.Thread(target=server.serve_forever, daemon=True).start()
                context = browser.new_context(viewport={"width": 1200, "height": 900})
                try:
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_port}/tests_ui/bidi-fixture.html")
                    page.wait_for_function("Array.isArray(window.rtlTestResults)")
                    results = page.evaluate("window.rtlTestResults")
                    failed = [result for result in results if not result["passed"]]
                    print(json.dumps({"edition": edition, "checks": len(results), "failed": failed}))
                    assert len(results) >= 30 and not failed
                finally:
                    context.close()
                    server.shutdown()
                    server.server_close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
