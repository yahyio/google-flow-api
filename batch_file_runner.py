import os
import sys
import re
import json
import time
import math
import ctypes
import base64
import random
import asyncio
import subprocess
import urllib.request
import websockets
from pathlib import Path

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_RETURN = 0x0D
VK_BACK = 0x08
VK_ESCAPE = 0x1B
VK_A = 0x41
VK_V = 0x56

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
  if (!window.__mouseTrackerInstalled) {
    window.__mouseTrackerInstalled = true;
    window.__lastMouse = { clientX: 0, clientY: 0, screenX: 0, screenY: 0 };
    window.addEventListener("mousemove", (e) => {
      window.__lastMouse = { clientX: e.clientX, clientY: e.clientY, screenX: e.screenX, screenY: e.screenY };
    }, { passive: true });
  }
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
    const btns = Array.from(root.querySelectorAll("button, a[role='button']"));
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
  const projectLink = findFirstVisible('a[href*="/project/"]');
  const newProjectBtn = findBtnByText(["Yeni proje", "New project"]);
  const ctaBtn = findBtnByText(["Google Flow ile oluştur", "Google Flow'u deneyin", "Try Google Flow"]);

  const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'))
    .filter(i => i.complete && i.naturalWidth > 200 && i.src)
    .map(i => i.src);

  return {
    url: window.location.href,
    dpr: window.devicePixelRatio || 1,
    mouse: window.__lastMouse,
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
    projectLink: rectOf(projectLink),
    newProjectBtn: rectOf(newProjectBtn),
    ctaBtn: rectOf(ctaBtn),
    imageSrcs: imgs
  };
})()
"""

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def move_os_mouse(target_x: int, target_y: int, duration: float = 0.36):
    start_x, start_y = get_cursor_pos()
    dist = math.hypot(target_x - start_x, target_y - start_y)
    steps = max(16, min(60, int(dist / 12)))
    ctrl_x = (start_x + target_x) / 2.0 + random.uniform(-40, 40)
    ctrl_y = (start_y + target_y) / 2.0 + random.uniform(-40, 40)
    step_sleep = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        inv = 1.0 - t
        bx = inv * inv * start_x + 2 * inv * t * ctrl_x + t * t * target_x
        by = inv * inv * start_y + 2 * inv * t * ctrl_y + t * t * target_y
        user32.SetCursorPos(int(bx), int(by))
        time.sleep(step_sleep)
    user32.SetCursorPos(int(target_x), int(target_y))

def os_left_click(x: int, y: int):
    move_os_mouse(x, y, duration=random.uniform(0.30, 0.48))
    time.sleep(random.uniform(0.08, 0.16))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.05, 0.10))
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

def set_clipboard_text(text: str):
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]

    encoded = (text + "\0").encode("utf-16-le")
    for _ in range(5):
        if user32.OpenClipboard(0):
            break
        time.sleep(0.05)
    user32.EmptyClipboard()
    h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    ptr = kernel32.GlobalLock(h_mem)
    ctypes.memmove(ptr, encoded, len(encoded))
    kernel32.GlobalUnlock(h_mem)
    user32.SetClipboardData(CF_UNICODETEXT, h_mem)
    user32.CloseClipboard()

def press_vk(vk: int):
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(random.uniform(0.04, 0.08))
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

def press_ctrl_combo(vk: int):
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(random.uniform(0.04, 0.08))
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(random.uniform(0.04, 0.08))
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(random.uniform(0.03, 0.06))
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)

class RawCDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

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

class ScreenMapper:
    def __init__(self, cdp: RawCDPClient):
        self.cdp = cdp
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.origin_x = 0.0
        self.origin_y = 100.0

    async def calibrate(self):
        await self.cdp.get_state()
        p1x, p1y = 500, 450
        move_os_mouse(p1x, p1y, duration=0.25)
        await asyncio.sleep(0.35)
        st1 = await self.cdp.get_state()
        m1 = st1.get("mouse") or {}
        c1x, c1y = m1.get("clientX", 0), m1.get("clientY", 0)

        p2x, p2y = 900, 650
        move_os_mouse(p2x, p2y, duration=0.25)
        await asyncio.sleep(0.35)
        st2 = await self.cdp.get_state()
        m2 = st2.get("mouse") or {}
        c2x, c2y = m2.get("clientX", 0), m2.get("clientY", 0)

        if abs(c2x - c1x) > 50 and abs(c2y - c1y) > 50:
            self.scale_x = (p2x - p1x) / float(c2x - c1x)
            self.scale_y = (p2y - p1y) / float(c2y - c1y)
            self.origin_x = p1x - c1x * self.scale_x
            self.origin_y = p1y - c1y * self.scale_y
        else:
            dpr = float(st2.get("dpr") or 1.0)
            self.scale_x = dpr
            self.scale_y = dpr
            self.origin_x = 0.0
            self.origin_y = 85.0 * dpr

    def to_screen(self, box: dict) -> tuple[int, int]:
        jx = box["x"] + random.uniform(-min(12, box["w"] * 0.2), min(12, box["w"] * 0.2))
        jy = box["y"] + random.uniform(-min(6, box["h"] * 0.2), min(6, box["h"] * 0.2))
        sx = int(self.origin_x + jx * self.scale_x)
        sy = int(self.origin_y + jy * self.scale_y)
        return sx, sy

    def click_box(self, box: dict):
        sx, sy = self.to_screen(box)
        os_left_click(sx, sy)

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
            FLOW_URL
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(30):
        if get_flow_ws_url():
            break
        time.sleep(0.5)
    return proc

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

async def ensure_in_editor(cdp: RawCDPClient, mapper: ScreenMapper) -> bool:
    for _ in range(40):
        st = await cdp.get_state()
        if st.get("editor"):
            return True
        if st.get("acceptBtn"):
            mapper.click_box(st["acceptBtn"])
            await asyncio.sleep(1.5)
            continue
        if st.get("ctaBtn"):
            mapper.click_box(st["ctaBtn"])
            await asyncio.sleep(3.0)
            continue
        if st.get("projectLink"):
            mapper.click_box(st["projectLink"])
            await asyncio.sleep(3.5)
            continue
        if st.get("newProjectBtn"):
            mapper.click_box(st["newProjectBtn"])
            await asyncio.sleep(3.5)
            continue
        await asyncio.sleep(1.0)
    return False

async def attach_reference_hardware(cdp: RawCDPClient, mapper: ScreenMapper, ref_path: Path):
    st = await cdp.get_state()
    if not st.get("addBtn"):
        return

    mapper.click_box(st["addBtn"])
    await asyncio.sleep(random.uniform(1.3, 1.8))

    st = await cdp.get_state()
    if st.get("searchInput"):
        mapper.click_box(st["searchInput"])
        await asyncio.sleep(0.3)
        press_ctrl_combo(VK_A)
        await asyncio.sleep(0.1)
        press_vk(VK_BACK)
        await asyncio.sleep(0.2)
        set_clipboard_text(ref_path.stem)
        press_ctrl_combo(VK_V)
        await asyncio.sleep(1.6)

        st = await cdp.get_state()
        lib_box = st.get("libRoccoV2") or st.get("libRocco")
        if lib_box:
            mapper.click_box(lib_box)
            await asyncio.sleep(1.3)
            st = await cdp.get_state()
            if st.get("confirmAddBtn"):
                mapper.click_box(st["confirmAddBtn"])
                await asyncio.sleep(1.4)
            return

    st = await cdp.get_state()
    if st.get("uploadBtn"):
        mapper.click_box(st["uploadBtn"])
        await asyncio.sleep(1.8)
        set_clipboard_text(str(ref_path))
        press_ctrl_combo(VK_V)
        await asyncio.sleep(0.4)
        press_vk(VK_RETURN)
        await asyncio.sleep(3.8)

        for _ in range(10):
            st = await cdp.get_state()
            if st.get("acceptBtn"):
                mapper.click_box(st["acceptBtn"])
                await asyncio.sleep(2.0)
                break
            await asyncio.sleep(0.5)

        st = await cdp.get_state()
        if st.get("confirmAddBtn"):
            mapper.click_box(st["confirmAddBtn"])
            await asyncio.sleep(1.5)
    else:
        press_vk(VK_ESCAPE)
        await asyncio.sleep(0.5)

async def submit_prompt_hardware(cdp: RawCDPClient, mapper: ScreenMapper, prompt: str):
    st = await cdp.get_state()
    if not st.get("editor"):
        await ensure_in_editor(cdp, mapper)
        st = await cdp.get_state()

    editor_box = st.get("editor")
    if not editor_box:
        raise RuntimeError("Prompt kutusu bulunamadi")

    mapper.click_box(editor_box)
    await asyncio.sleep(random.uniform(0.25, 0.45))
    press_ctrl_combo(VK_A)
    await asyncio.sleep(0.15)
    press_vk(VK_BACK)
    await asyncio.sleep(0.25)

    set_clipboard_text(prompt)
    press_ctrl_combo(VK_V)
    await asyncio.sleep(random.uniform(1.1, 1.7))

    st = await cdp.get_state()
    if st.get("genBtn"):
        mapper.click_box(st["genBtn"])
    else:
        press_vk(VK_RETURN)

    await asyncio.sleep(2.0)
    st = await cdp.get_state()
    if st.get("editorText"):
        if st.get("genBtn"):
            mapper.click_box(st["genBtn"])
        else:
            press_vk(VK_RETURN)
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
                await cdp.send_cmd("Network.setCookies", {"cookies": sess_data["cookies"]})
        except Exception:
            pass

    st = await cdp.get_state()
    if "flow.google.com" not in st.get("url", "") and "labs.google" not in st.get("url", ""):
        await cdp.send_cmd("Page.navigate", {"url": FLOW_URL})
        await asyncio.sleep(4.0)
    else:
        await asyncio.sleep(2.5)

    mapper = ScreenMapper(cdp)
    await mapper.calibrate()

    if not await ensure_in_editor(cdp, mapper):
        raise RuntimeError("Flow proje editoru acilamadi")

    await mapper.calibrate()
    failures = []

    for num, prompt in pending_scenes:
        print(f"[Sahne {num:02d}] Uretiliyor...", flush=True)
        scene_done = False

        for attempt in range(1, 3):
            try:
                await asyncio.sleep(1.5)
                before_srcs = set((await cdp.get_state()).get("imageSrcs") or [])

                if ref_path and ref_path.exists():
                    await attach_reference_hardware(cdp, mapper, ref_path)

                await submit_prompt_hardware(cdp, mapper, prompt)

                waited = 0
                new_srcs = []
                while waited < 120:
                    await asyncio.sleep(1.0)
                    waited += 1

                    if waited % 14 == 0:
                        rx, ry = random.randint(350, 850), random.randint(250, 550)
                        move_os_mouse(rx, ry, duration=0.35)

                    st = await cdp.get_state()
                    if st.get("retryBtn"):
                        await asyncio.sleep(random.uniform(3.5, 5.5))
                        st = await cdp.get_state()
                        if st.get("retryBtn"):
                            mapper.click_box(st["retryBtn"])
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
                press_vk(VK_ESCAPE)
                await asyncio.sleep(2.0)
                await ensure_in_editor(cdp, mapper)

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
