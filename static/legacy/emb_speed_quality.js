/* EMBORGANIZER v0.8.5 adaptive speed + quality + TURBOEMB background preview + GDrive sync layer.
   Separated for easier debugging: device profile, parallel upload, one-file conversion, direct folder upload. */
(function () {
  "use strict";

  const LS_MODE = "emb_speed_quality_mode_v080";
  const LS_FOLDER_MODE = "emb_folder_upload_mode_v080";
  let serverProfile = null;
  let booted = false;

  function safeText(value) { return String(value == null ? "" : value); }
  function escapeHtml(value) {
    if (typeof window.escapeHtml === "function") return window.escapeHtml(value);
    return safeText(value).replace(/[&<>"']/g, function (m) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[m];
    });
  }
  function supportedEmbFile(name) { return /\.(dst|pes|jef|exp|vp3|hus|xxx|emb)$/i.test(name || ""); }
  function clamp(n, a, b) { n = Number(n); return Number.isFinite(n) ? Math.max(a, Math.min(b, n)) : a; }
  function makeId(prefix) {
    const c = window.crypto || window.msCrypto;
    if (c && c.getRandomValues) {
      const arr = new Uint32Array(3); c.getRandomValues(arr);
      return prefix + Array.from(arr).map(v => v.toString(16)).join("") + Date.now().toString(16);
    }
    return prefix + Math.random().toString(16).slice(2) + Date.now().toString(16);
  }
  function authHeaders() {
    const headers = {};
    try {
      if (typeof googleIdToken !== "undefined" && googleIdToken && typeof tokenNotExpired === "function" && tokenNotExpired(googleIdToken)) {
        headers.Authorization = "Bearer " + googleIdToken;
      }
    } catch (e) {}
    return headers;
  }
  function apiFetch(url, options) {
    if (typeof window.apiFetch === "function") return window.apiFetch(url, options || {});
    options = options || {}; options.headers = Object.assign({}, options.headers || {}, authHeaders());
    return fetch(url, options);
  }
  function xhrPostForm(url, form, onProgress) {
    return new Promise(function (resolve) {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      const headers = authHeaders();
      Object.keys(headers).forEach(k => xhr.setRequestHeader(k, headers[k]));
      xhr.upload.onprogress = function (e) { if (e.lengthComputable && onProgress) onProgress(e.loaded, e.total); };
      xhr.onload = function () {
        let data = {};
        try { data = JSON.parse(xhr.responseText || "{}"); }
        catch (e) { data = {ok:false, error:"Server returned non-JSON. Status " + xhr.status}; }
        resolve({ok:xhr.status >= 200 && xhr.status < 300, status:xhr.status, data:data});
      };
      xhr.onerror = function () { resolve({ok:false, status:0, data:{ok:false, error:"Network upload failed."}}); };
      xhr.send(form);
    });
  }

  function ensureProgressUi() {
    let bar = document.getElementById("globalProgress");
    if (!bar) {
      bar = document.createElement("div");
      bar.id = "globalProgress";
      bar.className = "globalProgress";
      bar.innerHTML = '<div class="globalProgressTop"><span id="globalProgressLabel">Working...</span><span id="globalProgressPercent">0%</span></div><div class="globalProgressTrack"><div class="globalProgressFill" id="globalProgressFill"></div></div><div class="globalProgressDetail" id="globalProgressDetail"></div>';
      document.body.appendChild(bar);
    }
    return bar;
  }
  function setProgress(label, percent, detail) {
    percent = Math.round(clamp(percent, 0, 100));
    try { if (typeof window.setGlobalProgress === "function") window.setGlobalProgress(label, percent, detail || ""); } catch (e) {}
    const bar = ensureProgressUi();
    bar.classList.add("show");
    const fill = document.getElementById("globalProgressFill");
    const pct = document.getElementById("globalProgressPercent");
    const lab = document.getElementById("globalProgressLabel");
    const det = document.getElementById("globalProgressDetail");
    if (fill) fill.style.width = percent + "%";
    if (pct) pct.innerText = percent + "%";
    if (lab) lab.innerText = label || "Working...";
    if (det) det.innerText = detail || "";
    const cpFill = document.getElementById("convertProgressFill");
    const cpPct = document.getElementById("convertProgressPercent");
    const cpLab = document.getElementById("convertProgressLabel");
    const cpDet = document.getElementById("convertProgressDetail");
    const panel = document.getElementById("convertProgressPanel");
    if (panel) panel.classList.add("show");
    if (cpFill) cpFill.style.width = percent + "%";
    if (cpPct) cpPct.innerText = percent + "%";
    if (cpLab) cpLab.innerText = label || "Working...";
    if (cpDet) cpDet.innerText = detail || "";
  }

  function detectAutoKey() {
    const cores = navigator.hardwareConcurrency || 2;
    const mem = navigator.deviceMemory || 0;
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection || {};
    const width = Math.min(screen.width || window.innerWidth || 9999, window.innerWidth || 9999);
    const touch = (navigator.maxTouchPoints || 0) > 0;
    const mobileLike = width <= 850 || /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
    if (conn.saveData || /(^|-)2g$/.test(conn.effectiveType || "")) return "mobile_safe";
    if (mobileLike || (touch && width <= 1024) || cores <= 4 || (mem && mem <= 4)) return "mobile_safe";
    if (cores >= 12 && (!mem || mem >= 16)) return "desktop_turbo";
    if (cores >= 8 && (!mem || mem >= 8)) return "desktop_turbo";
    return "balanced";
  }
  function currentModeKey() {
    const saved = localStorage.getItem(LS_MODE) || "auto";
    return saved === "auto" ? detectAutoKey() : saved;
  }
  function currentModeLabel() {
    const saved = localStorage.getItem(LS_MODE) || "auto";
    const key = currentModeKey();
    if (saved === "auto") return "Auto → " + ((serverProfile && serverProfile.presets && serverProfile.presets[key] && serverProfile.presets[key].label) || key);
    return (serverProfile && serverProfile.presets && serverProfile.presets[key] && serverProfile.presets[key].label) || key;
  }
  function currentSettings() {
    const presets = (serverProfile && serverProfile.presets) || {};
    const fallback = {
      mobile_safe:{upload_parallel:2, convert_parallel:1, import_upload_parallel:2, default_image_size:2200},
      balanced:{upload_parallel:4, convert_parallel:2, import_upload_parallel:4, default_image_size:2400},
      desktop_turbo:{upload_parallel:8, convert_parallel:4, import_upload_parallel:8, default_image_size:3200},
      desktop_turbo_pro:{upload_parallel:12, convert_parallel:6, import_upload_parallel:12, default_image_size:3600}
    };
    const key = currentModeKey();
    return Object.assign({}, fallback[key] || fallback.balanced, presets[key] || {}, {key:key, mode_label:currentModeLabel()});
  }
  async function loadServerProfile() {
    if (serverProfile) return serverProfile;
    try {
      const res = await fetch("/api/speed-profile", {headers: authHeaders()});
      const data = await res.json();
      if (data && data.ok) serverProfile = data;
    } catch (e) {}
    serverProfile = serverProfile || {presets:{}};
    return serverProfile;
  }

  function insertSpeedPanel(host, kind) {
    if (!host || host.querySelector(".speedQualityPanel[data-kind='" + kind + "']")) return;
    const panel = document.createElement("div");
    panel.className = "speedQualityPanel";
    panel.dataset.kind = kind;
    panel.innerHTML = [
      '<div class="speedQualityTop"><b>Speed + Quality</b><span class="speedQualityStatus" data-speed-status>Auto tuning...</span></div>',
      '<div class="speedQualityControls">',
      '  <label>Performance <select data-speed-mode><option value="auto">Auto</option><option value="mobile_safe">Mobile Safe</option><option value="balanced">Balanced</option><option value="desktop_turbo">Desktop Turbo</option><option value="desktop_turbo_pro">Desktop Turbo Pro</option></select></label>',
      '  <label>Folder upload <select data-folder-mode><option value="direct_parallel">Direct parallel</option><option value="zip_fallback">ZIP fallback</option></select></label>',
      '</div>',
      '<div class="speedQualityHint">Final images stay high quality. Desktop Turbo Pro raises queue pressure for stronger CPUs; mobile stays safe.</div>'
    ].join("");
    host.appendChild(panel);
    const mode = panel.querySelector("[data-speed-mode]");
    const folder = panel.querySelector("[data-folder-mode]");
    mode.value = localStorage.getItem(LS_MODE) || "auto";
    folder.value = localStorage.getItem(LS_FOLDER_MODE) || "direct_parallel";
    mode.addEventListener("change", function () { localStorage.setItem(LS_MODE, mode.value); refreshSpeedPanels(); });
    folder.addEventListener("change", function () { localStorage.setItem(LS_FOLDER_MODE, folder.value); refreshSpeedPanels(); });
  }
  async function loadDriveSyncSettings() {
    try {
      const res = await apiFetch("/api/drive-sync-settings");
      return await res.json();
    } catch (e) {
      return {ok:false, error:String(e)};
    }
  }
  async function saveDriveSyncSettings(payload) {
    try {
      const res = await apiFetch("/api/drive-sync-settings", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload || {})});
      return await res.json();
    } catch (e) {
      return {ok:false, error:String(e)};
    }
  }
  function insertDriveSyncPanel(host) {
    if (!host || host.querySelector(".driveSyncPanel")) return;
    const panel = document.createElement("div");
    panel.className = "driveSyncPanel";
    panel.innerHTML = [
      '<div class="speedQualityTop"><b>Google Drive Sync</b><span class="speedQualityStatus" data-drive-sync-status>Checking...</span></div>',
      '<div class="speedQualityControls">',
      '  <label><span>Enable sync</span><select data-drive-sync-enabled><option value="1">Enabled</option><option value="0">Disabled</option></select></label>',
      '  <label><span>Max local cache</span><select data-cache-max><option value="200">200 MB</option><option value="400">400 MB</option><option value="800">800 MB</option><option value="1200">1.2 GB</option></select></label>',
      '</div>',
      '<div class="driveSyncActions"><button type="button" class="btn" data-drive-sync-now>Sync now</button><button type="button" class="btn ghost" data-cache-clean>Clean cache</button></div>',
      '<div class="speedQualityHint" data-drive-sync-hint>Drive sync runs slowly in the background so imports stay fast.</div>'
    ].join("");
    host.appendChild(panel);
    const enabled = panel.querySelector("[data-drive-sync-enabled]");
    const cache = panel.querySelector("[data-cache-max]");
    const status = panel.querySelector("[data-drive-sync-status]");
    const hint = panel.querySelector("[data-drive-sync-hint]");
    async function refresh() {
      const data = await loadDriveSyncSettings();
      if (data && data.ok) {
        const settings = data.settings || {};
        enabled.value = settings.enabled ? "1" : "0";
        const mb = String(settings.cache_max_mb || 400);
        cache.value = ["200","400","800","1200"].includes(mb) ? mb : "400";
        const cacheText = data.cache ? (data.cache.mb + " / " + data.cache.max_mb + " MB") : "cache unknown";
        status.innerText = (data.connected ? "Connected" : "Needs sign in") + " · " + (settings.enabled ? "Enabled" : "Disabled");
        hint.innerText = "Background sync: " + (data.background_workers || 1) + " worker(s), cache " + cacheText + ".";
      } else {
        status.innerText = "Unavailable";
        hint.innerText = (data && data.error) || "Could not read sync settings.";
      }
    }
    enabled.addEventListener("change", async function () { await saveDriveSyncSettings({enabled: enabled.value === "1"}); refresh(); });
    cache.addEventListener("change", async function () { await saveDriveSyncSettings({cache_max_mb: Number(cache.value || 400)}); refresh(); });
    panel.querySelector("[data-cache-clean]").addEventListener("click", async function () {
      status.innerText = "Cleaning...";
      try { await apiFetch("/api/cache-clean", {method:"POST"}); } catch(e) {}
      refresh();
    });
    panel.querySelector("[data-drive-sync-now]").addEventListener("click", async function () {
      status.innerText = "Queued...";
      try {
        const res = await apiFetch("/api/drive-sync-now", {method:"POST"});
        const data = await res.json();
        hint.innerText = data.ok ? ("Drive sync queued: " + (data.total_files || 0) + " file(s).") : (data.error || "Could not queue sync.");
      } catch(e) { hint.innerText = "Could not queue sync."; }
      refresh();
    });
    refresh();
  }

  function refreshSpeedPanels() {
    const s = currentSettings();
    document.querySelectorAll(".speedQualityPanel").forEach(function (panel) {
      const status = panel.querySelector("[data-speed-status]");
      const mode = panel.querySelector("[data-speed-mode]");
      const folder = panel.querySelector("[data-folder-mode]");
      if (mode) mode.value = localStorage.getItem(LS_MODE) || "auto";
      if (folder) folder.value = localStorage.getItem(LS_FOLDER_MODE) || "direct_parallel";
      if (status) status.innerText = s.mode_label + " · upload ×" + s.upload_parallel + " · render ×" + s.convert_parallel;
    });
  }
  function installSpeedPanels() {
    const converterHost = document.querySelector("#convertDrop")?.closest(".panel,.drop,.converter") || document.querySelector("#convertResults")?.parentElement;
    const importHost = document.querySelector("#folderUploadSummary")?.parentElement || document.querySelector("#progressWrap")?.parentElement;
    insertSpeedPanel(converterHost, "convert");
    insertSpeedPanel(importHost, "import");
    insertDriveSyncPanel(importHost);
    refreshSpeedPanels();
  }

  async function runQueue(items, concurrency, worker) {
    const results = new Array(items.length);
    let next = 0;
    async function runOne() {
      while (next < items.length) {
        const idx = next++;
        results[idx] = await worker(items[idx], idx);
      }
    }
    const runners = [];
    for (let i = 0; i < Math.max(1, Math.min(concurrency, items.length)); i++) runners.push(runOne());
    await Promise.all(runners);
    return results;
  }

  function getSelectedConvertFiles() {
    try { if (typeof selectedConvertFiles !== "undefined" && selectedConvertFiles && selectedConvertFiles.length) return Array.from(selectedConvertFiles); } catch (e) {}
    const input = document.getElementById("convertFiles");
    return input && input.files ? Array.from(input.files) : [];
  }
  function createConvertPlaceholder(box, file, index) {
    const isMain = box && box.classList.contains("gallery");
    const div = document.createElement("div");
    div.className = isMain ? "item speedFileCard" : "card speedFileCard";
    div.dataset.index = String(index);
    const body = isMain ? "itemBody" : "card-body";
    div.innerHTML = '<div class="speedFilePreview">Queued</div><div class="' + body + '"><div class="badge">Waiting</div>' +
      (isMain ? '<div class="title">' + escapeHtml(file.name) + '</div>' : '<h3>' + escapeHtml(file.name) + '</h3>') +
      '<div class="speedMiniTrack"><div class="speedMiniFill"></div></div><div class="speedMiniText">Waiting for adaptive queue...</div></div>';
    box.appendChild(div);
    return div;
  }
  function updatePlaceholder(card, status, pct, text) {
    if (!card) return;
    const badge = card.querySelector(".badge");
    const fill = card.querySelector(".speedMiniFill");
    const label = card.querySelector(".speedMiniText");
    const prev = card.querySelector(".speedFilePreview");
    if (badge) badge.innerText = status;
    if (fill) fill.style.width = Math.round(clamp(pct, 0, 100)) + "%";
    if (label) label.innerText = text || status;
    if (prev && pct < 100) prev.innerText = Math.round(clamp(pct, 0, 100)) + "%";
  }
  function renderConvertCard(card, item) {
    const isMain = card.classList.contains("item");
    const body = isMain ? "itemBody" : "card-body";
    const info = isMain ? "path" : "info";
    if (item && item.ok) {
      const cache = item.cache_hit ? ' · cache hit' : '';
      card.innerHTML = '<img src="' + escapeHtml(item.image_url) + '" data-fullscreen-src="' + escapeHtml(item.image_url) + '" alt="' + escapeHtml(item.file_name) + '">' +
        '<div class="' + body + '"><div class="badge">Converted</div>' +
        (isMain ? '<div class="title">' + escapeHtml(item.file_name) + '</div>' : '<h3>' + escapeHtml(item.file_name) + '</h3>') +
        '<div class="' + info + '">Format: ' + escapeHtml(item.format) + ' | Stitches: ' + escapeHtml(item.stitches) + ' | Colors: ' + escapeHtml(item.colors) + '<br>Size: ' + escapeHtml(item.width_mm == null ? "unknown" : item.width_mm) + ' x ' + escapeHtml(item.height_mm == null ? "unknown" : item.height_mm) + ' mm<br>Engine: ' + escapeHtml(item.engine || "adaptive") + escapeHtml(cache) + '</div>' +
        (isMain ? '<div class="actions"><a class="btn teal" style="text-decoration:none;" href="' + escapeHtml(item.download_url) + '" download>Download Image</a></div>' : '<br><a class="btn" href="' + escapeHtml(item.download_url) + '" download>Download Image</a>') +
        '</div>';
    } else {
      const name = item && item.file_name ? item.file_name : "File";
      const err = item && item.error ? item.error : "Could not convert this file.";
      card.innerHTML = '<div class="' + body + '"><div class="badge" style="background:#fee2e2;color:#991b1b;">Failed</div>' +
        (isMain ? '<div class="title">' + escapeHtml(name) + '</div>' : '<h3>' + escapeHtml(name) + '</h3>') +
        '<div class="' + info + '">' + escapeHtml(err) + '</div></div>';
    }
    try {
      card.querySelectorAll("img[data-fullscreen-src]").forEach(function (img) {
        img.addEventListener("click", function (event) {
          event.preventDefault(); event.stopPropagation();
          const src = img.dataset.fullscreenSrc || img.src;
          if (window.EMBSpeedQuality && window.EMBSpeedQuality.openFullscreen) window.EMBSpeedQuality.openFullscreen(src, img.alt || "Preview");
        });
      });
    } catch (e) {}
  }
  function openFullscreen(src, title) {
    if (!src) return;
    const old = document.getElementById("embFullscreenOverlay");
    if (old) old.remove();
    const overlay = document.createElement("div");
    overlay.className = "embFullscreenOverlay";
    overlay.id = "embFullscreenOverlay";
    overlay.innerHTML = '<div class="embFullscreenTop"><div class="embFullscreenTitle">' + escapeHtml(title || "Preview") + '</div><button type="button" class="embFullscreenClose">Close</button></div><img class="embFullscreenImage" src="' + escapeHtml(src) + '" alt="' + escapeHtml(title || "Preview") + '">';
    overlay.addEventListener("click", function (e) { if (e.target === overlay || e.target.classList.contains("embFullscreenClose")) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  async function adaptiveConvertToImages() {
    await loadServerProfile();
    const settings = currentSettings();
    const files = getSelectedConvertFiles().filter(f => supportedEmbFile(f.name));
    const outFormat = document.getElementById("convertFormat")?.value || "png";
    const imageSize = document.getElementById("convertSize")?.value || settings.default_image_size || "2400";
    const box = document.getElementById("convertResults");
    if (!files.length) { alert("Choose embroidery files first."); return; }
    const batchId = makeId("batch_");
    const jobId = makeId("convert_");
    const convertParallel = Math.max(1, Math.min(Number(settings.convert_parallel || 1), files.length));
    if (box) box.innerHTML = "";
    const isMain = box && box.classList.contains("gallery");
    let summary = null;
    if (box) {
      summary = document.createElement("div");
      summary.className = isMain ? "panel speedBatchSummary" : "card speedBatchSummary";
      summary.innerHTML = isMain ? '<b>Adaptive parallel conversion started.</b><br><span class="muted">' + escapeHtml(settings.mode_label) + ' · render ×' + convertParallel + '</span>' : '<div class="card-body"><b>Adaptive parallel conversion started.</b><br><span class="info">' + escapeHtml(settings.mode_label) + ' · render ×' + convertParallel + '</span></div>';
      box.appendChild(summary);
    }
    const cards = files.map((file, idx) => box ? createConvertPlaceholder(box, file, idx) : null);
    let done = 0;
    const results = await runQueue(files, convertParallel, async function (file, idx) {
      const form = new FormData();
      form.append("file", file, file.name);
      form.append("output_format", outFormat);
      form.append("image_size", imageSize);
      form.append("convert_batch_id", batchId);
      form.append("convert_job_id", jobId);
      form.append("total_files", String(files.length));
      form.append("worker_hint", String(convertParallel));
      updatePlaceholder(cards[idx], "Uploading", 5, "Uploading to server...");
      const upload = await xhrPostForm("/api/convert-one-image", form, function (loaded, total) {
        const pct = 5 + Math.floor((loaded / Math.max(1, total)) * 45);
        updatePlaceholder(cards[idx], "Uploading", pct, (loaded / 1048576).toFixed(2) + " / " + (total / 1048576).toFixed(2) + " MB");
        const overall = Math.floor(((done + pct / 100) / files.length) * 92);
        setProgress("Adaptive parallel conversion", overall, file.name);
      });
      updatePlaceholder(cards[idx], "Rendering", 78, "Native C++ renderer + cache check...");
      const item = (upload.data && upload.data.result) || {ok:false, file_name:file.name, error:(upload.data && upload.data.error) || "Upload failed"};
      done++;
      renderConvertCard(cards[idx], item);
      setProgress("Adaptive parallel conversion", Math.floor((done / files.length) * 94), done + "/" + files.length + " file(s) ready");
      return item;
    });
    let zipUrl = "";
    try {
      const form = new FormData();
      form.append("convert_batch_id", batchId);
      form.append("convert_job_id", jobId);
      const res = await xhrPostForm("/api/convert-finalize-batch", form);
      if (res.ok && res.data && res.data.ok) zipUrl = res.data.zip_url || "";
    } catch (e) {}
    const okCount = results.filter(r => r && r.ok).length;
    if (summary) {
      summary.innerHTML = isMain
        ? '<b>Done. ' + okCount + '/' + results.length + ' file(s) converted.</b><br><span class="muted">' + escapeHtml(settings.mode_label) + ' · render ×' + convertParallel + '</span>' + (zipUrl ? '<br><br><a class="btn gold" style="display:inline-block;text-decoration:none;" href="' + escapeHtml(zipUrl) + '">Download All as ZIP</a>' : '')
        : '<div class="card-body"><div class="badge">Done</div><h3>' + okCount + '/' + results.length + ' file(s) converted</h3><div class="info">' + escapeHtml(settings.mode_label) + ' · render ×' + convertParallel + '</div>' + (zipUrl ? '<a class="btn" href="' + escapeHtml(zipUrl) + '">Download All as ZIP</a>' : '') + '</div>';
    }
    setProgress("Conversion complete", 100, okCount + "/" + results.length + " file(s) converted with high-quality output");
  }

  function getSelectedImportFiles() {
    try { if (typeof selectedImportFiles !== "undefined" && selectedImportFiles && selectedImportFiles.length) return Array.from(selectedImportFiles); } catch (e) {}
    const input = document.getElementById("folderUploadInput");
    return input && input.files ? Array.from(input.files).filter(f => supportedEmbFile(f.name)) : [];
  }
  function relPath(file) { return file.webkitRelativePath || file.name || "design"; }
  async function adaptiveStartUploadedFolderImport(originalFallback) {
    await loadServerProfile();
    const folderMode = localStorage.getItem(LS_FOLDER_MODE) || "direct_parallel";
    if (folderMode === "zip_fallback") return originalFallback.apply(this, arguments);
    try { if (typeof ensureSignedIn === "function" && !ensureSignedIn('Sign in with Google to import folders and save previews in your library.')) return; } catch (e) {}
    const files = getSelectedImportFiles().filter(f => supportedEmbFile(f.name));
    if (!files.length) { alert("Choose an embroidery folder first."); return; }
    const settings = currentSettings();
    const concurrency = Math.max(1, Math.min(Number(settings.import_upload_parallel || settings.upload_parallel || 2), files.length));
    const progressWrap = document.getElementById("progressWrap");
    const progressFill = document.getElementById("progressFill");
    const progressText = document.getElementById("progressText");
    const currentFolder = document.getElementById("currentFolder");
    const perFile = document.getElementById("perFileStatus");
    if (progressWrap) progressWrap.style.display = "block";
    if (perFile) { perFile.style.display = "block"; perFile.innerHTML = ""; }
    const batchId = makeId("import_");
    let uploaded = 0;
    let failed = 0;
    const recent = [];
    function redraw(name, status) {
      const pct = Math.floor((uploaded / Math.max(1, files.length)) * 50);
      if (progressFill) progressFill.style.width = Math.max(2, pct) + "%";
      if (progressText) progressText.innerText = "Direct parallel upload: " + uploaded + "/" + files.length + " uploaded" + (failed ? " · " + failed + " failed" : "");
      if (currentFolder) currentFolder.innerText = name || (settings.mode_label + " · upload ×" + concurrency);
      recent.push({name:name, status:status});
      if (recent.length > 60) recent.shift();
      if (perFile) perFile.innerHTML = '<b>Direct parallel upload:</b> ' + uploaded + '/' + files.length + ' &nbsp; <span class="muted">' + escapeHtml(settings.mode_label) + ' · upload ×' + concurrency + '</span>' + recent.slice(-40).reverse().map(r => '<div style="border-top:1px solid #e2e8f0;padding:4px 0;"><b>' + escapeHtml(r.status) + '</b> · ' + escapeHtml(r.name) + '</div>').join('');
      setProgress("Direct parallel folder upload", pct, uploaded + "/" + files.length + " · " + (name || ""));
    }
    redraw("Starting adaptive upload...", "queued");
    await runQueue(files, concurrency, async function (file) {
      const name = relPath(file);
      const form = new FormData();
      form.append("file", file, name);
      form.append("relative_path", name);
      form.append("import_batch_id", batchId);
      redraw(name, "uploading");
      const res = await xhrPostForm("/api/import-upload-one", form, function (loaded, total) {
        const pct = Math.floor(((uploaded + (loaded / Math.max(1, total))) / Math.max(1, files.length)) * 50);
        if (progressFill) progressFill.style.width = Math.max(2, pct) + "%";
        setProgress("Direct parallel folder upload", pct, (loaded / 1048576).toFixed(2) + " MB · " + name);
      });
      if (res.ok && res.data && res.data.ok && !res.data.skipped) uploaded++;
      else failed++;
      const previewQueued = !!(res.data && res.data.immediate_preview && res.data.immediate_preview.queued);
      redraw(name, res.ok && res.data && res.data.ok ? (previewQueued ? "uploaded · preview queued" : "uploaded") : "failed");
    });
    if (!uploaded) {
      const msg = "No supported files uploaded. Falling back to ZIP path may help.";
      if (progressText) progressText.innerText = msg;
      setProgress("Upload failed", 100, msg);
      return;
    }
    const form = new FormData();
    form.append("import_batch_id", batchId);
    form.append("total_files", String(files.length));
    form.append("upload_mode", "direct_parallel");
    const finalRes = await xhrPostForm("/api/import-finalize-upload", form);
    const data = finalRes.data || {};
    if (!finalRes.ok || !data.ok) {
      const msg = data.error || "Could not start preview generation.";
      if (progressText) progressText.innerText = msg;
      setProgress("Import failed", 100, msg);
      return;
    }
    try { activeJob = data.job_id; activeJobMissingRetries = 0; backgroundImportLoadedOnce = false; } catch (e) { window.activeJob = data.job_id; window.activeJobMissingRetries = 0; window.backgroundImportLoadedOnce = false; }
    if (progressFill) progressFill.style.width = "52%";
    if (progressText) progressText.innerText = "Upload done. TURBOEMB background preview generation started for " + uploaded + " file(s)...";
    setProgress("TURBOEMB background previews", 52, "Uploaded " + uploaded + " file(s). CPU workers: " + (data.workers || 1));
    if (typeof pollProgress === "function") pollProgress();
  }

  function installOverrides() {
    window.convertToImages = adaptiveConvertToImages;
    if (typeof window.startUploadedFolderImport === "function" && !window.startUploadedFolderImport.embSpeedQuality) {
      const original = window.startUploadedFolderImport;
      const wrapped = function () { return adaptiveStartUploadedFolderImport(original); };
      wrapped.embSpeedQuality = true;
      window.startUploadedFolderImport = wrapped;
      window.startImport = wrapped;
    }
  }

  async function boot() {
    if (booted) return; booted = true;
    await loadServerProfile();
    installSpeedPanels();
    installOverrides();
    refreshSpeedPanels();
  }

  window.EMBSpeedQuality = { currentSettings, refreshSpeedPanels, openFullscreen, adaptiveConvertToImages };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
