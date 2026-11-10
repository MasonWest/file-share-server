"""Optional browser regression: python scripts/check_search_ui.py (requires Playwright)."""
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_filesvc as fixture
from playwright.async_api import async_playwright


async def main():
    root = Path(fixture.SHARE_TMP)
    deep = root / "工作资料" / "合同"
    deep.mkdir(parents=True)
    (deep / "预算报表.pdf").write_text("nested")
    (root / "工作资料" / "说明.txt").write_text("other")
    for i in range(205):
        (root / f"report-{i:03}.txt").write_text("pagination")
    (deep / "report-205.txt").write_text("nested pagination")
    client = fixture.client()
    output = Path(tempfile.mkdtemp(prefix="filebox-ui-"))
    errors = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        await context.add_init_script("sessionStorage.setItem('admin_token', 'test-passphrase-2026')")
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        async def route_request(route):
            request = route.request
            url = urlsplit(request.url)
            query = parse_qs(url.query).get("q", [""])[0]
            if url.path.startswith("/api/list") and query == "slow":
                await asyncio.sleep(1)
            if url.path.startswith("/api/list") and query == "fail":
                await route.fulfill(status=500, json={"detail": "测试读取失败"})
                return
            response = client.request(request.method, url.path + ("?" + url.query if url.query else ""), headers=request.headers, content=request.post_data_buffer)
            headers = {k: v for k, v in response.headers.items() if k not in {"content-length", "content-encoding"}}
            await route.fulfill(status=response.status_code, headers=headers, body=response.content)

        await page.route("**/*", route_request)
        await page.goto("http://filebox.test/")
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 200")
        await page.screenshot(path=str(output / "desktop.png"))
        search = page.locator(".search input")
        await search.fill("预算")
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 1 && document.querySelector('.row-file').textContent.includes('预算报表.pdf')")
        assert await page.locator(".entry-path").inner_text() == "位置：工作资料/合同"
        await page.locator(".row-file .share-action").click()
        assert await page.locator(".drawer.on .dr-head p").inner_text() == "工作资料/合同/预算报表.pdf"
        await page.get_by_role("button", name="关闭", exact=True).click()
        await page.locator(".row-file .location-link").click()
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 2")
        assert await search.input_value() == ""
        navigation = page.get_by_role("navigation", name="文件列表目录导航")
        assert await navigation.locator('[aria-current="page"]').inner_text() == "合同"
        await navigation.get_by_role("button", name="工作资料", exact=True).click()
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 1")
        assert "说明.txt" in await page.locator(".row-file").inner_text()
        await page.get_by_role("button", name="返回上一级目录", exact=True).click()
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 200")
        assert await page.locator(".list-up").count() == 0
        await page.locator(".folder-link").click()
        await navigation.get_by_role("button", name="根目录", exact=True).click()
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 200")
        await search.fill("report")
        await page.wait_for_function("document.querySelector('.card-head .pill').textContent.includes('206')")
        await page.locator(".more-row button").click()
        await page.wait_for_function("document.querySelectorAll('.row-file').length === 206")
        assert await page.locator(".row-file", has_text="report-205.txt").count() == 1
        await search.fill("slow")
        await page.wait_for_timeout(350)
        await search.fill("预算")
        await page.wait_for_timeout(1400)
        assert await page.locator(".row-file").count() == 1
        assert "预算报表.pdf" in await page.locator(".row-file").inner_text()
        await search.fill("no-such-file")
        await page.locator(".table-wrap .empty").wait_for()
        await search.fill("fail")
        await page.locator(".list-status[role=alert]").wait_for()
        assert await page.locator(".table-wrap .empty").count() == 0
        await search.fill("预算")
        await page.locator(".row-file").wait_for()
        for toast in await page.locator(".toast .x").all():
            await toast.click()
        await page.screenshot(path=str(output / "search.png"), full_page=True)
        for width in [360, 390, 768]:
            await page.set_viewport_size({"width": width, "height": 844})
            await page.wait_for_timeout(350)
            dimensions = await page.evaluate("({width: innerWidth, content: document.documentElement.scrollWidth})")
            assert dimensions["content"] == width, dimensions
            for button in await page.locator(".row-file .row-actions button").all():
                box = await button.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
            await page.screenshot(path=str(output / f"search-{width}.png"), full_page=True)
        await page.locator(".icon-btn").first.click()
        await page.wait_for_timeout(350)
        await page.screenshot(path=str(output / "dark.png"), full_page=True)
        mobile_context = await browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
        await mobile_context.add_init_script("sessionStorage.setItem('admin_token', 'test-passphrase-2026')")
        mobile = await mobile_context.new_page()
        await mobile.route("**/*", route_request)
        await mobile.goto("http://filebox.test/")
        await mobile.locator(".row-dir").wait_for()
        assert await mobile.locator(".dz-touch").is_visible()
        await mobile.locator(".folder-link").click()
        await mobile.wait_for_function("document.querySelectorAll('.row-file').length === 1")
        assert "说明.txt" in await mobile.locator(".row-file").inner_text()
        await mobile.locator(".folder-link").click()
        await mobile.wait_for_function("document.querySelectorAll('.row-file').length === 2")
        mobile_navigation = mobile.get_by_role("navigation", name="文件列表目录导航")
        for width in [360, 390]:
            await mobile.set_viewport_size({"width": width, "height": 844})
            assert await mobile.evaluate("document.documentElement.scrollWidth === innerWidth")
            for button in [mobile.locator(".list-up"), mobile_navigation.get_by_role("button", name="根目录", exact=True)]:
                box = await button.bounding_box()
                assert box and box["x"] >= 0 and box["x"] + box["width"] <= width
        await mobile.screenshot(path=str(output / "touch-mobile.png"), full_page=True)
        await mobile.get_by_role("button", name="返回上一级目录", exact=True).click()
        await mobile.wait_for_function("document.querySelectorAll('.row-file').length === 1")
        await mobile_navigation.get_by_role("button", name="根目录", exact=True).click()
        await mobile.wait_for_function("document.querySelectorAll('.row-file').length === 200")
        assert await mobile.locator(".list-up").count() == 0
        assert not errors, errors
        await browser.close()
    print(json.dumps({"status": "passed", "checks": ["recursive search", "full result paths", "share path", "open parent and clear query", "clickable folder breadcrumbs", "parent and root navigation on desktop and touch mobile", "pagination", "stale request", "empty and failure states", "responsive 360/390/768", "dark theme", "no browser errors"], "screenshots": str(output)}))


if __name__ == "__main__":
    asyncio.run(main())
