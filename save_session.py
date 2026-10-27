import os
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

async def main():
    os.makedirs("auth", exist_ok=True)
    session_file = "auth/session.json"
    storage = session_file if os.path.exists(session_file) else None

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
        await page.goto("https://flow.google.com/")
        print("Lutfen acilan tarayicida Google hesabinizla oturum acin ve Flow ana sayfasina/projenize girin.")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, input, "Giris tamamlandiktan sonra burada ENTER tusuna basin: ")
        await context.storage_state(path=session_file)
        print(f"Yeni oturum basariyla kaydedildi: {os.path.abspath(session_file)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
