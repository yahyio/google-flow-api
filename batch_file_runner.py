import os
import sys
import re
import asyncio
import base64
import time
import random
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

SESSION_PATH = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\session.json")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FLOW_URL = "https://flow.google.com/"

def parse_prompt_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")

    ref_match = re.search(r"Flow'da her prompt'tan önce (.+?) dosyasını", content)
    ref_file_rel = ref_match.group(1).strip() if ref_match else None

    out_match = re.search(r"Çıkan resmi (.+?) klasörüne", content)
    out_dir_rel = out_match.group(1).strip() if out_match else None

    scenes = []
    pattern = r"=== SAHNE\s+(\d+)\s*===\s*\n(.*?)(?=\n=== SAHNE|\Z)"
    for m in re.finditer(pattern, content, re.DOTALL):
        scene_num = int(m.group(1))
        prompt_text = m.group(2).strip()
        scenes.append((scene_num, prompt_text))

    return ref_file_rel, out_dir_rel, scenes

async def open_flow_project(page):
    await page.goto(FLOW_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    link = await page.query_selector('a[href*="/project/"]')
    if link:
        href = await link.get_attribute("href")
        url = href if href.startswith("http") else "https://flow.google.com" + href
        await page.goto(url, wait_until="domcontentloaded")
    else:
        btn = await page.query_selector('button:has-text("Yeni proje"), button:has-text("New project")')
        if btn:
            await btn.click()
    await page.wait_for_selector("div.ProseMirror", timeout=45000)

async def attach_reference(page, ref_path: Path):
    add_btn = page.locator('button[aria-label*="İçerik öğelerini istem kutusuna ekle"]').last
    if not (await add_btn.count() and await add_btn.is_visible()):
        return

    await add_btn.click()
    await page.wait_for_timeout(800)

    upload_btn = page.locator('.cdk-overlay-container button.upload-button, .cdk-overlay-container button[aria-label*="Medya yükle"]').first
    if not (await upload_btn.count()):
        await page.keyboard.press("Escape")
        return

    async with page.expect_file_chooser(timeout=10000) as fc_info:
        await upload_btn.click(force=True)

    file_chooser = await fc_info.value
    await file_chooser.set_files(str(ref_path))
    await page.wait_for_timeout(2500)

    accept = page.locator('button:has-text("Kabul ediyorum"), button:has-text("I agree")')
    if await accept.count():
        try:
            await accept.first.click()
            await page.wait_for_timeout(1500)
        except Exception:
            pass

    for _ in range(15):
        spinners = await page.query_selector_all('.mat-mdc-progress-spinner, mat-spinner')
        if not spinners:
            break
        await asyncio.sleep(1.0)

async def handle_retry_if_present(page):
    retry_btn = page.locator('button:has-text("Tekrar dene"), button:has-text("Try again")')
    if await retry_btn.count() and await retry_btn.first.is_visible():
        try:
            await retry_btn.first.click()
            await asyncio.sleep(2.0)
            return True
        except Exception:
            pass
    return False

async def stop_trailing_generation_if_active(page):
    stop_selectors = [
        'button[aria-label*="Durdur"]',
        'button[aria-label*="Stop"]',
        'button:has(mat-icon:has-text("stop"))',
        'button:has(mat-icon:has-text("pause"))'
    ]
    for sel in stop_selectors:
        stop_btn = page.locator(sel)
        if await stop_btn.count() and await stop_btn.first.is_visible():
            try:
                await stop_btn.first.click()
                await asyncio.sleep(1.5)
                return True
            except Exception:
                pass
    return False

async def wait_until_ready_for_input(page):
    await stop_trailing_generation_if_active(page)
    for _ in range(15):
        stop_active = False
        for sel in ['button[aria-label*="Durdur"]', 'button:has(mat-icon:has-text("stop"))']:
            loc = page.locator(sel)
            if await loc.count() and await loc.first.is_visible():
                stop_active = True
                try:
                    await loc.first.click()
                except Exception:
                    pass
                break
        if not stop_active:
            gen_btn = page.locator('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]').last
            if await gen_btn.count() and await gen_btn.is_visible():
                break
        await asyncio.sleep(1.0)

async def save_rendered_image(page, img_el, out_path: Path):
    data_url = await img_el.evaluate("""img => {
        const c = document.createElement('canvas');
        c.width = img.naturalWidth;
        c.height = img.naturalHeight;
        c.getContext('2d').drawImage(img, 0, 0);
        return c.toDataURL('image/png');
    }""")
    raw = base64.b64decode(data_url.split(",", 1)[1])
    out_path.write_bytes(raw)

async def submit_prompt(page, prompt: str):
    await wait_until_ready_for_input(page)

    editor = await page.query_selector("div.ProseMirror")
    if not editor:
        await open_flow_project(page)
        editor = await page.query_selector("div.ProseMirror")

    await editor.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await asyncio.sleep(0.1)

    await page.keyboard.type(prompt, delay=2)
    await asyncio.sleep(0.4)

    gen_btn = page.locator('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]').last
    if await gen_btn.count():
        await gen_btn.click()
    else:
        await page.keyboard.press("Enter")

    await asyncio.sleep(1.0)

    if (await editor.inner_text()).strip():
        await editor.click()
        await page.keyboard.press("Enter")
        await asyncio.sleep(1.0)

    if (await editor.inner_text()).strip() and await gen_btn.count():
        try:
            await gen_btn.click(force=True)
            await asyncio.sleep(1.0)
        except Exception:
            pass

async def run_batch(file_path_str: str):
    file_path = Path(file_path_str).resolve()
    base_dir = file_path.parent.parent.parent
    ref_rel, out_rel, scenes = parse_prompt_file(file_path)

    ref_path = (base_dir / ref_rel).resolve() if ref_rel else None
    out_dir = (base_dir / out_rel).resolve() if out_rel else (file_path.parent / "sahneler").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pending_scenes = []
    for num, prompt in scenes:
        existing = list(out_dir.glob(f"sahne_{num:02d}_*.png"))
        if not existing:
            pending_scenes.append((num, prompt))

    print(f"Total scenes: {len(scenes)} | Pending scenes to generate: {len(pending_scenes)}")

    if not pending_scenes:
        print("All scenes already generated.")
        return

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        "--start-maximized"
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME_EXE if os.path.exists(CHROME_EXE) else None,
            headless=False,
            args=launch_args,
            ignore_default_args=["--enable-automation"]
        )

        context = await browser.new_context(
            storage_state=str(SESSION_PATH),
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

        await open_flow_project(page)

        for num, prompt in pending_scenes:
            print(f"Generating Scene {num:02d}...")

            for attempt in range(1, 4):
                try:
                    initial_count = await page.evaluate("() => document.querySelectorAll('img[alt*=\"Option\"]').length")

                    if ref_path and ref_path.exists():
                        print(f"Attaching reference: {ref_path.name}")
                        await attach_reference(page, ref_path)

                    await submit_prompt(page, prompt)

                    waited = 0
                    success = False
                    while waited < 90:
                        await asyncio.sleep(1.0)
                        waited += 1

                        if await handle_retry_if_present(page):
                            waited = 0

                        current_count = await page.evaluate("() => document.querySelectorAll('img[alt*=\"Option\"]').length")
                        if current_count > initial_count:
                            success = True
                            break

                    if not success:
                        raise TimeoutError(f"Scene {num} timed out")

                    await asyncio.sleep(1.5)

                    new_opts = await page.query_selector_all('img[alt*="Option"]')
                    if len(new_opts) >= 2:
                        target_imgs = new_opts[-2:]
                    elif len(new_opts) == 1:
                        target_imgs = [new_opts[-1]]
                    else:
                        target_imgs = []

                    for idx, img_el in enumerate(target_imgs, start=1):
                        dest_file = out_dir / f"sahne_{num:02d}_{idx}.png"
                        await save_rendered_image(page, img_el, dest_file)
                        print(f"Saved: {dest_file.name}")

                    await stop_trailing_generation_if_active(page)

                    delay = random.uniform(2.5, 4.0)
                    await asyncio.sleep(delay)
                    break

                except Exception as e:
                    print(f"Scene {num:02d} attempt {attempt} failed: {e}")
                    await handle_retry_if_present(page)
                    await stop_trailing_generation_if_active(page)
                    await page.screenshot(path=str(out_dir / f"_error_{num:02d}.png"))
                    await asyncio.sleep(2.0)
                    await open_flow_project(page)

        await browser.close()
        print("Batch processing completed.")

if __name__ == "__main__":
    target_file = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450\videolar\01-raccoons-smarter\kalan-promptlar.txt"
    asyncio.run(run_batch(target_file))
