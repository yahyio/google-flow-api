import os
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


async def main():
    base_dir = Path(__file__).resolve().parent
    profile_dir = base_dir / "auth" / "chrome_profile"
    session_file = base_dir / "auth" / "session.json"
    profile_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1600, "height": 1000},
            locale="tr-TR",
            timezone_id="Europe/Istanbul"
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://accounts.google.com/ServiceLogin?continue=https://flow.google.com/", wait_until="domcontentloaded")
        print("Lutfen acilan kalici profil penceresinde Google hesabiniza giris yapin.")
        print("Bu profil diske (auth/chrome_profile) kaydedilecegi icin bir daha cikis yapmaz.")

        for _ in range(300):
            await asyncio.sleep(1.0)
            try:
                cur_url = page.url
                if "accounts.google.com" in cur_url or "/about" in cur_url:
                    continue
                target = await page.query_selector(
                    'div.ProseMirror, a[href*="/project/"], button:has-text("Yeni proje"), button:has-text("New project")'
                )
                if target:
                    break
            except Exception:
                pass

        await asyncio.sleep(3.0)
        try:
            await context.storage_state(path=str(session_file))
        except Exception:
            pass
        print("Kalici profil kaydedildi:", profile_dir.resolve())
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
