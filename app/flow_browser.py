import os
import sys
import asyncio
import base64
import time
import json
import tempfile
from typing import Optional, Dict, Any
import requests
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from app.config import settings
from app.models import ImageModel, AspectRatio

CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

class FlowBrowserSession:
    _instance: Optional["FlowBrowserSession"] = None
    
    def __init__(self):
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.lock = asyncio.Lock()
        self._is_initialized = False
        self.last_error: Optional[str] = None
        self.last_screenshot: Optional[bytes] = None

    @classmethod
    def get_instance(cls) -> "FlowBrowserSession":
        if cls._instance is None:
            cls._instance = FlowBrowserSession()
        return cls._instance

    async def _cleanup(self):
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        self.page = None

        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        self.context = None

        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        self.browser = None

        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass
        self.playwright = None

    async def warmup(self):
        try:
            await asyncio.sleep(4)
            session_file = settings.SESSION_STORAGE_PATH
            if not os.path.isabs(session_file):
                session_file = os.path.abspath(session_file)
            has_env = bool(os.getenv("SESSION_JSON") or os.getenv("SESSION_BASE64"))
            if os.path.exists(session_file) or has_env:
                await self.initialize()
        except Exception as e:
            self.last_error = str(e)

    async def initialize(self):
        if self._is_initialized and self.page and not self.page.is_closed():
            return

        async with self.lock:
            if self._is_initialized and self.page and not self.page.is_closed():
                return

            try:
                self.playwright = await async_playwright().start()

                launch_args = [
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-software-rasterizer",
                    "--disable-infobars",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--renderer-process-limit=1",
                    "--mute-audio",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-breakpad",
                    "--disable-component-update",
                    "--disable-default-apps",
                    "--disable-domain-reliability",
                    "--disable-sync",
                    "--js-flags=--max-old-space-size=160"
                ]

                session_file = settings.SESSION_STORAGE_PATH
                if not os.path.isabs(session_file):
                    session_file = os.path.abspath(session_file)

                if not os.path.exists(session_file) or os.path.getsize(session_file) == 0:
                    session_base64 = os.getenv("SESSION_BASE64")
                    session_raw = os.getenv("SESSION_JSON")
                    if session_base64:
                        os.makedirs(os.path.dirname(session_file), exist_ok=True)
                        with open(session_file, "wb") as f:
                            f.write(base64.b64decode(session_base64.strip()))
                    elif session_raw:
                        session_raw = session_raw.strip()
                        if (session_raw.startswith("'") and session_raw.endswith("'")) or (session_raw.startswith('"') and session_raw.endswith('"')):
                            session_raw = session_raw[1:-1].strip()
                        os.makedirs(os.path.dirname(session_file), exist_ok=True)
                        with open(session_file, "w", encoding="utf-8") as f:
                            f.write(session_raw)

                if not os.path.exists(session_file) or os.path.getsize(session_file) == 0:
                    raise RuntimeError("Oturum dosyasi bulunamadi. Render Environment ayarlarina SESSION_JSON veya SESSION_BASE64 ekleyin.")

                try:
                    with open(session_file, "r", encoding="utf-8") as f:
                        json.load(f)
                except Exception as e:
                    raise RuntimeError(f"Oturum dosyasi gecerli bir JSON formati degil: {e}")

                exec_path = CHROME_EXE if (sys.platform == "win32" and os.path.exists(CHROME_EXE)) else None

                self.browser = await self.playwright.chromium.launch(
                    executable_path=exec_path,
                    headless=settings.HEADLESS,
                    args=launch_args,
                    ignore_default_args=["--enable-automation"]
                )
                self.context = await self.browser.new_context(
                    storage_state=session_file,
                    viewport={"width": 1280, "height": 720} if settings.HEADLESS else None,
                    no_viewport=not settings.HEADLESS,
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                    locale="tr-TR",
                    timezone_id="Europe/Istanbul"
                )

                self.page = await self.context.new_page()

                await self.page.add_init_script("""
                    delete Object.getPrototypeOf(navigator).webdriver;
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {}, app: {} };
                    Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
                """)

                await self.page.goto("https://flow.google.com/", wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(2)

                cur_url = self.page.url
                if "accounts.google.com" in cur_url or "/about" in cur_url:
                    raise RuntimeError(f"Google oturumunuzun suresi dolmus veya cikis yapilmis (URL: {cur_url}). Lutfen 'login.bat' veya 'python save_session.py' calistirarak yeniden giris yapin.")

                for btn_text in ["Anladım", "Got it", "Kabul ediyorum", "Accept all", "Tümünü kabul et", "Devam et", "Continue"]:
                    dismiss_btn = await self.page.query_selector(f'button:has-text("{btn_text}")')
                    if dismiss_btn:
                        try:
                            await dismiss_btn.click()
                            await asyncio.sleep(1)
                        except Exception:
                            pass

                prose = await self.page.query_selector("div.ProseMirror")
                if not prose:
                    try:
                        await self.page.wait_for_selector('a[href*="/project/"], button:has-text("Yeni proje"), button:has-text("New project"), button:has-text("Yeni"), button:has-text("New")', timeout=15000)
                    except Exception:
                        pass

                    cur_url = self.page.url
                    if "accounts.google.com" in cur_url:
                        raise RuntimeError(f"Google oturumu gecersiz. Yonlendirildi: {cur_url}")

                    project_link = await self.page.query_selector('a[href*="/project/"]')
                    if project_link:
                        project_url = await project_link.get_attribute("href")
                        if not project_url.startswith("http"):
                            project_url = "https://flow.google.com" + project_url
                        await self.page.goto(project_url, wait_until="domcontentloaded", timeout=30000)
                    else:
                        new_proj_btn = await self.page.query_selector('button:has-text("Yeni proje"), button:has-text("New project"), button:has-text("Yeni"), button:has-text("New")')
                        if new_proj_btn:
                            await new_proj_btn.click()
                            await self.page.wait_for_timeout(3000)

                await self.page.wait_for_selector("div.ProseMirror", timeout=35000)
                self._is_initialized = True
                self.last_error = None
            except Exception as e:
                self.last_error = str(e)
                self._is_initialized = False
                try:
                    if self.page and not self.page.is_closed():
                        self.last_screenshot = await self.page.screenshot(full_page=False)
                except Exception:
                    pass
                await self._cleanup()
                raise e

    async def _attach_reference_image(self, image_base64: Optional[str] = None, image_url: Optional[str] = None):
        if not image_base64 and not image_url:
            return

        temp_path = None
        try:
            if image_base64:
                if "," in image_base64:
                    image_base64 = image_base64.split(",")[1]
                img_bytes = base64.b64decode(image_base64)
            elif image_url:
                resp = requests.get(image_url, timeout=30)
                resp.raise_for_status()
                img_bytes = resp.content

            fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.write(fd, img_bytes)
            os.close(fd)

            add_btn = self.page.locator('button[aria-label*="İçerik öğelerini istem kutusuna ekle"]').last
            if not (await add_btn.count() and await add_btn.is_visible()):
                return

            await add_btn.click()
            await self.page.wait_for_timeout(800)

            upload_btn = self.page.locator('.cdk-overlay-container button.upload-button, .cdk-overlay-container button[aria-label*="Medya yükle"]').first
            if not (await upload_btn.count()):
                await self.page.keyboard.press("Escape")
                return

            async with self.page.expect_file_chooser(timeout=10000) as fc_info:
                await upload_btn.click(force=True)

            file_chooser = await fc_info.value
            await file_chooser.set_files(temp_path)
            await self.page.wait_for_timeout(2000)

            accept = self.page.locator('button:has-text("Kabul ediyorum"), button:has-text("I agree")')
            if await accept.count():
                try:
                    await accept.first.click()
                    await self.page.wait_for_timeout(1500)
                except Exception:
                    pass

            for _ in range(15):
                spinners = await self.page.query_selector_all('.mat-mdc-progress-spinner, mat-spinner')
                if not spinners:
                    break
                await asyncio.sleep(1.0)

        except Exception:
            pass
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    async def _handle_retry_if_present(self):
        retry_btn = self.page.locator('button:has-text("Tekrar dene"), button:has-text("Try again")')
        if await retry_btn.count() and await retry_btn.first.is_visible():
            try:
                await retry_btn.first.click()
                await asyncio.sleep(2.0)
                return True
            except Exception:
                pass
        return False

    async def _stop_trailing_generation_if_active(self):
        stop_selectors = [
            'button[aria-label*="Durdur"]',
            'button[aria-label*="Stop"]',
            'button:has(mat-icon:has-text("stop"))',
            'button:has(mat-icon:has-text("pause"))'
        ]
        for sel in stop_selectors:
            stop_btn = self.page.locator(sel)
            if await stop_btn.count() and await stop_btn.first.is_visible():
                try:
                    await stop_btn.first.click()
                    await asyncio.sleep(1.5)
                    return True
                except Exception:
                    pass
        return False

    async def _wait_until_ready_for_input(self):
        await self._stop_trailing_generation_if_active()
        for _ in range(15):
            stop_active = False
            for sel in ['button[aria-label*="Durdur"]', 'button:has(mat-icon:has-text("stop"))']:
                loc = self.page.locator(sel)
                if await loc.count() and await loc.first.is_visible():
                    stop_active = True
                    try:
                        await loc.first.click()
                    except Exception:
                        pass
                    break
            if not stop_active:
                gen_btn = self.page.locator('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]').last
                if await gen_btn.count() and await gen_btn.is_visible():
                    break
            await asyncio.sleep(1.0)

    async def generate_image(
        self,
        prompt: str,
        model: ImageModel = ImageModel.NANO_BANANA_2_1,
        aspect_ratio: AspectRatio = AspectRatio.RATIO_16_9,
        seed: Optional[int] = None,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        await self.initialize()

        async with self.lock:
            start_time = time.time()
            try:
                await self._wait_until_ready_for_input()

                initial_count = await self.page.evaluate("""
                    () => document.querySelectorAll('img[alt*="Option"]').length
                """)

                if image_base64 or image_url:
                    await self._attach_reference_image(image_base64=image_base64, image_url=image_url)

                editor = await self.page.query_selector("div.ProseMirror")
                if not editor:
                    project_link = await self.page.query_selector('a[href*="/project/"]')
                    if project_link:
                        url = await project_link.get_attribute("href")
                        if not url.startswith("http"):
                            url = "https://flow.google.com" + url
                        await self.page.goto(url, wait_until="domcontentloaded")
                        await self.page.wait_for_selector("div.ProseMirror", timeout=20000)
                        editor = await self.page.query_selector("div.ProseMirror")

                if not editor:
                    raise RuntimeError("Editor not found")

                await editor.click()
                await self.page.keyboard.press("Control+A")
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(0.1)
                await self.page.keyboard.type(prompt, delay=2)
                await asyncio.sleep(0.4)

                gen_btn = self.page.locator('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]').last
                if await gen_btn.count():
                    await gen_btn.click()
                else:
                    await self.page.keyboard.press("Enter")

                await asyncio.sleep(1.0)

                if (await editor.inner_text()).strip():
                    await editor.click()
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(1.0)

                if (await editor.inner_text()).strip() and await gen_btn.count():
                    try:
                        await gen_btn.click(force=True)
                        await asyncio.sleep(1.0)
                    except Exception:
                        pass

                timeout = settings.GENERATION_TIMEOUT
                elapsed = 0
                new_image_found = False

                while elapsed < timeout:
                    await asyncio.sleep(1.0)
                    elapsed += 1.0

                    if await self._handle_retry_if_present():
                        elapsed = 0

                    current_count = await self.page.evaluate("""
                        () => document.querySelectorAll('img[alt*="Option"]').length
                    """)
                    if current_count > initial_count:
                        new_image_found = True
                        break

                if not new_image_found:
                    raise TimeoutError(f"Image generation timeout after {timeout} seconds")

                await asyncio.sleep(1.5)

                img_data = await self.page.evaluate("""
                    () => {
                        const imgs = document.querySelectorAll('img[alt*="Option"]');
                        const lastImg = imgs[imgs.length - 1];
                        if (!lastImg) return null;

                        const canvas = document.createElement('canvas');
                        canvas.width = lastImg.naturalWidth;
                        canvas.height = lastImg.naturalHeight;
                        const ctx = canvas.getContext('2d');
                        ctx.drawImage(lastImg, 0, 0);

                        return {
                            src: lastImg.src,
                            dataUrl: canvas.toDataURL('image/png'),
                            width: lastImg.naturalWidth,
                            height: lastImg.naturalHeight
                        };
                    }
                """)

                await self._stop_trailing_generation_if_active()

                if not img_data or not img_data.get("dataUrl"):
                    raise RuntimeError("Failed to extract image from canvas")

                data_url = img_data["dataUrl"]
                base64_data = data_url.split(",")[1] if "," in data_url else data_url
                image_bytes = base64.b64decode(base64_data)

                exec_time = round(time.time() - start_time, 2)

                return {
                    "image_url": img_data["src"],
                    "image_base64": base64_data,
                    "image_bytes": image_bytes,
                    "width": img_data["width"],
                    "height": img_data["height"],
                    "execution_time_seconds": exec_time
                }
            except Exception as e:
                self.last_error = str(e)
                try:
                    if self.page and not self.page.is_closed():
                        self.last_screenshot = await self.page.screenshot(full_page=False)
                except Exception:
                    pass
                raise e

    async def close(self):
        async with self.lock:
            await self._cleanup()
            self._is_initialized = False
