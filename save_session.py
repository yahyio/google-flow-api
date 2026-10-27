import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

async def main():
    os.makedirs("auth", exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        await page.goto("https://flow.google.com/")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "Giris yaptiktan sonra ENTER tusuna basin: ")
        await context.storage_state(path="auth/session.json")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
