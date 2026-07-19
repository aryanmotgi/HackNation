/* ============================================================================
   Forge intake wizard — vanilla JS, no frameworks.
   5 steps, PDF parse (POST /api/intake/parse), preview + save
   (POST /api/intake/confirm). All wizard state lives in `state`.
   ========================================================================== */

(function () {
  "use strict";

  // ── Wizard state ─────────────────────────────────────────────────────
  var state = {
    step: 1,
    completed: {},          // { stepNum: true } once visited/advanced past
    voice_style: "warm_professional",
    currency: "USD",        // carried from draft.currency
    payment_terms: "",      // carried from draft.payment_terms
    questions: [],          // carried from parse response
    parsed: false,
  };

  var TOTAL = 3;

  // ── Tiny DOM helpers ─────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }
  function val(id) { var el = $(id); return el ? el.value.trim() : ""; }
  function setVal(id, v) { var el = $(id); if (el && v !== null && v !== undefined) el.value = v; }
  function num(id) {
    var raw = val(id);
    if (raw === "") return null;
    var n = Number(raw);
    return isNaN(n) ? null : n;
  }
  function splitList(id) {
    return val(id).split(",").map(function (s) { return s.trim(); }).filter(Boolean);
  }

  // ── Navigation ───────────────────────────────────────────────────────
  function showStep(n) {
    n = Math.max(1, Math.min(TOTAL, n));
    state.step = n;

    var steps = document.querySelectorAll(".fg-step");
    steps.forEach(function (s) {
      s.classList.toggle("active", Number(s.getAttribute("data-step")) === n);
    });

    updateChecklist();
    updateProgress();
    window.scrollTo({ top: 0, behavior: "smooth" });

    if (n === 3) { refreshLockedBanner(); previewSpec(); }  // Guardrails = final step
  }

  function gotoStep(n) {
    // mark every step before the target as completed (visited)
    for (var i = 1; i < n; i++) state.completed[i] = true;
    state.completed[state.step] = true;
    showStep(n);
  }

  function updateChecklist() {
    var items = document.querySelectorAll(".fg-check-item");
    items.forEach(function (it) {
      var s = Number(it.getAttribute("data-step"));
      it.classList.remove("active", "done");
      var numEl = it.querySelector(".fg-check-num");
      if (s === state.step) {
        it.classList.add("active");
        numEl.textContent = s;
      } else if (state.completed[s]) {
        it.classList.add("done");
        numEl.textContent = "✓";
      } else {
        numEl.textContent = s;
      }
    });
  }

  function updateProgress() {
    // count completed sections (visited/advanced past)
    var done = 0;
    for (var i = 1; i <= TOTAL; i++) if (state.completed[i]) done++;
    $("prog-count").textContent = done;
    $("prog-fill").style.width = (done / TOTAL * 100) + "%";
  }

  // ── Step 3: live locked-rule banner ──────────────────────────────────
  function refreshLockedBanner() {
    var floor = num("deal_floor_price");
    var shown = (floor === null) ? "0" : floor;
    $("locked-text").innerHTML =
      "Never quote below <b>$" + shown + "</b> per unit. Only an authorized human can override this.";
  }

  // ── Step 2: PDF upload / parse ───────────────────────────────────────
  function setUploadStatus(kind, fname, msg, showReplace) {
    var box = $("upload-status");
    box.classList.remove("err");
    box.classList.add("show");
    if (kind === "err") box.classList.add("err");
    var icon = $("upload-status-icon");
    if (kind === "loading") icon.innerHTML = '<span class="fg-spinner"></span>';
    else if (kind === "err") icon.textContent = "⚠";
    else icon.textContent = "✓";
    $("upload-fname").textContent = fname || "";
    $("upload-msg").textContent = msg || "";
    $("upload-replace").style.display = showReplace ? "" : "none";
  }

  function fillDraft(draft) {
    if (!draft) return;
    setVal("deal_product", draft.product);
    setVal("deal_sku", draft.sku);
    setVal("deal_quantity", draft.quantity);
    setVal("deal_opening_price", draft.opening_price);
    setVal("deal_target_price", draft.target_price);
    setVal("deal_floor_price", draft.floor_price);
    setVal("deal_lead_time_days", draft.lead_time_days);
    // carry-over for later steps
    if (draft.currency) state.currency = draft.currency;
    if (draft.payment_terms) {
      state.payment_terms = draft.payment_terms;
      setVal("hr_payment_terms", draft.payment_terms);
    }
    // seed require-approval-below from the floor if empty
    if (val("hr_require_approval_below") === "" && draft.floor_price != null) {
      setVal("hr_require_approval_below", draft.floor_price);
    }
    refreshLockedBanner();
    state.parsed = true;
  }

  function parsePdf(file) {
    setUploadStatus("loading", file.name, "— extracting…", false);
    var fd = new FormData();
    fd.append("pdf", file, file.name || "price_sheet.pdf");
    fetch("/api/intake/parse", { method: "POST", body: fd })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (res) {
        if (!res.ok) {
          setUploadStatus("err", file.name, "— " + (res.data.error || "could not parse"), true);
          return;
        }
        state.questions = res.data.questions || [];
        fillDraft(res.data.draft);
        var found = (res.data.draft && res.data.draft._found) || [];
        var n = found.length;
        setUploadStatus("ok", file.name,
          "— extracted " + (n ? n + " field" + (n === 1 ? "" : "s") : "the details") + ". Review below.",
          true);
      })
      .catch(function (e) {
        setUploadStatus("err", file.name, "— " + e.message, true);
      });
  }

  function wireUpload() {
    var zone = $("upload-zone");
    var input = $("pdf-input");

    zone.addEventListener("click", function (e) {
      if (e.target && e.target.id === "use-sample") return;
      input.click();
    });
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) parsePdf(input.files[0]);
    });

    // drag & drop
    ["dragenter", "dragover"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.add("drag"); });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      zone.addEventListener(ev, function (e) { e.preventDefault(); zone.classList.remove("drag"); });
    });
    zone.addEventListener("drop", function (e) {
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) parsePdf(f);
    });

    // "use sample PDF" — fetch from /static and submit it
    $("use-sample").addEventListener("click", function (e) {
      e.stopPropagation();
      setUploadStatus("loading", "price_sheet_sample.pdf", "— loading sample…", false);
      fetch("/static/price_sheet_sample.pdf")
        .then(function (r) {
          if (!r.ok) throw new Error("sample not found (" + r.status + ")");
          return r.blob();
        })
        .then(function (blob) {
          var file = new File([blob], "price_sheet_sample.pdf", { type: "application/pdf" });
          parsePdf(file);
        })
        .catch(function (err) {
          setUploadStatus("err", "price_sheet_sample.pdf", "— " + err.message, false);
        });
    });

    $("upload-replace").addEventListener("click", function () {
      input.value = "";
      input.click();
    });
  }

  // ── Voice cards ──────────────────────────────────────────────────────
  function wireVoiceCards() {
    var cards = document.querySelectorAll(".fg-voice-card");
    cards.forEach(function (c) {
      c.addEventListener("click", function () {
        cards.forEach(function (x) { x.classList.remove("sel"); });
        c.classList.add("sel");
        state.voice_style = c.getAttribute("data-voice");
      });
    });
  }

  // ── Build confirm payload from state ─────────────────────────────────
  function collectTriggers() {
    var keys = [
      "price_below_floor",
      "unsupported_customization",
      "angry_or_manager",
      "order_exceeds_transfer_limit",
    ];
    var out = [];
    keys.forEach(function (k) {
      var el = $("trig_" + k);
      if (el && el.checked) out.push(k);
    });
    return out;
  }

  function buildPayload(confirm) {
    // deal numbers
    var deal = {
      product: val("deal_product"),
      sku: val("deal_sku"),
      quantity: num("deal_quantity"),
      unit: "units",
      opening_price: num("deal_opening_price"),
      target_price: num("deal_target_price"),
      floor_price: num("deal_floor_price"),
      currency: state.currency || "USD",
      volume_tiers: [],
      lead_time_days: num("deal_lead_time_days"),
      payment_terms: val("hr_payment_terms") || state.payment_terms || "",
      shipping_terms: val("hr_shipping_terms"),
    };
    var vqty = num("deal_volume_qty");
    var vprice = num("deal_volume_price");
    if (vqty !== null && vprice !== null) {
      deal.volume_tiers = [{ tier_qty: vqty, price: vprice }];
    }

    var payload = {
      company: {
        name: val("company_name"),
        website: val("company_website"),
        location: val("company_location"),
        timezone: val("company_timezone"),
        languages: splitList("company_languages"),
        sales_hours: val("company_sales_hours"),
      },
      deal: deal,
      hard_rules: {
        forbidden_terms: splitList("hr_forbidden_terms"),
        walk_away_price: null,
        require_approval_below: num("hr_require_approval_below"),
        transfer_deals_above: num("hr_transfer_deals_above"),
        escalation_triggers: collectTriggers(),
        always_propose_next_step: true,
      },
      voice: {
        agent_name: val("voice_agent_name"),
        phone: val("voice_phone"),
        voice_style: state.voice_style,
        conversation_style: val("voice_conversation_style"),
        elevenlabs_agent_id: null,
      },
      questions: state.questions,
      source: "pdf",
      confirm: !!confirm,
    };
    return payload;
  }

  // ── Confirm errors banner ────────────────────────────────────────────
  function showErrors(errors) {
    var box = $("confirm-errors");
    var list = $("confirm-errors-list");
    list.innerHTML = "";
    if (!errors || !errors.length) {
      box.classList.remove("show");
      return;
    }
    errors.forEach(function (e) {
      var li = document.createElement("li");
      li.textContent = e;
      list.appendChild(li);
    });
    box.classList.add("show");
  }

  // ── Step 5: preview (confirm:false) ──────────────────────────────────
  function previewSpec() {
    fetch("/api/intake/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload(false)),
    })
      .then(function (r) { return r.json().then(function (d) { return d; }); })
      .then(function (data) { showErrors(data.errors); })
      .catch(function () { /* preview is best-effort */ });
  }

  // ── Step 5: save (confirm:true) ──────────────────────────────────────
  function launch() {
    var btn = $("launch");
    btn.disabled = true;
    btn.textContent = "Saving…";
    fetch("/api/intake/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildPayload(true)),
    })
      .then(function (r) {
        return r.json().then(function (d) { return { status: r.status, data: d }; });
      })
      .then(function (res) {
        btn.disabled = false;
        btn.textContent = "Save & launch agent";
        if (res.status === 422 || res.data.ok === false) {
          showErrors(res.data.errors && res.data.errors.length ? res.data.errors : ["Could not save. Please review your entries."]);
          $("success-panel").classList.remove("show");
          window.scrollTo({ top: 0, behavior: "smooth" });
          return;
        }
        // success
        showErrors([]);
        var panel = $("success-panel");
        $("success-path").textContent = res.data.path ? "Saved to " + res.data.path : "Saved";
        $("success-json").textContent = JSON.stringify(res.data.spec, null, 2);
        panel.classList.add("show");
        btn.textContent = "Launched ✓";
        state.completed[3] = true;
        updateProgress();
        updateChecklist();
        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
        // Cool transition into the dashboard.
        setTimeout(function () {
          var t = $("launch-transition");
          t.classList.add("show");
          setTimeout(function () { window.location.href = "/dashboard"; }, 2100);
        }, 700);
      })
      .catch(function (e) {
        btn.disabled = false;
        btn.textContent = "Save & launch agent";
        showErrors(["Network error: " + e.message]);
      });
  }

  // ── Wire everything ──────────────────────────────────────────────────
  function init() {
    // Back / Next buttons
    document.querySelectorAll("[data-next]").forEach(function (b) {
      b.addEventListener("click", function () {
        gotoStep(Number(b.getAttribute("data-next")));
      });
    });

    // Checklist navigation
    document.querySelectorAll(".fg-check-item").forEach(function (it) {
      it.addEventListener("click", function () {
        gotoStep(Number(it.getAttribute("data-step")));
      });
    });

    wireUpload();
    wireVoiceCards();

    // Live locked banner + approval seed as floor changes
    var floorEl = $("deal_floor_price");
    if (floorEl) {
      floorEl.addEventListener("input", function () {
        refreshLockedBanner();
        if (val("hr_require_approval_below") === "") {
          setVal("hr_require_approval_below", val("deal_floor_price"));
        }
      });
    }

    // Launch (final step)
    $("launch").addEventListener("click", launch);

    // Start
    showStep(1);
    state.completed[1] = true;
    updateChecklist();
    updateProgress();
    refreshLockedBanner();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
