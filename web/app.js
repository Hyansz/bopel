"use strict";

/* ═══════════════════════════════════════════════════════════════════
   BOPEL Automation Toolkit 2.0 — front-end pywebview (SPA)
   Navigasi antar screen murni JS (show/hide section), tanpa reload.

   KONTRAK JS <-> PYTHON (JANGAN diubah namanya / urutan argumennya):
   Dipanggil Python (evaluate_js):
     appendLogLine(key, line)          updateSummaryCards(key, s)
     onToolStarted(key)                onToolFinished(key, success, error, banner)
     pushItems(key, items)             showScreenshotPreviews(key, items)
   Method Api yang dipanggil JS:
     get_config, start_tool(script, key), stop_tool(script),
     set_active_store(name, start, end), copy_text, get_logs,
     get_system_info, get_settings_info, exit_app
   ═══════════════════════════════════════════════════════════════════ */

const DEFAULT_TOOLS = [
  { name: "Checklist Automation", script: "check.py",
    description: "Checklist pesanan dan validasi harga Shopee vs aplikasi" },
  { name: "Inventory Scanner", script: "scan.py",
    description: "Scan status pembayaran dan validasi Excel" },
];
const APP_META = { name: "Bopel Automation Toolkit", version: "2.0.0", subtitle: "Internal Warehouse Utilities" };

const $ = (sel) => document.querySelector(sel);
const REDUCE_MOTION = !!(window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

/* ── ikon SVG inline (tanpa jaringan) ─────────────────────────────── */
const IC = {
  checklist: '<polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
  scan: '<path d="M4 7V4h16v3"/><path d="M9 20h6"/><path d="M12 4v16"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h0a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51h0a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v0a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  exit: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
  tick: '<polyline class="draw" pathLength="1" points="20 6 9 17 4 12"/>',
  cross: '<line class="draw" pathLength="1" x1="18" y1="6" x2="6" y2="18"/><line class="draw" pathLength="1" x1="6" y1="6" x2="18" y2="18"/>',
  play: '<polygon points="7 4 20 12 7 20 7 4"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
  download: '<path d="M12 3v12"/><path d="m7 10 5 5 5-5"/><path d="M5 21h14"/>',
  alert: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
  info: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5V12l3 2"/>',
  terminal: '<polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>',
  dot: '<circle cx="12" cy="12" r="9"/>',
};
function svg(name, size = 18, cls = "") {
  return `<svg ${cls ? `class="${cls}" ` : ""}viewBox="0 0 24 24" width="${size}" height="${size}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[name] || IC.dot}</svg>`;
}
const TOOL_ICON = { "check.py": "checklist", "check_new.py": "checklist", "screenshot_iklan.py": "image", "scan.py": "scan" };
function hydrateIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = svg(el.dataset.icon, Number(el.dataset.size) || 18);
  });
}

// Mode default
const DEFAULT_TOOL_MODE = { "scan.py": "Scan Kode Pesanan" };

/* ── state global ─────────────────────────────────────────────────── */
let TOOLS = DEFAULT_TOOLS;
let currentTool = null;          // { name, script, description, ... }
let STORES = [];
let storeChoice = null;
let dataMode = null;             // "manual" | "otomatis" | null (wajib dipilih)
let CONFIG = null;               // salinan get_config (untuk makro paste)
let fetchRange = null;
const lastRun = {};              // script -> { ok, at } (hasil terakhir sesi ini)
const unseen = {};               // script -> "done" | "fail" (badge sidebar)

/* ── util kecil ───────────────────────────────────────────────────── */
function escHtml(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function pad2(n) { return String(n).padStart(2, "0"); }
function fmtElapsed(t) {
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  return `${pad2(Math.floor(s / 60))}:${pad2(s % 60)}`;
}
function fmtClock(d) { return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`; }
function baseScript(key) {
  const s = String(key).split("::")[0];
  return s === "shopee_fetch.py" ? "check.py" : s;
}
function toolNameOf(key) {
  const raw = String(key).split("::")[0];
  if (raw === "shopee_fetch.py") return "Fetch Shopee";
  const t = TOOLS.find((x) => x.script === raw);
  return t ? t.name : raw;
}
function hotkeyText() { return (CONFIG && CONFIG.paste_macro && CONFIG.paste_macro.hotkey) || "Ctrl+Alt+V"; }
function bridgeApi() { return window.pywebview && window.pywebview.api; }

function showToast(text, kind = "info", ms = 2400) {
  const root = $("#toast-root");
  if (!root) return;
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.innerHTML = `<span class="toast-ic">${svg(kind === "error" ? "cross" : kind === "success" ? "tick" : "info", 16)}</span><span></span>`;
  t.lastChild.textContent = text;
  root.appendChild(t);
  while (root.children.length > 3) root.firstChild.remove();
  setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 220); }, ms);
}

/* ── sidebar ──────────────────────────────────────────────────────── */
function renderSidebar(tools) {
  const box = $("#sidebar-tools");
  box.innerHTML = "";
  for (const t of tools) {
    const btn = document.createElement("button");
    btn.className = "sb-item";
    btn.dataset.nav = "tool";
    btn.dataset.script = t.script;
    btn.title = t.name;
    btn.setAttribute("aria-label", t.name);
    btn.innerHTML =
      `<span class="sb-icon">${svg(TOOL_ICON[t.script] || "dot")}</span>` +
      `<span class="sb-label">${escHtml(t.name)}</span>` +
      `<span class="sb-state" aria-hidden="true"><i class="pulse-dot"></i>${svg("tick", 16, "st-ok")}${svg("cross", 16, "st-fail")}</span>`;
    if (currentTool && currentTool.script === t.script && isSectionActive("tool")) btn.classList.add("active");
    box.appendChild(btn);
  }
  // Tambahkan tombol Sales Order (SOON)
  const soBtn = document.createElement("button");
  soBtn.className = "sb-item";
  soBtn.dataset.nav = "so";
  soBtn.setAttribute("aria-label", "Sales Order");
  soBtn.innerHTML = `<span class="sb-icon">${svg("doc")}</span><span class="sb-label">Sales Order</span>`;
  if (isSectionActive("so")) soBtn.classList.add("active");
  box.appendChild(soBtn);

  refreshSidebarStates();
}

function setActiveNav(btn) {
  document.querySelectorAll(".sb-item").forEach((b) => { b.classList.remove("active"); b.removeAttribute("aria-current"); });
  if (btn) { btn.classList.add("active"); btn.setAttribute("aria-current", "page"); }
}

function showSection(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  const section = document.querySelector(`.screen[data-section="${name}"]`);
  if (section) section.classList.add("active");
  const main = $("#main");
  if (main) main.scrollTop = 0;
}

function isSectionActive(name) {
  const s = document.querySelector(`.screen[data-section="${name}"]`);
  return !!(s && s.classList.contains("active"));
}

/* indikator per tool di sidebar + garis progres global + chip header */
function refreshSidebarStates() {
  let running = 0;
  for (const st of Object.values(toolStates)) if (st.running) running++;
  document.querySelectorAll('.sb-item[data-nav="tool"]').forEach((btn) => {
    const sc = btn.dataset.script;
    const isRun = Object.entries(toolStates).some(([k, st]) => st.running && baseScript(k) === sc);
    btn.dataset.state = isRun ? "running" : (unseen[sc] || "");
  });
  document.body.classList.toggle("is-running", running > 0);
  const hr = $("#hd-running");
  if (hr) {
    hr.classList.toggle("hidden", running === 0);
    $("#hd-running-text").textContent = running === 1 ? "1 proses berjalan" : `${running} proses berjalan`;
  }
  if (isSectionActive("dashboard")) renderDashboardTools();
}

/* ── navigasi ─────────────────────────────────────────────────────── */
function onNavClick(e) {
  const btn = e.target.closest(".sb-item");
  if (!btn) return;
  const nav = btn.dataset.nav;

  if (nav === "tool") {
    const script = btn.dataset.script;
    const tool = TOOLS.find((t) => t.script === script);
    if (!tool) return;
    currentTool = tool;
    setActiveNav(btn);
    delete unseen[script];
    refreshSidebarStates();
    renderToolHeader(tool);
    const hasModes = Array.isArray(tool.modes) && tool.modes.length > 0;
    if (hasModes && lastModeRun[tool.script]) {
      const key = runKey(script, lastModeRun[tool.script]);
      const mode = tool.modes.find((m) => m.name === lastModeRun[tool.script]);
      activeRun = { key, script: (mode && mode.script) || script };
      renderRun(key);
    } else {
      activeRun = hasModes ? null : { key: script, script };
      renderRun(hasModes ? null : script);
    }
    showSection("tool");
  } else if (nav === "dashboard") {
    setActiveNav(btn);
    showSection("dashboard");
    renderDashboard();
    refreshSystemInfo();
  } else if (nav === "so") {
    setActiveNav(btn);
    showSection("so");
  } else if (nav === "logs") {
    setActiveNav(btn);
    showSection("logs");
    refreshLogs(true);
  } else if (nav === "settings") {
    setActiveNav(btn);
    showSection("settings");
    refreshSettings();
  } else if (nav === "exit") {
    const api = bridgeApi();
    if (api && typeof api.exit_app === "function") api.exit_app();
    else console.log("[exit] bridge belum tersedia");
  }
}

/* ── state per-run (tool / mode) ──────────────────────────────────── */
const toolStates = {};

function toolStateOf(script) {
  if (!toolStates[script]) {
    toolStates[script] = {
      logHtml: [],
      summary: { total: null, ok: null, beda: null, notfound: null, durasi: null },
      banner: null,
      error: null,
      statusCls: "idle",
      statusText: "Siap",
      progress: 0,
      running: false,
      startedAt: null,
      stopRequested: false,
      items: [],
      copyFilter: "ok",
      screenshotFiles: [],
      shotIdx: 0,
    };
  }
  return toolStates[script];
}

/* key unik per (tool, mode): scan.py dipakai 2 mode */
function runKey(script, modeName) { return modeName ? script + "::" + modeName : script; }

let activeRun = null;            // { key, script } yang sedang DITAMPILKAN
const lastModeRun = {};          // tool.script -> nama mode terpilih / terakhir

function isActiveRun(key) { return !!(activeRun && activeRun.key === key && isSectionActive("tool")); }

function failRun(st, msg) {
  st.statusCls = "failed";
  st.statusText = "Gagal";
  st.error = msg || "Penyebab tidak diketahui.";
  st.progress = 0;
  st.running = false;
  st.startedAt = null;
}

/* ── status chip, progres, tombol ─────────────────────────────────── */
function leadIcon(cls) {
  if (cls === "running") return '<i class="pulse-dot"></i>';
  if (cls === "finished") return svg("tick", 16);
  if (cls === "failed") return svg("cross", 16);
  if (cls === "stopped") return svg("stop", 14);
  return '<i class="idle-dot"></i>';
}

function setStatus(cls, text) {
  const el = $("#tool-status");
  if (el.dataset.cls !== cls) {          // ikon digambar ulang hanya saat status berganti
    el.dataset.cls = cls;
    el.className = "status-chip tool-status " + cls;
    $("#tool-status-lead").innerHTML = leadIcon(cls);
  }
  $("#tool-status-text").textContent = text;
}

function statusLabel(st) {
  if (!st) return "Siap";
  if (st.statusCls === "running") return "Berjalan " + (st.startedAt ? fmtElapsed(st.startedAt) : "00:00");
  return st.statusText || "Siap";
}

function setProgress(st) {
  const wrap = $("#tool-progress-wrap");
  const fill = $("#tool-progress");
  const cls = st ? st.statusCls : "idle";
  wrap.classList.toggle("indeterminate", cls === "running");
  wrap.classList.toggle("done", cls === "finished");
  wrap.classList.toggle("failed", cls === "failed");
  fill.style.transform = cls === "running" ? "" : `scaleX(${cls === "finished" || cls === "failed" ? 1 : 0})`;
}

/* tool yang wajib memilih Manual/Otomatis dulu: Checklist (toko+Fetch) dan tool
   dengan auto_open_app (Otomatis = membuka aplikasi desktop, mis. Inventory BSM) */
function needsDataMode(tool) {
  if (!tool) return false;
  if (tool.auto_open_app) return true;
  return !!(tool.uses_stores && STORES.length && (tool.modes?.length || !tool.date_range));
}

function startHint(st) {
  if (st && st.running) return "";
  const fetchSt = toolStates["shopee_fetch.py"];
  if (fetchSt && fetchSt.running) return "Menunggu Fetch selesai";
  if (currentTool && !currentTool.modes?.length && needsDataMode(currentTool) && !dataMode) return "Pilih mode dulu";
  if (currentTool && Array.isArray(currentTool.modes) && currentTool.modes.length && !lastModeRun[currentTool.script]) return "Pilih mode dulu";
  return "";
}

function startDisabled(st) {
  if (st && st.running) return true;
  if (toolStates["shopee_fetch.py"] && toolStates["shopee_fetch.py"].running) return true;
  if (currentTool && !currentTool.modes?.length && needsDataMode(currentTool) && !dataMode) return true;
  if (currentTool && Array.isArray(currentTool.modes) && currentTool.modes.length && !lastModeRun[currentTool.script]) return true;
  return false;
}

function renderRunButtons(st) {
  const running = !!(st && st.running);
  const sb = $("#start-btn");
  sb.disabled = startDisabled(st);
  sb.classList.toggle("is-running", running);
  $("#start-label").textContent = running ? "Berjalan" : "Start";
  $("#start-ic").innerHTML = running ? '<span class="spinner"></span>' : svg("play", 14);
  $("#stop-btn").disabled = !running;
  const h = startHint(st);
  const hint = $("#start-hint");
  hint.textContent = h;
  hint.classList.toggle("hidden", !h);
}

/* ── ringkasan (kartu metrik) ─────────────────────────────────────── */
const SUM_FIELDS = [["total", "#sum-total"], ["ok", "#sum-ok"], ["beda", "#sum-beda"], ["notfound", "#sum-notfound"], ["durasi", "#sum-durasi"]];

function paintMetric(field, el, v, loading) {
  const card = el.closest(".sum-card");
  card.classList.toggle("loading", !!loading);
  card.classList.toggle("is-on", v != null && Number(v) > 0 && field !== "total" && field !== "durasi");
}

function renderSummary(st) {
  for (const [f, sel] of SUM_FIELDS) {
    const el = $(sel);
    const v = st && st.summary[f] != null ? st.summary[f] : null;
    if (el._raf) cancelAnimationFrame(el._raf);
    el.textContent = v != null ? v : "--";
    paintMetric(f, el, v, st && st.running && v == null);
  }
}

function countUp(el, to) {
  if (el._raf) cancelAnimationFrame(el._raf);
  const t0 = performance.now(), dur = 450;
  const step = (t) => {
    const p = Math.min(1, (t - t0) / dur);
    el.textContent = p < 1 ? Math.round(to * (1 - Math.pow(1 - p, 3))) : to;
    if (p < 1) el._raf = requestAnimationFrame(step);
  };
  el._raf = requestAnimationFrame(step);
}

function setMetric(field, sel, v) {
  const el = $(sel);
  const n = Number(v);
  if (!REDUCE_MOTION && Number.isInteger(n) && n > 0 && n < 100000 && String(v).trim() === String(n)) countUp(el, n);
  else el.textContent = v;
  paintMetric(field, el, v, false);
}

/* ── render satu run ke DOM ───────────────────────────────────────── */
function renderRun(key) {
  const st = key ? toolStateOf(key) : null;
  const cls = st ? st.statusCls : "idle";
  renderSummary(st);
  setStatus(cls, statusLabel(st));
  setProgress(st);

  const b = $("#success-banner");
  if (st && st.banner && cls === "finished") { $("#banner-text").textContent = st.banner; b.classList.add("show"); }
  else b.classList.remove("show");
  const ep = $("#error-panel");
  if (st && cls === "failed") { $("#error-text").textContent = st.error || ""; ep.classList.remove("hidden"); }
  else ep.classList.add("hidden");

  const isShot = !!(currentTool && currentTool.script === "screenshot_iklan.py");
  const sumRow = document.querySelector(".sum-row");
  if (sumRow) sumRow.classList.toggle("hidden", isShot);

  const logEl = $("#tool-log");
  logEl.innerHTML = st ? st.logHtml.join("") : "";
  $("#log-count").textContent = st && st.logHtml.length ? `${st.logHtml.length} baris` : "";
  $("#log-empty-text").textContent = st && st.running
    ? "Menunggu output pertama…"
    : (startHint(st) === "Pilih mode dulu" ? "Belum ada output. Pilih mode lalu tekan Start." : "Belum ada output. Tekan Start untuk memulai.");
  scrollLog(true);

  renderRunButtons(st);
  if (currentTool) refreshModeButtons(currentTool);
  renderCopyBar(st);
  renderScreenshotPreview(st);
}

/* auto-scroll log dengan tombol jeda */
let logPaused = false;
function scrollLog(force) {
  const el = $("#tool-log");
  if (force) setPaused(false);
  if (!logPaused) el.scrollTop = el.scrollHeight;
}
function setPaused(v) {
  logPaused = v;
  $("#scroll-label").textContent = v ? "Lanjutkan gulir" : "Jeda gulir";
  $("#scroll-ic").innerHTML = svg(v ? "play" : "pause", 14);
  $("#scroll-toggle").setAttribute("aria-label", v ? "Lanjutkan gulir otomatis" : "Jeda gulir otomatis");
}

/* ── mode & kontrol ───────────────────────────────────────────────── */
function refreshModeButtons(tool) {
  const running = Object.entries(toolStates).some(
    ([k, st]) => (k === tool.script || k.startsWith(tool.script + "::")) && st.running
  );
  const fetchRunning = !!(toolStates["shopee_fetch.py"] && toolStates["shopee_fetch.py"].running);
  document.querySelectorAll("#mode-btns .btn.choice, #data-mode-btns .btn.choice").forEach((b) => (b.disabled = running || fetchRunning));
  // Guard: fetch-btn mungkin tidak ada (di-hapus dari HTML)
  const fb = $("#fetch-btn");
  if (fb) fb.disabled = running || fetchRunning;
}

function syncZones() {
  const modeHidden = $("#mode-btns").classList.contains("hidden") && $("#data-mode-btns").classList.contains("hidden");
  $("#zone-mode").classList.toggle("hidden", modeHidden);
  const srcHidden = $("#zone-source").classList.contains("hidden");
  const help = $("#ctl-help");
  $("#tool-toolbar").classList.toggle("hidden", modeHidden && srcHidden);
  help.classList.toggle("hidden", !help.textContent || (modeHidden && srcHidden));
}

function setHelp(text) { $("#ctl-help").textContent = text || ""; syncZones(); }

function updateHelp(tool) {
  const hasModes = Array.isArray(tool.modes) && tool.modes.length > 0;
  if (hasModes) {
    const m = tool.modes.find((x) => x.name === lastModeRun[tool.script]);
    setHelp(m ? (m.description || "") : "Pilih mode untuk melanjutkan.");
  } else if (tool.auto_open_app) {
    setHelp(dataMode === "otomatis" ? `Aplikasi ${tool.auto_open_app} dibuka otomatis. Setelah siap, tekan Start.`
      : dataMode === "manual" ? "Siapkan data sendiri, lalu tekan Start."
      : "Pilih mode untuk melanjutkan.");
  } else setHelp("");
}

function renderModeSeg(tool) {
  const box = $("#mode-btns");
  const hasModes = Array.isArray(tool.modes) && tool.modes.length > 0;
  box.classList.toggle("hidden", !hasModes);
  box.innerHTML = "";
  if (hasModes) {
    for (const m of tool.modes) {
      const b = document.createElement("button");
      const on = m.name === lastModeRun[tool.script];
      b.className = "btn choice" + (on ? " active" : "");
      b.textContent = m.name;
      b.title = m.description || "";
      b.dataset.modeName = m.name;
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", on ? "true" : "false");
      b.addEventListener("click", () => selectMode(tool, m));
      box.appendChild(b);
    }
  }
  refreshModeButtons(tool);
}

/* memilih mode TIDAK menjalankan apa pun — Start yang menjalankan */
function selectMode(tool, mode) {
  lastModeRun[tool.script] = mode.name;
  const key = runKey(tool.script, mode.name);
  activeRun = { key, script: mode.script || tool.script };
  renderModeSeg(tool);
  updateHelp(tool);
  renderRun(key);
}

function renderToolHeader(tool) {
  $("#tool-name").textContent = tool.name;
  $("#tool-desc").textContent = tool.description || "";
  renderModeSeg(tool);
  if (needsDataMode(tool)) dataMode = "otomatis"; // Default ke mode otomatis

  // Aktifkan mode default untuk tool dengan mode (misal: Scan Kode Pesanan)
  if (tool.modes && tool.modes.length > 0) {
    const defaultMode = DEFAULT_TOOL_MODE[tool.script];
    if (defaultMode) {
      const mode = tool.modes.find((m) => m.name === defaultMode);
      if (mode) {
        lastModeRun[tool.script] = mode.name;
        activeRun = { key: runKey(tool.script, mode.name), script: mode.script || tool.script };
      }
    }
  }

  fetchRange = null;
  refreshModeButtons(tool);
  renderDataModeButtons(tool);
  applyDataModeUI(tool);
  updateHelp(tool);
}

function renderDataModeButtons(tool) {
  const box = $("#data-mode-btns");
  const needMode = needsDataMode(tool);
  box.classList.toggle("hidden", !needMode);
  if (!needMode) { syncZones(); return; }
  box.innerHTML = "";
  for (const [label, val] of [["Manual", "manual"], ["Otomatis", "otomatis"]]) {
    const b = document.createElement("button");
    b.className = "btn choice" + (dataMode === val ? " active" : "");
    b.textContent = label;
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", dataMode === val ? "true" : "false");
    b.title = val === "manual"
      ? "Salin data Shopee sendiri, lalu klik Start"
      : (tool.auto_open_app ? `Buka aplikasi ${tool.auto_open_app}, lalu klik Start`
        : "Ambil data dari Chrome toko lewat Fetch, lalu klik Start");
    b.addEventListener("click", () => {
      dataMode = val;
      renderDataModeButtons(tool);
      applyDataModeUI(tool);
      updateHelp(tool);
      if (val === "otomatis" && tool.auto_open_app) openDesktopApp(tool.auto_open_app);
    });
    box.appendChild(b);
  }
  refreshModeButtons(tool);
  syncZones();
}

function applyDataModeUI(tool) {
  const hasStores = !!(tool && tool.uses_stores && STORES.length);
  const isAuto = dataMode === "otomatis" && hasStores;
  const noDataMode = hasStores && tool.date_range && !tool.modes?.length;
  const isShot = !!(noDataMode && currentTool && currentTool.script === "screenshot_iklan.py");
  const showZone = isAuto || noDataMode;
  $("#zone-source").classList.toggle("hidden", !showZone);
  $("#store-btns").classList.toggle("hidden", !showZone || isShot);
  $("#store-group").classList.toggle("hidden", !showZone || isShot);
  $("#date-range").classList.toggle("hidden", !showZone);

  // Logika baru: Fetch hanya muncul di Checklist Automation (check_new.py / check.py)
  const isChecklist = tool && (tool.script === "check_new.py" || tool.script === "check.py");
  const fetchBtn = $("#fetch-btn");
  if (fetchBtn) {
    // Sembunyikan jika tool bukan checklist, atau jika mode bukan otomatis
    fetchBtn.classList.toggle("hidden", !(isChecklist && isAuto));
  }

  if (showZone) {
    if (!isShot) renderStoreButtons(tool);
    renderDateRange();
  }
  refreshModeButtons(tool);
  syncZones();
  renderRun(activeRun ? activeRun.key : null);
}

/* ── rentang tanggal ──────────────────────────────────────────────── */
function isoOffset(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}
function todayISO() { return isoOffset(0); }

const DATE_PRESETS = [["Hari ini", 0, 0], ["Kemarin", 1, 1], ["7 hari", 6, 0]];

function renderDateRange() {
  if (!fetchRange) fetchRange = { start: todayISO(), end: todayISO() };
  const s = $("#date-start"), e = $("#date-end");
  s.value = fetchRange.start;
  e.value = fetchRange.end;
  s.onchange = () => { fetchRange.start = s.value; renderDatePresets(); };
  e.onchange = () => { fetchRange.end = e.value; renderDatePresets(); };
  renderDatePresets();
}

function renderDatePresets() {
  const box = $("#date-presets");
  box.innerHTML = "";
  for (const [label, a, b] of DATE_PRESETS) {
    const btn = document.createElement("button");
    const on = fetchRange && fetchRange.start === isoOffset(a) && fetchRange.end === isoOffset(b);
    btn.className = "btn choice" + (on ? " active" : "");
    btn.textContent = label;
    btn.addEventListener("click", () => {
      fetchRange = { start: isoOffset(a), end: isoOffset(b) };
      renderDateRange();
    });
    box.appendChild(btn);
  }
}

function currentDateRange() {
  return { start: fetchRange ? fetchRange.start : todayISO(), end: fetchRange ? fetchRange.end : todayISO() };
}

/* Otomatis pada tool auto_open_app: minta Python membuka aplikasi desktop.
   Hanya nama (kunci di config.yaml desktop_apps) yang dikirim, bukan path. */
async function openDesktopApp(name) {
  const api = bridgeApi();
  if (!api || typeof api.open_desktop_app !== "function") {
    showToast(`Tidak bisa membuka ${name}: fitur belum tersedia di aplikasi`, "error", 3600);
    return;
  }
  showToast(`Membuka ${name}…`, "info", 1800);
  try {
    const res = await api.open_desktop_app(name);
    if (res && res.ok) showToast(`${name} dibuka`, "success");
    else showToast(`Gagal membuka ${name}: ${(res && res.message) || "alasan tidak diketahui"}`, "error", 4200);
  } catch (err) { showToast(`Gagal membuka ${name}: ${err}`, "error", 4200); }
}

function pushActiveStore(api, name) {
  const r = currentDateRange();
  return api.set_active_store(name, r.start, r.end).catch(() => {});
}

/* ── selector toko ────────────────────────────────────────────────── */
function renderStoreButtons(tool) {
  const box = $("#store-btns");
  const usesStores = !!(tool && tool.uses_stores && STORES.length);
  box.classList.toggle("hidden", !usesStores);
  if (!usesStores) return;
  box.innerHTML = "";
  const chosen = storeChoice || (STORES.find((x) => x.enabled) || {}).name;
  for (const s of STORES) {
    const b = document.createElement("button");
    const on = s.enabled && s.name === chosen;
    b.className = "btn choice store" + (on ? " active" : "");
    b.textContent = shortStore(s.name);
    b.title = s.name;
    b.setAttribute("aria-label", "Pilih " + s.name);
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", on ? "true" : "false");
    if (!s.enabled) b.disabled = true;
    b.addEventListener("click", () => {
      storeChoice = s.name;
      renderStoreButtons(tool);
      const api = bridgeApi();
      if (api && typeof api.set_active_store === "function") pushActiveStore(api, s.name);
    });
    box.appendChild(b);
  }
  if (!storeChoice) {
    const first = STORES.find((s) => s.enabled);
    if (first) {
      storeChoice = first.name;
      const api = bridgeApi();
      if (api && typeof api.set_active_store === "function") pushActiveStore(api, first.name);
    }
  }
}

/* ── Screenshot Iklan: kartu per toko ─────────────────────────────── */
const STORE_STATUS_TEXT = { wait: "Menunggu", proc: "Memproses", done: "Selesai", fail: "Gagal" };

function shortStore(name) { return String(name).replace(/^Toko\s*\d+\s*[—–-]\s*/, "").trim(); }
function fileKey(name) { return shortStore(name).replace(/\s+/g, "_").toLowerCase(); }

function storeStatus(st, idx, hasFile) {
  if (hasFile) return "done";
  if (!st) return "wait";
  if (st.statusCls === "running") return idx < st.shotIdx ? "done" : idx === st.shotIdx ? "proc" : "wait";
  if (st.statusCls === "finished") return "done";
  if (st.statusCls === "failed") return idx < st.shotIdx ? "done" : idx === st.shotIdx ? "fail" : "wait";
  return "wait";
}

function captionFor(fileName) {
  const storeName = fileName.replace(/_\d{4}_sd_\d{4}\.png$/, "").replace(/\.png$/i, "").replace(/_/g, " ");
  const now = new Date();
  return `Shopee Ads ${storeName} ${pad2(now.getDate())}/${pad2(now.getMonth() + 1)}/${now.getFullYear()}`;
}

function renderScreenshotPreview(st) {
  const box = $("#shot-previews");
  const isShot = !!(currentTool && currentTool.script === "screenshot_iklan.py");
  box.classList.toggle("hidden", !isShot);
  if (!isShot) return;
  const items = (st && st.screenshotFiles) || [];
  const used = new Set();
  const cards = STORES.filter((s) => s.enabled).map((s, i) => {
    const k = fileKey(s.name);
    const it = items.find((x) => x.path && x.path.split(/[\\/]/).pop().toLowerCase().includes(k));
    if (it) used.add(it);
    return { label: shortStore(s.name), idx: i, item: it };
  });
  items.filter((x) => !used.has(x)).forEach((it, j) => cards.push({ label: (it.path || "Screenshot").split(/[\\/]/).pop(), idx: cards.length + j, item: it }));

  box.innerHTML = `<div class="shot-paste-hint"><span class="hotkey-chip"></span><span>tempel 3 gambar + caption otomatis setelah proses selesai</span></div><div class="store-grid"></div>`;
  box.querySelector(".hotkey-chip").textContent = hotkeyText();
  const grid = box.querySelector(".store-grid");
  for (const c of cards) {
    const status = storeStatus(st, c.idx, !!c.item);
    const card = document.createElement("div");
    card.className = "store-card";
    card.dataset.idx = c.idx;
    card.dataset.status = status;
    card.innerHTML = `<div class="store-head"><span class="store-name"></span><span class="badge" data-status="${status}">${STORE_STATUS_TEXT[status]}</span></div>
      <div class="thumb-box">${c.item ? '<img class="shot-thumb" alt="">' : svg("image", 28)}</div>`;
    card.querySelector(".store-name").textContent = c.label;
    card.querySelector(".store-name").title = c.label;
    if (c.item) {
      const name = c.item.path ? c.item.path.split(/[\\/]/).pop() : "screenshot";
      const img = card.querySelector(".shot-thumb");
      img.src = c.item.uri || "";
      img.alt = "Hasil screenshot iklan " + c.label;
      const p = document.createElement("div");
      p.className = "shot-path"; p.textContent = name; p.title = c.item.path || "";
      const capBtn = document.createElement("button");
      capBtn.className = "btn secondary small copy-caption";
      capBtn.setAttribute("aria-label", "Salin caption " + c.label);
      capBtn.innerHTML = svg("copy", 14) + "<span>Salin Caption</span>";
      capBtn.addEventListener("click", async () => {
        const api = bridgeApi();
        if (api && typeof api.copy_text === "function") {
          const res = await api.copy_text(captionFor(name));
          flashCopy(capBtn, !!(res && res.ok), "Caption tersalin");
        }
      });
      card.append(p, capBtn);
    }
    grid.appendChild(card);
  }
}

function updateStoreBadges(st) {
  document.querySelectorAll("#shot-previews .store-card").forEach((card) => {
    const hasFile = !!card.querySelector(".shot-thumb");
    const s = storeStatus(st, Number(card.dataset.idx), hasFile);
    card.dataset.status = s;
    const badge = card.querySelector(".badge");
    badge.dataset.status = s;
    badge.textContent = STORE_STATUS_TEXT[s];
  });
}

/* dipanggil Python saat run selesai — array {path, uri} per toko */
function showScreenshotPreviews(key, items) {
  const st = toolStateOf(key);
  st.screenshotFiles = Array.isArray(items) ? items : [];
  if (isActiveRun(key)) renderScreenshotPreview(st);
}

function onShotCopyClick() {}

/* ── salin per kolom → Excel ──────────────────────────────────────── */
/* Bar salin per kolom: selalu tampil di tool Checklist (agar fiturnya terlihat); tombol aktif
   setelah Python mengirim data lewat pushItems(key, items). */
const COPY_TOOLS = new Set(["check.py", "check_new.py"]);

function renderCopyBar(st) {
  const bar = $("#copy-bar");
  const supports = !!(currentTool && COPY_TOOLS.has(currentTool.script));
  const hasItems = !!(st && Array.isArray(st.items) && st.items.length > 0);
  bar.classList.toggle("hidden", !(hasItems || supports));
  if (!(hasItems || supports)) return;
  const sel = $("#copy-filter");
  const filter = st ? st.copyFilter : "ok";
  if (sel.value !== filter) sel.value = filter;
  const rows = hasItems ? st.items.filter((it) => it.kategori === filter) : [];
  let note;
  if (!hasItems) {
    note = st && st.statusCls === "finished"
      ? "Proses selesai, tetapi tidak ada data yang dikirim untuk disalin"
      : st && st.running ? "Tersedia setelah proses selesai" : "Tersedia setelah proses dijalankan";
  } else {
    note = rows.length ? `${rows.length} item, baris sejajar di ketiga kolom` : "Tidak ada item di status ini";
  }
  $("#copy-count").textContent = note;
  bar.querySelectorAll(".btn").forEach((b) => (b.disabled = !rows.length));
  sel.disabled = !hasItems;
}

function copyColumn(field, btn) {
  if (!activeRun) return;
  const st = toolStateOf(activeRun.key);
  const rows = st.items.filter((it) => it.kategori === st.copyFilter);
  if (!rows.length) { showToast("Tidak ada data untuk disalin", "info"); return; }
  const text = rows.map((r) => {
    const v = r[field] != null ? r[field] : "";
    if (field === "harga_shopee" && /^\d+$/.test(v)) return Number(v).toLocaleString("en-US");
    return v;
  }).join("\n");
  copyTextToClipboard(btn, text);
}

function onCopyFilterChange() {
  if (!activeRun) return;
  const st = toolStateOf(activeRun.key);
  st.copyFilter = $("#copy-filter").value;
  renderCopyBar(st);
}

function pushItems(key, items) {
  const st = toolStateOf(key);
  st.items = Array.isArray(items) ? items : [];
  if (isActiveRun(key)) renderCopyBar(st);
}

/* ── pewarnaan log ────────────────────────────────────────────────── */
const LOG_MARKER_CLASS = { "[RUN]": "info", "[OK]": "success", "[FAIL]": "error", "[ERROR]": "error", "[DEBUG]": "debug" };
const LOG_ERR_MARKERS = ["\u274c", "\u26d4", "\u2718"];
const LOG_WARN_MARKERS = ["\u26a0", "\u23f3", "\u{1F4CC}"];
const LOG_OK_MARKERS = ["\u2705", "\u2714"];

function styleLogLine(line) {
  line = String(line);
  const stripped = line.replace(/^\s+/, "");
  if (!stripped) return escHtml(line);
  const lead = line.slice(0, line.length - stripped.length);
  const m = stripped.match(/^(\S+)([\s\S]*)$/);
  const first = m[1], rest = m[2];
  let cls = LOG_MARKER_CLASS[first] || "";
  if (!cls) {
    if (LOG_ERR_MARKERS.some((x) => first.startsWith(x))) cls = "error";
    else if (LOG_WARN_MARKERS.some((x) => first.startsWith(x))) cls = "warn";
    else if (LOG_OK_MARKERS.some((x) => first.startsWith(x))) cls = "success";
  }
  if (!cls) return escHtml(line);
  return escHtml(lead) + `<span class="log-marker log-marker-${cls}">${escHtml(first)}</span>` + escHtml(rest);
}

/* level baris log: info | warn | error (untuk filter & warna baris) */
function classifyLog(line) {
  const s = String(line);
  if (/\[FAIL\]|\[ERROR\]|\bERROR\b|\bCRITICAL\b|Traceback|\u274c|\u26d4|\u2718/.test(s)) return "error";
  if (/\bWARN(ING)?\b|\u26a0|\u23f3/.test(s)) return "warn";
  return "info";
}

/* ── dipanggil Python (reader thread) via evaluate_js ─────────────── */
function appendLogLine(key, line) {
  const st = toolStateOf(key);
  const lv = classifyLog(line);
  const html = styleLogLine(line);
  st.logHtml.push(`<span class="lv-${lv}">${html}</span>\n`);
  /* tahap Screenshot Iklan: nama toko yang muncul di log = toko yang sedang diproses */
  if (baseScript(key) === "screenshot_iklan.py") {
    const low = String(line).toLowerCase();
    STORES.filter((s) => s.enabled).forEach((s, i) => {
      const n = (s.name.match(/Toko\s*(\d+)/i) || [])[1];
      if (i > st.shotIdx && (low.includes(shortStore(s.name).toLowerCase()) || (n && new RegExp("toko\\s*" + n + "\\b").test(low)))) st.shotIdx = i;
    });
  }
  if (isActiveRun(key)) {
    const el = $("#tool-log");
    el.insertAdjacentHTML("beforeend", `<span class="log-anim lv-${lv}">${html}</span>\n`);
    $("#log-count").textContent = `${st.logHtml.length} baris`;
    scrollLog(false);
    if (baseScript(key) === "screenshot_iklan.py") updateStoreBadges(st);
  }
}

function updateSummaryCards(key, s) {
  const st = toolStateOf(key);
  for (const [f] of SUM_FIELDS) if (s[f] != null) st.summary[f] = s[f];
  if (!isActiveRun(key)) return;
  for (const [f, sel] of SUM_FIELDS) if (s[f] != null) setMetric(f, sel, s[f]);
  for (const [f, sel] of SUM_FIELDS) if (st.summary[f] == null && st.running) paintMetric(f, $(sel), null, true);
}

function onToolStarted(key) {
  const st = toolStateOf(key);
  if (!st.startedAt) st.startedAt = Date.now();
  st.stopRequested = false;
  st.running = true;
  st.statusCls = "running";
  st.statusText = "Berjalan";
  st.error = null;
  st.progress = 20;
  if (isActiveRun(key)) renderRun(key);
  refreshSidebarStates();
}

/* tidak ada auto-nav setelah selesai: user tetap di tempat; badge di
   sidebar + toast memberi tahu hasilnya. */
function markToolHasResult(key, ok) {
  const sc = baseScript(key);
  unseen[sc] = ok ? "done" : "fail";
  lastRun[sc] = { ok: !!ok, at: new Date() };
}

function onToolFinished(key, success, error, banner) {
  const st = toolStateOf(key);
  const wasStopped = st.stopRequested || st.statusCls === "stopped";
  if (success) {
    if (st.summary.durasi == null && st.startedAt) st.summary.durasi = ((Date.now() - st.startedAt) / 1000).toFixed(1);
    st.statusCls = "finished";
    st.statusText = "Selesai";
    st.progress = 100;
    st.banner = banner;
    st.error = null;
  } else if (wasStopped) {
    st.statusCls = "stopped";
    st.statusText = "Dihentikan";
    st.error = null;
  } else {
    failRun(st, error);
  }
  st.running = false;
  st.startedAt = null;
  st.stopRequested = false;
  markToolHasResult(key, success);
  if (isActiveRun(key)) renderRun(key);
  refreshSidebarStates();
  const name = toolNameOf(key);
  if (success) showToast(`${name} selesai`, "success");
  else if (wasStopped) showToast(`${name} dihentikan`, "info");
  else showToast(`${name} gagal`, "error", 3600);
}

function resetRunState(st) {
  st.logHtml = [];
  st.summary = { total: null, ok: null, beda: null, notfound: null, durasi: null };
  st.banner = null;
  st.error = null;
  st.statusCls = "running";
  st.statusText = "Berjalan";
  st.progress = 20;
  st.running = true;
  st.startedAt = Date.now();
  st.stopRequested = false;
  st.items = [];
  st.copyFilter = "ok";
  st.screenshotFiles = [];
  st.shotIdx = 0;
}

/* ── Start / Stop ─────────────────────────────────────────────────── */
function startFailed(st, key, msg) {
  failRun(st, msg);
  renderRun(key);
  refreshSidebarStates();
}

/* UI langsung berubah ke "Berjalan" saat Start diklik (tanpa menunggu callback Python) */
function launch(script, key, st, before) {
  const api = bridgeApi();
  if (!api || typeof api.start_tool !== "function") return startFailed(st, key, "Jembatan ke aplikasi belum siap. Tutup lalu buka ulang BOPEL.");
  const go = () => api.start_tool(script, key);
  Promise.resolve(before ? before(api) : null).then(go).then((res) => {
    if (!res || !res.ok) startFailed(st, key, "Tidak bisa memulai: " + ((res && res.message) || "alasan tidak diketahui"));
  }).catch((err) => startFailed(st, key, "Kesalahan jembatan: " + err));
}

function onStart() {
  if (!currentTool) return;
  if (Array.isArray(currentTool.modes) && currentTool.modes.length) {
    const m = currentTool.modes.find((x) => x.name === lastModeRun[currentTool.script]);
    if (m) onModeClick(currentTool, m);
    return;
  }
  const script = currentTool.script;
  const key = script;
  activeRun = { key, script };
  const st = toolStateOf(key);
  resetRunState(st);
  renderRun(key);
  refreshSidebarStates();
  const needsStore = currentTool.uses_stores && STORES.length;
  const isShot = currentTool.script === "screenshot_iklan.py";
  launch(script, key, st, needsStore
    ? (api) => pushActiveStore(api, isShot ? null : (storeChoice || (STORES.find((s) => s.enabled) || {}).name))
    : null);
}

/* menjalankan sebuah mode (dipanggil Start bila tool punya modes) */
function onModeClick(tool, mode) {
  const script = mode.script || tool.script;
  const key = runKey(tool.script, mode.name);
  lastModeRun[tool.script] = mode.name;
  activeRun = { key, script };
  const st = toolStateOf(key);
  resetRunState(st);
  renderModeSeg(tool);
  renderRun(key);
  refreshSidebarStates();
  launch(script, key, st, null);
}

function onStop() {
  if (!currentTool) return;
  const run = activeRun || { key: currentTool.script, script: currentTool.script };
  const st = toolStateOf(run.key);
  st.stopRequested = true;
  const api = bridgeApi();
  if (api && typeof api.stop_tool === "function") api.stop_tool(run.script);
  st.statusCls = "stopped";
  st.statusText = "Dihentikan";
  st.running = false;
  st.startedAt = null;
  renderRun(run.key);
  refreshSidebarStates();
}

function onFetchClick() {
  const script = "shopee_fetch.py";
  const key = script;
  const st = toolStateOf(key);
  if (st.running) { activeRun = { key, script }; renderRun(key); return; }
  activeRun = { key, script };
  resetRunState(st);
  renderRun(key);
  refreshSidebarStates();
  launch(script, key, st, (api) => pushActiveStore(api, storeChoice || (STORES.find((s) => s.enabled) || {}).name));
}

/* ── dashboard ────────────────────────────────────────────────────── */
function meterTone(p) { return p >= 90 ? "crit" : p >= 75 ? "warn" : ""; }
function setMeter(barSel, valSel, text) {
  const p = Math.max(0, Math.min(100, parseFloat(text) || 0));
  const bar = $(barSel);
  bar.style.transform = `scaleX(${p / 100})`;
  bar.className = meterTone(p);
  $(valSel).textContent = text;
}

async function refreshSystemInfo() {
  const api = bridgeApi();
  if (!api || typeof api.get_system_info !== "function") return;
  try {
    const info = await api.get_system_info();
    if (!info) return;
    if (info.python) $("#dash-python").textContent = `Python ${info.python}${info.os ? "  |  " + info.os : ""}`;
    if (info.date) $("#dash-date").textContent = info.date;
    if (info.cpu) setMeter("#dash-cpu-bar", "#dash-cpu", info.cpu);
    if (info.ram) setMeter("#dash-ram-bar", "#dash-ram", info.ram);
  } catch (err) { /* polling gagal sekali — abaikan */ }
}

function renderMacro() {
  const pm = CONFIG && CONFIG.paste_macro;
  $("#macro-hotkey").textContent = hotkeyText();
  const badge = $("#macro-state");
  if (pm && typeof pm.enabled === "boolean") {
    badge.dataset.status = pm.enabled ? "done" : "fail";
    badge.textContent = pm.enabled ? "Aktif" : "Nonaktif";
  } else {
    badge.dataset.status = "wait";
    badge.textContent = "Status tidak terbaca";
  }
}

function renderDashboardTools() {
  const box = $("#dash-tools");
  if (!box) return;
  box.innerHTML = "";
  for (const t of TOOLS) {
    const isRun = Object.entries(toolStates).some(([k, st]) => st.running && baseScript(k) === t.script);
    const lr = lastRun[t.script];
    const dot = isRun ? "" : lr ? (lr.ok ? "ok" : "fail") : "";
    const text = isRun ? "Sedang berjalan" : lr ? `${lr.ok ? "Selesai" : "Gagal"} pukul ${fmtClock(lr.at)}` : "Belum dijalankan di sesi ini";
    const card = document.createElement("div");
    card.className = "tool-card";
    card.innerHTML = `<div class="tool-card-top"><span class="tool-card-ic">${svg(TOOL_ICON[t.script] || "dot", 20)}</span><h4></h4></div><p></p>
      <div class="tool-card-foot"><span class="tool-card-status">${isRun ? '<i class="pulse-dot"></i>' : `<i class="dot ${dot}"></i>`}<span></span></span><button class="btn secondary small">Buka</button></div>`;
    card.querySelector("h4").textContent = t.name;
    card.querySelector("p").textContent = t.description || "";
    card.querySelector(".tool-card-status span:last-child").textContent = text;
    const open = card.querySelector("button");
    open.setAttribute("aria-label", "Buka " + t.name);
    open.addEventListener("click", () => {
      const item = document.querySelector(`.sb-item[data-nav="tool"][data-script="${t.script}"]`);
      if (item) item.click();
    });
    box.appendChild(card);
  }
}

function renderDashboard() { renderMacro(); renderDashboardTools(); }

/* ── log aplikasi: filter + cari ──────────────────────────────────── */
let logsRendered = 0;
let allLogs = [];
let logFilter = "all";
let logQuery = "";

function renderLogsPanel() {
  const panel = $("#log-panel");
  const q = logQuery.trim().toLowerCase();
  const rows = allLogs.filter((l) => (logFilter === "all" || classifyLog(l) === logFilter) && (!q || String(l).toLowerCase().includes(q)));
  const atBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 40;
  panel.innerHTML = rows.map((l) => `<span class="lv-${classifyLog(l)}">${styleLogLine(l)}</span>`).join("\n");
  $("#logs-count").textContent = allLogs.length ? `${rows.length} dari ${allLogs.length} baris` : "";
  $("#logs-empty-text").textContent = allLogs.length ? "Tidak ada baris yang cocok dengan filter atau pencarian." : "Belum ada log. Log muncul setelah tool dijalankan.";
  if (atBottom) panel.scrollTop = panel.scrollHeight;
}

async function refreshLogs(force) {
  const api = bridgeApi();
  if (!api || typeof api.get_logs !== "function") return;
  try {
    const logs = await api.get_logs();
    if (!Array.isArray(logs)) return;
    if (!force && logs.length === logsRendered) return;
    allLogs = logs;
    logsRendered = logs.length;
    renderLogsPanel();
  } catch (err) { /* abaikan */ }
}

/* ── pengaturan ───────────────────────────────────────────────────── */
async function refreshSettings() {
  const pm = CONFIG && CONFIG.paste_macro;
  $("#set-macro-hotkey").textContent = hotkeyText();
  $("#set-macro-state").textContent = pm && typeof pm.enabled === "boolean" ? (pm.enabled ? "Aktif" : "Nonaktif") : "Tidak terbaca";
  $("#set-macro-alt").textContent = pm && Array.isArray(pm.hotkey_cadangan) && pm.hotkey_cadangan.length ? pm.hotkey_cadangan.join(", ") : "--";
  const api = bridgeApi();
  if (!api || typeof api.get_settings_info !== "function") return;
  try {
    const info = await api.get_settings_info();
    if (!info) return;
    if (info.app) {
      $("#set-app-name").textContent = info.app.name;
      $("#set-app-version").textContent = info.app.version;
    }
    if (Array.isArray(info.tools)) {
      const ul = $("#set-tools");
      ul.innerHTML = "";
      for (const t of info.tools) {
        const li = document.createElement("li");
        li.innerHTML = "<span></span><span class='mono-sm'></span>";
        li.firstChild.textContent = t.name;
        li.lastChild.textContent = t.script;
        ul.appendChild(li);
      }
    }
    if (info.python) {
      $("#set-py-version").textContent = info.python.version;
      $("#set-py-exec").textContent = info.python.executable;
    }
  } catch (err) { /* abaikan */ }
}

/* ── salin ke clipboard + umpan balik ─────────────────────────────── */
function flashCopy(btn, ok, okMsg) {
  if (btn) {
    btn.classList.remove("copied", "copy-fail");
    void btn.offsetWidth;
    btn.classList.add(ok ? "copied" : "copy-fail");
    setTimeout(() => btn.classList.remove("copied", "copy-fail"), 1500);
  }
  showToast(ok ? (okMsg || "Tersalin") : "Gagal menyalin", ok ? "success" : "error", 1500);
}

async function copyTextToClipboard(btn, text) {
  let ok = false;
  const api = bridgeApi();
  if (api && typeof api.copy_text === "function") {
    try { const res = await api.copy_text(text); ok = !!(res && res.ok); } catch (err) { ok = false; }
  }
  if (!ok) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
    document.body.removeChild(ta);
  }
  flashCopy(btn, ok);
}

/* ── jam & timer ──────────────────────────────────────────────────── */
function tickClock() {
  const n = new Date();
  $("#clock").textContent = `${pad2(n.getHours())}:${pad2(n.getMinutes())}:${pad2(n.getSeconds())}`;
}

function tickRunTimer() {
  if (!activeRun || !isSectionActive("tool")) return;
  const st = toolStates[activeRun.key];
  if (st && st.running) setStatus("running", statusLabel(st));
}

/* ── init ─────────────────────────────────────────────────────────── */
let bridgeInited = false;

function initBridge() {
  if (bridgeInited) return true;
  const api = bridgeApi();
  if (!api || typeof api.get_config !== "function") return false;
  bridgeInited = true;
  api.get_config()
    .then((cfg) => applyConfig(cfg))
    .catch((err) => { bridgeInited = false; console.warn("[config] gagal:", err); });
  return true;
}

function whenBridgeReady() {
  if (initBridge()) return;
  window.addEventListener("pywebviewready", initBridge, { once: true });
  let n = 0;
  const t = setInterval(() => { if (initBridge() || ++n > 40) clearInterval(t); }, 250);
}

document.addEventListener("DOMContentLoaded", () => {
  hydrateIcons();
  $("#app-title").textContent = APP_META.name;
  $("#app-subtitle").textContent = APP_META.subtitle;
  $("#app-version").textContent = `v${APP_META.version}`;
  renderSidebar(TOOLS);
  setPaused(false);
  renderDashboard();

  document.querySelector(".sidebar").addEventListener("click", onNavClick);
  $("#start-btn").addEventListener("click", onStart);
  $("#stop-btn").addEventListener("click", onStop);
  const fetchBtn = $("#fetch-btn");
  if (fetchBtn) fetchBtn.addEventListener("click", onFetchClick);
  $("#scroll-toggle").addEventListener("click", () => { if (logPaused) scrollLog(true); else setPaused(false); });
  $("#tool-log").addEventListener("scroll", (e) => {
    const el = e.currentTarget;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
    if (!atBottom && !logPaused) setPaused(true);
    else if (atBottom && logPaused) setPaused(false);
  });
  $("#copy-tool-log-btn").addEventListener("click", (e) => copyTextToClipboard(e.currentTarget, $("#tool-log").textContent));
  $("#copy-error-btn").addEventListener("click", (e) =>
    copyTextToClipboard(e.currentTarget, ($("#error-text").textContent + "\n\n" + $("#tool-log").textContent).trim()));
  $("#copy-log-btn").addEventListener("click", (e) => copyTextToClipboard(e.currentTarget, $("#log-panel").textContent));
  $("#copy-kode-btn").addEventListener("click", (e) => copyColumn("kode", e.currentTarget));
  $("#copy-harga-btn").addEventListener("click", (e) => copyColumn("harga_shopee", e.currentTarget));
  $("#copy-faktur-btn").addEventListener("click", (e) => copyColumn("no_faktur", e.currentTarget));
  $("#copy-filter").addEventListener("change", onCopyFilterChange);

  $("#log-filter").addEventListener("click", (e) => {
    const b = e.target.closest(".btn.choice");
    if (!b) return;
    logFilter = b.dataset.level;
    document.querySelectorAll("#log-filter .btn.choice").forEach((x) => {
      const on = x === b;
      x.classList.toggle("active", on);
      x.setAttribute("aria-checked", on ? "true" : "false");
    });
    renderLogsPanel();
  });
  $("#log-search").addEventListener("input", (e) => { logQuery = e.target.value; renderLogsPanel(); });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !isSectionActive("dashboard")) {
      showSection("dashboard");
      setActiveNav(document.querySelector('.sb-item[data-nav="dashboard"]'));
      renderDashboard();
      refreshSystemInfo();
    }
  });

  tickClock();
  setInterval(() => {
    tickClock();
    tickRunTimer();
    if (isSectionActive("dashboard")) refreshSystemInfo();
    if (isSectionActive("logs")) refreshLogs(false);
  }, 1000);

  whenBridgeReady();
  dismissSplash();
});

/* Splash: robot di tengah -> geser ke kiri sambil wajah jadi centang -> tulisan BOPEL ->
   subjudul. Posisi akhir tetap di tengah layar. Lama total = SPLASH_MS sejak animasi mulai. */
/* Sejajarkan pusat HURUF kapital BOPEL dengan pusat KEPALA robot (bukan kotak gambar yang
   ikut menghitung antena). Dihitung dari metrik font yang benar-benar terpakai. */
function alignMarkToHead(sp) {
  try {
    const mark = sp.querySelector(".splash-mark");
    const svgEl = sp.querySelector(".splash-bot svg");
    const cs = getComputedStyle(mark);
    const ctx = document.createElement("canvas").getContext("2d");
    ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const m = ctx.measureText("BOPEL");
    const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize);
    const baseline = (lh - (m.fontBoundingBoxAscent + m.fontBoundingBoxDescent)) / 2 + m.fontBoundingBoxAscent;
    const capCenter = baseline - m.actualBoundingBoxAscent / 2;      // dari atas kotak teks
    const scale = svgEl.getBoundingClientRect().height / 78;         // tinggi viewBox robot = 78
    const headOffset = (50 - 42) * scale;                            // pusat kepala (y=50) vs pusat viewBox (y=42)
    mark.style.translate = `0 ${(headOffset + lh / 2 - capCenter).toFixed(1)}px`;
  } catch (e) { /* abaikan: tetap tampil, hanya tanpa penyelarasan halus */ }
}

const SPLASH_MS = 3400;
const SPLASH_LAYOUT = "wide";   // "wide": subjudul selebar ikon+BOPEL | "stack": ikon besar, teks rata kiri
function dismissSplash() {
  const sp = document.getElementById("splash");
  if (!sp) return;
  const lock = sp.querySelector(".splash-lockup");
  const bot = sp.querySelector(".splash-bot");
  const text = sp.querySelector(".splash-text");
  const sub = sp.querySelector(".splash-sub");
  const start = () => {
    if (lock) lock.dataset.layout = SPLASH_LAYOUT;
    if (SPLASH_LAYOUT === "wide") alignMarkToHead(sp);
    if (SPLASH_LAYOUT === "wide" && lock && sub) {      // regangkan huruf subjudul sampai selebar ikon+BOPEL
      sub.style.letterSpacing = "0px";
      const w0 = sub.getBoundingClientRect().width, n = sub.textContent.length;
      if (n > 1) sub.style.letterSpacing = Math.max(0, (lock.offsetWidth - w0) / (n - 1)) + "px";
    }
    if (lock && bot && text) {
      const shift = (text.offsetLeft + text.offsetWidth - bot.offsetLeft - bot.offsetWidth) / 2;
      lock.style.setProperty("--shift", shift + "px");
    }
    sp.classList.add("go");
    setTimeout(() => {
      sp.classList.add("splash-hide");
      setTimeout(() => sp.remove(), 280);
    }, REDUCE_MOTION ? 900 : SPLASH_MS);
  };
  const fontsReady = document.fonts && document.fonts.ready
    ? Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 700))])
    : Promise.resolve();
  fontsReady.then(start);
}

function applyConfig(cfg) {
  if (!cfg) return;
  CONFIG = cfg;
  if (cfg.app) {
    if (cfg.app.name) $("#app-title").textContent = cfg.app.name;
    if (cfg.app.subtitle) $("#app-subtitle").textContent = cfg.app.subtitle;
    if (cfg.app.version) $("#app-version").textContent = `v${cfg.app.version}`;
  }
  if (Array.isArray(cfg.tools) && cfg.tools.length) {
    TOOLS = cfg.tools.map((t) => ({
      name: t.name, script: t.script, description: t.description || "",
      modes: t.modes || [], uses_stores: !!t.uses_stores,
      date_range: !!t.date_range,
      auto_open_app: t.auto_open_app || null,
    }));
    renderSidebar(TOOLS);
  }
  if (Array.isArray(cfg.stores) && cfg.stores.length) STORES = cfg.stores;
  renderDashboard();
}
