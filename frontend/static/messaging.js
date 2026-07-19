/* Messaging view — turn-by-turn negotiation console.
   Reads the shared snapshot from /api/sessions and renders one .thread per
   customer. The reasoning under each agent bubble is the star. */

(function () {
  "use strict";

  var PRIMARY = ["cust_alpha", "cust_bravo", "cust_charlie"];
  var DELTA = "cust_delta";

  var STYLE_BADGE = {
    hard_haggler: "badge--hard",
    responsive: "badge--responsive",
    goes_silent: "badge--silent"
  };

  // ---- small helpers ------------------------------------------------------
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function focusedCustomer() {
    var params = new URLSearchParams(window.location.search);
    return params.get("focus");
  }

  // Turn "3.2" / 3.2 into a stable 2-decimal string for chips.
  function fmtPrice(v) {
    var n = Number(v);
    if (!isFinite(n)) return String(v);
    return n.toFixed(2);
  }

  // Shorten a guardrail string into a compact chip label.
  function guardrailLabel(raw) {
    if (/next step/i.test(raw)) return "next-step added";
    var m = raw.match(/clamped to floor/i);
    if (m) {
      var floor = raw.match(/floor\s+([\d.]+)/i);
      if (floor) return "floor clamp → " + floor[1];
      return "floor clamp";
    }
    // Fall back to stripping the GUARDRAIL: prefix.
    return raw.replace(/^GUARDRAIL:\s*/i, "").trim();
  }

  // ---- mode tag -----------------------------------------------------------
  function setModeTag(data) {
    var tag = document.getElementById("mode-tag");
    if (!tag) return;
    var mock = data.model_mode === "mock";
    tag.classList.toggle("mode-tag--mock", mock);
    var label = mock ? "MOCK" : "LIVE · " + (data.model || "");
    tag.innerHTML = "";
    tag.appendChild(el("span", "mode-tag__dot"));
    tag.appendChild(document.createTextNode(" " + label));
  }

  // ---- turn rendering -----------------------------------------------------
  function renderCustomerTurn(ev, i) {
    var turn = el("div", "turn turn--customer");
    turn.style.animationDelay = (i * 90) + "ms";

    var bubble = el("div", "bubble bubble--customer");
    bubble.appendChild(el("div", "bubble__who", "CUSTOMER"));
    bubble.appendChild(el("div", null, ev.message || ""));
    turn.appendChild(bubble);

    if (ev.counter_price != null) {
      var chips = el("div", "chips");
      chips.appendChild(el("span", "chip chip--counter", "counter " + fmtPrice(ev.counter_price)));
      turn.appendChild(chips);
    }
    return turn;
  }

  function renderAgentTurn(ev, i, currency) {
    var turn = el("div", "turn");
    turn.style.animationDelay = (i * 90) + "ms";

    var bubble = el("div", "bubble bubble--agent");
    bubble.appendChild(el("div", "bubble__who", "AGENT"));
    bubble.appendChild(el("div", null, ev.message || ""));
    turn.appendChild(bubble);

    if (ev.reasoning) {
      turn.appendChild(el("div", "reason", ev.reasoning));
    }

    var guardrails = ev.guardrails || [];
    if (ev.offer_price != null || guardrails.length) {
      var chips = el("div", "chips");
      if (ev.offer_price != null) {
        chips.appendChild(el("span", "chip chip--offer",
          "offer " + fmtPrice(ev.offer_price) + " " + (currency || "")));
      }
      guardrails.forEach(function (g) {
        chips.appendChild(el("span", "chip chip--guardrail", guardrailLabel(g)));
      });
      turn.appendChild(chips);
    }
    return turn;
  }

  // ---- thread rendering ---------------------------------------------------
  function renderThread(session, isFocus) {
    var thread = el("div", "thread");
    if (session.status === "needs-human") thread.classList.add("thread--alert");

    // head
    var head = el("div", "thread__head");
    var name = el("div", "thread__name");
    name.appendChild(document.createTextNode(session.name || ""));
    var badge = el("span", "badge " + (STYLE_BADGE[session.style] || ""),
      session.label || session.style || "");
    name.appendChild(badge);
    head.appendChild(name);

    var deal = el("div", "thread__deal",
      (session.product || "") + " · floor " + fmtPrice(session.floor) +
      " " + (session.currency || ""));
    head.appendChild(deal);
    thread.appendChild(head);

    // body — conversation
    var body = el("div", "thread__body");
    (session.events || []).forEach(function (ev, i) {
      if (ev.speaker === "customer") {
        body.appendChild(renderCustomerTurn(ev, i));
      } else {
        body.appendChild(renderAgentTurn(ev, i, session.currency));
      }
    });
    thread.appendChild(body);

    // escalation banner (Charlie)
    if (session.result === "escalated") {
      thread.classList.add("thread--alert");
      var banner = el("div", "escalation-banner");
      banner.appendChild(el("span", "escalation-banner__icon", "⚠"));
      banner.appendChild(document.createTextNode("Declining history — handed to a human."));
      thread.appendChild(banner);
    }

    // outcome strip
    var strip = el("div", "outcome-strip");
    strip.appendChild(el("span", "outcome-strip__label", "OUTCOME"));

    // Right side: plain result text + mono score (wrapper carries no class).
    var right = el("div", null);
    var parts = el("span", "mono");
    var resultTxt = session.result || "";
    if (session.agreed_price != null) {
      resultTxt += " · " + fmtPrice(session.agreed_price) + " " + (session.currency || "");
    }
    parts.textContent = resultTxt + "  ";
    right.appendChild(parts);

    var score = el("span", "outcome-strip__score",
      session.outcome_score != null ? fmtPrice(session.outcome_score) : "—");
    if (session.result === "closed") score.style.color = "var(--green-ink)";
    else if (session.result === "escalated") score.style.color = "var(--red)";
    right.appendChild(score);

    strip.appendChild(right);
    thread.appendChild(strip);

    if (isFocus) thread.dataset.focus = "true";
    return thread;
  }

  // ---- board render -------------------------------------------------------
  function render(data) {
    setModeTag(data);

    var board = document.getElementById("board");
    board.innerHTML = "";

    var byId = {};
    (data.customers || []).forEach(function (c) { byId[c.customer_id] = c; });

    var focus = focusedCustomer();
    var showDelta = focus === DELTA && byId[DELTA];

    var ids = PRIMARY.slice();
    if (showDelta) ids.push(DELTA);

    var focusNode = null;
    ids.forEach(function (id) {
      var session = byId[id];
      if (!session) return;
      var isFocus = showDelta && id === DELTA;
      var node = renderThread(session, isFocus);
      board.appendChild(node);
      if (isFocus) focusNode = node;
    });

    if (!board.children.length) {
      board.appendChild(el("div", "loading", "No negotiations to show."));
    }

    if (focusNode) {
      requestAnimationFrame(function () {
        focusNode.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }

  // ---- data ---------------------------------------------------------------
  function load(url, opts) {
    return fetch(url, opts).then(function (r) { return r.json(); });
  }

  function boot() {
    load("/api/sessions").then(render).catch(function () {
      var board = document.getElementById("board");
      if (board) board.innerHTML = '<div class="loading">Could not load negotiations.</div>';
    });

    var btn = document.getElementById("replay-btn");
    if (btn) {
      btn.addEventListener("click", function () {
        btn.disabled = true;
        var board = document.getElementById("board");
        if (board) board.innerHTML = '<div class="loading">Replaying round…</div>';
        load("/api/refresh", { method: "POST" })
          .then(render)
          .catch(function () {
            if (board) board.innerHTML = '<div class="loading">Replay failed.</div>';
          })
          .then(function () { btn.disabled = false; });
      });
    }
  }

  boot();
})();
