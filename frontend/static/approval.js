/* Lowball — Approvals page. Reads /api/sessions, surfaces escalated deals as
   human-decision requests. Approve/Reject resolve client-side (demo). */
(function () {
  "use strict";

  var TRIGGERS = [
    { ic: "💵", t: "Price below floor", d: "Buyer pushes under the hard floor price." },
    { ic: "📦", t: "Order over limit", d: "Total value exceeds the auto-transfer threshold." },
    { ic: "🙋", t: "Angry / wants manager", d: "Buyer escalates or asks for a human." },
    { ic: "🧩", t: "Unsupported custom", d: "Request outside the agreed spec." },
  ];

  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function fx(n) { var v = Number(n); return isNaN(v) ? "—" : v.toFixed(2); }
  function isNeedsHuman(c) { return c && (c.status === "needs-human" || c.escalate_flag === true); }

  function renderMode(data) {
    var tag = document.getElementById("mode-tag");
    if (!tag) return;
    var mock = data.model_mode !== "live";
    tag.classList.toggle("mode-tag--mock", mock);
    tag.innerHTML = '<span class="mode-tag__dot"></span> ' + esc(mock ? "MOCK" : "LIVE · " + (data.model || "model"));
  }

  function renderTriggers() {
    var el = document.getElementById("apv-triggers");
    if (!el) return;
    el.innerHTML = TRIGGERS.map(function (t) {
      return '<div class="apv-trigger"><div class="apv-trigger__ic">' + t.ic + '</div>' +
        '<div class="apv-trigger__t">' + esc(t.t) + '</div>' +
        '<div class="apv-trigger__d">' + esc(t.d) + '</div></div>';
    }).join("");
  }

  function tag(txt, flag) { return '<span class="apv__tag' + (flag ? " apv__tag--flag" : "") + '">' + esc(txt) + '</span>'; }

  function requestHTML(c) {
    var mem = c.memory || {};
    var scores = (mem.past_calls || []).map(function (p) { return fx(p.outcome_score); }).join(" → ");
    var flags = (mem.risk_flags || []);
    return '<div class="apv" data-id="' + esc(c.customer_id) + '">' +
      '<div><div class="apv__cust">' + esc(c.name) + '</div>' +
        '<div class="apv__meta">' + esc(c.label || c.style) + ' · ' + esc(mem.region || "") + ' · ' + esc(c.product) + '</div>' +
        '<div class="apv__reason">' + esc(c.summary || "Declining outcomes across recent calls — agent confidence low, needs a human decision.") + '</div>' +
        '<div class="apv__tags">' +
          tag("declining outcomes", true) +
          (scores ? tag("scores " + scores) : "") +
          tag("floor $" + fx(c.floor)) +
          flags.map(function (f) { return tag(f, true); }).join("") +
        '</div></div>' +
      '<div class="apv__actions">' +
        '<button class="apv__btn apv__btn--approve" data-act="approve">Approve override</button>' +
        '<button class="apv__btn apv__btn--reject" data-act="reject">Hold / decline</button>' +
      '</div></div>';
  }

  function refreshCount() {
    var open = document.querySelectorAll(".apv:not(.apv--resolved)").length;
    var countEl = document.getElementById("apv-count");
    if (countEl) countEl.textContent = open + (open === 1 ? " request" : " requests");
    var side = document.getElementById("side-approvals");
    if (side) { side.textContent = open; side.hidden = open === 0; }
    var list = document.getElementById("apv-list");
    if (open === 0 && list && !list.querySelector(".apv-empty")) {
      var done = document.createElement("div");
      done.className = "apv-empty";
      done.innerHTML = '<div class="apv-empty__ic">✓</div><div class="apv-empty__t">Queue clear</div>' +
        '<div>Every escalation has a human decision.</div>';
      list.appendChild(done);
    }
  }

  function resolve(card, act) {
    card.classList.add("apv--resolved");
    var actions = card.querySelector(".apv__actions");
    var ok = act === "approve";
    actions.outerHTML = '<div class="apv__resolved ' + (ok ? "apv__resolved--ok" : "apv__resolved--no") + '">' +
      (ok ? "✓ Override approved" : "✕ Held for review") + '</div>';
    refreshCount();
  }

  function render(data) {
    renderMode(data);
    renderTriggers();
    var pending = (data.customers || []).filter(isNeedsHuman);
    var list = document.getElementById("apv-list");
    if (!list) return;
    if (!pending.length) {
      list.innerHTML = '<div class="apv-empty"><div class="apv-empty__ic">✓</div>' +
        '<div class="apv-empty__t">Queue clear</div><div>No escalations waiting on a human.</div></div>';
    } else {
      list.innerHTML = pending.map(requestHTML).join("");
    }
    refreshCount();
    list.addEventListener("click", function (ev) {
      var btn = ev.target.closest(".apv__btn");
      if (!btn) return;
      resolve(btn.closest(".apv"), btn.getAttribute("data-act"));
    });
  }

  fetch("/api/sessions").then(function (r) { return r.json(); }).then(render).catch(function (e) {
    var list = document.getElementById("apv-list");
    if (list) list.innerHTML = '<div class="loading">Failed to load: ' + esc(e.message) + '</div>';
  });
})();
