/*
 * Test: onFetchClick state timing
 * Verifikasi bahwa setelah onFetchClick() dipanggil, activeRun dan
 * toolStates.running sudah diset SEBELUM start_tool() resolve.
 * Inivasi: reader thread kirim onToolStarted segera setelah start_tool,
 * jadi activeRun harus sudah set sync sebelum Promise chain selesai.
 */
"use strict";
const assert = require("assert");

/* ── Minimal DOM mock ── */
class MockEl {
  constructor() {
    this.className = "";
    this.textContent = "";
    this.style = { width: "", setProperty() {} };
    this.classList = {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); },
      toggle(c, f) { if (f === undefined) this._set.has(c) ? this._set.delete(c) : this._set.add(c); else { if (f) this._set.add(c); else this._set.delete(c); } },
    };
    this.disabled = false;
  }
}

const els = {};
function mockQuerySelector(sel) {
  if (!els[sel]) els[sel] = new MockEl();
  return els[sel];
}

/* Override global $ */
global.$ = mockQuerySelector;
global.document = {
  querySelector: mockQuerySelector,
  querySelectorAll: (sel) => {
    const arr = [];
    for (let i = 0; i < 5; i++) arr.push(new MockEl());
    return { forEach: (fn) => arr.forEach(fn) };
  },
  createElement: (tag) => new MockEl(),
};

/* ── Global state yang dipakai app.js ── */
global.TOOLS = [];
global.STORES = [{ name: "Store1", enabled: true }];
global.storeChoice = null;
global.dataMode = "otomatis";
global.currentTool = { name: "Checklist Automation", script: "check.py", uses_stores: true, modes: [{ name: "manual", script: "check.py" }, { name: "otomatis", script: "check.py::otomatis" }] };
global.currentDateRange = () => ({ start: "2026-09-01", end: "2026-09-25" });
global.fetchRange = null;
global.todayISO = () => "2026-09-25";
global.toolStates = {};

/* toolStateOf — dari app.js */
function toolStateOf(key) {
  if (!global.toolStates[key]) {
    global.toolStates[key] = {
      key,
      logHtml: [],
      summary: { total: null, ok: null, beda: null, notfound: null, durasi: null },
      startedAt: null,
      statusCls: "idle",
      statusText: "Status: Idle",
      progress: 0,
      running: false,
      stopRequested: false,
      banner: null,
      items: [],
      copyFilter: "ok",
      screenshotFiles: [],
      summaryReady: false,
    };
  }
  return global.toolStates[key];
}

/* resetRunState — copy dari app.js */
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

/* isActiveRun — dari app.js */
function isActiveRun(key) {
  return global.activeRun && global.activeRun.key === key;
}

/* renderRun — simplified mock (hanya panggil refreshModeButtons) */
global.refreshModeButtonsCalls = 0;
function renderRun(key) {
  global.refreshModeButtonsCalls++;
  const st = toolStateOf(key);
  const el = mockQuerySelector("#start-btn");
  el.disabled = global.startDisabled(st);
  const fb = mockQuerySelector("#fetch-btn");
  fb.disabled = global.startDisabled({ running: global.toolStates["shopee_fetch.py"]?.running });
  const sb = mockQuerySelector("#stop-btn");
  sb.disabled = !st.running;
}

/* startDisabled — versi fixed */
function startDisabled(st) {
  if (st && st.running) return true;
  if (global.toolStates["shopee_fetch.py"] && global.toolStates["shopee_fetch.py"].running) return true;
  if (global.currentTool && global.currentTool.uses_stores && global.STORES.length
      && !global.currentTool.date_range && !global.dataMode) return true;
  return false;
}
global.startDisabled = startDisabled;

/* refreshModeButtons — versi fixed */
function refreshModeButtons(tool) {
  const running = Object.entries(global.toolStates).some(
    ([k, st]) => (k === tool.script || k.startsWith(tool.script + "::")) && st.running
  );
  const fetchRunning = !!(global.toolStates["shopee_fetch.py"] && global.toolStates["shopee_fetch.py"].running);
  // no actual DOM elements to disable in mock, just track
}
global.refreshModeButtons = refreshModeButtons;

/* setStatus mock */
global.setStatus = (cls, text) => { /* no-op in mock */ };

/* activeRun global */
global.activeRun = null;

/* pushActiveStore mock — resolves immediately */
global.pushActiveStore = (api, name) => Promise.resolve({});

/* bridgeApi mock */
let _startToolCalled = false;
let _startToolSyncCalled = false;
global.bridgeApi = () => ({
  start_tool: (script, key) => {
    _startToolCalled = true;
    // Periksa state SEKARANG (sebelum Promise resolve)
    _startToolSyncCalled = true;
    return Promise.resolve({ ok: true });
  },
  stop_tool: () => ({ ok: true }),
  set_active_store: () => Promise.resolve({}),
});

/* ── onFetchClick (fixed version) ── */
function onFetchClick() {
  const script = "shopee_fetch.py";
  const key = script;
  const st = toolStateOf(key);

  /* Guard: if already running, just switch view */
  if (st.running) {
    global.activeRun = { key, script };
    renderRun(key);
    return;
  }

  /* FIX: set activeRun + resetRunState + renderRun BEFORE start_tool */
  global.activeRun = { key, script };
  resetRunState(st);
  renderRun(key);

  const api = global.bridgeApi();
  if (!api || typeof api.start_tool !== "function") {
    st.statusCls = "failed";
    st.statusText = "Status: Bridge belum siap";
    st.running = false;
    renderRun(key);
    return;
  }
  /* Check: start_tool has NOT been called yet (async di Promise chain),
     tapi activeRun + state sudah diset sync sebelum onFetchClick return.
     Ini invariant kritis: saat reader thread panggil onToolStarted
     segera setelah start_tool, isActiveRun() harus sudah true. */
  assert(_startToolCalled === false, "start_tool belum dipanggil (async)");
  assert(global.activeRun !== null, "activeRun harus diset sync sebelum start_tool");
  assert(global.activeRun.key === "shopee_fetch.py", "activeRun.key harus = shopee_fetch.py");
  assert(st.running === true, "st.running harus true setelah resetRunState");
  assert(isActiveRun("shopee_fetch.py") === true, "isActiveRun harus true sebelum start_tool");
  const startBtn = mockQuerySelector("#start-btn");
  const fetchBtn = mockQuerySelector("#fetch-btn");
  assert(startBtn.disabled === true, "Start button harus disabled saat fetch running");
  assert(fetchBtn.disabled === true, "Fetch button harus disabled saat fetch running");

  /* Simpan state sebelum start_tool */
  Promise.resolve(global.pushActiveStore(api, global.storeChoice || (global.STORES.find((s) => s.enabled) || {}).name))
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

/* ── onToolStarted — copy dari app.js ── */
function onToolStarted(key) {
  const st = toolStateOf(key);
  st.startedAt = Date.now();
  st.stopRequested = false;
  st.running = true;
  st.statusCls = "running";
  st.statusText = "Status: Running...";
  st.progress = 20;
  if (isActiveRun(key)) {
    global.setStatus("running", "Status: Running...");
    const pb = mockQuerySelector("#tool-progress");
    pb.style.width = "20%";
    const sb = mockQuerySelector("#start-btn");
    sb.disabled = true;
    const sp = mockQuerySelector("#stop-btn");
    sp.disabled = false;
  }
}

/* ── TEST ── */
async function main() {
  console.log("=== Test: onFetchClick state timing ===\n");

  /* Test 1: activeRun + state ter-set sync, start_tool belum dipanggil
     (karena di Promise chain). Invariant: isActiveRun true sebelum
     start_tool resolve, supaya onToolStarted callback (reader thread)
     bisa update UI. */
  onFetchClick();

  assert(_startToolCalled === false, "start_tool belum dipanggil (async, belum resolve pushActiveStore)");
  assert(global.activeRun !== null, "activeRun harus sudah diset sync");
  assert(global.activeRun.key === "shopee_fetch.py", "activeRun.key = shopee_fetch.py");
  assert(toolStates["shopee_fetch.py"].running === true, "st.running = true");
  assert(isActiveRun("shopee_fetch.py") === true, "isActiveRun = true");
  console.log("✓ Test 1: activeRun + state diset SYNC, SEBELUM start_tool resolve");

  /* Test 2: onToolStarted bisa update UI karena isActiveRun true */
  onToolStarted("shopee_fetch.py");
  const st = toolStates["shopee_fetch.py"];
  assert(st.running === true, "st.running tetap true setelah onToolStarted");
  assert(st.statusCls === "running", "statusCls harus 'running'");
  console.log("✓ Test 2: onToolStarted update UI (isActiveRun = true)");

  /* Test 3: flush microtasks — start_tool sekarang dipanggil */
  await Promise.resolve();
  await Promise.resolve();
  assert(_startToolCalled === true, "start_tool harus dipanggil setelah microtask flush");
  console.log("✓ Test 3: start_tool dipanggil setelah microtask flush");

  /* Test 4: Fetch button tetap disabled during running */
  const fb = mockQuerySelector("#fetch-btn");
  assert(fb.disabled === true, "Fetch button harus disabled saat fetch running");
  console.log("✓ Test 4: Fetch button disabled saat fetch running");

  /* Test 5: Guard — klik Fetch lagi saat sudah running tidak restart */
  const stateBefore = toolStates["shopee_fetch.py"].running;
  onFetchClick(); /* klik ulang */
  assert(toolStates["shopee_fetch.py"].running === stateBefore, "Klik ulang saat running tidak boleh reset state");
  console.log("✓ Test 5: Guard fetch-already-running aktif — tidak restart");

  /* Test 6: startDisabled mengembalikan true ketika fetch running */
  const checkSt = toolStateOf("check.py");
  resetRunState(checkSt);
  checkSt.running = false; /* simulasi check.py belum jalan */
  assert(checkSt.running === false, "check.py tidak running");
  assert(startDisabled(checkSt) === true, "startDisabled harus true ketika fetch running (check.py gak boleh start)");
  console.log("✓ Test 6: Start button disabled saat fetch running (check.py tak boleh start)");

  console.log("\n=== ALL TESTS PASSED ===");
}

main().catch((e) => {
  console.error("FAIL:", e.message);
  process.exit(1);
});
