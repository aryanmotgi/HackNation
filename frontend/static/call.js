/* Call Desk — in-browser voice call to the manufacturer's ElevenLabs agent.
   Uses the @elevenlabs/client SDK against a PUBLIC agent (agent_id only, no key).
   The SDK owns mic capture + audio playback + turn-taking; this file drives the
   phone UI (states, timer, waveform, transcript). */

import { Conversation } from 'https://cdn.jsdelivr.net/npm/@elevenlabs/client/+esm';

const phone   = document.getElementById('phone');
const AGENT   = (phone.dataset.agent || '').trim();

const callBtn   = document.getElementById('callBtn');
const callLabel = document.getElementById('callBtnLabel');
const statusText= document.getElementById('statusText');
const statusDot = document.getElementById('statusDot');
const timerEl   = document.getElementById('timer');
const speaker   = document.getElementById('speaker');
const viz       = document.getElementById('viz');
const hint      = document.getElementById('hint');
const avatar    = document.getElementById('avatar');
const log       = document.getElementById('log');
const logBody   = document.getElementById('logBody');

let convo = null;
let state = 'idle';            // idle | connecting | live | ending
let tStart = 0, tTick = null;

function setStatus(text, cls) {
  statusText.textContent = text;
  statusDot.className = 'phone__dot' + (cls ? ' phone__dot--' + cls : '');
}

function fmt(sec) {
  const m = String(Math.floor(sec / 60)).padStart(2, '0');
  const s = String(sec % 60).padStart(2, '0');
  return `${m}:${s}`;
}

function startTimer() {
  tStart = Date.now();
  timerEl.hidden = false;
  timerEl.textContent = '00:00';
  tTick = setInterval(() => {
    timerEl.textContent = fmt(Math.floor((Date.now() - tStart) / 1000));
  }, 1000);
}
function stopTimer() { clearInterval(tTick); tTick = null; }

function addLine(role, text) {
  if (!text) return;
  log.hidden = false;
  const row = document.createElement('div');
  row.className = 'call-log__row call-log__row--' + role;
  row.innerHTML = `<span class="call-log__who">${role === 'agent' ? 'Agent' : 'You'}</span>
                   <span class="call-log__msg"></span>`;
  row.querySelector('.call-log__msg').textContent = text;
  logBody.appendChild(row);
  logBody.scrollTop = logBody.scrollHeight;
}

// --- call lifecycle -----------------------------------------------------------
async function startCall() {
  if (!AGENT) { setStatus('No agent configured', 'red'); return; }
  state = 'connecting';
  phone.classList.add('is-connecting');
  callBtn.disabled = true;
  callLabel.textContent = 'Ringing…';
  setStatus('Connecting…', 'amber');
  hint.textContent = 'Allow microphone access when prompted.';

  try {
    convo = await Conversation.startSession({
      agentId: AGENT,
      onConnect: () => {
        state = 'live';
        phone.classList.remove('is-connecting');
        phone.classList.add('is-live');
        callBtn.disabled = false;
        toHangup();
        setStatus('Connected', 'green');
        hint.textContent = 'You are live. Speak to negotiate — tap the red button to hang up.';
        startTimer();
      },
      onDisconnect: () => endCall(true),
      onError: (e) => {
        console.error('[call] error', e);
        setStatus('Call failed', 'red');
        hint.textContent = 'Could not connect. Check the agent is set to Public in ElevenLabs.';
        resetButton();
        phone.classList.remove('is-connecting', 'is-live');
        state = 'idle';
      },
      onModeChange: (m) => {
        // m.mode: 'speaking' (agent talking) | 'listening' (your turn)
        const speaking = m && m.mode === 'speaking';
        phone.classList.toggle('agent-speaking', speaking);
        phone.classList.toggle('you-speaking', !speaking && state === 'live');
        speaker.textContent = speaking ? 'Agent speaking…' : 'Listening to you…';
      },
      onMessage: (msg) => {
        if (!msg) return;
        const role = msg.source === 'ai' || msg.source === 'agent' ? 'agent' : 'user';
        addLine(role, msg.message || msg.text || '');
      },
    });
  } catch (err) {
    console.error('[call] startSession failed', err);
    setStatus('Call failed', 'red');
    hint.textContent = String(err && err.message || err).includes('Permission')
      ? 'Microphone blocked — allow it in the browser and try again.'
      : 'Could not reach the agent. Confirm it is Public in ElevenLabs.';
    resetButton();
    phone.classList.remove('is-connecting');
    state = 'idle';
  }
}

async function endCall(remote) {
  if (state === 'idle' || state === 'ending') { if (remote) hangupUi(); return; }
  state = 'ending';
  try { if (convo && !remote) await convo.endSession(); } catch (e) { /* ignore */ }
  convo = null;
  hangupUi();
}

function hangupUi() {
  stopTimer();
  state = 'idle';
  phone.classList.remove('is-live', 'is-connecting', 'agent-speaking', 'you-speaking');
  resetButton();
  setStatus('Call ended', '');
  speaker.innerHTML = '&nbsp;';
  hint.textContent = 'Uses your microphone. Speak naturally — the agent listens and replies.';
  setTimeout(() => { if (state === 'idle') setStatus('Ready to call', ''); }, 1800);
}

function toHangup() {
  callBtn.classList.remove('callbtn--go');
  callBtn.classList.add('callbtn--end');
  callLabel.textContent = 'Hang up';
}
function resetButton() {
  callBtn.disabled = false;
  callBtn.classList.remove('callbtn--end');
  callBtn.classList.add('callbtn--go');
  callLabel.textContent = 'Call';
  timerEl.hidden = true;
}

callBtn.addEventListener('click', () => {
  if (state === 'idle') startCall();
  else if (state === 'live') endCall(false);
});

window.addEventListener('beforeunload', () => { if (convo) { try { convo.endSession(); } catch (e) {} } });
