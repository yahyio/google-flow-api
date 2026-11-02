import os
import re
import sys
import json
import time
import base64
import argparse
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

PROMPT_RE = re.compile(
    r"Prompt\s*\([^)]*\)\s*:\s*\n(.*?)(?=\n-{5,}|\n═{5,}|\Z)",
    re.DOTALL
)
HEADER_RE = re.compile(r"SAHNE\s+(\d+)\s+—\s+([^\n]+)")


def parse_prompts_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    scenes = []
    simple_matches = list(re.finditer(r"===\s*SAHNE\s+(\d+)\s*===\s*\n(.*?)(?=\n===\s*SAHNE|\Z)", text, re.DOTALL))
    if simple_matches:
        for m in simple_matches:
            num = int(m.group(1))
            prompt = " ".join(m.group(2).strip().split())
            if prompt:
                scenes.append({
                    "num": num,
                    "title": f"Sahne {num}",
                    "prompt": prompt
                })
        return scenes

    blocks = re.split(r"═{10,}\s*\n(?=SAHNE\s+\d+)", text)
    for block in blocks:
        hm = HEADER_RE.search(block)
        pm = PROMPT_RE.search(block)
        if hm and pm:
            num = int(hm.group(1))
            title = hm.group(2).strip()
            prompt = " ".join(pm.group(1).strip().split())
            scenes.append({
                "num": num,
                "title": title,
                "prompt": prompt
            })
    return scenes


def resolve_ref_image(base_dir: str, ref_arg: str):
    if not ref_arg:
        return None
    candidates = [
        ref_arg,
        os.path.join(base_dir, ref_arg),
        os.path.join(base_dir, "..", ref_arg),
        os.path.join(base_dir, "..", "..", ref_arg),
    ]
    for c in candidates:
        full = os.path.abspath(c)
        if os.path.isfile(full):
            return full
    return None


def copy_to_clipboard(text: str):
    try:
        proc = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
        proc.communicate(input=text.encode("utf-16-le"))
    except Exception:
        pass


CONSOLE_LOADER = (
    "fetch('http://127.0.0.1:8765/ tasks'.replace(' ',''))"
    ".then(r=>r.json()).then(async cfg=>{"
    "try{Object.defineProperty(document,'hidden',{get:()=>false,configurable:true});"
    "Object.defineProperty(document,'visibilityState',{get:()=>'visible',configurable:true});"
    "document.hasFocus=()=>true;"
    "window.requestAnimationFrame=cb=>setTimeout(()=>cb(performance.now()),16);"
    "const ac=new(window.AudioContext||window.webkitAudioContext)();const osc=ac.createOscillator();const g=ac.createGain();"
    "g.gain.value=0.00001;osc.connect(g);g.connect(ac.destination);osc.start();}catch(e){}"
    "try{const rb=await fetch('http://127.0.0.1:8765/ref-image').then(r=>r.blob());"
    "window.__roccoFile=new File([rb],cfg.refName||'rocco_sheet_v2.png',{type:'image/png'});"
    "const origClick=HTMLInputElement.prototype.click;"
    "HTMLInputElement.prototype.click=function(){"
    "if(this.type==='file'&&window.__roccoFile){"
    "const dt=new DataTransfer();dt.items.add(window.__roccoFile);this.files=dt.files;"
    "this.dispatchEvent(new Event('input',{bubbles:true}));"
    "this.dispatchEvent(new Event('change',{bubbles:true}));return;}"
    "return origClick.apply(this,arguments);};}catch(e){}"
    "const sleep=ms=>new Promise(r=>setTimeout(r,ms));"
    "const log=msg=>fetch('http://127.0.0.1:8765/log',{method:'POST',mode:'no-cors',body:JSON.stringify({msg})}).catch(()=>{});"
    "const badge=document.createElement('div');"
    "badge.style.cssText='position:fixed;bottom:16px;right:16px;z-index:999999;background:rgb(15,23,42);color:rgb(56,189,248);padding:12px 18px;border-radius:10px;font:600 13px sans-serif;box-shadow:0 8px 24px rgba(0,0,0,0.5);border:1px solid rgb(56,189,248);pointer-events:none;';"
    "document.body.appendChild(badge);"
    "const setStatus=t=>{badge.textContent=t;log(t);};"
    "const getImgs=()=>Array.from(document.querySelectorAll('img[alt*=\"Option\"],img[src*=\"/asb/\"]')).filter(i=>i.complete&&i.naturalWidth>200&&i.src);"
    "const attachRef=async()=>{"
    "const refKey=(cfg.refName||'rocco_sheet').replace('.png','');"
    "const addBtns=Array.from(document.querySelectorAll('button[aria-label*=\"İçerik öğelerini istem kutusuna ekle\"],button[aria-label*=\"Add content\"]')).filter(b=>b.offsetParent!==null);"
    "if(!addBtns.length)return;"
    "addBtns[addBtns.length-1].click();"
    "await sleep(1300);"
    "let overlay=document.querySelector('.cdk-overlay-container');"
    "const findItem=()=>Array.from((overlay||document).querySelectorAll('.cdk-overlay-container button, .cdk-overlay-container [role=\"button\"], .cdk-overlay-container img')).find(el=>{"
    "const t=((el.textContent||'')+' '+(el.getAttribute('aria-label')||'')+' '+(el.getAttribute('alt')||'')).toLowerCase();"
    "return t.includes('rocco')||t.includes(refKey.toLowerCase())||t.includes('ref_');});"
    "let item=findItem();"
    "if(!item){"
    "const inp=document.querySelector('.cdk-overlay-container input[placeholder*=\"Öğe\"], .cdk-overlay-container input[placeholder*=\"Search\"]');"
    "if(inp){const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;"
    "setter.call(inp,'rocco');inp.dispatchEvent(new Event('input',{bubbles:true}));await sleep(1200);item=findItem();}}"
    "if(item){const btn=item.closest('button')||item;btn.click();await sleep(1000);"
    "const conf=Array.from(document.querySelectorAll('.cdk-overlay-container button')).find(b=>(b.textContent||'').includes('İsteme ekle')||(b.textContent||'').includes('Add to prompt'));"
    "if(conf){conf.click();await sleep(900);}"
    "}else if(window.__roccoFile){"
    "const upBtn=document.querySelector('.cdk-overlay-container button.upload-button, .cdk-overlay-container button[aria-label*=\"Medya yükle\"]');"
    "if(upBtn){upBtn.click();await sleep(3500);"
    "const acc=Array.from(document.querySelectorAll('button')).find(b=>(b.textContent||'').includes('Kabul ediyorum')||(b.textContent||'').includes('I agree'));"
    "if(acc){acc.click();await sleep(1500);}"
    "const conf=Array.from(document.querySelectorAll('.cdk-overlay-container button')).find(b=>(b.textContent||'').includes('İsteme ekle')||(b.textContent||'').includes('Add to prompt'));"
    "if(conf){conf.click();await sleep(1000);}}}"
    "document.body.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',code:'Escape',keyCode:27,bubbles:true}));"
    "await sleep(400);};"
    "setStatus('Baslatildi: '+cfg.scenes.length+' sahne uretilecek (PC serbest)');"
    "for(let i=0;i<cfg.scenes.length;i++){"
    "const s=cfg.scenes[i];"
    "setStatus('Sahne '+s.num+' ('+(i+1)+'/'+cfg.scenes.length+') hazirlaniyor...');"
    "for(let w=0;w<20;w++){"
    "const stopBtn=Array.from(document.querySelectorAll('button[aria-label*=\"Durdur\"],button[aria-label*=\"Stop\"]')).find(b=>b.offsetParent!==null);"
    "if(stopBtn){stopBtn.click();await sleep(1200);}else break;}"
    "const ed=document.querySelector('div.ProseMirror');"
    "if(!ed){setStatus('HATA: ProseMirror editor bulunamadi!');break;}"
    "ed.focus();"
    "const sel=window.getSelection();const rng=document.createRange();rng.selectNodeContents(ed);sel.removeAllRanges();sel.addRange(rng);"
    "document.execCommand('delete',false,null);await sleep(300);"
    "await attachRef();"
    "ed.focus();"
    "const sel2=window.getSelection();const rng2=document.createRange();rng2.selectNodeContents(ed);rng2.collapse(false);sel2.removeAllRanges();sel2.addRange(rng2);"
    "const txt=' '+s.prompt;"
    "let ok=document.execCommand('insertText',false,txt);"
    "if(!ok||!(ed.innerText||'').includes(s.prompt.slice(0,20))){"
    "const dt=new DataTransfer();dt.setData('text/plain',txt);"
    "ed.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));}"
    "await sleep(900);"
    "const beforeSrcs=new Set(getImgs().map(im=>im.src));"
    "const genBtns=Array.from(document.querySelectorAll('button[aria-label*=\"Oluşturmaya başla\"],button[aria-label*=\"Generate\"]')).filter(b=>b.offsetParent!==null);"
    "if(genBtns.length){genBtns[genBtns.length-1].click();}"
    "else{ed.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,bubbles:true}));}"
    "await sleep(2200);"
    "if((ed.innerText||'').trim().length>30&&genBtns.length){genBtns[genBtns.length-1].click();await sleep(1000);}"
    "setStatus('Sahne '+s.num+' uretiliyor...');"
    "let newImgs=[];let retries=0;"
    "for(let t=0;t<90;t++){"
    "await sleep(1500);"
    "const cur=getImgs().filter(im=>!beforeSrcs.has(im.src));"
    "if(cur.length>0){await sleep(2500);newImgs=getImgs().filter(im=>!beforeSrcs.has(im.src));break;}"
    "const rBtn=Array.from(document.querySelectorAll('button')).find(b=>b.offsetParent!==null&&((b.textContent||'').trim()==='Tekrar dene'||(b.textContent||'').trim()==='Try again'));"
    "if(rBtn){retries++;if(retries>2){setStatus('Sahne '+s.num+' bot/oran engeline takildi, 30sn bekleniyor...');await sleep(30000);retries=0;}"
    "else{setStatus('Sahne '+s.num+' Tekrar dene bekleniyor (20sn)...');await sleep(20000);rBtn.click();t=0;}}}"
    "if(!newImgs.length){setStatus('Sahne '+s.num+' zaman asimi, sonrakine geciliyor...');continue;}"
    "for(let k=0;k<newImgs.length;k++){"
    "try{const im=newImgs[k];const c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight;"
    "c.getContext('2d').drawImage(im,0,0);const dataUrl=c.toDataURL('image/png');"
    "await fetch('http://127.0.0.1:8765/save',{method:'POST',mode:'no-cors',body:JSON.stringify({scene:s.num,index:k+1,dataUrl})});"
    "}catch(e){log('Kayit hatasi: '+e);}}"
    "setStatus('Sahne '+s.num+' kaydedildi ('+newImgs.length+' gorsel)');"
    "const waitMs=6500+Math.floor(Math.random()*3500);"
    "await sleep(waitMs);}"
    "setStatus('TUM SAHNELER TAMAMLANDI!');"
    "fetch('http://127.0.0.1:8765/done',{method:'POST',mode:'no-cors',body:'{}'}).catch(()=>{});"
    "});"
)


class FlowBridgeServer:
    def __init__(self, pending_scenes, out_dir: str, ref_path: str):
        self.pending_scenes = pending_scenes
        self.out_dir = out_dir
        self.ref_path = ref_path
        self.ref_name = os.path.basename(ref_path) if ref_path else "rocco_sheet_v2.png"
        self.saved_scenes = set()
        self.finished = False


def run_server(bridge: FlowBridgeServer, port: int):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header("Access-Control-Allow-Private-Network", "true")
            self.send_header("Cache-Control", "no-store")

        def do_OPTIONS(self):
            self.send_response(200)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path.startswith("/tasks"):
                remaining = [
                    s for s in bridge.pending_scenes
                    if not os.path.exists(os.path.join(bridge.out_dir, f"sahne_{s['num']:02d}_1.png"))
                ]
                payload = json.dumps({
                    "refName": bridge.ref_name,
                    "scenes": remaining
                }, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(payload)
                print(f"\n[BAGLANDI] Tarayici {len(remaining)} sahnelik gorev listesini aldi (Arka planda calisiyor, PC'yi rahatca kullanabilirsiniz).")
                return

            if self.path.startswith("/ref-image"):
                if bridge.ref_path and os.path.exists(bridge.ref_path):
                    with open(bridge.ref_path, "rb") as f:
                        img_bytes = f.read()
                    self.send_response(200)
                    self._cors()
                    self.send_header("Content-Type", "image/png")
                    self.end_headers()
                    self.wfile.write(img_bytes)
                    return
                self.send_response(404)
                self._cors()
                self.end_headers()
                return

            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b"OK")

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode("utf-8", errors="ignore")
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                data = {}

            if self.path.startswith("/log"):
                msg = data.get("msg", "")
                if msg:
                    print(f"[FLOW] {msg}")
            elif self.path.startswith("/save"):
                scene_num = int(data.get("scene", 0))
                idx = int(data.get("index", 1))
                data_url = data.get("dataUrl", "")
                if scene_num > 0 and data_url:
                    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
                    img_bytes = base64.b64decode(b64)
                    filename = f"sahne_{scene_num:02d}_{idx}.png"
                    filepath = os.path.join(bridge.out_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(img_bytes)
                    kb = len(img_bytes) // 1024
                    bridge.saved_scenes.add(scene_num)
                    print(f"  [KAYDEDILDI] {filename} ({kb} KB) -> {filepath}")
            elif self.path.startswith("/done"):
                print("\n[TAMAMLANDI] Tum sahneler uretildi ve kaydedildi!")
                bridge.finished = True

            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, format, *args):
            return

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1.0
    while not bridge.finished:
        remaining = [
            s for s in bridge.pending_scenes
            if not os.path.exists(os.path.join(bridge.out_dir, f"sahne_{s['num']:02d}_1.png"))
        ]
        if not remaining:
            print("\n[TAMAMLANDI] Listedeki tum sahneler sahneler/ klasorune kaydedildi!")
            break
        server.handle_request()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompts_file")
    parser.add_argument("--ref", default="_marka/rocco_sheet_v2.png")
    parser.add_argument("--out", default="sahneler")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    prompts_path = os.path.abspath(args.prompts_file)
    if not os.path.exists(prompts_path):
        print(f"Dosya bulunamadi: {prompts_path}")
        sys.exit(1)

    base_dir = os.path.dirname(prompts_path)
    out_dir = args.out if os.path.isabs(args.out) else os.path.join(base_dir, args.out)
    os.makedirs(out_dir, exist_ok=True)

    ref_path = resolve_ref_image(base_dir, args.ref)
    scenes = parse_prompts_file(prompts_path)

    pending = []
    for s in scenes:
        out_file = os.path.join(out_dir, f"sahne_{s['num']:02d}_1.png")
        if os.path.exists(out_file) and os.path.getsize(out_file) > 10000:
            print(f"[ATLANDI] Sahne {s['num']:02d} zaten var: {out_file}")
        else:
            pending.append(s)

    if not pending:
        print("Uretilecek kalan sahne yok, hepsi tamamlanmis!")
        return

    copy_to_clipboard(CONSOLE_LOADER)

    print("=" * 72)
    print(f"TOPLAM {len(pending)} SAHNE URETILECEK (Sahne {pending[0]['num']} -> Sahne {pending[-1]['num']})")
    print(f"Cikti klasoru : {out_dir}")
    print(f"Referans      : {ref_path}")
    print("=" * 72)
    print("FARE / KLAVYE / EKRAN ODAK MUDehalesi YOKTUR — PC'nizi normal kullanabilirsiniz!")
    print("")
    print("Sadece 1 kez normal Chrome'daki Flow sekmesinde F12 -> Console kismina")
    print("Ctrl+V yapip Enter'a basin (kod su an panonuza kopyalandi).")
    print("Sonrasinda baska sekmeye/uygulamaya gecebilirsiniz, arka planda uretip kaydeder.")
    print("=" * 72)

    bridge = FlowBridgeServer(pending, out_dir, ref_path)
    run_server(bridge, args.port)


if __name__ == "__main__":
    main()
