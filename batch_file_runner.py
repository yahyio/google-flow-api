import os
import sys
import re
import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

SESSION = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\session.json")
FLOW_URL = "https://flow.google.com/"
RESULT_IMG = 'img[src*="/asb/"]'
GEN_TIMEOUT_S = 120
SETTLE_S = 4
NEWEST_SCAN = 4
USER_RETRY_WAIT_S = 15 * 60
DEFAULT_TARGET = r"C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450\videolar\03-humans-vanished\kalan-promptlar.txt"

PROMPT_ADD_BTN = 'button[aria-label="İçerik öğelerini istem kutusuna ekle"]'
PICKER_SEARCH = 'input[placeholder="Öğe arayın"]'
ADD_TO_PROMPT = 'button:has-text("İsteme ekle")'

def parse_prompt_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
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

async def open_project(page):
    await page.goto(FLOW_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    link = await page.query_selector('a[href*="/project/"]')
    if link:
        href = await link.get_attribute("href")
        await page.goto(
            href if href.startswith("http") else "https://flow.google.com" + href,
            wait_until="domcontentloaded"
        )
    else:
        btn = await page.query_selector('button:has-text("Yeni proje"), button:has-text("New project")')
        if btn:
            await btn.click()
    await page.wait_for_selector("div.ProseMirror", timeout=45000)

async def upload_to_library(page, ref: Path):
    async with page.expect_file_chooser(timeout=10000) as fc:
        await page.locator('button:has-text("Medya yükle")').first.click()
    await (await fc.value).set_files(str(ref))
    await page.wait_for_timeout(2000)
    accept = page.locator('button:has-text("Kabul ediyorum"), button:has-text("I agree")')
    if await accept.count():
        await accept.first.click()
    await page.wait_for_timeout(5000)

async def attach_reference(page, ref: Path):
    await page.locator(PROMPT_ADD_BTN).click()
    await page.wait_for_timeout(1200)
    await page.locator(PICKER_SEARCH).fill(ref.stem)
    await page.wait_for_timeout(1500)
    item = page.locator(f'.cdk-overlay-container button:has-text("{ref.name}")')
    if not await item.count():
        await upload_to_library(page, ref)
        await page.locator(PICKER_SEARCH).fill(ref.stem)
        await page.wait_for_timeout(1500)
    await item.first.click()
    await page.wait_for_timeout(1200)
    confirm = page.locator(ADD_TO_PROMPT)
    if await confirm.count() and await confirm.first.is_visible():
        await confirm.first.click()
        await page.wait_for_timeout(1500)
    if await page.locator(PICKER_SEARCH).count():
        raise RuntimeError("Reference picker is still open")

async def save_image(page, context, el, path: Path):
    src = await el.get_attribute("src")
    if src and src.startswith("http"):
        resp = await context.request.get(src)
        if resp.ok:
            path.write_bytes(await resp.body())
            return
    data_url = await el.evaluate("""img => {
        const c = document.createElement('canvas');
        c.width = img.naturalWidth; c.height = img.naturalHeight;
        c.getContext('2d').drawImage(img, 0, 0);
        return c.toDataURL('image/png');
    }""")
    path.write_bytes(base64.b64decode(data_url.split(",", 1)[1]))

async def result_srcs(page) -> list[str]:
    return await page.evaluate(
        "sel => [...document.querySelectorAll(sel)].filter(i => i.naturalWidth > 256).map(i => i.src)",
        RESULT_IMG
    )

async def submit_prompt(page, prompt: str):
    editor = await page.query_selector("div.ProseMirror")
    await editor.click()
    await page.keyboard.press("Control+A")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(prompt, delay=5)
    await page.wait_for_timeout(800)
    gen = page.locator('button[aria-label="Oluşturmaya başla"], button[aria-label*="Generate"]').last
    await gen.click()
    await page.wait_for_timeout(2000)
    if (await editor.inner_text()).strip():
        await editor.click()
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)
    if (await editor.inner_text()).strip():
        raise RuntimeError("Prompt was not submitted")

async def settled_srcs(page) -> set[str]:
    last, stable = -1, 0
    srcs = []
    for _ in range(30):
        srcs = await result_srcs(page)
        stable = stable + 1 if len(srcs) == last else 0
        if stable >= 3:
            break
        last = len(srcs)
        await page.wait_for_timeout(1000)
    return set(srcs)

async def wait_for_user_retry(page) -> bool:
    retry = page.locator('button:has-text("Tekrar dene"), button:has-text("Try again")')
    if not (await retry.count() and await retry.first.is_visible()):
        return False
    await page.bring_to_front()
    print("WAITING_FOR_USER: Flow 'Tekrar dene' gosteriyor, kullanicinin basmasi bekleniyor", flush=True)
    for _ in range(USER_RETRY_WAIT_S):
        await page.wait_for_timeout(1000)
        if not (await retry.count() and await retry.first.is_visible()):
            print("RESUMED: kullanici devam ettirdi", flush=True)
            return True
    raise RuntimeError("USER_RETRY_TIMEOUT: 'Tekrar dene' 15 dakika boyunca basilmadi")

async def run_once(page, context, prompt: str, ref: Path | None, out_dir: Path, scene_num: int) -> list[Path]:
    before = await settled_srcs(page)
    if ref:
        await attach_reference(page, ref)
    await submit_prompt(page, prompt)

    new: list[str] = []
    waited = 0
    while waited < GEN_TIMEOUT_S:
        await page.wait_for_timeout(1000)
        waited += 1
        if await wait_for_user_retry(page):
            waited = 0
        new = [src for src in (await result_srcs(page))[:NEWEST_SCAN] if src not in before]
        if new:
            break
    else:
        raise TimeoutError(f"No result after {GEN_TIMEOUT_S}s")

    await page.wait_for_timeout(SETTLE_S * 1000)
    new = [src for src in (await result_srcs(page))[:NEWEST_SCAN] if src not in before]
    saved = []
    for i, src in enumerate(dict.fromkeys(new), 1):
        el = await page.query_selector(f'img[src="{src}"]')
        path = out_dir / f"sahne_{scene_num:02d}_{i}.png"
        await save_image(page, context, el, path)
        saved.append(path)
    return saved

async def run_batch(target_str: str):
    target_path = Path(target_str).resolve()
    if target_path.is_dir():
        file_path = (target_path / "kalan-promptlar.txt").resolve()
    else:
        file_path = target_path

    video_dir = file_path.parent
    base_dir = video_dir.parent.parent
    ref_rel, out_rel, scenes = parse_prompt_file(file_path)

    ref_path = resolve_reference_path(base_dir, video_dir, ref_rel)
    out_dir = (video_dir / "sahneler").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    todo = [
        (num, prompt)
        for num, prompt in scenes
        if not list(out_dir.glob(f"sahne_{num:02d}_*.png"))
    ]
    print(f"{len(todo)} scenes to generate", flush=True)
    if not todo:
        return

    failures = []
    async with async_playwright() as p:
        async def launch():
            b = await p.chromium.launch(headless=False)
            c = await b.new_context(storage_state=str(SESSION), viewport={"width": 1600, "height": 1000})
            pg = await c.new_page()
            await open_project(pg)
            return b, c, pg

        browser, context, page = await launch()
        stop = False
        for n, prompt in todo:
            if stop:
                break
            for attempt in range(1, 3):
                try:
                    print(f"scene {n:02d}: generating...", flush=True)
                    saved = await run_once(page, context, prompt, ref_path, out_dir, n)
                    print(f"scene {n:02d}: {len(saved)} images saved", flush=True)
                    break
                except Exception as e:
                    print(f"scene {n:02d} attempt {attempt} failed: {e}", flush=True)
                    if "USER_RETRY_TIMEOUT" in str(e):
                        failures += [m for m, _ in todo if m >= n]
                        stop = True
                        break
                    if page.is_closed() or not browser.is_connected():
                        browser, context, page = await launch()
                        continue
                    await page.screenshot(path=str(out_dir / f"_error_{n:02d}.png"))
                    await open_project(page)
            else:
                failures.append(n)

        await browser.close()

    (out_dir / "_hatalar.txt").write_text("\n".join(map(str, failures)), encoding="utf-8")
    print(f"done, failed scenes: {failures or 'none'}", flush=True)

if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    asyncio.run(run_batch(target_arg))
