/* Lowball — automated Judge Demo tour.
   One click walks judges through the whole product: agent setup wizard →
   Overview → Live demo (agent greets) → Negotiations → Ask agent → Memory
   (3D graph spins) → Approvals → wrap-up. State lives in localStorage so the
   tour survives page navigations. No manual clicks needed. */
(function () {
  "use strict";

  // inject styling for the flashing buttons + tour banner (works on every page)
  (function injectCSS() {
    var s = document.createElement("style");
    s.textContent =
      "@keyframes jbPulse{0%,100%{box-shadow:0 0 0 0 rgba(30,212,123,.55)}50%{box-shadow:0 0 24px 5px rgba(30,212,123,.7)}}" +
      ".btn--flash,.fg-judge{animation:jbPulse 1.5s ease-in-out infinite}" +
      ".fg-judge{background:#0E8C4E;color:#fff;border:none;border-radius:10px;padding:9px 16px;font-weight:700;font-size:13.5px;cursor:pointer;font-family:inherit}" +
      ".fg-judge:hover{filter:brightness(1.08)}" +
      "#judge-banner{position:fixed;top:0;left:0;right:0;z-index:99999;display:flex;align-items:center;gap:14px;padding:9px 18px;background:linear-gradient(90deg,#0B1C13,#0E2A1B);border-bottom:1px solid rgba(30,212,123,.4);color:#EAF4EC;font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:13px;box-shadow:0 6px 20px rgba(0,0,0,.4)}" +
      "#judge-banner .jb__dot{width:9px;height:9px;border-radius:50%;background:#1ED47B;box-shadow:0 0 10px #1ED47B;animation:jbPulse 1.2s infinite}" +
      "#judge-banner .jb__label b{color:#1ED47B}" +
      "#judge-banner .jb__prog{flex:1;max-width:280px;height:5px;border-radius:100px;background:rgba(255,255,255,.12);overflow:hidden}" +
      "#judge-banner .jb__fill{height:100%;background:#1ED47B;box-shadow:0 0 10px #1ED47B;transition:width .5s ease;width:0}" +
      "#judge-banner .jb__stop{margin-left:auto;background:transparent;border:1px solid rgba(255,255,255,.25);color:#EAF4EC;border-radius:8px;padding:5px 12px;cursor:pointer;font-family:inherit;font-size:12px}" +
      "#judge-banner.jb--done{border-color:#1ED47B}" +
      "body.judge-touring{padding-top:40px}";
    (document.head || document.documentElement).appendChild(s);
  })();

  var KEY = "lowballJudgeTour";
  var STEPS = [
    { route: "/",           name: "Agent setup" },
    { route: "/dashboard",  name: "Overview" },
    { route: "/call",       name: "Live demo" },
    { route: "/messaging",  name: "Negotiations" },
    { route: "/chat",       name: "Ask agent" },
    { route: "/graph",      name: "Memory" },
    { route: "/approval",   name: "Approvals" },
    { route: "/dashboard",  name: "Wrap up" },
  ];

  function get() { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; } }
  function set(v) { localStorage.setItem(KEY, JSON.stringify(v)); }
  function clear() { localStorage.removeItem(KEY); }
  function pathIs(route) { var p = location.pathname; return p === route || (route === "/" && p === "/intake"); }

  // exposed to the "Judges — run demo" buttons
  window.startJudgeTour = function () {
    set({ active: true, step: 0 });
    try { fetch("/api/sessions"); } catch (e) {} // start warming the negotiation cache now
    if (pathIs("/")) drive(); else location.href = "/";
  };
  window.stopJudgeTour = function () { clear(); location.href = "/dashboard"; };

  // ---- banner --------------------------------------------------------------
  function banner(name, idx, total, done) {
    var b = document.getElementById("judge-banner");
    if (!b) {
      b = document.createElement("div");
      b.id = "judge-banner";
      b.innerHTML =
        '<div class="jb__dot"></div>' +
        '<div class="jb__label"><b>Judge demo</b> · <span id="jb-step"></span></div>' +
        '<div class="jb__prog"><div class="jb__fill" id="jb-fill"></div></div>' +
        '<button class="jb__stop" onclick="stopJudgeTour()">✕ Stop</button>';
      document.body.appendChild(b);
    }
    document.body.classList.add("judge-touring");
    document.getElementById("jb-step").textContent = done ? name : name + "  (" + (idx + 1) + "/" + total + ")";
    document.getElementById("jb-fill").style.width = ((idx + 1) / total * 100) + "%";
    if (done) b.classList.add("jb--done");
  }

  // ---- helpers -------------------------------------------------------------
  function click(sel) { var e = document.querySelector(sel); if (e) e.click(); return !!e; }
  function pause(ms, next) { setTimeout(next, ms); }
  function advance(cur) {
    var n = cur + 1;
    if (n >= STEPS.length) return;
    set({ active: true, step: n });
    setTimeout(function () { location.href = STEPS[n].route; }, 400);
  }

  // ---- per-page actions ----------------------------------------------------
  function intakeWalk() {
    // click through Company → Catalog → Guardrails, then launch (redirects)
    setTimeout(function () { click('[data-next="2"]'); }, 1600);
    setTimeout(function () { click('[data-next="3"]'); }, 3600);
    setTimeout(function () {
      set({ active: true, step: 1 });     // pre-advance so /dashboard matches on load
      if (!click('#launch')) location.href = "/dashboard";
    }, 5600);
  }

  function liveDemo(done) {
    // best-effort: make the agent greet the judges (needs mic + public agent)
    try {
      if (typeof window.startTourCall === "function") {
        window.startTourCall("Hi judges! This is our live voice demo of Lowball. I negotiate deals for manufacturers, and I remember every customer.");
      }
    } catch (e) { /* non-fatal */ }
    pause(13000, done);
  }

  function askAgent(done) {
    var inp = document.getElementById("chat-input");
    var send = document.getElementById("chat-send");
    if (inp && send) {
      inp.value = "Which customer is most at risk right now, and what should we do about it?";
      send.click();
    }
    pause(9000, done);
  }

  function spinGraph(done) {
    var tries = 0;
    (function enable() {
      var g = window.__lowballGraph;
      if (g && g.controls) {
        var c = g.controls();
        c.autoRotate = true;
        c.autoRotateSpeed = 2.4;
      } else if (tries++ < 20) { return void setTimeout(enable, 300); }
      pause(8500, done);
    })();
  }

  function wrapUp() {
    banner("Demo complete ✓", STEPS.length - 1, STEPS.length, true);
    setTimeout(clear, 6000);
  }

  function runAction(i, done) {
    switch (STEPS[i].name) {
      case "Agent setup": return intakeWalk();
      case "Live demo": return liveDemo(done);
      case "Ask agent": return askAgent(done);
      case "Memory": return spinGraph(done);
      case "Wrap up": return wrapUp();
      default: return pause(7500, done); // Overview, Negotiations, Approvals
    }
  }

  // ---- driver --------------------------------------------------------------
  function drive() {
    var st = get();
    if (!st || !st.active) return;
    var step = STEPS[st.step];
    if (!pathIs(step.route)) { location.href = step.route; return; }
    banner(step.name, st.step, STEPS.length, false);
    runAction(st.step, function () { advance(st.step); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", drive);
  else drive();
})();
