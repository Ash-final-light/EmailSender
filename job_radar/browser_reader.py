"""Read public, JavaScript-rendered company careers pages using an ordinary Chromium session.

No logins, form submissions, stealth plugins, CAPTCHA handling, or private API calls.
"""
from .core import public_url
from bs4 import BeautifulSoup
import re


class BrowserReader:
    def __init__(self):
        self.runtime = self.browser = None

    def close(self):
        if self.browser:
            self.browser.close()
        if self.runtime:
            self.runtime.stop()

    def read(self, url, reserve_view=None):
        from .sources import allowed_host, domain, parse_html, detail_url
        from playwright.sync_api import sync_playwright, Error
        if not public_url(url) or not allowed_host(domain(url)):
            return {"status": "unverified_domain", "url": url, "text": ""}
        if not self.runtime:
            self.runtime = sync_playwright().start()
            self.browser = self.runtime.chromium.launch(headless=True)
        context = self.browser.new_context(locale="zh-CN")
        # Documents stay within reviewed source domains. Assets may use public CDNs;
        # always reject local destinations and all non-HTTPS network requests.
        def route(request_route):
            request = request_route.request
            if not public_url(request.url) or (request.is_navigation_request()
                    and not allowed_host(domain(request.url))):
                request_route.abort()
            elif request.resource_type in ("image", "media", "font"):
                request_route.abort()
            else:
                request_route.continue_()
        context.route("**/*", route)
        try:
            page = context.new_page()
            page.set_default_timeout(12000)
            response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
            if response and response.status in (401, 403, 429, 451):
                return {"status": "restricted", "url": url, "text": ""}
            # Wait for content, bounded by the ordinary page timeout. Never solve challenges.
            try:
                page.wait_for_function("document.body && document.body.innerText.trim().length > 100", timeout=12000)
                page.wait_for_load_state("networkidle", timeout=8000)
            except Error:
                pass
            additional_links = []
            if not detail_url(url):
                inputs = page.locator("input[placeholder*='搜索'],input[placeholder*='职位'],input[placeholder*='关键']")
                if not inputs.count():
                    listing = page.get_by_role("link", name=re.compile(r"^(职位|招聘职位|所有职位|查看所有职位|实习生投递)$"))
                    if listing.count() and listing.first.is_visible() and (reserve_view is None or reserve_view()):
                        try:
                            listing.first.click(timeout=10000)
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except Error:
                            pass
                # Use the site's visible job search, retaining results from both terms.
                for term in ("客户端", "Unity"):
                    inputs = page.locator("input[placeholder*='搜索'],input[placeholder*='职位'],input[placeholder*='关键']")
                    if not inputs.count() or not inputs.first.is_visible():
                        break
                    if reserve_view is not None and not reserve_view():
                        break
                    try:
                        inputs.first.fill(term)
                        inputs.first.press("Enter")
                        try:
                            page.wait_for_load_state("networkidle", timeout=8000)
                        except Error:
                            pass
                        intermediate = parse_html(page.content(), page.url, url)
                        additional_links += intermediate.get("job_links", [])
                    except Error:
                        break
            content = page.content()
            # Generated CSS and embedded runtime scripts can be megabytes while the
            # visible listing is small. Apply the content cap after removing them.
            soup = BeautifulSoup(content, "html.parser")
            for tag in soup.find_all(["style", "script"]):
                if tag.get("type") != "application/ld+json":
                    tag.decompose()
            content = str(soup)
            if len(content.encode("utf-8")) > 2000000:
                return {"status": "oversized", "url": url, "text": ""}
            result = parse_html(content, page.url, url)
            all_links = {row["url"]: row for row in additional_links + result.get("job_links", [])}
            result["job_links"] = list(all_links.values())
            result["reader"] = "browser"
            result["rendered_at_url"] = page.url
            result["coverage"] = "当前公开页面；未承诺覆盖站内全部分页"
            return result
        except Error:
            return {"status": "browser_error", "url": url, "text": ""}
        finally:
            context.close()
