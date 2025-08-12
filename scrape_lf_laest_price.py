# playwright_lf.py
import json
import sys
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

URL_TEMPLATE = "https://my.litefinance.org/trading/chart?symbol={}"

def main(symbol="EURUSD", headful=False):
    out = {"symbol": symbol}
    screenshot_path = Path(f"screenshot_{symbol}.png")
    html_path = Path(f"page_{symbol}.html")

    try:
        with sync_playwright() as pw:
            # Launch browser
            browser = pw.chromium.launch(headless=not headful, args=["--disable-gpu"])
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36"
            )

            # Make navigation and selector timeouts more forgiving
            page.set_default_navigation_timeout(60000)  # 60s nav timeout
            page.set_default_timeout(30000)  # 30s general timeout

            # Optional: block images/styles/fonts to speed up page load
            def route_handler(route, request):
                if request.resource_type in ("image", "stylesheet", "font"):
                    return route.abort()
                return route.continue_()
            page.route("**/*", route_handler)

            url = URL_TEMPLATE.format(symbol.upper())
            # don't wait for networkidle (socket.io keeps the connection alive)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Wait for the bid/ask elements that you identified (.js_value_price_bid / .js_value_price_ask)
            page.wait_for_selector(".js_value_price_bid", timeout=20000)
            page.wait_for_selector(".js_value_price_ask", timeout=20000)

            # Read values (strip spaces)
            bid_text = page.inner_text(".js_value_price_bid").strip()
            ask_text = page.inner_text(".js_value_price_ask").strip()

            out.update({"bid": bid_text, "ask": ask_text})
            print(json.dumps(out))

            # clean up
            browser.close()
            return 0

    except PlaywrightTimeoutError as e:
        # Save screenshot + page HTML for debugging
        try:
            # try to capture screenshot and HTML where possible
            with sync_playwright() as pw2:
                # a tiny headful snapshot fallback (if headless browser failed earlier)
                browser2 = pw2.chromium.launch(headless=True)
                page2 = browser2.new_page()
                page2.goto(URL_TEMPLATE.format(symbol.upper()), wait_until="domcontentloaded", timeout=20000)
                page2.screenshot(path=str(screenshot_path))
                html_path.write_text(page2.content(), encoding="utf-8")
                browser2.close()
        except Exception:
            pass

        print("TimeoutError: page did not load in time (saved screenshot/html if possible).", file=sys.stderr)
        traceback.print_exc()
        return 2

    except Exception as e:
        traceback.print_exc()
        return 3

if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "EURUSD"
    # pass "headful" as second argument to see the browser window while debugging:
    headful = len(sys.argv) > 2 and sys.argv[2].lower() in ("1", "true", "headful")
    sys.exit(main(sym, headful=headful))
