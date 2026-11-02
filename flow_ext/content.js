let lastMouse = { clientX: 0, clientY: 0, screenX: 0, screenY: 0, ts: 0 };

window.addEventListener("mousemove", (e) => {
  lastMouse = {
    clientX: e.clientX,
    clientY: e.clientY,
    screenX: e.screenX,
    screenY: e.screenY,
    ts: Date.now()
  };
}, { passive: true });

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
      if (isVis(b) && (b.innerText || "").toLowerCase().includes(low)) {
        return b;
      }
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

function collectState() {
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
    mouse: lastMouse,
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
}

function extractCanvasDataUrl(targetSrc) {
  const imgs = Array.from(document.querySelectorAll('img[alt*="Option"], img[src*="/asb/"]'));
  const img = imgs.find(i => i.src === targetSrc);
  if (!img || !img.naturalWidth) return null;
  const c = document.createElement("canvas");
  c.width = img.naturalWidth;
  c.height = img.naturalHeight;
  c.getContext("2d").drawImage(img, 0, 0);
  return c.toDataURL("image/png");
}

let busy = false;

setInterval(() => {
  if (busy) return;
  busy = true;
  const st = collectState();
  chrome.runtime.sendMessage({ type: "BRIDGE_POST", path: "/state", payload: st }, (resp) => {
    if (resp && resp.ok && resp.data && resp.data.extractSrc) {
      const targetSrc = resp.data.extractSrc;
      const destName = resp.data.destName;
      const dataUrl = extractCanvasDataUrl(targetSrc);
      if (dataUrl) {
        chrome.runtime.sendMessage({
          type: "BRIDGE_POST",
          path: "/save-image",
          payload: { destName, dataUrl, src: targetSrc }
        }, () => { busy = false; });
      } else {
        chrome.runtime.sendMessage({ type: "FETCH_IMAGE_BASE64", url: targetSrc }, (r2) => {
          if (r2 && r2.ok && r2.dataUrl) {
            chrome.runtime.sendMessage({
              type: "BRIDGE_POST",
              path: "/save-image",
              payload: { destName, dataUrl: r2.dataUrl, src: targetSrc }
            }, () => { busy = false; });
          } else {
            busy = false;
          }
        });
      }
    } else {
      busy = false;
    }
  });
}, 400);
