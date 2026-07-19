/* Lowball — Overview dashboard. Vanilla JS.
   Renders from /api/sessions; replay POSTs /api/refresh. */
(function () {
  "use strict";

  var BADGE_MAP = { hard_haggler: "badge--hard", responsive: "badge--responsive", goes_silent: "badge--silent" };
  var PILL_MAP = { won: "pill--won", active: "pill--active", "needs-human": "pill--needs-human" };
  var state = { customers: [] };

  // ---- helpers ------------------------------------------------------------
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function fx(n, d) { var v = Number(n); return isNaN(v) ? "—" : v.toFixed(d == null ? 2 : d); }
  function pct(n) { var v = Number(n); return isNaN(v) ? 0 : Math.max(0, Math.min(100, v * 100)); }
  function isNeedsHuman(c) { return c && (c.status === "needs-human" || c.escalate_flag === true); }
  function units(product) { var m = String(product || "").match(/·\s*([\d.]+k?\s*units)/i); return m ? m[1] : "—"; }
  function buyerOffer(c) {
    var last = null, ev = c.events || [];
    for (var i = 0; i < ev.length; i++) if (ev[i].speaker === "customer" && ev[i].counter_price != null) last = ev[i].counter_price;
    return last;
  }
  function greeting() {
    var h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }

  // ---- mode tag -----------------------------------------------------------
  function renderModeTag(data) {
    var tag = document.getElementById("mode-tag");
    if (!tag) return;
    var mock = data.model_mode !== "live";
    tag.classList.toggle("mode-tag--mock", mock);
    tag.innerHTML = '<span class="mode-tag__dot"></span> ' + esc(mock ? "MOCK" : "LIVE · " + (data.model || "model"));
  }

  // ---- metrics ------------------------------------------------------------
  function renderMetrics(m) {
    m = m || {};
    var el = document.getElementById("metrics");
    if (!el) return;
    var total = m.total != null ? m.total : (state.customers.length || 0);
    var needs = m.needs_human || 0;
    var ofN = "of " + total + " accounts";
    function card(label, value, foot, alert) {
      return '<div class="mcard' + (alert ? " mcard--alert" : "") + '">' +
        '<div class="mcard__label">' + esc(label) + '</div>' +
        '<div class="mcard__value' + (alert ? " mcard__value--alert" : "") + '">' + value + '</div>' +
        '<div class="mcard__foot">' + esc(foot) + '</div></div>';
    }
    el.innerHTML =
      card("Active negotiations", (m.active_negotiations || 0), ofN) +
      card("Deals won", (m.deals_won || 0), ofN) +
      card("Avg price capture", fx(m.avg_price_capture, 2), "0–1 of floor→target") +
      card("Needs human", needs, ofN, needs > 0);
  }

  // ---- featured negotiation ----------------------------------------------
  function renderFeatured(customers) {
    var el = document.getElementById("feat");
    if (!el) return;
    var c = null, i;
    for (i = 0; i < customers.length; i++) if (customers[i].status === "active") { c = customers[i]; break; }
    if (!c) c = customers[0];
    if (!c) { el.innerHTML = '<div class="loading">No negotiations.</div>'; return; }

    var region = (c.memory && c.memory.region) || "";
    var offer = buyerOffer(c);
    var tactic = (c.memory && c.memory.winning_tactics && c.memory.winning_tactics[0]) || null;
    var strat = tactic ? (tactic.description || tactic.label)
      : ("Hold the floor at " + fx(c.floor, 2) + " and concede slowly toward target " + fx(c.target, 2) + ".");

    el.innerHTML =
      '<div class="feat__head"><span class="feat__tag">Ready for judge demo</span>' +
      '<a class="feat__start" href="/messaging?focus=' + encodeURIComponent(c.customer_id) + '">Start rehearsal →</a></div>' +
      '<div class="feat__name">' + esc(c.name) + '</div>' +
      '<div class="feat__meta">' + esc(c.label || c.style) + ' · ' + esc(region) + '</div>' +
      '<div class="feat__grid">' +
        cell("Discussing", esc(c.product.split("·")[0].trim())) +
        cell("Requested", esc(units(c.product))) +
        cell("Buyer offer", offer != null ? "$" + fx(offer, 2) : "—") +
        cell("Hard floor", "$" + fx(c.floor, 2) + " 🔒") +
      '</div>' +
      '<div class="feat__strat"><b>✦ Agent strategy</b><span>' + esc(strat) + '</span></div>';
  }
  function cell(k, v) { return '<div class="feat__cell"><div class="feat__k">' + esc(k) + '</div><div class="feat__v">' + v + '</div></div>'; }

  // ---- approval mini ------------------------------------------------------
  function renderApproval(customers) {
    var pending = customers.filter(isNeedsHuman);
    var countEl = document.getElementById("approve-count");
    var itemEl = document.getElementById("approve-item");
    var sideBadge = document.getElementById("side-approvals");
    var n = pending.length;

    if (countEl) countEl.textContent = n + " pending";
    if (sideBadge) { sideBadge.textContent = n; sideBadge.hidden = n === 0; }
    if (!itemEl) return;

    if (!n) {
      itemEl.innerHTML = '<div class="approve__empty">No requests waiting. Agent is clear.</div>';
      var btn = document.getElementById("approve-btn"); if (btn) btn.style.opacity = ".5";
      return;
    }
    var c = pending[0];
    var scores = (c.memory && c.memory.past_calls || []).map(function (p) { return fx(p.outcome_score, 2); });
    itemEl.innerHTML =
      '<div class="approve__item">' +
        '<div class="approve__cust">' + esc(c.name) + '</div>' +
        '<div class="approve__reason">' + esc(c.summary || "Declining outcomes — needs a human decision.") + '</div>' +
        '<div class="approve__conf">recent scores ' + (scores.join(" → ") || "—") + '</div>' +
      '</div>';
  }

  // ---- account cards ------------------------------------------------------
  function renderCards(customers) {
    var grid = document.getElementById("card-grid");
    if (!grid) return;
    if (!customers.length) { grid.innerHTML = '<div class="loading">No customers.</div>'; return; }
    grid.innerHTML = customers.map(cardHTML).join("");
  }
  function cardHTML(c) {
    var alert = isNeedsHuman(c);
    var w = pct(c.outcome_score);
    var fill = 'width:' + w + '%' + (alert ? ';background:var(--red)' : '');
    return '' +
      '<a class="acct' + (alert ? " acct--alert" : "") + '" href="#" data-id="' + esc(c.customer_id) + '" role="button">' +
        '<div class="acct__top"><div>' +
          '<div class="acct__name">' + esc(c.name) + '</div>' +
          '<div class="acct__region">' + esc((c.memory && c.memory.region) || "") + '</div>' +
        '</div><div class="acct__badges">' +
          '<span class="badge ' + (BADGE_MAP[c.style] || "") + '">' + esc(c.label || c.style || "") + '</span>' +
          '<span class="pill ' + (PILL_MAP[c.status] || "") + '">' + esc(c.status || "") + '</span>' +
        '</div></div>' +
        '<div class="acct__deal">' + esc(c.product) + '</div>' +
        '<div class="acct__row"><span>floor ' + fx(c.floor, 2) + ' ' + esc(c.currency || "") + '</span>' +
          '<span>target ' + fx(c.target, 2) + ' ' + esc(c.currency || "") + '</span></div>' +
        '<div class="acct__bar"><div class="acct__fill" style="' + fill + '"></div></div>' +
        '<div class="acct__foot"><span>score ' + fx(c.outcome_score, 2) + '</span>' +
          '<a class="acct__thread" href="/messaging?focus=' + encodeURIComponent(c.customer_id) + '" data-thread="1">View thread →</a></div>' +
      '</a>';
  }

  // ---- drawer -------------------------------------------------------------
  function openPanel(id) {
    var c = null, i;
    for (i = 0; i < state.customers.length; i++) if (state.customers[i].customer_id === id) { c = state.customers[i]; break; }
    if (!c) return;
    document.getElementById("panel-body").innerHTML = panelHTML(c);
    document.getElementById("panel").classList.add("open");
    document.getElementById("panel").setAttribute("aria-hidden", "false");
    document.getElementById("backdrop").classList.add("open");
  }
  function closePanel() {
    document.getElementById("panel").classList.remove("open");
    document.getElementById("panel").setAttribute("aria-hidden", "true");
    document.getElementById("backdrop").classList.remove("open");
  }
  function memrow(k, v) { return '<div class="memrow"><span class="memrow__k">' + esc(k) + '</span><span class="memrow__v">' + v + '</span></div>'; }
  function panelHTML(c) {
    var mem = c.memory || {};
    var flags = (mem.risk_flags && mem.risk_flags.length) ? mem.risk_flags.join(", ") : "none";
    var cur = c.currency || "";
    var html = '';
    html += '<p class="eyebrow">' + esc(mem.region || "") + '</p>';
    html += '<h1 class="h1" style="font-size:22px">' + esc(c.name) + '</h1>';
    html += '<p class="sub">' + esc(c.product) + '</p>';
    html += memrow("Style", esc(c.label || mem.style || c.style || ""));
    html += memrow("Region", esc(mem.region || ""));
    html += memrow("Risk flags", esc(flags));
    html += memrow("Floor / target", fx(c.floor, 2) + " / " + fx(c.target, 2) + " " + esc(cur));
    html += memrow("Latest score", fx(c.outcome_score, 2));
    var tactics = mem.winning_tactics || [];
    html += '<div class="section-head" style="margin:24px 0 6px"><div class="section-title">Tactics that worked</div></div>';
    html += tactics.length ? tactics.map(function (t) {
      return '<div class="tactic"><span class="tactic__dot"></span><span>' + esc(t.label || t.pattern_id || "") +
        '</span><span class="tactic__src">' + esc(t.source || "") + '</span></div>';
    }).join("") : '<div class="tactic"><span>No tactics recorded.</span></div>';
    var calls = mem.past_calls || [];
    html += '<div class="section-head" style="margin:24px 0 6px"><div class="section-title">Past calls</div></div>';
    html += calls.length ? calls.map(function (p) {
      var sc = Number(p.outcome_score), chip = sc < 0.4 ? "score-chip--lo" : "score-chip--hi";
      return '<div class="callitem' + (sc < 0.5 ? " callitem--decline" : "") + '"><div class="callitem__meta">' +
        '<span>' + esc(String(p.ts || "").slice(0, 10)) + '</span><span class="score-chip ' + chip + '">' + fx(p.outcome_score, 2) +
        '</span></div><div class="callitem__summary">' + esc(p.summary || "") + '</div></div>';
    }).join("") : '<div class="callitem"><div class="callitem__summary">No prior calls.</div></div>';
    return html;
  }

  // ---- render root --------------------------------------------------------
  function render(data) {
    state.customers = data.customers || [];
    var g = document.getElementById("greet"); if (g) g.textContent = greeting() + ", Aryan.";
    renderModeTag(data);
    renderMetrics(data.metrics);
    renderFeatured(state.customers);
    renderApproval(state.customers);
    renderCards(state.customers);
  }

  // ---- data ---------------------------------------------------------------
  function load() {
    fetch("/api/sessions").then(function (r) { return r.json(); }).then(render).catch(function (e) {
      var grid = document.getElementById("card-grid");
      if (grid) grid.innerHTML = '<div class="loading">Failed to load: ' + esc(e.message) + '</div>';
    });
  }
  function replay(btn) {
    if (btn) btn.disabled = true;
    fetch("/api/refresh", { method: "POST" }).then(function (r) { return r.json(); })
      .then(render).catch(function () {}).then(function () { if (btn) btn.disabled = false; });
  }

  // ---- events -------------------------------------------------------------
  function init() {
    ["replay-btn", "replay-btn2", "judge-btn"].forEach(function (id) {
      var b = document.getElementById(id);
      if (b) b.addEventListener("click", function () { replay(b); });
    });
    var grid = document.getElementById("card-grid");
    if (grid) grid.addEventListener("click", function (ev) {
      if (ev.target.closest("[data-thread]")) return;
      var card = ev.target.closest(".acct");
      if (!card) return;
      ev.preventDefault();
      openPanel(card.getAttribute("data-id"));
    });
    document.getElementById("panel-close").addEventListener("click", closePanel);
    document.getElementById("backdrop").addEventListener("click", closePanel);
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") closePanel(); });
    load();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
