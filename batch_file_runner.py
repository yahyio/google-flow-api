import os
import sys
import re
import asyncio
import base64
import random
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

SESSION_PATH = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\session.json")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FLOW_URL = "https://flow.google.com/"
DEFAULT_TARGET = r"C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450\videolar\03-humans-vanished\kalan-promptlar.txt"

STYLE_V2 = (
    "Style: adult animated sitcom, thin uniform black linework, flat muted colors, simple hard shadows, "
    "same style as the attached sheet, not a kids' cartoon. Keep the scene simple: a plain flat "
    "single-color background and at most one or two objects. 16:9 landscape, no text, no letters, no watermark."
)
ROCCO_V2 = (
    "Using the attached character sheet, draw Rocco the raccoon EXACTLY as designed (same tired half-lidded "
    "eyes, black eye mask, mustard-yellow hoodie, gray pants, red sneakers, ringed tail). Scene: {scene}. "
)
WORLD_V2 = (
    "Use the attached character sheet ONLY as a style reference; Rocco does not appear in this image. "
    "Any raccoons or animals are ordinary animals without clothes. Scene: {scene}. "
)

def parse_prompt_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")

    if file_path.name.lower() == "senaryo.md":
        scenes = []
        for line in content.splitlines():
            m = re.match(r"^\| (\d+) \| (.+?) \| (.+?) \|$", line)
            if m:
                scene_num = int(m.group(1))
                scene_desc = m.group(3).strip()
                prefix = ROCCO_V2 if "Rocco" in scene_desc else WORLD_V2
                scenes.append((scene_num, prefix.format(scene=scene_desc) + STYLE_V2))
        return "rocco_sheet_v2.png", None, scenes

    header_part = content.split("=== SAHNE")[0]
    ref_match = re.search(r"Flow'da her prompt'tan önce (.+?) dosyasını", header_part)
    if not ref_match:
        ref_match = re.search(r"([a-zA-Z0-9_./\\-]+\.png)", header_part)
    ref_file_rel = ref_match.group(1).strip() if ref_match else "rocco_sheet_v2.png"

    out_match = re.search(r"Çıkan resmi (.+?) klasörüne", header_part)
    out_dir_rel = out_match.group(1).strip() if out_match else None

    scenes = []
    pattern = r"=== SAHNE\s+(\d+)\s*===\s*\n(.*?)(?=\n=== SAHNE|\Z)"
    for m in re.finditer(pattern, content, re.DOTALL):
        scene_num = int(m.group(1))
        prompt_text = m.group(2).strip()
        scenes.append((scene_num, prompt_text))

    return ref_file_rel, out_dir_rel, scenes

def resolve_reference_path(base_dir: Path, video_dir: Path, ref_rel: str | None) -> Path | None:
    candidates = []
    if ref_rel:
        candidates.append(base_dir / ref_rel)
        candidates.append(base_dir / "_marka" / Path(ref_rel).name)
        candidates.append(video_dir / ref_rel)
    candidates.append(base_dir / "_marka" / "rocco_sheet_v2.png")
    candidates.append(base_dir / "_marka" / "rocco_sheet.png")
    for c in candidates:
        if c.exists():
            return c.resolve()
    return None

async def open_flow_project(page):
    await page.goto(FLOW_URL, wait_until="domcontentloaded", timeout=35000)
    await page.wait_for_timeout(2500)

    if "/about" in page.url:
        cta = page.locator('button:has-text("Google Flow ile oluştur"), button:has-text("Google Flow\'u deneyin"), button:has-text("Try Google Flow")').first
        if await cta.count():
            try:
                await cta.click()
                await page.wait_for_timeout(3000)
            except Exception:
                pass

    for btn_text in ["Anladım", "Got it", "Kabul ediyorum", "Accept all", "Tümünü kabul et", "Devam et", "Continue"]:
        dismiss_btn = await page.query_selector(f'button:has-text("{btn_text}")')
        if dismiss_btn:
            try:
                await dismiss_btn.click()
                await page.wait_for_timeout(800)
            except Exception:
                pass

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass

    editor = await page.query_selector("div.ProseMirror")
    if not editor:
        try:
            await page.wait_for_selector('a[href*="/project/"], button:has-text("Yeni proje"), button:has-text("New project"), button:has-text("Yeni"), button:has-text("New")', timeout=15000)
        except Exception:
            pass

        link = await page.query_selector('a[href*="/project/"]')
        if link:
            href = await link.get_attribute("href")
            url = href if href.startswith("http") else "https://flow.google.com" + href
            await page.goto(url, wait_until="domcontentloaded", timeout=35000)
        else:
            btn = await page.query_selector('button:has-text("Yeni proje"), button:has-text("New project"), button:has-text("Yeni"), button:has-text("New")')
            if btn:
                await btn.click()
                await page.wait_for_timeout(3000)

    await page.wait_for_selector("div.ProseMirror", timeout=45000)

async def attach_reference(page, ref_path: Path):
    try:
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
    except Exception:
        pass

    add_btn = page.locator('button[aria-label*="İçerik öğelerini istem kutusuna ekle"], button[aria-label*="Add content"]').last
    if not (await add_btn.count() and await add_btn.is_visible()):
        return

    await add_btn.click()
    await page.wait_for_timeout(1000)

    search_input = page.locator('input[placeholder="Öğe arayın"], input[placeholder*="Search"]').first
    if await search_input.count() and await search_input.is_visible():
        await search_input.fill(ref_path.stem)
        await page.wait_for_timeout(1300)
        lib_item = page.locator(f'.cdk-overlay-container button:has-text("{ref_path.name}")').first
        if await lib_item.count() and await lib_item.is_visible():
            await lib_item.click()
            await page.wait_for_timeout(1000)
            confirm = page.locator('button:has-text("İsteme ekle"), button:has-text("Add to prompt")').first
            if await confirm.count() and await confirm.is_visible():
                await confirm.click()
                await page.wait_for_timeout(1200)
            return

    upload_btn = page.locator('.cdk-overlay-container button.upload-button, .cdk-overlay-container button[aria-label*="Medya yükle"], button:has-text("Medya yükle")').first
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

    confirm = page.locator('button:has-text("İsteme ekle"), button:has-text("Add to prompt")').first
    if await confirm.count() and await confirm.is_visible():
        await confirm.click()
        await page.wait_for_timeout(1200)

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

async def get_rendered_image_srcs(page) -> list[str]:
    return await page.evaluate("""() => {
        const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'));
        return imgs
            .filter(i => i.complete && i.naturalWidth > 200 && i.src)
            .map(i => i.src);
    }""")

async def get_settled_image_srcs(page) -> set[str]:
    last_count = -1
    stable = 0
    srcs = []
    for _ in range(15):
        srcs = await get_rendered_image_srcs(page)
        if len(srcs) == last_count:
            stable += 1
            if stable >= 2:
                break
        else:
            stable = 0
        last_count = len(srcs)
        await asyncio.sleep(0.8)
    return set(srcs)

async def save_image_by_src(page, context, src: str, out_path: Path) -> bool:
    if src.startswith("http"):
        try:
            resp = await context.request.get(src)
            if resp.ok:
                out_path.write_bytes(await resp.body())
                return True
        except Exception:
            pass

    data_url = await page.evaluate("""(targetSrc) => {
        const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'));
        const img = imgs.find(i => i.src === targetSrc);
        if (!img || !img.naturalWidth) return null;
        const c = document.createElement('canvas');
        c.width = img.naturalWidth;
        c.height = img.naturalHeight;
        c.getContext('2d').drawImage(img, 0, 0);
        return c.toDataURL('image/png');
    }""", src)

    if data_url and "," in data_url:
        raw = base64.b64decode(data_url.split(",", 1)[1])
        out_path.write_bytes(raw)
        return True
    return False

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

async def run_batch(target_str: str):
    target_path = Path(target_str).resolve()
    if target_path.is_dir():
        if (target_path / "kalan-promptlar.txt").exists():
            file_path = (target_path / "kalan-promptlar.txt").resolve()
        elif (target_path / "senaryo.md").exists():
            file_path = (target_path / "senaryo.md").resolve()
        else:
            raise FileNotFoundError(f"kalan-promptlar.txt veya senaryo.md bulunamadi: {target_path}")
    else:
        file_path = target_path

    video_dir = file_path.parent
    base_dir = video_dir.parent.parent
    ref_rel, out_rel, scenes = parse_prompt_file(file_path)

    ref_path = resolve_reference_path(base_dir, video_dir, ref_rel)
    if out_rel and (base_dir / out_rel).exists():
        out_dir = (base_dir / out_rel).resolve()
    else:
        out_dir = (video_dir / "sahneler").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pending_scenes = []
    for num, prompt in scenes:
        existing = list(out_dir.glob(f"sahne_{num:02d}_*.png"))
        if not existing:
            pending_scenes.append((num, prompt))

    print(f"Hedef klasor: {video_dir.name}")
    print(f"Referans gorsel: {ref_path if ref_path else 'Yok'}")
    print(f"Toplam sahne: {len(scenes)} | Uretilecek kalan sahne: {len(pending_scenes)}", flush=True)

    if not pending_scenes:
        print("Tum sahneler zaten uretilmis.", flush=True)
        return

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--disable-infobars",
        "--start-maximized"
    ]

    failures = []

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
            print(f"[Sahne {num:02d}] Uretiliyor...", flush=True)
            scene_done = False

            for attempt in range(1, 4):
                try:
                    before_srcs = await get_settled_image_srcs(page)

                    if ref_path and ref_path.exists():
                        await attach_reference(page, ref_path)

                    await submit_prompt(page, prompt)

                    waited = 0
                    new_srcs = []
                    while waited < 120:
                        await asyncio.sleep(1.0)
                        waited += 1

                        if await handle_retry_if_present(page):
                            waited = 0

                        current_srcs = await get_rendered_image_srcs(page)
                        new_srcs = [s for s in current_srcs if s not in before_srcs]
                        if new_srcs:
                            break

                    if not new_srcs:
                        raise TimeoutError(f"Sahne {num:02d} zaman asimina ugradi (120sn)")

                    await asyncio.sleep(2.5)
                    current_srcs = await get_rendered_image_srcs(page)
                    final_new_srcs = list(dict.fromkeys([s for s in current_srcs if s not in before_srcs]))
                    if not final_new_srcs:
                        final_new_srcs = list(dict.fromkeys(new_srcs))

                    saved_count = 0
                    for idx, src in enumerate(final_new_srcs[:2], start=1):
                        dest_file = out_dir / f"sahne_{num:02d}_{idx}.png"
                        if await save_image_by_src(page, context, src, dest_file):
                            saved_count += 1
                            print(f"  -> Kaydedildi: {dest_file.name}", flush=True)

                    if saved_count == 0:
                        raise RuntimeError(f"Sahne {num:02d} gorseli kaydedilemedi")

                    await stop_trailing_generation_if_active(page)
                    scene_done = True

                    delay = random.uniform(2.0, 3.5)
                    await asyncio.sleep(delay)
                    break

                except Exception as e:
                    print(f"[Sahne {num:02d}] Deneme {attempt} basarisiz: {e}", flush=True)
                    await handle_retry_if_present(page)
                    await stop_trailing_generation_if_active(page)
                    try:
                        await page.screenshot(path=str(out_dir / f"_error_{num:02d}.png"))
                    except Exception:
                        pass
                    await asyncio.sleep(2.0)
                    await open_flow_project(page)

            if not scene_done:
                failures.append(num)

        (out_dir / "_hatalar.txt").write_text("\n".join(map(str, failures)), encoding="utf-8")
        await browser.close()
        print(f"Tamamlandi. Basarisiz sahneler: {failures if failures else 'Yok'}", flush=True)

if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    asyncio.run(run_batch(target_arg))
