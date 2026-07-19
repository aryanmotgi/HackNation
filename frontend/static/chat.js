(function () {
  "use strict";

  function $(id) { return document.getElementById(id); }

  async function setModeTag() {
    try {
      var s = await fetch("/api/sessions").then(function (r) { return r.json(); });
      var tag = $("mode-tag");
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
    whoEl.textContent = isAgent ? "Loomhaus AI" : "You";
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
    whoEl.textContent = "Loomhaus AI";
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
      if (r.ok) {
        addBubble("agent", data.answer, data.source);
      } else {
        addBubble("agent", "Error: " + (data.error || r.status), null);
      }
    } catch (e) {
      typing.remove();
      addBubble("agent", "Network error: " + e.message, null);
    }

    $("chat-send").disabled = false;
    input.disabled = false;
    input.focus();
  }

  function init() {
    setModeTag();

    addBubble(
      "agent",
      "Ask me anything about your customers, tactics, call history, or deal performance. " +
      "Select a customer above for focused answers, or leave it on ‘All customers’ for a summary view.",
      null
    );

    $("chat-send").addEventListener("click", send);

    $("chat-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        send();
      }
    });

    $("chat-input").addEventListener("input", function () {
      this.style.height = "auto";
      this.style.height = Math.min(this.scrollHeight, 120) + "px";
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
