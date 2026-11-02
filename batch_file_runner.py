import os
import sys
import re
import json
import time
import math
import base64
import random
import asyncio
import subprocess
import urllib.request
import websockets
from pathlib import Path

SESSION_PATH = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\session.json")
PROFILE_DIR = Path(r"C:\Users\yahowa\Desktop\reverseinstafly\google-flow-api\auth\chrome_human_profile")
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FLOW_URL = "https://flow.google.com/"
CDP_PORT = 9244
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

STATE_JS = r"""
(() => {
  function isVis(el) {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width <= 2 || r.height <= 2) return false;
    const st = window.getComputedStyle(el);
    return st.visibility !== "hidden" && st.display !== "none" && parseFloat(st.opacity || "1") > 0.05;
  }
  function rectOf(el) {
    if (!isVis(el)) return null;
    const r = el.getBoundingClientRect();
    return {
      x: Math.round(r.left + r.width / 2),
      y: Math.round(r.top + r.height / 2),
      w: Math.round(r.width),
      h: Math.round(r.height)
    };
  }
  function findBtnByText(texts, containerSel) {
    const root = containerSel ? document.querySelector(containerSel) : document;
    if (!root) return null;
    const btns = Array.from(root.querySelectorAll("button, a, [role='button'], [role='option']"));
    for (const t of texts) {
      const low = t.toLowerCase();
      for (const b of btns) {
        if (isVis(b) && (b.innerText || "").toLowerCase().includes(low)) return b;
      }
    }
    return null;
  }
  function findLastVisible(sel) {
    const els = Array.from(document.querySelectorAll(sel)).filter(isVis);
    return els.length ? els[els.length - 1] : null;
  }
  function findFirstVisible(sel) {
    const els = Array.from(document.querySelectorAll(sel)).filter(isVis);
    return els.length ? els[0] : null;
  }
  const editor = findFirstVisible("div.ProseMirror");
  const addBtn = findLastVisible('button[aria-label*="İçerik öğelerini istem kutusuna ekle"], button[aria-label*="Add content"]');
  const searchInput = findFirstVisible('input[placeholder="Öğe arayın"], input[placeholder*="Search"]');
  const libRoccoV2 = findBtnByText(["rocco_sheet_v2.png", "rocco_sheet_v2"], ".cdk-overlay-container");
  const libRocco = findBtnByText(["rocco_sheet.png", "rocco_sheet"], ".cdk-overlay-container");
  const uploadBtn = findFirstVisible('.cdk-overlay-container button.upload-button, .cdk-overlay-container button[aria-label*="Medya yükle"]') || findBtnByText(["Medya yükle", "Upload media"], ".cdk-overlay-container");
  const confirmAddBtn = findBtnByText(["İsteme ekle", "Add to prompt"], ".cdk-overlay-container") || findBtnByText(["İsteme ekle", "Add to prompt"]);
  const acceptBtn = findBtnByText(["Kabul ediyorum", "I agree", "Anladım", "Got it"]);
  const genBtn = findLastVisible('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]');
  const retryBtn = findBtnByText(["Tekrar dene", "Try again"]);
  const projectLinkEl = findFirstVisible('a[href*="/project/"]');
  const newProjectBtn = findBtnByText(["Yeni proje", "New project"]);
  const ctaBtn = findBtnByText(["Google Flow ile oluştur", "Google Flow'u deneyin", "Try Google Flow"]);

  const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'))
    .filter(i => i.complete && i.naturalWidth > 200 && i.src)
    .map(i => i.src);

  return {
    url: window.location.href,
    editor: rectOf(editor),
    editorText: editor ? (editor.innerText || "").trim() : "",
    addBtn: rectOf(addBtn),
    searchInput: rectOf(searchInput),
    libRoccoV2: rectOf(libRoccoV2),
    libRocco: rectOf(libRocco),
    uploadBtn: rectOf(uploadBtn),
    confirmAddBtn: rectOf(confirmAddBtn),
    acceptBtn: rectOf(acceptBtn),
    genBtn: rectOf(genBtn),
    retryBtn: rectOf(retryBtn),
    projectLink: rectOf(projectLinkEl),
    projectHref: projectLinkEl ? projectLinkEl.href : null,
    newProjectBtn: rectOf(newProjectBtn),
    ctaBtn: rectOf(ctaBtn),
    imageSrcs: imgs
  };
})()
"""

class RawCDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0
        self.mouse_x = 400.0
        self.mouse_y = 400.0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=50 * 1024 * 1024)

    async def send_cmd(self, method: str, params: dict | None = None) -> dict:
        self.msg_id += 1
        cid = self.msg_id
        payload = {"id": cid, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            raw = await self.ws.recv()
            data = json.loads(raw)
            if data.get("id") == cid:
                return data.get("result") or {}

    async def eval_js(self, expr: str):
        res = await self.send_cmd("Runtime.evaluate", {
            "expression": expr,
            "returnByValue": True,
            "awaitPromise": True,
            "silent": True
        })
        return (res.get("result") or {}).get("value")

    async def get_state(self) -> dict:
        val = await self.eval_js(STATE_JS)
        return val if isinstance(val, dict) else {}

    async def human_move(self, target_x: float, target_y: float, duration: float = 0.35):
        start_x, start_y = self.mouse_x, self.mouse_y
        dist = math.hypot(target_x - start_x, target_y - start_y)
        steps = max(14, min(40, int(dist / 15)))
        ctrl_x = (start_x + target_x) / 2.0 + random.uniform(-35, 35)
        ctrl_y = (start_y + target_y) / 2.0 + random.uniform(-35, 35)
        step_sleep = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            inv = 1.0 - t
            bx = inv * inv * start_x + 2 * inv * t * ctrl_x + t * t * target_x
            by = inv * inv * start_y + 2 * inv * t * ctrl_y + t * t * target_y
            await self.send_cmd("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": round(bx, 1),
                "y": round(by, 1),
                "button": "none",
                "pointerType": "mouse"
            })
            await asyncio.sleep(step_sleep)
        self.mouse_x, self.mouse_y = target_x, target_y

    async def human_click_box(self, box: dict):
        tx = box["x"] + random.uniform(-min(10, box["w"] * 0.2), min(10, box["w"] * 0.2))
        ty = box["y"] + random.uniform(-min(5, box["h"] * 0.2), min(5, box["h"] * 0.2))
        await self.human_move(tx, ty, duration=random.uniform(0.28, 0.45))
        await asyncio.sleep(random.uniform(0.06, 0.14))
        await self.send_cmd("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": round(tx, 1),
            "y": round(ty, 1),
            "button": "left",
            "buttons": 1,
            "clickCount": 1,
            "pointerType": "mouse"
        })
        await asyncio.sleep(random.uniform(0.05, 0.11))
        await self.send_cmd("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": round(tx, 1),
            "y": round(ty, 1),
            "button": "left",
            "buttons": 0,
            "clickCount": 1,
            "pointerType": "mouse"
        })

    async def press_key(self, key: str, code: str, vk: int, modifiers: int = 0):
        await self.send_cmd("Input.dispatchKeyEvent", {
            "type": "rawKeyDown",
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": vk,
            "nativeVirtualKeyCode": vk,
            "modifiers": modifiers
        })
        await asyncio.sleep(random.uniform(0.04, 0.08))
        await self.send_cmd("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": vk,
            "nativeVirtualKeyCode": vk,
            "modifiers": modifiers
        })

    async def clear_and_paste(self, text: str):
        await self.press_key("a", "KeyA", 65, modifiers=2)
        await asyncio.sleep(0.1)
        await self.press_key("Backspace", "Backspace", 8)
        await asyncio.sleep(0.15)
        if len(text) > 1:
            await self.send_cmd("Input.insertText", {"text": text[:-1]})
            await asyncio.sleep(random.uniform(0.15, 0.3))
            last_ch = text[-1]
            await self.send_cmd("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "text": last_ch,
                "unmodifiedText": last_ch,
                "key": last_ch
            })
            await asyncio.sleep(0.05)
            await self.send_cmd("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": last_ch
            })
        else:
            await self.send_cmd("Input.insertText", {"text": text})

    async def upload_file_to_input(self, file_path: Path) -> bool:
        doc = await self.send_cmd("DOM.getDocument", {"depth": -1})
        root_id = (doc.get("root") or {}).get("nodeId")
        if not root_id:
            return False
        q = await self.send_cmd("DOM.querySelector", {
            "nodeId": root_id,
            "selector": 'input[type="file"]'
        })
        node_id = q.get("nodeId")
        if not node_id:
            return False
        await self.send_cmd("DOM.setFileInputFiles", {
            "nodeId": node_id,
            "files": [str(file_path)]
        })
        return True

    async def extract_image_bytes(self, target_src: str) -> bytes | None:
        js = f"""
        (() => {{
            const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'));
            const img = imgs.find(i => i.src === {json.dumps(target_src)});
            if (!img || !img.naturalWidth) return null;
            const c = document.createElement('canvas');
            c.width = img.naturalWidth;
            c.height = img.naturalHeight;
            c.getContext('2d').drawImage(img, 0, 0);
            return c.toDataURL('image/png');
        }})()
        """
        data_url = await self.eval_js(js)
        if data_url and isinstance(data_url, str) and "," in data_url:
            return base64.b64decode(data_url.split(",", 1)[1])
        return None

    async def close(self):
        if self.ws:
            await self.ws.close()

def get_flow_ws_url() -> str | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=2) as r:
            targets = json.loads(r.read().decode("utf-8"))
        for t in targets:
            if t.get("type") == "page" and ("flow.google" in t.get("url", "") or "labs.google" in t.get("url", "")):
                return t.get("webSocketDebuggerUrl")
        for t in targets:
            if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                return t.get("webSocketDebuggerUrl")
    except Exception:
        pass
    return None

def launch_chrome() -> subprocess.Popen | None:
    if get_flow_ws_url():
        return None
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            CHROME_EXE,
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
            "about:blank"
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(30):
        if get_flow_ws_url():
            break
        time.sleep(0.5)
    return proc

def sanitize_cookies(raw_cookies: list[dict]) -> list[dict]:
    cleaned = []
    for c in raw_cookies:
        c = dict(c)
        if c.get("name", "").startswith("__Host-"):
            dom = c.pop("domain", "").lstrip(".")
            c["url"] = f"https://{dom}{c.get('path', '/')}"
        if c.get("expires", -1) <= 0:
            c.pop("expires", None)
        cleaned.append(c)
    return cleaned

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

async def ensure_in_editor(cdp: RawCDPClient) -> bool:
    for _ in range(45):
        st = await cdp.get_state()
        if st.get("editor"):
            return True
        if st.get("acceptBtn"):
            await cdp.human_click_box(st["acceptBtn"])
            await asyncio.sleep(1.5)
            continue
        if st.get("projectHref"):
            await cdp.send_cmd("Page.navigate", {"url": st["projectHref"]})
            await asyncio.sleep(4.0)
            continue
        if st.get("newProjectBtn"):
            await cdp.human_click_box(st["newProjectBtn"])
            await asyncio.sleep(3.5)
            continue
        if st.get("ctaBtn"):
            await cdp.human_click_box(st["ctaBtn"])
            await asyncio.sleep(3.5)
            new_ws = get_flow_ws_url()
            if new_ws and new_ws != cdp.ws_url:
                await cdp.close()
                cdp.ws_url = new_ws
                await cdp.connect()
            continue
        await asyncio.sleep(1.0)
    return False

async def attach_reference_cdp(cdp: RawCDPClient, ref_path: Path):
    st = await cdp.get_state()
    if not st.get("addBtn"):
        return

    await cdp.human_click_box(st["addBtn"])
    await asyncio.sleep(random.uniform(1.2, 1.7))

    st = await cdp.get_state()
    if st.get("searchInput"):
        await cdp.human_click_box(st["searchInput"])
        await asyncio.sleep(0.25)
        await cdp.clear_and_paste(ref_path.stem)
        await asyncio.sleep(1.5)

        st = await cdp.get_state()
        lib_box = st.get("libRoccoV2") or st.get("libRocco")
        if lib_box:
            await cdp.human_click_box(lib_box)
            await asyncio.sleep(1.2)
            st = await cdp.get_state()
            if st.get("confirmAddBtn"):
                await cdp.human_click_box(st["confirmAddBtn"])
                await asyncio.sleep(1.3)
            return

    if await cdp.upload_file_to_input(ref_path):
        await asyncio.sleep(3.0)
        for _ in range(10):
            st = await cdp.get_state()
            if st.get("acceptBtn"):
                await cdp.human_click_box(st["acceptBtn"])
                await asyncio.sleep(2.0)
                break
            await asyncio.sleep(0.5)
        st = await cdp.get_state()
        if st.get("confirmAddBtn"):
            await cdp.human_click_box(st["confirmAddBtn"])
            await asyncio.sleep(1.4)
    else:
        await cdp.press_key("Escape", "Escape", 27)
        await asyncio.sleep(0.5)

async def submit_prompt_cdp(cdp: RawCDPClient, prompt: str):
    st = await cdp.get_state()
    if not st.get("editor"):
        await ensure_in_editor(cdp)
        st = await cdp.get_state()

    editor_box = st.get("editor")
    if not editor_box:
        raise RuntimeError("Prompt kutusu bulunamadi")

    await cdp.human_click_box(editor_box)
    await asyncio.sleep(random.uniform(0.2, 0.4))
    await cdp.clear_and_paste(prompt)
    await asyncio.sleep(random.uniform(0.9, 1.5))

    st = await cdp.get_state()
    if st.get("genBtn"):
        await cdp.human_click_box(st["genBtn"])
    else:
        await cdp.press_key("Enter", "Enter", 13)

    await asyncio.sleep(2.0)
    st = await cdp.get_state()
    if st.get("editorText"):
        if st.get("genBtn"):
            await cdp.human_click_box(st["genBtn"])
        else:
            await cdp.press_key("Enter", "Enter", 13)
        await asyncio.sleep(1.5)

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

    chrome_proc = launch_chrome()
    ws_url = get_flow_ws_url()
    if not ws_url:
        raise RuntimeError("Chrome WebSocket baglantisi bulunamadi")

    cdp = RawCDPClient(ws_url)
    await cdp.connect()

    if SESSION_PATH.exists():
        try:
            sess_data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
            if sess_data.get("cookies"):
                await cdp.send_cmd("Network.setCookies", {"cookies": sanitize_cookies(sess_data["cookies"])})
        except Exception:
            pass

    await cdp.send_cmd("Page.navigate", {"url": "https://labs.google/fx/tr/tools/flow"})
    await asyncio.sleep(4.5)

    if not await ensure_in_editor(cdp):
        raise RuntimeError("Flow proje editoru acilamadi")

    failures = []

    for num, prompt in pending_scenes:
        print(f"[Sahne {num:02d}] Uretiliyor...", flush=True)
        scene_done = False

        for attempt in range(1, 3):
            try:
                await asyncio.sleep(1.5)
                before_srcs = set((await cdp.get_state()).get("imageSrcs") or [])

                if ref_path and ref_path.exists():
                    await attach_reference_cdp(cdp, ref_path)

                await submit_prompt_cdp(cdp, prompt)

                waited = 0
                new_srcs = []
                while waited < 120:
                    await asyncio.sleep(1.0)
                    waited += 1

                    if waited % 12 == 0:
                        await cdp.human_move(random.randint(300, 900), random.randint(200, 600), duration=0.3)

                    st = await cdp.get_state()
                    if st.get("retryBtn"):
                        await asyncio.sleep(random.uniform(4.0, 6.0))
                        st = await cdp.get_state()
                        if st.get("retryBtn"):
                            await cdp.human_click_box(st["retryBtn"])
                            waited = 0
                            await asyncio.sleep(3.0)

                    cur_srcs = st.get("imageSrcs") or []
                    new_srcs = [s for s in cur_srcs if s not in before_srcs]
                    if new_srcs:
                        break

                if not new_srcs:
                    raise TimeoutError(f"Sahne {num:02d} zaman asimina ugradi (120sn)")

                await asyncio.sleep(3.5)
                cur_srcs = (await cdp.get_state()).get("imageSrcs") or []
                final_new_srcs = list(dict.fromkeys([s for s in cur_srcs if s not in before_srcs]))
                if not final_new_srcs:
                    final_new_srcs = list(dict.fromkeys(new_srcs))

                saved_count = 0
                for idx, src in enumerate(final_new_srcs[:2], start=1):
                    img_bytes = await cdp.extract_image_bytes(src)
                    if img_bytes:
                        dest_file = out_dir / f"sahne_{num:02d}_{idx}.png"
                        dest_file.write_bytes(img_bytes)
                        saved_count += 1
                        print(f"  -> Kaydedildi: {dest_file.name}", flush=True)

                if saved_count == 0:
                    raise RuntimeError(f"Sahne {num:02d} gorseli kaydedilemedi")

                scene_done = True
                await asyncio.sleep(random.uniform(5.0, 8.0))
                break

            except Exception as e:
                print(f"[Sahne {num:02d}] Deneme {attempt} basarisiz: {e}", flush=True)
                await cdp.press_key("Escape", "Escape", 27)
                await asyncio.sleep(2.0)
                await ensure_in_editor(cdp)

        if not scene_done:
            failures.append(num)

    await cdp.close()
    (out_dir / "_hatalar.txt").write_text("\n".join(map(str, failures)), encoding="utf-8")
    print(f"Tamamlandi. Basarisiz sahneler: {failures if failures else 'Yok'}", flush=True)
    if chrome_proc:
        try:
            chrome_proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    asyncio.run(run_batch(target_arg))
