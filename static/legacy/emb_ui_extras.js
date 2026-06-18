/* emborganizer separated behavior layer: progress, BETA tag, mobile-friendly preview/fullscreen. */
(function () {
  "use strict";

  let convertPollTimer = null;
  let hideProgressTimer = null;

  function safeText(value) {
    return String(value == null ? "" : value);
  }

  function escapeHtml(value) {
    if (typeof window.escapeHtml === "function") return window.escapeHtml(value);
    return safeText(value).replace(/[&<>"']/g, function (m) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[m];
    });
  }

  function clampPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return Math.max(0, Math.min(100, Math.round(n)));
  }

  function makeConvertJobId() {
    const cryptoObj = window.crypto || window.msCrypto;
    if (cryptoObj && cryptoObj.getRandomValues) {
      const arr = new Uint32Array(4);
      cryptoObj.getRandomValues(arr);
      return "convert_" + Array.from(arr).map(v => v.toString(16)).join("") + "_" + Date.now().toString(16);
    }
    return "convert_" + Math.random().toString(16).slice(2) + "_" + Date.now().toString(16);
  }

  function ensureGlobalProgressBar() {
    let bar = document.getElementById("globalProgress");
    if (bar) return bar;
    bar = document.createElement("div");
    bar.id = "globalProgress";
    bar.className = "globalProgress";
    bar.innerHTML = [
      '<div class="globalProgressTop">',
      '  <span id="globalProgressLabel">Working...</span>',
      '  <span id="globalProgressPercent">0%</span>',
      '</div>',
      '<div class="globalProgressTrack"><div class="globalProgressFill" id="globalProgressFill"></div></div>',
      '<div class="globalProgressDetail" id="globalProgressDetail"></div>'
    ].join("");
    document.body.appendChild(bar);
    return bar;
  }

  function ensureConvertProgressPanel() {
    let panel = document.getElementById("convertProgressPanel");
    if (panel) return panel;
    const host = document.querySelector("#convertDrop")?.parentElement || document.querySelector("#convertResults")?.parentElement;
    if (!host) return null;
    panel = document.createElement("div");
    panel.id = "convertProgressPanel";
    panel.className = "convertProgressPanel";
    panel.setAttribute("aria-live", "polite");
    panel.innerHTML = [
      '<div class="convertProgressHead">',
      '  <b id="convertProgressLabel">Ready to convert</b>',
      '  <span id="convertProgressPercent">0%</span>',
      '</div>',
      '<div class="convertProgressTrack"><div class="convertProgressFill" id="convertProgressFill"></div></div>',
      '<div class="convertProgressDetail" id="convertProgressDetail">Choose files and start conversion.</div>'
    ].join("");
    host.appendChild(panel);
    return panel;
  }

  function setEnhancedProgress(label, percent, detail, options) {
    const value = clampPercent(percent);
    const bar = ensureGlobalProgressBar();
    const panel = ensureConvertProgressPanel();
    const shouldHide = options && options.hideAfterDone;

    if (bar) {
      bar.classList.add("show");
      const fill = document.getElementById("globalProgressFill");
      const pct = document.getElementById("globalProgressPercent");
      const lab = document.getElementById("globalProgressLabel");
      const det = document.getElementById("globalProgressDetail");
      if (fill) fill.style.width = value + "%";
      if (pct) pct.innerText = value + "%";
      if (lab) lab.innerText = label || "Working...";
      if (det) det.innerText = detail || "";
    }

    if (panel) {
      panel.classList.add("show");
      const fill = document.getElementById("convertProgressFill");
      const pct = document.getElementById("convertProgressPercent");
      const lab = document.getElementById("convertProgressLabel");
      const det = document.getElementById("convertProgressDetail");
      if (fill) fill.style.width = value + "%";
      if (pct) pct.innerText = value + "%";
      if (lab) lab.innerText = label || "Working...";
      if (det) det.innerText = detail || "";
    }

    if (hideProgressTimer) clearTimeout(hideProgressTimer);
    if (value >= 100 && shouldHide) {
      hideProgressTimer = setTimeout(function () {
        const gp = document.getElementById("globalProgress");
        if (gp) gp.classList.remove("show");
      }, 2200);
    }
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

  function apiGetJson(url) {
    const fetcher = typeof window.apiFetch === "function" ? window.apiFetch : function (u, options) { return fetch(u, options || {}); };
    return fetcher(url, {headers: authHeaders()}).then(function (res) {
      return res.text().then(function (text) {
        try { return JSON.parse(text || "{}"); }
        catch (e) { return {ok:false, error:"Server returned non-JSON progress."}; }
      });
    }).catch(function () { return {ok:false, error:"Progress check failed."}; });
  }

  function startConvertPolling(jobId) {
    if (convertPollTimer) clearTimeout(convertPollTimer);
    let lastProgress = 48;
    const poll = function () {
      apiGetJson("/api/convert-progress?job_id=" + encodeURIComponent(jobId)).then(function (data) {
        if (data && data.ok) {
          lastProgress = Math.max(lastProgress, clampPercent(data.progress || 0));
          const processed = data.processed || data.done || 0;
          const total = data.total || 0;
          const detail = data.current_file || data.message || (total ? (processed + "/" + total + " file(s)") : "Server conversion is running...");
          setEnhancedProgress(data.message || "Native server conversion", lastProgress, detail);
          if (data.status === "done" || data.status === "error") return;
        } else if (lastProgress < 55) {
          setEnhancedProgress("Waiting for server conversion", lastProgress, "Upload is complete; server is preparing the conversion job...");
        }
        convertPollTimer = setTimeout(poll, 650);
      });
    };
    convertPollTimer = setTimeout(poll, 450);
  }

  function xhrPostForm(url, form, onUploadProgress) {
    return new Promise(function (resolve) {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      const headers = authHeaders();
      Object.keys(headers).forEach(function (key) { xhr.setRequestHeader(key, headers[key]); });
      xhr.upload.onprogress = function (event) {
        if (event.lengthComputable && onUploadProgress) onUploadProgress(event.loaded, event.total);
      };
      xhr.onload = function () {
        let data;
        try { data = JSON.parse(xhr.responseText || "{}"); }
        catch (e) {
          const preview = String(xhr.responseText || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 260);
          data = {ok:false, error:"Server returned non-JSON. Status " + xhr.status + ". " + (preview || "Check server logs.")};
        }
        resolve({ok:xhr.status >= 200 && xhr.status < 300, status:xhr.status, data:data});
      };
      xhr.onerror = function () { resolve({ok:false, status:0, data:{ok:false, error:"Network upload failed."}}); };
      xhr.send(form);
    });
  }

  function getSelectedConvertFiles() {
    try {
      if (typeof selectedConvertFiles !== "undefined" && selectedConvertFiles && selectedConvertFiles.length) return selectedConvertFiles;
    } catch (e) {}
    const input = document.getElementById("convertFiles");
    return input ? input.files : null;
  }

  function renderConvertResults(data) {
    const box = document.getElementById("convertResults");
    if (!box) return;
    const isMainApp = box.classList.contains("gallery");
    const cardClass = isMainApp ? "item" : "card";
    const bodyClass = isMainApp ? "itemBody" : "card-body";
    const infoClass = isMainApp ? "path" : "info";
    box.innerHTML = "";

    if (data.zip_url) {
      const zipPanel = document.createElement("div");
      zipPanel.className = isMainApp ? "panel" : "card";
      zipPanel.innerHTML = isMainApp
        ? '<b>' + (data.results || []).length + ' file(s) converted.</b><br><br><a class="btn gold" style="display:inline-block;text-decoration:none;" href="' + escapeHtml(data.zip_url) + '">Download All as ZIP</a>'
        : '<div class="card-body"><div class="badge">Done</div><h3>' + (data.results || []).length + ' file(s) processed</h3><a class="btn" href="' + escapeHtml(data.zip_url) + '">Download All as ZIP</a></div>';
      box.appendChild(zipPanel);
    }

    (data.results || []).forEach(function (item) {
      const div = document.createElement("div");
      div.className = cardClass;
      if (item.ok) {
        const engineLine = item.engine ? '<br>Engine: ' + escapeHtml(item.engine) : '';
        const image = '<img src="' + escapeHtml(item.image_url) + '" data-fullscreen-src="' + escapeHtml(item.image_url) + '" alt="' + escapeHtml(item.file_name) + '">';
        const download = isMainApp
          ? '<div class="actions"><a class="btn teal" style="text-decoration:none;" href="' + escapeHtml(item.download_url) + '" download>Download Image</a></div>'
          : '<br><a class="btn" href="' + escapeHtml(item.download_url) + '" download>Download Image</a>';
        div.innerHTML = image +
          '<div class="' + bodyClass + '">' +
          '<div class="badge">Converted</div>' +
          (isMainApp ? '<div class="title">' + escapeHtml(item.file_name) + '</div>' : '<h3>' + escapeHtml(item.file_name) + '</h3>') +
          '<div class="' + infoClass + '">Format: ' + escapeHtml(item.format) + ' | Stitches: ' + escapeHtml(item.stitches) + ' | Colors: ' + escapeHtml(item.colors) + '<br>' +
          'Size: ' + escapeHtml(item.width_mm == null ? "unknown" : item.width_mm) + ' x ' + escapeHtml(item.height_mm == null ? "unknown" : item.height_mm) + ' mm' + engineLine + '</div>' +
          download +
          '</div>';
      } else {
        div.innerHTML = '<div class="' + bodyClass + '">' +
          '<div class="badge" style="background:#fee2e2;color:#991b1b;">Failed</div>' +
          (isMainApp ? '<div class="title">' + escapeHtml(item.file_name) + '</div>' : '<h3>' + escapeHtml(item.file_name) + '</h3>') +
          '<div class="' + infoClass + '">' + escapeHtml(item.error || "Could not convert this file.") + '</div>' +
          '</div>';
      }
      box.appendChild(div);
    });

    enhanceInlineFullscreenImages(box);
  }

  async function enhancedConvertToImages() {
    const files = getSelectedConvertFiles();
    const outFormat = document.getElementById("convertFormat")?.value || "png";
    const imageSize = document.getElementById("convertSize")?.value || "1200";
    const box = document.getElementById("convertResults");

    if (!files || !files.length) {
      alert("Choose embroidery files first.");
      return;
    }

    const jobId = makeConvertJobId();
    const form = new FormData();
    Array.from(files).forEach(function (file) { form.append("files", file); });
    form.append("output_format", outFormat);
    form.append("image_size", imageSize);
    form.append("convert_job_id", jobId);

    if (box) {
      const waitingClass = box.classList.contains("gallery") ? "panel" : "card";
      box.innerHTML = waitingClass === "panel"
        ? '<div class="panel">Uploading and converting ' + files.length + ' file(s)...</div>'
        : '<div class="card"><div class="card-body"><b>Uploading and converting ' + files.length + ' file(s)...</b></div></div>';
    }

    ensureConvertProgressPanel();
    setEnhancedProgress("Preparing conversion", 2, files.length + " file(s) selected");
    startConvertPolling(jobId);

    const uploadResult = await xhrPostForm("/api/convert-to-images", form, function (loaded, total) {
      const pct = 3 + Math.floor((loaded / Math.max(1, total)) * 42);
      setEnhancedProgress("Uploading converter files", pct, (loaded / 1048576).toFixed(2) + " / " + (total / 1048576).toFixed(2) + " MB");
    });

    if (convertPollTimer) {
      clearTimeout(convertPollTimer);
      convertPollTimer = null;
    }

    const data = uploadResult.data || {};
    if (!uploadResult.ok || !data.ok) {
      if (box) {
        const error = escapeHtml(data.error || "Conversion failed.");
        box.innerHTML = box.classList.contains("gallery") ? '<div class="panel">' + error + '</div>' : '<div class="card"><div class="card-body">' + error + '</div></div>';
      }
      setEnhancedProgress("Conversion failed", 100, data.error || "Could not convert files.", {hideAfterDone:false});
      return;
    }

    renderConvertResults(data);
    setEnhancedProgress("Conversion complete", 100, (data.results || []).length + " file(s) processed with " + (data.workers || 1) + " worker(s).", {hideAfterDone:true});
  }

  function updateSelectedFilesText(files) {
    const count = files ? files.length : 0;
    let target = document.getElementById("selectedFilesText");
    if (!target) {
      const input = document.getElementById("convertFiles");
      if (input && input.parentElement) {
        target = document.createElement("div");
        target.id = "selectedFilesText";
        target.style.cssText = "margin:10px 0;color:#475569;font-weight:800;";
        input.parentElement.appendChild(target);
      }
    }
    if (target) target.innerText = count ? count + " file(s) selected" : "";
  }

  function installConvertEnhancements() {
    if (!document.getElementById("convertFiles") || !document.getElementById("convertResults")) return;
    ensureGlobalProgressBar();
    ensureConvertProgressPanel();
    window.convertToImages = enhancedConvertToImages;

    const input = document.getElementById("convertFiles");
    if (input && !input.dataset.embEnhancedPick) {
      input.dataset.embEnhancedPick = "1";
      input.addEventListener("change", function () { updateSelectedFilesText(input.files); });
    }

    const drop = document.getElementById("convertDrop");
    if (drop && !drop.dataset.embEnhancedDrop) {
      drop.dataset.embEnhancedDrop = "1";
      drop.addEventListener("drop", function () { setTimeout(function () { updateSelectedFilesText(getSelectedConvertFiles()); }, 0); });
    }
  }

  function addBetaTagToElement(el) {
    if (!el || el.querySelector(".betaPill")) return;
    const tag = document.createElement("span");
    tag.className = "betaPill";
    tag.textContent = "BETA";
    el.appendChild(tag);
  }

  function markImageSearchBeta() {
    document.querySelectorAll(".nav button").forEach(function (btn) {
      if (/image\s*search/i.test(btn.textContent)) addBetaTagToElement(btn);
    });
    const heading = document.querySelector("#imagesearch h1");
    addBetaTagToElement(heading);
    document.querySelectorAll("h3,h2").forEach(function (el) {
      if (/image\s*search/i.test(el.textContent) && !/BETA/i.test(el.textContent)) addBetaTagToElement(el);
    });
  }

  function openEmbFullscreen(src, title) {
    if (!src) return;
    closeEmbFullscreen();
    const overlay = document.createElement("div");
    overlay.className = "embFullscreenOverlay";
    overlay.id = "embFullscreenOverlay";
    overlay.innerHTML = [
      '<div class="embFullscreenTop">',
      '  <div class="embFullscreenTitle">' + escapeHtml(title || "Preview") + '</div>',
      '  <button type="button" class="embFullscreenClose">Close</button>',
      '</div>',
      '<img class="embFullscreenImage" src="' + escapeHtml(src) + '" alt="' + escapeHtml(title || "Preview") + '">'
    ].join("");
    overlay.addEventListener("click", function (event) {
      if (event.target === overlay || event.target.classList.contains("embFullscreenClose")) closeEmbFullscreen();
    });
    document.body.appendChild(overlay);
    document.body.style.overflow = "hidden";
  }

  function closeEmbFullscreen() {
    const overlay = document.getElementById("embFullscreenOverlay");
    if (overlay) overlay.remove();
    document.body.style.overflow = "";
  }

  function enhanceInlineFullscreenImages(root) {
    (root || document).querySelectorAll("img[data-fullscreen-src]").forEach(function (img) {
      if (img.dataset.embFullscreenReady) return;
      img.dataset.embFullscreenReady = "1";
      img.title = img.title || "Tap again to open fullscreen";
      img.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        openEmbFullscreen(img.dataset.fullscreenSrc || img.currentSrc || img.src, img.alt || "Preview");
      });
    });
  }

  function enhancePreviewModal() {
    const modal = document.getElementById("previewModal");
    if (!modal) return;
    const grid = document.getElementById("fileGrid");
    const head = modal.querySelector(".modalHead");
    if (head && !document.getElementById("fullscreenHint")) {
      const hint = document.createElement("div");
      hint.id = "fullscreenHint";
      hint.className = "fullscreenHint";
      hint.textContent = "Tip: tap any preview image again to open fullscreen.";
      head.insertAdjacentElement("afterend", hint);
    }
    if (grid) {
      grid.querySelectorAll(".fileCard img").forEach(function (img) {
        img.dataset.fullscreenSrc = img.dataset.fullscreenSrc || img.getAttribute("src") || "";
        const title = img.closest(".fileCard")?.querySelector(".fileInfo b")?.textContent || "Preview";
        img.alt = img.alt || title;
      });
      enhanceInlineFullscreenImages(grid);
    }
  }

  function installPreviewEnhancements() {
    if (typeof window.openPreview === "function" && !window.openPreview.embEnhanced) {
      const originalOpenPreview = window.openPreview;
      const wrapped = async function () {
        const result = await originalOpenPreview.apply(this, arguments);
        setTimeout(enhancePreviewModal, 0);
        return result;
      };
      wrapped.embEnhanced = true;
      window.openPreview = wrapped;
    }
    document.addEventListener("click", function (event) {
      const img = event.target.closest ? event.target.closest(".fileCard img") : null;
      if (!img) return;
      img.dataset.fullscreenSrc = img.dataset.fullscreenSrc || img.getAttribute("src") || "";
      openEmbFullscreen(img.dataset.fullscreenSrc, img.alt || "Preview");
    }, true);
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") closeEmbFullscreen();
    });
  }

  function boot() {
    installConvertEnhancements();
    markImageSearchBeta();
    installPreviewEnhancements();
    enhanceInlineFullscreenImages(document);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
