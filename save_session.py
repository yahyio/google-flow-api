import os
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

async def main():
    session_file = Path("auth/session.json")
    session_file.parent.mkdir(parents=True, exist_ok=True)

    storage = str(session_file) if session_file.exists() and session_file.stat().st_size > 0 else None
    exec_path = CHROME_EXE if os.path.exists(CHROME_EXE) else None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=exec_path,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
            ignore_default_args=["--enable-automation"]
        )
        context = await browser.new_context(
            storage_state=storage,
            no_viewport=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        page = await context.new_page()

        await page.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
        """)

        await page.goto("https://flow.google.com/")
        print("Lutfen acilan Chrome penceresinde Google hesabiniza giris yapin.")
        print("Flow arayuzu veya proje sayfasi acildiginda oturum otomatik olarak algilanacaktir...")

        logged_in = False
        for _ in range(300):
            await asyncio.sleep(1.0)
            try:
                cur_url = page.url
                if "/project" in cur_url:
                    logged_in = True
                    break

                target = await page.query_selector('div.ProseMirror, a[href*="/project/"], button:has-text("Yeni proje"), button:has-text("New project"), a.project-card, [aria-label*="Yeni proje"]')
                if target:
                    logged_in = True
                    break
            except Exception:
                pass

        if not logged_in:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, input, "Otomatik algilanamadiysa giris yaptiktan sonra ENTER tusuna basin: ")

        await asyncio.sleep(2.0)
        await context.storage_state(path=str(session_file))
        print("Giris basarili! Oturum kaydedildi:", session_file.resolve())
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
