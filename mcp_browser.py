import html, re, asyncio, base64
from mcp.server.fastmcp import FastMCP
from playwright.async_api import async_playwright

mcp = FastMCP("browser", instructions="""
Headless browser tools using Playwright.
Use for JavaScript-heavy pages that requests can't handle.
Note: Reuters blocks headless browsers entirely; try search_web instead.
""")

_playwright = None
_browser = None

async def _ensure_browser() -> None:
    global _playwright, _browser
    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-gpu", "--disable-dev-shm-usage"]
        )

async def _new_page() -> tuple:
    await _ensure_browser()
    ctx = await _browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    page = await ctx.new_page()
    await page.route("**/*", lambda route, request:
        route.abort() if request.resource_type in ("image", "media", "font", "stylesheet")
        else route.continue_())
    return page, ctx

@mcp.tool(
    name="browser_fetch",
    description="Fetch content menggunakan headless browser. Untuk situs JS-heavy yang requests biasa tidak handle."
)
async def browser_fetch(url: str, max_chars: int = 10000) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        page, ctx = await _new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(1000)
        text = await page.inner_text("body")
        await ctx.close()
        text = re.sub(r'\s+', ' ', text).strip()
        text = html.unescape(text)
        text = text.replace('\ufeff', '')
        if not text:
            return "(page loaded but no text content detected)"
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[...truncated]"
        return text
    except Exception as e:
        return f"(browser error: {e})"

@mcp.tool(
    name="screenshot",
    description="Ambil screenshot dari URL dan return base64 PNG"
)
async def screenshot(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        page, ctx = await _new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        data = base64.b64encode(await page.screenshot(full_page=False)).decode()
        await ctx.close()
        return f"data:image/png;base64,{data}"
    except Exception as e:
        return f"(screenshot error: {e})"

if __name__ == "__main__":
    mcp.run(transport="stdio")
