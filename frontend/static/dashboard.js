/* Manufacturer negotiation dashboard — Sales Desk view.
   Vanilla JS. Renders from /api/sessions; replay POSTs /api/refresh. */
(function () {
  "use strict";

  var BADGE_MAP = {
    hard_haggler: "badge--hard",
    responsive: "badge--responsive",
    goes_silent: "badge--silent"
  };
  var PILL_MAP = {
    won: "pill--won",
    active: "pill--active",
    "needs-human": "pill--needs-human"
  };

  var state = { customers: [] };

  // ---- helpers ------------------------------------------------------------
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  function fx(n, d) {
    var v = Number(n);
    if (isNaN(v)) return "—";
    return v.toFixed(d == null ? 2 : d);
  }
  function pct(n) {
    var v = Number(n);
    if (isNaN(v)) return 0;
    return Math.max(0, Math.min(100, v * 100));
  }
  function isNeedsHuman(c) {
    return c && (c.status === "needs-human" || c.escalate_flag === true);
  }

  // ---- mode tag -----------------------------------------------------------
  function renderModeTag(data) {
    var tag = document.getElementById("mode-tag");
    if (!tag) return;
    var mock = data.model_mode !== "live";
    tag.classList.toggle("mode-tag--mock", mock);
    var label = mock ? "MOCK" : "LIVE · " + (data.model || "model");
    tag.innerHTML = '<span class="mode-tag__dot"></span> ' + esc(label);
  }

  // ---- metrics ------------------------------------------------------------
  function renderMetrics(m) {
    m = m || {};
    var total = m.total != null ? m.total : (state.customers.length || 0);
    var needs = m.needs_human || 0;
    var el = document.getElementById("metrics");
    if (!el) return;

    function tile(label, value, foot, extraTile, extraVal) {
      return '' +
        '<div class="tile' + (extraTile ? " " + extraTile : "") + '">' +
        '<div class="tile__label">' + esc(label) + '</div>' +
        '<div class="tile__value mono' + (extraVal ? " " + extraVal : "") + '">' + value + '</div>' +
        '<div class="tile__foot">' + esc(foot) + '</div>' +
        '</div>';
    }

    var ofN = "of " + total + " accounts";
    var html = "";
    html += tile("Active negotiations", (m.active_negotiations || 0), ofN, "tile--neutral");
    html += tile("Deals won", (m.deals_won || 0), ofN);
    html += tile("Avg price capture", fx(m.avg_price_capture, 2), "0–1 of floor→target");
    html += tile("Needs human", needs, ofN,
      needs > 0 ? "tile--alert" : "tile--neutral",
      needs > 0 ? "tile__value--alert" : "");
    el.innerHTML = html;
  }

  // ---- cards --------------------------------------------------------------
  function renderCards(customers) {
    var grid = document.getElementById("card-grid");
    if (!grid) return;
    if (!customers || !customers.length) {
      grid.innerHTML = '<div class="loading">No customers.</div>';
      return;
    }
    grid.innerHTML = customers.map(cardHTML).join("");
  }

  function cardHTML(c) {
    var badgeClass = BADGE_MAP[c.style] || "";
    var pillClass = PILL_MAP[c.status] || "";
    var alert = isNeedsHuman(c);
    var w = pct(c.outcome_score);
    var fillStyle = 'width:' + w + '%';
    // Documented exception: red fill for needs-human only.
    if (alert) fillStyle += ';background:var(--red)';

    return '' +
      '<article class="card' + (alert ? " card--alert" : "") + '" ' +
        'data-id="' + esc(c.customer_id) + '" role="button" tabindex="0">' +
        '<div class="card__top">' +
          '<div>' +
            '<div class="card__name">' + esc(c.name) + '</div>' +
            '<div class="card__region">' + esc((c.memory && c.memory.region) || "") + '</div>' +
          '</div>' +
          '<div class="card__row" style="margin-top:0;gap:8px">' +
            '<span class="badge ' + badgeClass + '">' + esc(c.label || c.style || "") + '</span>' +
            '<span class="pill ' + pillClass + '">' + esc(c.status || "") + '</span>' +
          '</div>' +
        '</div>' +
        '<div class="card__deal">' + esc(c.product) + '</div>' +
        '<div class="card__row">' +
          '<span class="card__meta">floor ' + fx(c.floor, 2) + ' ' + esc(c.currency || "") + '</span>' +
          '<span class="card__meta">target ' + fx(c.target, 2) + ' ' + esc(c.currency || "") + '</span>' +
        '</div>' +
        '<div class="card__scorebar"><div class="card__scorefill" style="' + fillStyle + '"></div></div>' +
        '<div class="card__row">' +
          '<span class="card__meta">score ' + fx(c.outcome_score, 2) + '</span>' +
          '<a class="card__meta" href="/messaging?focus=' + encodeURIComponent(c.customer_id) + '" ' +
            'data-thread="1">View thread →</a>' +
        '</div>' +
      '</article>';
  }

  // ---- drawer -------------------------------------------------------------
  function openPanel(id) {
    var c = null;
    for (var i = 0; i < state.customers.length; i++) {
      if (state.customers[i].customer_id === id) { c = state.customers[i]; break; }
    }
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

  function memrow(k, v) {
    return '<div class="memrow"><span class="memrow__k">' + esc(k) +
      '</span><span class="memrow__v">' + v + '</span></div>';
  }

  function panelHTML(c) {
    var mem = c.memory || {};
    var flags = (mem.risk_flags && mem.risk_flags.length) ? mem.risk_flags.join(", ") : "none";
    var cur = c.currency || "";

    var html = "";
    html += '<p class="eyebrow">' + esc(mem.region || "") + '</p>';
    html += '<h1 class="h1" style="font-size:22px">' + esc(c.name) + '</h1>';
    html += '<p class="sub">' + esc(c.product) + '</p>';

    html += memrow("Style", esc(c.label || mem.style || c.style || ""));
    html += memrow("Region", esc(mem.region || ""));
    html += memrow("Risk flags", esc(flags));
    html += memrow("Floor / target", fx(c.floor, 2) + " / " + fx(c.target, 2) + " " + esc(cur));
    html += memrow("Latest score", fx(c.outcome_score, 2));

    // Tactics that worked
    var tactics = mem.winning_tactics || [];
    html += '<div class="section-head" style="margin:24px 0 6px">' +
      '<div class="section-title">Tactics that worked</div></div>';
    if (tactics.length) {
      html += tactics.map(function (t) {
        return '<div class="tactic">' +
          '<span class="tactic__dot"></span>' +
          '<span>' + esc(t.label || t.pattern_id || "") + '</span>' +
          '<span class="tactic__src">' + esc(t.source || "") + '</span>' +
          '</div>';
      }).join("");
    } else {
      html += '<div class="tactic"><span>No tactics recorded.</span></div>';
    }

    // Past calls (newest first, as provided)
    var calls = mem.past_calls || [];
    html += '<div class="section-head" style="margin:24px 0 6px">' +
      '<div class="section-title">Past calls</div></div>';
    if (calls.length) {
      html += calls.map(function (p) {
        var sc = Number(p.outcome_score);
        var chipCls = sc < 0.4 ? "score-chip--lo" : "score-chip--hi";
        var declineCls = sc < 0.5 ? " callitem--decline" : "";
        var ts = String(p.ts || "").slice(0, 10);
        return '<div class="callitem' + declineCls + '">' +
          '<div class="callitem__meta">' +
            '<span>' + esc(ts) + '</span>' +
            '<span class="score-chip ' + chipCls + '">' + fx(p.outcome_score, 2) + '</span>' +
          '</div>' +
          '<div class="callitem__summary">' + esc(p.summary || "") + '</div>' +
          '</div>';
      }).join("");
    } else {
      html += '<div class="callitem"><div class="callitem__summary">No prior calls.</div></div>';
    }

    return html;
  }

  // ---- render root --------------------------------------------------------
  function render(data) {
    state.customers = data.customers || [];
    renderModeTag(data);
    renderMetrics(data.metrics);
    renderCards(state.customers);
  }

  // ---- data ---------------------------------------------------------------
  function load() {
    fetch("/api/sessions")
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function (e) {
        var grid = document.getElementById("card-grid");
        if (grid) grid.innerHTML = '<div class="loading">Failed to load: ' + esc(e.message) + '</div>';
      });
  }

  function replay() {
    var btn = document.getElementById("replay-btn");
    if (btn) btn.disabled = true;
    fetch("/api/refresh", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(render)
      .catch(function () {})
      .then(function () { if (btn) btn.disabled = false; });
  }

  // ---- events -------------------------------------------------------------
  function init() {
    var replayBtn = document.getElementById("replay-btn");
    if (replayBtn) replayBtn.addEventListener("click", replay);

    var grid = document.getElementById("card-grid");
    if (grid) grid.addEventListener("click", function (ev) {
      var thread = ev.target.closest("[data-thread]");
      if (thread) return; // let the "View thread →" link navigate normally
      var card = ev.target.closest(".card");
      if (!card) return;
      ev.preventDefault();
      openPanel(card.getAttribute("data-id"));
    });
    if (grid) grid.addEventListener("keydown", function (ev) {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      var card = ev.target.closest(".card");
      if (!card) return;
      ev.preventDefault();
      openPanel(card.getAttribute("data-id"));
    });

    document.getElementById("panel-close").addEventListener("click", closePanel);
    document.getElementById("backdrop").addEventListener("click", closePanel);
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") closePanel();
    });

    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
