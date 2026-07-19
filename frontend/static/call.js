(function () {
  "use strict";
  var events = [
    { who: "system", text: "Buyer matched to West Coast Goods. Previous sample request and price sensitivity loaded from Kuzu memory." },
    { who: "agent", name: "Alex", text: "Hi Maya, I’m Alex, Nova Manufacturing’s AI sales assistant. I can help with product details and authorized pricing. What are you sourcing today?", reason: "Disclose AI identity, confirm intent, and keep private guardrails hidden." },
    { who: "buyer", name: "Maya", text: "I need 2,000 custom 500 ml stainless-steel bottles shipped to Los Angeles. What’s your best price?" },
    { who: "agent", name: "Alex", text: "For 2,000 units with custom printing and inspection, our opening price is $5.20 per unit. Is your 25-day timeline firm?", reason: "Open at the approved price and qualify the timeline before conceding." },
    { who: "buyer", name: "Maya", text: "Twenty-five days works, but another supplier quoted $4.20. Can you match it?" },
    { who: "agent", name: "Alex", text: "I can’t match $4.20 for 2,000 units. If you increase to 5,000, I’m authorized to offer $4.60 with the same 25-day lead time.", reason: "Reject the sub-floor request and trade price only for approved volume." },
    { who: "buyer", name: "Maya", text: "We can do 5,000 if the sample passes our inspection." },
    { who: "agent", name: "Alex", text: "Agreed: 5,000 units at $4.60, pending sample approval, with a 25-day lead time. I’ll send the paid sample request today.", reason: "Confirm every term and leave a concrete next step." }
  ];
  var index = 0, running = false, soundOn = true, timer = null;
  var $ = function (id) { return document.getElementById(id); };
  function speak(ev) {
    if (!soundOn || ev.who === "system" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(ev.text);
    utterance.pitch = ev.who === "buyer" ? 1.12 : 0.88;
    utterance.rate = 1.03;
    window.speechSynthesis.speak(utterance);
  }
  function renderEvent(ev) {
    var node = document.createElement(ev.who === "system" ? "p" : "article");
    node.className = "call-event call-event--" + ev.who;
    if (ev.who === "system") node.textContent = "✦ " + ev.text;
    else {
      var who = document.createElement("div"); who.className = "call-event__who"; who.textContent = ev.name + " · " + (ev.who === "agent" ? "NOVA AI AGENT" : "BUYER");
      var text = document.createElement("p"); text.textContent = ev.text;
      node.appendChild(who); node.appendChild(text);
      if (ev.reason) { var reason = document.createElement("small"); reason.textContent = "✦ AGENT REASONING · " + ev.reason; node.appendChild(reason); }
    }
    $("transcript").appendChild(node);
    node.scrollIntoView({ behavior: "smooth", block: "nearest" });
    speak(ev);
  }
  function step() {
    if (!running) return;
    if (index >= events.length) { finish("complete"); return; }
    var ev = events[index++]; renderEvent(ev);
    var pct = Math.round(index / events.length * 100);
    $("fact-progress").textContent = pct + "% complete";
    $("fact-status").textContent = ev.who === "buyer" ? "Buyer speaking" : ev.who === "agent" ? "Agent speaking" : "Memory loaded";
    $("speaker-state").textContent = ev.who === "system" ? "Preparing" : ev.name + " speaking";
    if (index >= 7) { $("fact-quantity").textContent = "5,000 units"; $("current-offer").textContent = "$4.60"; }
    timer = window.setTimeout(step, ev.who === "system" ? 1100 : 3200);
  }
  function start() {
    if (running) return;
    running = true; index = 0; $("call-empty").remove(); $("call-result").hidden = true;
    $("call-title").textContent = "Call in progress"; $("call-state").classList.add("live"); $("call-state").innerHTML = "<i></i> LIVE · REHEARSAL";
    $("handoff").disabled = false; $("end-call").disabled = false; step();
  }
  function finish(outcome) {
    running = false; window.clearTimeout(timer); if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    var completed = outcome === "complete";
    $("call-title").textContent = completed ? "Call complete" : outcome === "handoff" ? "Handed to a human" : "Call ended";
    $("call-state").classList.remove("live"); $("call-state").innerHTML = "<i></i> " + (completed ? "SAVED" : outcome === "handoff" ? "HANDED OFF" : "ENDED");
    $("fact-status").textContent = completed ? "Sample pending" : outcome === "handoff" ? "Human handoff" : "Ended early";
    if (completed) { $("fact-progress").textContent = "100% complete"; $("fact-quantity").textContent = "5,000 units"; $("current-offer").textContent = "$4.60"; }
    $("speaker-state").textContent = completed ? "Structured outcome saved" : "No outcome saved";
    $("handoff").disabled = true; $("end-call").disabled = true; $("call-result").hidden = !completed;
    if (completed) $("call-result").scrollIntoView({behavior:"smooth",block:"start"});
  }
  document.addEventListener("DOMContentLoaded", function () {
    $("start-call").addEventListener("click", start); $("end-call").addEventListener("click", function () { finish("ended"); });
    $("handoff").addEventListener("click", function () { finish("handoff"); });
    $("sound-toggle").addEventListener("click", function () { soundOn = !soundOn; this.textContent = soundOn ? "◕ Sound on" : "○ Sound off"; if (!soundOn && "speechSynthesis" in window) window.speechSynthesis.cancel(); });
  });
})();
