import os
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def main():
    base_dir = Path(__file__).resolve().parent
    session_file = base_dir / "auth" / "session.json"
    session_file.parent.mkdir(parents=True, exist_ok=True)

    storage = str(session_file) if session_file.exists() and session_file.stat().st_size > 0 else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=storage,
            viewport={"width": 1600, "height": 1000},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        page = await context.new_page()

        await page.goto("https://flow.google.com/", wait_until="domcontentloaded")
        print("Lutfen acilan pencerede Google hesabiniza giris yapin.")
        print("Flow proje ekrani acildiginda oturum otomatik olarak kaydedilecektir...")

        logged_in = False
        for _ in range(300):
            await asyncio.sleep(1.0)
            try:
                cur_url = page.url
                if "accounts.google.com" in cur_url:
                    continue
                target = await page.query_selector(
                    'div.ProseMirror, a[href*="/project/"], button:has-text("Yeni proje"), button:has-text("New project")'
                )
                if target:
                    logged_in = True
                    break
            except Exception:
                pass

        if not logged_in:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input, "Giris yaptiktan sonra ENTER tusuna basin: ")

        await asyncio.sleep(3.0)
        await context.storage_state(path=str(session_file))
        print("Giris basarili! Oturum kaydedildi:", session_file.resolve())
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
