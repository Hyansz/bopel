"use strict";

/* ═══════════════════════════════════════════════════════════════════
   BOPEL Automation Toolkit — front-end pywebview (SPA)
   Navigasi antar screen murni JS (show/hide section), tanpa reload.
   Fase 0: data placeholder (DEFAULT_TOOLS) — Fase 1 diganti dari
   bridge get_config() (core/config.py). Semua fungsi ditulis agar
   bisa di-extend fase berikutnya, bukan di-rewrite.
   ═══════════════════════════════════════════════════════════════════ */

/* ── placeholder sementara (Fase 1: window.pywebview.api.get_config()) ── */
const DEFAULT_TOOLS = [
  { name: "Checklist Automation", script: "check.py",
    description: "Checklist pesanan dan validasi harga Shopee vs aplikasi" },
  { name: "Inventory Scanner", script: "scan.py",
    description: "Scan status pembayaran dan validasi Excel" },
];

const APP_META = { name: "Bopel Automation Toolkit", version: "1.0.0", subtitle: "Internal Warehouse Utilities" };

const $ = (sel) => document.querySelector(sel);

/* tools dari config — Fase 1 mengisi ini dari bridge */
let TOOLS = DEFAULT_TOOLS;
let currentTool = null;   // { name, script, description }
/* toko Auto-Fetch Shopee (2026-08-19) — dari config.yaml stores: */
let STORES = [];
let storeChoice = null;   // nama toko terpilih (default: store enabled pertama)
/* mode data Checklist Automation (2026-08-19): "manual" | "otomatis" | null.
   WAJIB dipilih user sebelum Start aktif — tidak ada default diam-diam. */
let dataMode = null;

/* ── sidebar ──────────────────────────────────────────────────────── */
function renderSidebar(tools) {
  const box = $("#sidebar-tools");
  box.innerHTML = "";
  const icons = {
    "check.py": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>',
    "screenshot_iklan.py": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
    "scan.py": '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7V4h16v3"></path><path d="M9 20h6"></path><path d="M12 4v16"></path></svg>'
  };
  for (const t of tools) {
    const btn = document.createElement("button");
    btn.className = "sb-item";
    btn.dataset.nav = "tool";
    btn.dataset.script = t.script;
    const iconSvg = icons[t.script] || '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle></svg>';
    btn.innerHTML = `<span class="sb-icon">${iconSvg}</span><span>${t.name}</span>`;
    box.appendChild(btn);
  }
}

function setActiveNav(btn) {
  document.querySelectorAll(".sb-item").forEach((b) => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
}

function showSection(name) {
  document.querySelectorAll(".screen").forEach((s) => s.classList.remove("active"));
  const section = document.querySelector(`.screen[data-section="${name}"]`);
  if (section) section.classList.add("active");
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
    btn.classList.remove("sb-new"); // hasil tool ini sudah dilihat
    // Kelompok B/D: render state MILIK tool ini (dan mode terakhirnya
    // kalau tool punya modes). Tool/mode yang belum pernah dijalankan →
    // tampil KOSONG ("--", log kosong), BUKAN sisa state tool sebelumnya.
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
    refreshSystemInfo();
  } else if (nav === "logs") {
    setActiveNav(btn);
    showSection("logs");
    refreshLogs(true);
  } else if (nav === "settings") {
    setActiveNav(btn);
    showSection("settings");
    refreshSettings();
  } else if (nav === "exit") {
    // Fase 2: bridge exit_app(); sekarang fallback no-op yang aman.
    const api = window.pywebview && window.pywebview.api;
    if (api && typeof api.exit_app === "function") {
      api.exit_app();
    } else {
      console.log("[exit] bridge belum tersedia (Fase 2)");
    }
  }
}

/* ── tool screen: Start/Stop + streaming (Fase 2/3) ──────────────────
   STATE PER-TOOL (Kelompok B): tiap tool punya state sendiri
   (toolStates[script]) — log, summary cards, banner, status, progress.
   Streaming dari Python (appendLogLine/updateSummaryCards/onToolStarted/
   onToolFinished) sekarang membawa nama script; JS simpan ke state tool
   itu dan render ke DOM HANYA kalau tool itu lagi aktif. Pindah ke tool
   lain yang belum pernah dijalankan → tampil KOSONG ("--", log kosong),
   bukan sisa state tool sebelumnya. */
const toolStates = {};

function toolStateOf(script) {
  if (!toolStates[script]) {
    toolStates[script] = {
      logHtml: [],
      summary: { total: null, ok: null, beda: null, notfound: null, durasi: null },
      banner: null,
      statusCls: "idle",
      statusText: "Status: Idle",
      progress: 0,
      running: false,
      startedAt: null,
      stopRequested: false,
      items: [],          // struktur per-item (salin per kolom), di-push sekali saat selesai
      copyFilter: "ok",   // dropdown filter aktif per run state
      screenshotFiles: [], // Screenshot Iklan: DAFTAR {path, uri} per toko (loop semua toko)
    };
  }
  return toolStates[script];
}

/* Kelompok D — run key unik per (tool, mode): script yang sama bisa
   dipakai beberapa mode (scan.py = Scan Kode Pesanan & Scan Detail), jadi
   key-nya bukan cuma nama script. Python meng-echo key ini di semua
   push JS (start_tool(script, run_key)). */
function runKey(script, modeName) {
  return modeName ? script + "::" + modeName : script;
}

/* run yang sedang DITAMPILKAN — { key, script } (script = file yang
   benar-benar dijalankan; untuk mode bisa beda dari currentTool.script). */
let activeRun = null;
/* tool.script -> nama mode terakhir yang ditampilkan (retensi per mode) */
const lastModeRun = {};

function isActiveRun(key) {
  return activeRun && activeRun.key === key && isSectionActive("tool");
}

function bridgeApi() {
  return window.pywebview && window.pywebview.api;
}

function setStatus(cls, text) {
  const el = $("#tool-status");
  el.className = "tool-status " + cls;
  el.textContent = text;
}

/* Mode lain di-disable selama ada run tool ini yang masih jalan,
   biar gak muncul "Gagal start" (launcher menolak tool yang running).
   Dipanggil dari renderToolHeader & renderRun (biar ke-enable lagi
   saat run selesai). Tombol Fetch dari Shopee + tombol Mode (Manual/
   Otomatis) ikut di-disable: fetch menimpa clipboard yang sedang
   dibaca run tool yang jalan, dan ganti mode saat fetch jalan bikin
   tampilan berantakan. */
function refreshModeButtons(tool) {
  const running = Object.entries(toolStates).some(
    ([k, st]) => (k === tool.script || k.startsWith(tool.script + "::")) && st.running
  );
  const fetchRunning = !!(toolStates["shopee_fetch.py"] && toolStates["shopee_fetch.py"].running);
  document.querySelectorAll("#mode-btns .btn.choice").forEach((b) => (b.disabled = running || fetchRunning));
  const fb = $("#fetch-btn");
  fb.disabled = running || fetchRunning;
}

/* header tool: judul/desc + tombol MODE (kalau tool punya modes di
   config.yaml). Start disembunyikan saat ada modes (mode = aksi utama). */
function renderToolHeader(tool) {
  $("#tool-name").textContent = tool.name;
  $("#tool-desc").textContent = tool.description || "";
  const modeBox = $("#mode-btns");
  const hasModes = Array.isArray(tool.modes) && tool.modes.length > 0;
  if (hasModes) {
    modeBox.innerHTML = "";
    for (const m of tool.modes) {
      const b = document.createElement("button");
      b.className = "btn choice";
      b.textContent = m.name;
      b.title = m.description || "";
      b.dataset.modeName = m.name;
      b.addEventListener("click", () => onModeClick(tool, m));
      modeBox.appendChild(b);
    }
    modeBox.querySelectorAll(".btn.choice").forEach((b) =>
      b.classList.toggle("active", b.dataset.modeName === lastModeRun[tool.script]));
    refreshModeButtons(tool);
    modeBox.classList.remove("hidden");
    $("#start-btn").classList.add("hidden");
  } else {
    modeBox.classList.add("hidden");
    $("#start-btn").classList.remove("hidden");
  }
  const usesStores = !!(tool.uses_stores && STORES.length);
  /* ToolScreen dibuka -> mode data netral lagi (Start menunggu pilihan)
     dan rentang tanggal reset ke default (hari ini, lihat renderDateRange). */
  if (usesStores) dataMode = null;
  fetchRange = null;
  refreshModeButtons(tool);
  renderDataModeButtons(tool);
  applyDataModeUI(tool);
}

/* ── pilihan MODE DATA Manual vs Otomatis (Checklist Automation) ─────
   WAJIB dipilih user sebelum Start aktif — tidak ada default diam-diam.
   Manual = alur lama persis (selector Toko + Fetch tersembunyi, Start
   langsung aktif, shopee_fetch.py TIDAK dipanggil sama sekali).
   Otomatis = selector Toko + Fetch muncul (perilaku Auto-Fetch yang
   sudah dibangun); Start TETAP aktif — user yang putuskan kapan Start
   (clipboard tetap divalidasi check.py di KEDUA mode). Ganti pilihan
   sebelum Start = reset tampilan sesuai mode baru; clipboard yang sudah
   ada TIDAK dihapus (keputusan pakai/copy-ulang di tangan user). */
function renderDataModeButtons(tool) {
  const box = $("#data-mode-btns");
  /* Screenshot Iklan: uses_stores tapi tanpa mode Manual/Otomatis →
     sembunyikan tombol mode data (date_range langsung tampil). */
  const needsDataMode = !!(tool && tool.uses_stores && STORES.length
                          && (tool.modes?.length || (!tool.date_range)));
  box.classList.toggle("hidden", !needsDataMode);
  if (!needsDataMode) return;
  box.innerHTML = "";
  for (const [label, val] of [["Manual", "manual"], ["Otomatis", "otomatis"]]) {
    const b = document.createElement("button");
    b.className = "btn choice";
    b.textContent = label;
    b.title = val === "manual"
      ? "Copy data Shopee sendiri, lalu klik Start (alur manual lama)"
      : "Ambil data dari Chrome profile toko dulu (Fetch dari Shopee), lalu Start";
    b.addEventListener("click", () => {
      dataMode = val;
      renderDataModeButtons(tool);
      applyDataModeUI(tool);
    });
    if (dataMode === val) b.classList.add("active");
    box.appendChild(b);
  }
}

/* tampilkan/sembunyikan selector Toko + rentang tanggal + Fetch sesuai
   mode data aktif (Otomatis = ketiganya muncul, Manual = tersembunyi) */
function applyDataModeUI(tool) {
  const hasStores = !!(tool && tool.uses_stores && STORES.length);
  const isAuto = dataMode === "otomatis" && hasStores;
  /* Screenshot Iklan: uses_stores + date_range → hanya tanggal, TANPA
     selector toko — toko di-loop otomatis 1→2→3 oleh screenshot_iklan.py
     (set_active_store dikirim tanpa nama toko saat Start; script pilih
     toko sendiri). Fetch disembunyikan (tool ini bukan fetch). */
  const noDataMode = hasStores && tool.date_range && !tool.modes?.length;
  const isShot = !!(noDataMode && currentTool && currentTool.script === "screenshot_iklan.py");
  const showZone = isAuto || noDataMode;
  $("#zone-source").classList.toggle("hidden", !showZone);
  $("#store-btns").classList.toggle("hidden", !showZone || isShot);
  $("#date-range").classList.toggle("hidden", !showZone);
  $("#fetch-btn").classList.toggle("hidden", !isAuto);
  if (showZone) {
    if (!isShot) renderStoreButtons(tool);
    renderDateRange();
  }
  refreshModeButtons(tool);
  renderRun(activeRun ? activeRun.key : null);
}

/* ── rentang TANGGAL (Auto-Fetch, 2026-08-19) ────────────────────────
   Dua <input type="date"> (dari & sampai) sebelum tombol Fetch. Default
   hari ini untuk keduanya (aman: fetch tanpa sadar = data hari ini,
   bukan data salah besar). Reset tiap ToolScreen dibuka (renderToolHeader
   set fetchRange = null) → kembali ke hari ini. Nilai dikirim ke bridge
   set_active_store saat pilih toko & saat klik Fetch. */
let fetchRange = null;

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function renderDateRange() {
  const box = $("#date-range");
  /* VISIBILITAS diatur applyDataModeUI — di sini cuma isi value & handler.
     (Jangan toggle ulang di sini: untuk Screenshot Iklan box sudah tampil
     walau dataMode null.) */
  if (!fetchRange) fetchRange = { start: todayISO(), end: todayISO() };
  const s = $("#date-start");
  const e = $("#date-end");
  s.value = fetchRange.start;
  e.value = fetchRange.end;
  s.onchange = () => { fetchRange.start = s.value; };
  e.onchange = () => { fetchRange.end = e.value; };
}

function currentDateRange() {
  return { start: fetchRange ? fetchRange.start : todayISO(), end: fetchRange ? fetchRange.end : todayISO() };
}

function pushActiveStore(api, name) {
  const r = currentDateRange();
  return api.set_active_store(name, r.start, r.end).catch(() => {});
}

/* Start ter-kunci sampai mode data dipilih (tool uses_stores) */
function startDisabled(st) {
  if (st && st.running) return true;
  /* Jika fetch sedang berjalan, jangan bisa Start check.py — clipboard belum
     siap, check.py akan baca data kosong/partial. Ini sebab "bot binggung"
     setelah CTRL+L + paste link: user klik Start sebelum fetch selesai. */
  if (toolStates["shopee_fetch.py"] && toolStates["shopee_fetch.py"].running) return true;
  /* Screenshot Iklan: uses_stores + no modes → Start aktif tanpa pilih mode
     data (selector toko + tanggal selalu tampil, lihat applyDataModeUI). */
  if (currentTool && currentTool.uses_stores && STORES.length
      && !currentTool.date_range && !dataMode) return true;
  return false;
}

/* ── selector TOKO (Auto-Fetch Shopee) ───────────────────────────────
   Dirender dari config.yaml stores: — semua toko enabled = tombol
   pilihan (klik → simpan + kirim ke bridge set_active_store); toko
   disabled = placeholder murni UI (disabled, tanpa logic backend).
   Nambah toko = edit config stores: saja.
   Screenshot Iklan TIDAK pakai selector ini (toko di-loop 1→2→3 oleh
   screenshot_iklan.py — applyDataModeUI sembunyikan #store-btns). */
function renderStoreButtons(tool) {
  const box = $("#store-btns");
  const usesStores = !!(tool && tool.uses_stores && STORES.length);
  box.classList.toggle("hidden", !usesStores);
  if (!usesStores) return;
  box.innerHTML = "";
  for (const s of STORES) {
    const b = document.createElement("button");
    b.className = "btn choice store";
    b.textContent = s.name;
    b.title = "Pilih toko ini sebagai sumber Auto-Fetch";
    if (!s.enabled) b.disabled = true;
    b.addEventListener("click", () => {
      storeChoice = s.name;
      renderStoreButtons(tool);
      const api = bridgeApi();
      if (api && typeof api.set_active_store === "function") {
        pushActiveStore(api, s.name);
      }
    });
    if (s.enabled && s.name === (storeChoice || STORES.find((x) => x.enabled)?.name)) {
      b.classList.add("active");
    }
    box.appendChild(b);
  }
  if (!storeChoice) {
    const first = STORES.find((s) => s.enabled);
    if (first) {
      storeChoice = first.name;
      const api = bridgeApi();
      if (api && typeof api.set_active_store === "function") {
        pushActiveStore(api, first.name);
      }
    }
  }
}

/* render state sebuah run ke DOM (key null = tampilan kosong) */
function renderRun(key) {
  const st = key ? toolStateOf(key) : null;
  $("#sum-total").textContent = st && st.summary.total != null ? st.summary.total : "--";
  $("#sum-ok").textContent = st && st.summary.ok != null ? st.summary.ok : "--";
  $("#sum-beda").textContent = st && st.summary.beda != null ? st.summary.beda : "--";
  $("#sum-notfound").textContent = st && st.summary.notfound != null ? st.summary.notfound : "--";
  $("#sum-durasi").textContent = st && st.summary.durasi != null ? st.summary.durasi : "--";
  const b = $("#success-banner");
  if (st && st.banner) {
    b.textContent = st.banner;
    b.classList.add("show");
  } else {
    b.classList.remove("show");
  }
  setStatus(st ? st.statusCls : "idle", st ? st.statusText : "Status: Idle");
  $("#tool-progress").style.width = (st ? st.progress : 0) + "%";
  /* Screenshot Iklan: card ringkasan (TOTAL ITEM/SUKSES/CEK MANUAL/NOT
     FOUND/DURASI) tidak relevan — tool ini output-nya screenshot, bukan
     tabel scan. Hanya status+progress yang dipertahankan di kolom kiri.
     Tool lain (Checklist/Scanner) tetap pakai cards seperti biasa. */
  const sumRow = document.querySelector(".sum-row");
  const isShot = currentTool && currentTool.script === "screenshot_iklan.py";
  if (sumRow) sumRow.style.display = isShot ? "none" : "";
  const logEl = $("#tool-log");
  logEl.innerHTML = st ? st.logHtml.join("") : "";
  logEl.scrollTop = logEl.scrollHeight;
  $("#start-btn").disabled = startDisabled(st);
  $("#stop-btn").disabled = st ? !st.running : true;
  if (currentTool) refreshModeButtons(currentTool);
  renderCopyBar(st);
  renderScreenshotPreview(st);
}

/* Screenshot Iklan: preview thumbnail hasil run. Satu kartu per toko.
   SALIN SEKALI, FOTO TERPISAH (2026-09-17): saat run selesai Python
   menyalin SEMUA file PNG ke clipboard sekaligus (copy_files → CF_HDROP,
   file drop) — paste di WA/Telegram keluar N foto berbeda per toko,
   BUKAN 1 gambar gabungan. Tombol salin per kartu & "Salin Semua"
   dihapus (tidak perlu klik lagi). Preview pakai data URI (bukan
   file://): file:// broken image icon di pywebview/WebView2 karena
   permission & encoding path Windows. */
function renderScreenshotPreview(st) {
  const box = $("#shot-previews");
  const items = (st && st.screenshotFiles) || [];
  const show = !!(items.length && currentTool && (currentTool.script === "screenshot_iklan.py"));
  box.classList.toggle("hidden", !show);
  if (!show) return;
  box.innerHTML = `<div class="shot-paste-hint"><span>📌 Hotkey global aktif:</span><span class="hotkey-chip">Ctrl+Alt+V</span><span>tempel 3 gambar + caption otomatis</span></div>`;
  for (const it of items) {
    const name = it.path ? it.path.split(/[\\/]/).pop() : "screenshot";
    const card = document.createElement("div");
    card.className = "shot-card";
    card.innerHTML = `<span class="shot-card-title"></span>
      <img class="shot-thumb" alt="Preview screenshot iklan">
      <span class="shot-path"></span>
      <button class="btn sm copy-caption" style="margin-top:6px; background:#007acc; color:#fff; border:none; padding:4px 8px; border-radius:3px; cursor:pointer;">Copy Caption</button>`;
    card.querySelector(".shot-card-title").textContent = name;
    card.querySelector(".shot-thumb").src = it.uri || "";
    card.querySelector(".shot-path").textContent = it.path || "";
    const capBtn = card.querySelector(".copy-caption");
    capBtn.addEventListener("click", async () => {
      const storeName = name.replace(/_\d{4}_sd_\d{4}\.png$/, "").replace(/_/g, " ");
      const now = new Date();
      const dd = String(now.getDate()).padStart(2, "0");
      const mm = String(now.getMonth() + 1).padStart(2, "0");
      const yyyy = now.getFullYear();
      const caption = `Shopee Ads ${storeName} ${dd}/${mm}/${yyyy}`;
      const api = bridgeApi();
      if (api && typeof api.copy_text === "function") {
        const res = await api.copy_text(caption);
        if (res && res.ok) {
          capBtn.textContent = "Copied ✓";
          setTimeout(() => capBtn.textContent = "Copy Caption", 1500);
        }
      }
    });
    box.appendChild(card);
  }
}

/* dipanggil Python saat run selesai — array {path, uri} per toko */
function showScreenshotPreviews(key, items) {
  const st = toolStateOf(key);
  st.screenshotFiles = Array.isArray(items) ? items : [];
  if (isActiveRun(key)) renderScreenshotPreview(st);
}

/* Digantikan tombol Salin per kartu — lihat renderScreenshotPreview. */
function onShotCopyClick() {}

/* ── fitur salin per kolom (tempel Excel) ────────────────────────────
   Data item di-push Python SEKALI saat run selesai (pushItems) — tidak
   reparse dari log mentah per klik. Ketiga tombol (Kode / Harga Shopee /
   No Faktur) memakai daftar item yang SAMA (filter aktif + urutan asli
   dari tabel tool), jadi jumlah baris & urutannya sejajar persis antar
   kolom — aman ditempel ke 3 kolom Excel bersebelahan. */
function renderCopyBar(st) {
  const bar = $("#copy-bar");
  const hasItems = st && Array.isArray(st.items) && st.items.length > 0;
  bar.classList.toggle("hidden", !hasItems);
  if (!hasItems) return;
  const sel = $("#copy-filter");
  if (sel.value !== st.copyFilter) sel.value = st.copyFilter;
  const rows = st.items.filter((it) => it.kategori === st.copyFilter);
  $("#copy-count").textContent = rows.length
    ? `${rows.length} item — baris sejajar di ketiga kolom`
    : "0 item";
}

function copyColumn(field, btn) {
  if (!activeRun) return;
  const st = toolStateOf(activeRun.key);
  const rows = st.items.filter((it) => it.kategori === st.copyFilter);
  const text = rows
    .map((r) => {
      const v = r[field] != null ? r[field] : "";
      if (field === "harga_shopee" && /^\d+$/.test(v)) {
        return Number(v).toLocaleString("en-US");
      }
      return v;
    })
    .join("\n");
  copyTextToClipboard(btn, text);
}

function onCopyFilterChange() {
  if (!activeRun) return;
  const st = toolStateOf(activeRun.key);
  st.copyFilter = $("#copy-filter").value;
  renderCopyBar(st);
}

/* dipanggil Python saat run selesai — struktur per-item utk run ini */
function pushItems(key, items) {
  const st = toolStateOf(key);
  st.items = Array.isArray(items) ? items : [];
  if (isActiveRun(key)) renderCopyBar(st);
}

/* ── warna marker log — port style_log_line() dari ui/theme.py ──────
   Marker/prefix baris log di-wrap span dengan warna token theme yang
   SAMA dengan Textual (ui/theme.py COLOR_INFO/SUCCESS/ERROR/WARNING/
   SUBTLE = CSS var --amber/--green/--red/--text-low di style.css).
   Isi baris TIDAK diubah — teks tetap terbaca di monokrom. Baris tanpa
   marker dibiarkan apa adanya. Jangan re-invent mapping baru di sini;
   kalau token theme berubah, ubah ui/theme.py + style.css sekaligus. */
const LOG_MARKER_CLASS = {
  "[RUN]": "info",
  "[OK]": "success",
  "[FAIL]": "error",
  "[ERROR]": "error",
  "[DEBUG]": "debug",
};
const LOG_ERR_MARKERS = ["\u274c", "\u26d4", "\u2718"];   // ❌ ⛔ ✘
const LOG_WARN_MARKERS = ["\u26a0", "\u23f3", "\u{1F4CC}"]; // ⚠ ⏳ 📌
const LOG_OK_MARKERS = ["\u2705", "\u2714"];               // ✅ ✔

function escHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function styleLogLine(line) {
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

/* ── dipanggil Python (reader thread) via evaluate_js ─────────────── */
function appendLogLine(key, line) {
  const st = toolStateOf(key);
  st.logHtml.push(styleLogLine(line) + "\n");
  if (isActiveRun(key)) {
    const el = $("#tool-log");
    /* .log-anim = fade-in HANYA untuk insert live; riwayat (logHtml)
       disimpan TANPA kelas ini supaya replay/layar Logs tidak
       menganimasi ulang seluruh isi saat pindah mode. */
    el.insertAdjacentHTML("beforeend", `<span class="log-anim">${styleLogLine(line)}</span>\n`);
    el.scrollTop = el.scrollHeight;
  }
}

function updateSummaryCards(key, s) {
  const st = toolStateOf(key);
  if (s.total != null) st.summary.total = s.total;
  if (s.ok != null) st.summary.ok = s.ok;
  if (s.beda != null) st.summary.beda = s.beda;
  if (s.notfound != null) st.summary.notfound = s.notfound;
  if (s.durasi != null) st.summary.durasi = s.durasi;
  if (!isActiveRun(key)) return;
  if (s.total != null) $("#sum-total").textContent = s.total;
  if (s.ok != null) $("#sum-ok").textContent = s.ok;
  if (s.beda != null) $("#sum-beda").textContent = s.beda;
  if (s.notfound != null) $("#sum-notfound").textContent = s.notfound;
  if (s.durasi != null) $("#sum-durasi").textContent = s.durasi;
}

function onToolStarted(key) {
  const st = toolStateOf(key);
  st.startedAt = Date.now();
  st.stopRequested = false;
  st.running = true;
  st.statusCls = "running";
  st.statusText = "Status: Running...";
  st.progress = 20;
  if (isActiveRun(key)) {
    setStatus("running", "Status: Running...");
    $("#tool-progress").style.width = "20%";
    $("#start-btn").disabled = true;
    $("#stop-btn").disabled = false;
  }
}

/* ── setelah tool selesai: TETAP di tempat ───────────────────────────
   Sebelumnya (sesi sebelumnya): auto-nav ke Dashboard 5 dtk setelah
   sukses. KEPUTUSAN BARU — keputusan lama DI-SUPERSEDE: TIDAK ada
   auto-nav sama sekali. Kasus paling umum (user Start lalu menunggu di
   ToolScreen itu) → user tetap di ToolScreen, hasil langsung terlihat.
   Kalau user pindah ke layar lain saat tool jalan, dia TIDAK dipaksa
   pindah balik (prinsip yang sama dengan cancelAutoNav dulu: jangan
   ganggu navigasi manual user) — cukup window bring-to-front (Kelompok
   A2, di Python, untuk Finished DAN Failed) + badge hasil baru di
   sidebar (markToolHasResult) supaya user tahu run sudah selesai. */

/* badge "hasil baru" di item sidebar tool ini — muncul saat run tool/
   mode mana pun selesai (sukses ATAU gagal), dihapus saat user membuka
   tool itu. Key bisa berformat "script::Mode" → ambil nama script saja. */
function markToolHasResult(key) {
  const script = String(key).split("::")[0];
  const btn = document.querySelector(`.sb-item[data-nav="tool"][data-script="${script}"]`);
  if (btn) btn.classList.add("sb-new");
}

function onToolFinished(key, success, error, banner) {
  const st = toolStateOf(key);
  if (success) {
    if (st.summary.durasi == null && st.startedAt) {
      st.summary.durasi = ((Date.now() - st.startedAt) / 1000).toFixed(1);
    }
    st.statusCls = "finished";
    st.statusText = "Status: Finished";
    st.progress = 100;
    st.banner = banner;
  } else {
    st.statusCls = "failed";
    st.statusText = st.stopRequested
      ? "Status: Stopped by user"
      : "Status: Failed" + (error ? " \u2014 " + error : "");
  }
  st.running = false;
  st.startedAt = null;
  st.stopRequested = false;
  markToolHasResult(key);
  if (isActiveRun(key)) renderRun(key);
}

/* reset state sebuah run (mulai dari kosong) */
function resetRunState(st) {
  st.logHtml = [];
  st.summary = { total: null, ok: null, beda: null, notfound: null, durasi: null };
  st.banner = null;
  st.statusCls = "running";
  st.statusText = "Status: Running...";
  st.progress = 20;
  st.running = true;
  st.startedAt = Date.now();
  st.stopRequested = false;
  st.items = [];
  st.copyFilter = "ok";
  st.screenshotFiles = [];
}

function onStart() {
  if (!currentTool) return;
  const script = currentTool.script;
  const key = script;
  activeRun = { key, script };
  const st = toolStateOf(key);
  resetRunState(st);
  renderRun(key);
  const api = bridgeApi();
  if (!api || typeof api.start_tool !== "function") {
    st.statusCls = "failed";
    st.statusText = "Status: Bridge belum siap";
    st.running = false;
    renderRun(key);
    return;
  }
  /* Tool uses_stores (Screenshot Iklan, dsb.): kirim rentang tanggal ke
     bridge dulu (set_active_store → .active_store.json), supaya tool baca
     tanggal yang benar saat Start. Screenshot Iklan kirim TANPA nama toko
     (toko di-loop 1→2→3 oleh script — UI tidak milih toko). Checklist
     Otomatis tetap kirim nama toko terpilih. */
  const needsStore = currentTool.uses_stores && STORES.length;
  const isShot = currentTool.script === "screenshot_iklan.py";
  const doStart = () => api.start_tool(script, key);
  const run = needsStore
    ? Promise.resolve(pushActiveStore(api, isShot ? null : (storeChoice || (STORES.find((s) => s.enabled) || {}).name))).then(doStart)
    : Promise.resolve(doStart());
  run.then((res) => {
    if (!res || !res.ok) {
      st.statusCls = "failed";
      st.statusText = "Status: Gagal start (" + ((res && res.message) || "?") + ")";
      st.progress = 0;
      st.running = false;
      renderRun(key);
    }
  }).catch((err) => {
    st.statusCls = "failed";
    st.statusText = "Status: Error bridge: " + err;
    st.progress = 0;
    st.running = false;
    renderRun(key);
  });
}

/* Kelompok D — klik tombol MODE: mulai run mode itu (state per mode) */
function onModeClick(tool, mode) {
  const script = mode.script || tool.script;
  const key = runKey(tool.script, mode.name);
  lastModeRun[tool.script] = mode.name;
  activeRun = { key, script };
  const st = toolStateOf(key);
  resetRunState(st);
  renderToolHeader(tool); // highlight mode aktif
  renderRun(key);
  const api = bridgeApi();
  if (!api || typeof api.start_tool !== "function") {
    st.statusCls = "failed";
    st.statusText = "Status: Bridge belum siap";
    st.running = false;
    renderRun(key);
    return;
  }
  api.start_tool(script, key).then((res) => {
    if (!res || !res.ok) {
      st.statusCls = "failed";
      st.statusText = "Status: Gagal start (" + ((res && res.message) || "?") + ")";
      st.progress = 0;
      st.running = false;
      renderRun(key);
    }
  }).catch((err) => {
    st.statusCls = "failed";
    st.statusText = "Status: Error bridge: " + err;
    st.progress = 0;
    st.running = false;
    renderRun(key);
  });
}

function onStop() {
  if (!currentTool) return;
  const run = activeRun || { key: currentTool.script, script: currentTool.script };
  const st = toolStateOf(run.key);
  st.stopRequested = true;
  const api = bridgeApi();
  if (api && typeof api.stop_tool === "function") {
    api.stop_tool(run.script);
  }
  st.statusCls = "failed";
  st.statusText = "Status: Stopped by user";
  st.running = false;
  renderRun(run.key);
}

/* ── tombol "Fetch dari Shopee" (Auto-Fetch, 2026-08-19) ─────────────
   Jalanin shopee_fetch.py sebagai run biasa (streaming + status + Stop
   via launcher) dengan state sendiri. Hasilnya: blok Dana Dilepaskan
   tersalin ke clipboard — user lalu klik Start (check.py) seperti alur
   manual. TIDAK auto-trigger Start. */
function onFetchClick() {
  const script = "shopee_fetch.py";
  const key = script;
  const st = toolStateOf(key);

  /* Jika fetch sudah berjalan, jangan start ulang — cukup tampilkan view
     run yang sedang berjalan (log + status). Mencegah duplikat klik yang
     bikin "Gagal start (sudah running)" dan reset state yg sedang jalan. */
  if (st.running) {
    activeRun = { key, script };
    renderRun(key);
    return;
  }

  /* FIX (2026-09-25): Set activeRun + resetRunState + renderRun SEBELUM
     start_tool, sama seperti onStart() dan onModeClick(). Sebelumnya ini
     ada di .then() SETELAH start_tool resolve — berarti saat reader thread
     kirim onToolStarted, isActiveRun() masih false, UI gak update (status
     tetap "Idle", Start enabled, Stop disabled). User kira bot gak jalan /
     "binggung", klik ulang → "Gagal start (sudah running)" / klik Start →
     interferensi clipboard → harus stop+start berulang. */
  activeRun = { key, script };
  resetRunState(st);
  renderRun(key);

  const api = bridgeApi();
  if (!api || typeof api.start_tool !== "function") {
    st.statusCls = "failed";
    st.statusText = "Status: Bridge belum siap";
    st.running = false;
    renderRun(key);
    return;
  }
  /* Simpan dulu rentang tanggal terpilih (ke .active_store.json via
     bridge) SEBELUM fetch jalan — shopee_fetch.py baca state ini untuk
     dateRange di URL income. Kalau gagal dikirim pun fetch tetap jalan
     (state toko lama dipakai, perilaku aman). */
  Promise.resolve(pushActiveStore(api, storeChoice || (STORES.find((s) => s.enabled) || {}).name))
    .then(() => api.start_tool(script, key))
    .then((res) => {
      if (!res || !res.ok) {
        st.statusCls = "failed";
        st.statusText = "Status: Gagal start (" + ((res && res.message) || "?") + ")";
        st.progress = 0;
        st.running = false;
        renderRun(key);
      }
    })
    .catch((err) => {
      st.statusCls = "failed";
      st.statusText = "Status: Error bridge: " + err;
      st.progress = 0;
      st.running = false;
      renderRun(key);
    });
}

/* ── Fase 4: dashboard polling / logs / settings via bridge ────────── */
let logsRendered = 0;

function isSectionActive(name) {
  const s = document.querySelector(`.screen[data-section="${name}"]`);
  return s && s.classList.contains("active");
}

async function refreshSystemInfo() {
  const api = bridgeApi();
  if (!api || typeof api.get_system_info !== "function") return;
  try {
    const info = await api.get_system_info();
    if (!info) return;
    if (info.python) $("#dash-python").textContent = `Python ${info.python}  |  ${info.os || ""}`;
    if (info.terminal) $("#dash-term").textContent = `Terminal: ${info.terminal}`;
    if (info.date) $("#dash-date").textContent = `Date: ${info.date}`;
    if (info.cpu) $("#dash-cpu").textContent = info.cpu;
    if (info.ram) $("#dash-ram").textContent = info.ram;
  } catch (err) { /* polling gagal sekali — abaikan */ }
}

async function refreshLogs(force) {
  const panel = $("#log-panel");
  const api = bridgeApi();
  if (!api || typeof api.get_logs !== "function") return;
  try {
    const logs = await api.get_logs();
    if (!Array.isArray(logs)) return;
    if (force || logs.length < logsRendered) {
      panel.innerHTML = logs.map(styleLogLine).join("\n");
      logsRendered = logs.length;
      return;
    }
    if (logs.length > logsRendered) {
      panel.insertAdjacentHTML(
        "beforeend",
        (logsRendered > 0 ? "\n" : "") + logs.slice(logsRendered).map(styleLogLine).join("\n")
      );
      logsRendered = logs.length;
      panel.scrollTop = panel.scrollHeight;
    }
  } catch (err) { /* abaikan */ }
}

async function refreshSettings() {
  const api = bridgeApi();
  if (!api || typeof api.get_settings_info !== "function") return;
  try {
    const info = await api.get_settings_info();
    if (!info) return;
    if (info.app) {
      $("#set-app-name").textContent = `Name: ${info.app.name}`;
      $("#set-app-version").textContent = `Version: ${info.app.version}`;
    }
    if (Array.isArray(info.tools)) {
      $("#set-tools").textContent = info.tools
        .map((t) => `  - ${t.name}  (${t.script})`)
        .join("\n");
    }
    if (info.python) {
      $("#set-py-version").textContent = `Version: ${info.python.version}`;
      $("#set-py-exec").textContent = `Executable: ${info.python.executable}`;
    }
  } catch (err) { /* abaikan */ }
}

/* ── copy log ke clipboard (Kelompok C) ─────────────────────────────
   Context menu kanan di-disable pywebview di mode produksi, jadi
   right-click → Copy gak bisa. Rute utama: bridge copy_text() (pyperclip
   — sudah dipakai tool scan/check). Fallback browser: textarea + execCommand. */
async function copyTextToClipboard(btn, text) {
  let ok = false;
  const api = bridgeApi();
  if (api && typeof api.copy_text === "function") {
    try {
      const res = await api.copy_text(text);
      ok = !!(res && res.ok);
    } catch (err) { ok = false; }
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
  /* Feedback TANPA mengubah teks tombol: swap label ("Tersalin ✓")
     menyusutkan lebar tombol -> flex-wrap copy-bar REFLOW (tombol
     Faktur bisa tiba-tiba naik ke baris 1) -> klik berikutnya yang
     pakai koordinat lama meleset. Flash warna = nol pergeseran layout. */
  btn.classList.remove("copied", "copy-fail");
  void btn.offsetWidth; /* restart transisi/animasi */
  btn.classList.add(ok ? "copied" : "copy-fail");
  setTimeout(() => btn.classList.remove("copied", "copy-fail"), 1500);
}

/* ── clock titlebar (murni JS) ────────────────────────────────────── */
function tickClock() {
  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  $("#clock").textContent = `${hh}:${mm}:${ss}`;
}

/* ── init ─────────────────────────────────────────────────────────── */
/* Inisialisasi bridge js_api. pywebview menyuntik window.pywebview +
   mem-fire event 'pywebviewready' TANPA jaminan urutan vs DOMContentLoaded
   (di backend edgechromium, API siap SETELAH DOMContentLoaded — terverifikasi
   Fase 1). Jadi: coba langsung → listener event → fallback poll. */
let bridgeInited = false;

function initBridge() {
  if (bridgeInited) return true;
  const api = window.pywebview && window.pywebview.api;
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
  $("#app-title").textContent = APP_META.name;
  $("#app-subtitle").textContent = APP_META.subtitle;
  $("#sb-subtitle").textContent = APP_META.subtitle;
  $("#app-version").textContent = `v${APP_META.version}`;
  renderSidebar(TOOLS);

  document.querySelector(".sidebar").addEventListener("click", onNavClick);
  $("#start-btn").addEventListener("click", onStart);
  $("#stop-btn").addEventListener("click", onStop);
  $("#fetch-btn").addEventListener("click", onFetchClick);
  $("#copy-tool-log-btn").addEventListener("click", (e) =>
    copyTextToClipboard(e.currentTarget, $("#tool-log").textContent));
  $("#copy-log-btn").addEventListener("click", (e) =>
    copyTextToClipboard(e.currentTarget, $("#log-panel").textContent));
  $("#copy-kode-btn").addEventListener("click", (e) => copyColumn("kode", e.currentTarget));
  $("#copy-harga-btn").addEventListener("click", (e) => copyColumn("harga_shopee", e.currentTarget));
  $("#copy-faktur-btn").addEventListener("click", (e) => copyColumn("no_faktur", e.currentTarget));
  $("#copy-filter").addEventListener("change", onCopyFilterChange);

  // Esc = kembali ke dashboard (setara Textual Esc/Q)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !isSectionActive("dashboard")) {
      showSection("dashboard");
      setActiveNav(document.querySelector('.sb-item[data-nav="dashboard"]'));
      refreshSystemInfo();
    }
  });

  tickClock();
  setInterval(() => {
    tickClock();
    if (isSectionActive("dashboard")) refreshSystemInfo();
    if (isSectionActive("logs")) refreshLogs(false);
  }, 1000);

  whenBridgeReady();
  dismissSplash();
});

/* Splash: lantai 1 dtk sejak navigasi supaya terbaca (band ±1-1.5 dtk
   termasuk render awal); kalau init lebih lambat dari itu, splash
   bertahan sampai handler init selesai (wait=0) — tidak pernah jadi
   penghalang fungsi (pointer-events:none). */
function dismissSplash() {
  const sp = document.getElementById("splash");
  if (!sp) return;
  const wait = Math.max(0, 1000 - performance.now());
  setTimeout(() => {
    sp.classList.add("splash-hide");
    setTimeout(() => sp.remove(), 260);
  }, wait);
}

/* Disiapkan untuk Fase 1 — mengisi data dari config.yaml via bridge. */
function applyConfig(cfg) {
  if (!cfg) return;
  if (cfg.app) {
    if (cfg.app.name) $("#app-title").textContent = cfg.app.name;
    if (cfg.app.subtitle) { $("#app-subtitle").textContent = cfg.app.subtitle; $("#sb-subtitle").textContent = cfg.app.subtitle; }
    if (cfg.app.version) $("#app-version").textContent = `v${cfg.app.version}`;
  }
  if (Array.isArray(cfg.tools) && cfg.tools.length) {
    TOOLS = cfg.tools.map((t) => ({
      name: t.name, script: t.script, description: t.description || "",
      modes: t.modes || [], uses_stores: !!t.uses_stores,
      date_range: !!t.date_range,
    }));
    renderSidebar(TOOLS);
  }
  if (Array.isArray(cfg.stores) && cfg.stores.length) {
    STORES = cfg.stores;
  }
}
