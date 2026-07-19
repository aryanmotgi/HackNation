/* Lowball — Memory Q&A chat. Ask the agent about customers, tactics, call
   history. POSTs /api/chat; answers come from the Kuzu memory + LLM. */
(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }

  async function setModeTag() {
    try {
      var s = await fetch("/api/sessions").then(function (r) { return r.json(); });
      var tag = $("mode-tag");
      if (!tag) return;
      if (s.model_mode === "live") {
        tag.innerHTML = '<span class="mode-tag__dot"></span> LIVE \xb7 ' + s.model;
      } else {
        tag.className = "mode-tag mode-tag--mock";
        tag.innerHTML = '<span class="mode-tag__dot"></span> MOCK';
      }
    } catch (e) { /* non-fatal */ }
  }

  function addBubble(who, text, source) {
    var thread = $("chat-thread");
    var isAgent = who === "agent";

    var turn = document.createElement("div");
    turn.className = "turn" + (isAgent ? "" : " turn--customer");

    var bubble = document.createElement("div");
    bubble.className = "bubble" + (isAgent ? " bubble--agent" : " bubble--customer");

    var whoEl = document.createElement("div");
    whoEl.className = "bubble__who";
    whoEl.textContent = isAgent ? "Lowball AI" : "You";
    bubble.appendChild(whoEl);

    var msg = document.createElement("div");
    msg.textContent = text;
    bubble.appendChild(msg);

    if (source) {
      var badge = document.createElement("span");
      badge.className = "chat-source mode-tag" + (source === "mock" ? " mode-tag--mock" : "");
      badge.innerHTML = '<span class="mode-tag__dot"></span> ' + (source === "mock" ? "MOCK" : "LIVE");
      bubble.appendChild(badge);
    }

    turn.appendChild(bubble);
    thread.appendChild(turn);
    thread.scrollTop = thread.scrollHeight;
    return turn;
  }

  function addTyping() {
    var thread = $("chat-thread");
    var turn = document.createElement("div");
    turn.className = "turn";
    turn.id = "chat-typing";

    var bubble = document.createElement("div");
    bubble.className = "bubble bubble--agent";
    var whoEl = document.createElement("div");
    whoEl.className = "bubble__who";
    whoEl.textContent = "Lowball AI";
    bubble.appendChild(whoEl);
    var dots = document.createElement("div");
    dots.className = "chat-typing";
    dots.textContent = "•••";
    bubble.appendChild(dots);
    turn.appendChild(bubble);
    thread.appendChild(turn);
    thread.scrollTop = thread.scrollHeight;
    return turn;
  }

  async function send() {
    var input = $("chat-input");
    var message = input.value.trim();
    if (!message) return;
    var customerId = $("customer-select").value || null;

    input.value = "";
    input.style.height = "auto";
    $("chat-send").disabled = true;
    input.disabled = true;

    addBubble("user", message, null);
    var typing = addTyping();

    try {
      var r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, customer_id: customerId }),
      });
      var data = await r.json();
      typing.remove();
      if (r.ok) addBubble("agent", data.answer, data.source);
      else addBubble("agent", "Error: " + (data.error || r.status), null);
    } catch (e) {
      typing.remove();
      addBubble("agent", "Network error: " + e.message, null);
    }

    $("chat-send").disabled = false;
    input.disabled = false;
    input.focus();
  }

  function suggest(text) {
    var input = $("chat-input");
    input.value = text;
    input.focus();
  }

  function init() {
    setModeTag();
    addBubble("agent",
      "Ask me anything about your customers, tactics, call history, or deal performance. " +
      "Pick a customer above for focused answers, or leave it on ‘All customers’ for the big picture.",
      null);

    $("chat-send").addEventListener("click", send);
    $("chat-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
    $("chat-input").addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });

    var chips = document.querySelectorAll("[data-suggest]");
    for (var i = 0; i < chips.length; i++) {
      chips[i].addEventListener("click", function () { suggest(this.getAttribute("data-suggest")); });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
