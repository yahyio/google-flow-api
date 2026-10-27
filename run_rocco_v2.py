import os
import sys
import asyncio
import base64
import time
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

SESSION_PATH = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\session.json")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FLOW_URL = "https://flow.google.com/"

BASE_DIR = Path(r"C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450")
REF_IMAGE = BASE_DIR / "_marka" / "rocco_sheet.png"
OUTPUT_DIR = BASE_DIR / "_marka"

VARIATIONS = [
    (
        "A",
        "Redesign the raccoon from the attached sheet as a character for an adult animated sitcom aimed at grown-ups, not children. Keep his identity: gray fur, black eye mask, mustard-yellow hoodie, red sneakers, ringed tail, small notch in his left ear. New style: thin uniform black linework, flat muted colors, slightly lanky adult proportions, half-lidded tired eyes, dry sarcastic smirk, a few stubble-like fur tufts, subtle bags under the eyes. No big cute eyes, no chubby baby proportions. Character design sheet: front, 3/4, side, back view, plus 6 expressions (deadpan, shocked, smug, disgusted, thinking, exhausted). Plain light gray background, no text."
    ),
    (
        "B",
        "Redesign the raccoon from the attached sheet as the lead of an adult animated comedy series. Keep his identity: gray fur, black eye mask, mustard-yellow hoodie, red sneakers, ringed tail, small notch in his left ear. New style: thin wobbly black outlines, flat colors with simple hard shadows, wide unsettled eyes with small pupils, sharp toothy grin, slightly unkempt fur, wiry body, expressive but cynical. Mature comedic tone, not a kids' cartoon. Character design sheet: front, 3/4, side, back view, plus 6 expressions (manic grin, panicked, smug, horrified, scheming, unimpressed). Plain light gray background, no text."
    ),
    (
        "C",
        "Redesign the raccoon from the attached sheet as the narrator of an adult animated documentary-comedy. Keep his identity: gray fur, black eye mask, mustard-yellow hoodie, red sneakers, ringed tail, small notch in his left ear. New style: clean thin linework, flat desaturated palette with warm accents, realistic adult raccoon proportions standing upright, calm confident expression, raised eyebrow, slightly worn hoodie with rolled sleeves. Feels like a smart, slightly jaded storyteller, not a mascot for kids. Character design sheet: front, 3/4, side, back view, plus 6 expressions (knowing smirk, genuine surprise, concern, disbelief, explaining with a gesture, laughing). Plain light gray background, no text."
    )
]

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

async def submit_prompt(page, prompt: str):
    await wait_until_ready_for_input(page)
    editor = page.locator("div.ProseMirror")
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

async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pending = []
    for code, prompt in VARIATIONS:
        out1 = OUTPUT_DIR / f"rocco_v2_{code}_1.png"
        out2 = OUTPUT_DIR / f"rocco_v2_{code}_2.png"
        if not (out1.exists() and out2.exists()):
            pending.append((code, prompt, out1, out2))

    if not pending:
        print("All Rocco v2 variations already generated.")
        return

    print(f"Pending variations to generate: {[p[0] for p in pending]}")

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

        for code, prompt, out1, out2 in pending:
            print(f"Generating Rocco v2 Variation {code}...")

            for attempt in range(1, 4):
                try:
                    initial_count = await page.evaluate("() => document.querySelectorAll('img[alt*=\"Option\"]').length")

                    if REF_IMAGE.exists():
                        print(f"Attaching reference: {REF_IMAGE.name}")
                        await attach_reference(page, REF_IMAGE)

                    await submit_prompt(page, prompt)

                    waited = 0
                    success = False
                    while waited < 90:
                        await asyncio.sleep(1.0)
                        waited += 1

                        if await handle_retry_if_present(page):
                            waited = 0

                        current_count = await page.evaluate("() => document.querySelectorAll('img[alt*=\"Option\"]').length")
                        if current_count >= initial_count + 2:
                            success = True
                            break

                    if not success:
                        raise TimeoutError(f"Variation {code} timed out")

                    await asyncio.sleep(2.0)

                    images_data = await page.evaluate("""
                        () => {
                            const imgs = Array.from(document.querySelectorAll('img[alt*="Option"]')).slice(-2);
                            return imgs.map(img => {
                                const canvas = document.createElement('canvas');
                                canvas.width = img.naturalWidth;
                                canvas.height = img.naturalHeight;
                                const ctx = canvas.getContext('2d');
                                ctx.drawImage(img, 0, 0);
                                return canvas.toDataURL('image/png');
                            });
                        }
                    """)

                    if len(images_data) >= 1 and images_data[0]:
                        b64_1 = images_data[0].split(",")[1]
                        out1.write_bytes(base64.b64decode(b64_1))
                        print(f"Saved: {out1.name}")

                    if len(images_data) >= 2 and images_data[1]:
                        b64_2 = images_data[1].split(",")[1]
                        out2.write_bytes(base64.b64decode(b64_2))
                        print(f"Saved: {out2.name}")

                    await stop_trailing_generation_if_active(page)
                    break

                except Exception as e:
                    print(f"Variation {code} attempt {attempt} failed: {e}")
                    await stop_trailing_generation_if_active(page)
                    if attempt == 3:
                        print(f"Skipping Variation {code} after 3 attempts.")

        await browser.close()
        print("Completed Rocco v2 generation.")

if __name__ == "__main__":
    asyncio.run(main())
