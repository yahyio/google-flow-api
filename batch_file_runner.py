import os
import sys
import re
import json
import time
import math
import ctypes
import base64
import random
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import win32gui
import win32con

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

BRIDGE_PORT = 8765
DOWNLOADS_DIR = Path.home() / "Downloads"
DEFAULT_TARGET = r"C:\Users\yahowa\AppData\Local\Claude-Data\claude_pzs8sxrjxfjjc\scratch-workspaces\32a64456-85c9-45f5-8b4d-ee040224c3ac\a930890e-456b-4c02-a40d-d29cc3fddf62\scratch-2026-10-26-5e6450\videolar\03-humans-vanished\kalan-promptlar.txt"

CONSOLE_JS = r"""(() => {
  if (window.__flowHelperTimer) clearInterval(window.__flowHelperTimer);
  window.__lastMouse = { x: 0, y: 0 };
  window.addEventListener("mousemove", (e) => {
    window.__lastMouse = { x: e.clientX, y: e.clientY };
  }, { passive: true });

  const knownSrcs = new Set(
    Array.from(document.querySelectorAll('img[src*="/asb/"], img[alt*="Option"]'))
      .filter(i => i.complete && i.naturalWidth > 256 && i.src)
      .map(i => i.src)
  );
  let imgCounter = 0;
  const processingSrcs = new Set();

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

  function findBtn(texts, rootSel) {
    const root = rootSel ? document.querySelector(rootSel) : document;
    if (!root) return null;
    const els = Array.from(root.querySelectorAll("button, a, [role='button'], [role='option']"));
    for (const t of texts) {
      const low = t.toLowerCase();
      for (const el of els) {
        if (isVis(el) && (el.innerText || "").toLowerCase().includes(low)) return el;
      }
    }
    return null;
  }

  function findLast(sel) {
    const els = Array.from(document.querySelectorAll(sel)).filter(isVis);
    return els.length ? els[els.length - 1] : null;
  }

  function findFirst(sel) {
    const els = Array.from(document.querySelectorAll(sel)).filter(isVis);
    return els.length ? els[0] : null;
  }

  function exportImage(imgEl, idx) {
    try {
      const c = document.createElement("canvas");
      c.width = imgEl.naturalWidth;
      c.height = imgEl.naturalHeight;
      c.getContext("2d").drawImage(imgEl, 0, 0);
      const dataUrl = c.toDataURL("image/png");
      fetch("http://127.0.0.1:8765/save-raw", {
        method: "POST",
        mode: "no-cors",
        body: dataUrl
      }).catch(() => {
        const a = document.createElement("a");
        a.href = dataUrl;
        a.download = "flow_auto_img_" + idx + ".png";
        document.body.appendChild(a);
        a.click();
        a.remove();
      });
    } catch (e) {}
  }

  window.__flowHelperTimer = setInterval(() => {
    const imgs = Array.from(document.querySelectorAll('img[src*="/asb/"], img[alt*="Option"]'))
      .filter(i => i.complete && i.naturalWidth > 256 && i.src);

    for (const img of imgs) {
      if (!knownSrcs.has(img.src) && !processingSrcs.has(img.src)) {
        processingSrcs.add(img.src);
        setTimeout(() => {
          knownSrcs.add(img.src);
          imgCounter += 1;
          exportImage(img, imgCounter);
        }, 1200);
      }
    }

    const ed = findFirst("div.ProseMirror");
    const add = findLast('button[aria-label*="İçerik öğelerini istem kutusuna ekle"], button[aria-label*="Add content"]');
    const srch = findFirst('input[placeholder="Öğe arayın"], input[placeholder*="Search"]');
    const lib = findBtn(["rocco_sheet_v2.png", "rocco_sheet_v2", "rocco_sheet.png"], ".cdk-overlay-container");
    const conf = findBtn(["İsteme ekle", "Add to prompt"], ".cdk-overlay-container") || findBtn(["İsteme ekle", "Add to prompt"]);
    const gen = findLast('button[aria-label*="Oluşturmaya başla"], button[aria-label*="Generate"]');
    const rtry = findBtn(["Tekrar dene", "Try again"]);

    const st = {
      mx: window.__lastMouse.x,
      my: window.__lastMouse.y,
      dpr: window.devicePixelRatio || 1,
      ed: rectOf(ed),
      edLen: ed ? (ed.innerText || "").trim().length : 0,
      add: rectOf(add),
      srch: rectOf(srch),
      lib: rectOf(lib),
      conf: rectOf(conf),
      gen: rectOf(gen),
      rtry: rectOf(rtry),
      ic: imgCounter
    };
    document.title = "FLOW_STATE:" + JSON.stringify(st);
  }, 250);
  console.log("Flow Yardimcisi Aktif!");
})();"""

shared_lock = threading.Lock()
received_images = []

class RawImageHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8", errors="ignore") if length > 0 else ""
        if self.path == "/save-raw" and "," in raw:
            try:
                b64_data = raw.split(",", 1)[1].strip()
                img_bytes = base64.b64decode(b64_data)
                with shared_lock:
                    received_images.append(img_bytes)
            except Exception:
                pass
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"ok")

def start_local_receiver():
    try:
        server = HTTPServer(("127.0.0.1", BRIDGE_PORT), RawImageHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return server
    except Exception:
        return None

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

def move_os_mouse(target_x: int, target_y: int, duration: float = 0.38):
    start_x, start_y = get_cursor_pos()
    dist = math.hypot(target_x - start_x, target_y - start_y)
    steps = max(18, min(65, int(dist / 11)))
    ctrl_x = (start_x + target_x) / 2.0 + random.uniform(-45, 45)
    ctrl_y = (start_y + target_y) / 2.0 + random.uniform(-45, 45)
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
    move_os_mouse(x, y, duration=random.uniform(0.32, 0.50))
    time.sleep(random.uniform(0.08, 0.16))
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(random.uniform(0.05, 0.11))
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

def find_flow_window() -> tuple[int | None, dict | None]:
    found = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd) or ""
            if "FLOW_STATE:" in title:
                raw_json = title.split("FLOW_STATE:", 1)[1]
                idx = raw_json.rfind("}")
                if idx != -1:
                    raw_json = raw_json[:idx + 1]
                try:
                    st = json.loads(raw_json)
                    found.append((hwnd, st))
                except Exception:
                    pass
    win32gui.EnumWindows(enum_cb, None)
    return found[0] if found else (None, None)

def read_flow_state() -> dict:
    _, st = find_flow_window()
    return st or {}

def focus_flow_window():
    hwnd, _ = find_flow_window()
    if hwnd:
        try:
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            user32.keybd_event(0x12, 0, 0, 0)
            user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass

class ScreenMapper:
    def __init__(self):
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.origin_x = 0.0
        self.origin_y = 100.0

    def calibrate(self):
        focus_flow_window()
        time.sleep(0.3)
        p1x, p1y = 500, 450
        move_os_mouse(p1x, p1y, duration=0.25)
        time.sleep(0.4)
        st1 = read_flow_state()
        c1x, c1y = st1.get("mx", 0), st1.get("my", 0)

        p2x, p2y = 900, 650
        move_os_mouse(p2x, p2y, duration=0.25)
        time.sleep(0.4)
        st2 = read_flow_state()
        c2x, c2y = st2.get("mx", 0), st2.get("my", 0)

        if abs(c2x - c1x) > 40 and abs(c2y - c1y) > 40:
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

    def click_box(self, box: dict):
        focus_flow_window()
        jx = box["x"] + random.uniform(-min(10, box["w"] * 0.2), min(10, box["w"] * 0.2))
        jy = box["y"] + random.uniform(-min(5, box["h"] * 0.2), min(5, box["h"] * 0.2))
        sx = int(self.origin_x + jx * self.scale_x)
        sy = int(self.origin_y + jy * self.scale_y)
        os_left_click(sx, sy)

def parse_prompt_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8")
    header_part = content.split("=== SAHNE")[0]
    ref_match = re.search(r"([a-zA-Z0-9_./\\-]+\.png)", header_part)
    ref_file_rel = ref_match.group(1).strip() if ref_match else "rocco_sheet_v2.png"

    scenes = []
    pattern = r"=== SAHNE\s+(\d+)\s*===\s*\n(.*?)(?=\n=== SAHNE|\Z)"
    for m in re.finditer(pattern, content, re.DOTALL):
        scene_num = int(m.group(1))
        prompt_text = m.group(2).strip()
        scenes.append((scene_num, prompt_text))

    return ref_file_rel, scenes

def attach_reference_from_library(mapper: ScreenMapper, ref_stem: str):
    st = read_flow_state()
    if not st.get("add"):
        return

    mapper.click_box(st["add"])
    time.sleep(random.uniform(1.2, 1.6))

    st = read_flow_state()
    if st.get("srch"):
        mapper.click_box(st["srch"])
        time.sleep(0.3)
        press_ctrl_combo(VK_A)
        time.sleep(0.1)
        press_vk(VK_BACK)
        time.sleep(0.2)
        set_clipboard_text(ref_stem)
        press_ctrl_combo(VK_V)
        time.sleep(1.6)

    st = read_flow_state()
    if st.get("lib"):
        mapper.click_box(st["lib"])
        time.sleep(1.3)
        st = read_flow_state()
        if st.get("conf"):
            mapper.click_box(st["conf"])
            time.sleep(1.4)
    else:
        press_vk(VK_ESCAPE)
        time.sleep(0.5)

def submit_prompt_hardware(mapper: ScreenMapper, prompt: str):
    st = read_flow_state()
    if not st.get("ed"):
        raise RuntimeError("Flow prompt kutusu gorunmuyor")

    mapper.click_box(st["ed"])
    time.sleep(random.uniform(0.25, 0.45))
    press_ctrl_combo(VK_A)
    time.sleep(0.15)
    press_vk(VK_BACK)
    time.sleep(0.25)

    set_clipboard_text(prompt)
    press_ctrl_combo(VK_V)
    time.sleep(random.uniform(1.1, 1.7))

    st = read_flow_state()
    if st.get("gen"):
        mapper.click_box(st["gen"])
    else:
        press_vk(VK_RETURN)

    time.sleep(2.0)
    st = read_flow_state()
    if st.get("edLen", 0) > 5:
        if st.get("gen"):
            mapper.click_box(st["gen"])
        else:
            press_vk(VK_RETURN)
        time.sleep(1.5)

def collect_saved_images(out_dir: Path, scene_num: int) -> int:
    saved = 0
    with shared_lock:
        while received_images and saved < 2:
            img_bytes = received_images.pop(0)
            saved += 1
            dest = out_dir / f"sahne_{scene_num:02d}_{saved}.png"
            dest.write_bytes(img_bytes)
            print(f"  -> Kaydedildi: {dest.name}", flush=True)

    if saved == 0 and DOWNLOADS_DIR.exists():
        dl_files = sorted(DOWNLOADS_DIR.glob("flow_auto_img_*.png"), key=lambda p: p.stat().st_mtime)
        for f in dl_files[-2:]:
            saved += 1
            dest = out_dir / f"sahne_{scene_num:02d}_{saved}.png"
            dest.write_bytes(f.read_bytes())
            try:
                f.unlink()
            except Exception:
                pass
            print(f"  -> Kaydedildi: {dest.name}", flush=True)

    return saved

def run_batch(target_str: str):
    target_path = Path(target_str).resolve()
    if target_path.is_dir():
        file_path = (target_path / "kalan-promptlar.txt").resolve()
    else:
        file_path = target_path

    video_dir = file_path.parent
    ref_rel, scenes = parse_prompt_file(file_path)
    ref_stem = Path(ref_rel).stem

    out_dir = (video_dir / "sahneler").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    konsol_txt = video_dir / "konsol_kodu.txt"
    konsol_txt.write_text(CONSOLE_JS, encoding="utf-8")

    pending_scenes = []
    for num, prompt in scenes:
        if not list(out_dir.glob(f"sahne_{num:02d}_*.png")):
            pending_scenes.append((num, prompt))

    print(f"Hedef klasor: {video_dir.name}")
    print(f"Referans: {ref_rel} | Uretilecek kalan sahne: {len(pending_scenes)}", flush=True)

    if not pending_scenes:
        print("Tum sahneler zaten uretilmis.", flush=True)
        return

    start_local_receiver()
    set_clipboard_text(CONSOLE_JS)

    print("\n" + "=" * 68)
    print("  SIFIR BOT ALGILAMA MODU (Kendi Normal Chrome Tarayiciniz)")
    print("=" * 68)
    print("1. Normal Chrome tarayicinizda Google Flow projenizi acin.")
    print("2. F12 tusuna basip 'Console' sekmesine gecin.")
    print("3. Konsol kodu su an panonuza (Clipboard) OTO-KOPYALANDI!")
    print("   Console'a tiklayip Ctrl+V yapin ve Enter'a basin.")
    print("4. Ardindan F12 panelini kapatin ve fareyi birakin.")
    print("=" * 68 + "\n", flush=True)

    print("Chrome'da F12 -> Console'a kodu yapistirmaniz bekleniyor...", flush=True)
    while True:
        hwnd, st = find_flow_window()
        if hwnd and st:
            print("Baglanti kuruldu! Fare kalibre ediliyor (lutfen fareyi oynatmayin)...", flush=True)
            break
        time.sleep(0.5)

    time.sleep(1.5)
    mapper = ScreenMapper()
    mapper.calibrate()

    failures = []
    for num, prompt in pending_scenes:
        print(f"[Sahne {num:02d}] Uretiliyor...", flush=True)
        scene_done = False

        for attempt in range(1, 3):
            try:
                with shared_lock:
                    received_images.clear()

                before_ic = read_flow_state().get("ic", 0)

                attach_reference_from_library(mapper, ref_stem)
                submit_prompt_hardware(mapper, prompt)

                waited = 0
                detected = False
                while waited < 120:
                    time.sleep(1.0)
                    waited += 1

                    if waited % 15 == 0:
                        move_os_mouse(random.randint(350, 850), random.randint(250, 550), duration=0.35)

                    st = read_flow_state()
                    if st.get("rtry"):
                        time.sleep(random.uniform(3.5, 5.5))
                        st = read_flow_state()
                        if st.get("rtry"):
                            mapper.click_box(st["rtry"])
                            waited = 0
                            time.sleep(3.0)

                    with shared_lock:
                        has_http_img = len(received_images) > 0

                    if has_http_img or st.get("ic", 0) > before_ic:
                        detected = True
                        break

                if not detected:
                    raise TimeoutError(f"Sahne {num:02d} zaman asimina ugradi (120sn)")

                time.sleep(3.5)
                saved = collect_saved_images(out_dir, num)
                if saved == 0:
                    raise RuntimeError(f"Sahne {num:02d} gorseli alinamadi")

                scene_done = True
                time.sleep(random.uniform(5.0, 8.0))
                break

            except Exception as e:
                print(f"[Sahne {num:02d}] Deneme {attempt} basarisiz: {e}", flush=True)
                press_vk(VK_ESCAPE)
                time.sleep(2.5)
                mapper.calibrate()

        if not scene_done:
            failures.append(num)

    (out_dir / "_hatalar.txt").write_text("\n".join(map(str, failures)), encoding="utf-8")
    print(f"Tamamlandi! Basarisiz sahneler: {failures if failures else 'Yok'}", flush=True)

if __name__ == "__main__":
    target_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    run_batch(target_arg)
