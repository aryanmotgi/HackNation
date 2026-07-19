/* Intake wizard — multi-step: input → PDF parse → hard-rule questions → confirm → save.
   PDF path is fully wired; voice is stubbed. Talks to /api/intake/*. */

const state = { draft: null, questions: [], answers: {}, source: "pdf" };

// ── step navigation ──────────────────────────────────────────────────────────
function gotoStep(n) {
  document.querySelectorAll(".step").forEach(s =>
    s.classList.toggle("active", +s.dataset.step === n));
  document.querySelectorAll(".stepper__node").forEach(node => {
    const s = +node.dataset.step;
    node.classList.toggle("stepper__node--active", s === n);
    node.classList.toggle("stepper__node--done", s < n);
  });
  if (n === 4) doPreview(true);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── mode tag ─────────────────────────────────────────────────────────────────
async function setModeTag() {
  try {
    const s = await fetch("/api/sessions").then(r => r.json());
    const tag = document.getElementById("mode-tag");
    if (s.model_mode === "live") tag.innerHTML = `<span class="mode-tag__dot"></span> LIVE · ${s.model}`;
    else { tag.className = "mode-tag mode-tag--mock"; tag.innerHTML = `<span class="mode-tag__dot"></span> MOCK`; }
  } catch (e) { /* non-fatal */ }
}

// ── step 2: file + parse ─────────────────────────────────────────────────────
function wireUpload() {
  const dz = document.getElementById("dropzone");
  const input = document.getElementById("pdf-input");
  const parseBtn = document.getElementById("parse-btn");
  let file = null;

  const setFile = (f) => {
    file = f;
    document.getElementById("filename").textContent = f ? `Selected: ${f.name}` : "";
    parseBtn.disabled = !f;
  };
  dz.addEventListener("click", () => input.click());
  input.addEventListener("change", () => setFile(input.files[0]));
  dz.addEventListener("dragover", e => { e.preventDefault(); dz.classList.add("dropzone--over"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dropzone--over"));
  dz.addEventListener("drop", e => {
    e.preventDefault(); dz.classList.remove("dropzone--over");
    if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
  });

  parseBtn.addEventListener("click", async () => {
    if (!file) return;
    parseBtn.disabled = true; parseBtn.textContent = "Parsing…";
    const fd = new FormData(); fd.append("pdf", file);
    const res = await fetch("/api/intake/parse", { method: "POST", body: fd });
    const data = await res.json();
    parseBtn.textContent = "Parse PDF →"; parseBtn.disabled = false;
    const errBox = document.getElementById("parse-error");
    if (!res.ok) { errBox.innerHTML = alertHtml("error", "Parse failed", [data.error]); return; }
    errBox.innerHTML = "";
    state.draft = data.draft; state.questions = data.questions; state.answers = {};
    renderQuestions();
    gotoStep(3);
  });
}

// ── step 3: questions ────────────────────────────────────────────────────────
function renderQuestions() {
  const found = (state.draft._found || []).join(", ") || "nothing";
  const sum = document.getElementById("parse-summary");
  sum.style.display = "block";
  sum.innerHTML = `<span class="alert__title">Parsed from PDF:</span> ${found}. ` +
    `Answer the remaining hard-rule questions below.`;

  const wrap = document.getElementById("questions");
  wrap.innerHTML = state.questions.map(q => {
    const voice = `<button class="btn btn--ghost qcard__voice" data-voice="${q.id}" ` +
      `title="Voice answer coming soon" disabled>🎙️ voice</button>`;
    let control;
    if (q.type === "number")
      control = `<input class="input input--num" data-qid="${q.id}" type="number" step="0.01" placeholder="e.g. 3.20">`;
    else if (q.type === "list")
      control = `<input class="input" data-qid="${q.id}" placeholder="comma-separated">`;
    else
      control = `<input class="input" data-qid="${q.id}" placeholder="type your answer">`;
    return `<div class="qcard">${voice}<div class="qcard__prompt">${q.prompt}</div>${control}</div>`;
  }).join("") || `<div class="alert alert--ok">PDF covered everything — no extra questions.</div>`;
}

function collectAnswers() {
  const a = {};
  document.querySelectorAll("#questions [data-qid]").forEach(el => { a[el.dataset.qid] = el.value; });
  state.answers = a;
}

// ── step 4: confirm ──────────────────────────────────────────────────────────
async function doPreview(prefill) {
  const body = {
    draft: state.draft, answers: state.answers, source: state.source,
    confirm: false, deal_edits: prefill ? {} : readDealEdits(),
  };
  const res = await fetch("/api/intake/confirm", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json();
  const spec = data.spec;
  if (prefill) fillDealInputs(spec.deal);
  renderHardRules(spec.hard_rules);
  document.getElementById("confirm-errors").innerHTML =
    (data.errors && data.errors.length)
      ? alertHtml("error", "Fix these before saving", data.errors) : "";
  return data;
}

function fillDealInputs(deal) {
  for (const k of ["product", "quantity", "floor_price", "target_price", "currency", "payment_terms"]) {
    const el = document.getElementById("e-" + k);
    if (el) el.value = deal[k] == null ? "" : deal[k];
  }
}
function readDealEdits() {
  const d = {};
  for (const k of ["product", "quantity", "floor_price", "target_price", "currency", "payment_terms"]) {
    const el = document.getElementById("e-" + k);
    if (el && el.value !== "") d[k] = (k === "quantity") ? parseInt(el.value, 10)
      : (k === "floor_price" || k === "target_price") ? parseFloat(el.value) : el.value;
  }
  return d;
}
function renderHardRules(hr) {
  const rows = [
    ["Floor (enforced)", hr.floor_price],
    ["Forbidden terms", (hr.forbidden_terms || []).join(", ") || "—"],
    ["Walk-away price", hr.walk_away_price == null ? "—" : hr.walk_away_price],
    ["Escalation trigger", hr.escalation_trigger || "—"],
    ["Always propose next step", hr.always_propose_next_step ? "yes" : "no"],
  ];
  document.getElementById("hardrules-preview").innerHTML = rows.map(
    ([k, v]) => `<div class="memrow"><span class="memrow__k">${k}</span><span class="memrow__v">${v}</span></div>`
  ).join("");
}

async function doConfirm() {
  // re-preview with edits so hard rules reflect edited floor, then save if clean
  await doPreview(false);
  const body = {
    draft: state.draft, answers: state.answers, source: state.source,
    confirm: true, deal_edits: readDealEdits(),
  };
  const res = await fetch("/api/intake/confirm", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    document.getElementById("confirm-errors").innerHTML =
      alertHtml("error", "Fix these before saving", data.errors || ["Save failed."]);
    return;
  }
  document.getElementById("saved-path").textContent = "Saved to " + data.path;
  document.getElementById("saved-id").textContent = data.job_id;
  document.getElementById("final-json").textContent = JSON.stringify(data.spec, null, 2);
  gotoStep(5);
}

// ── helpers ──────────────────────────────────────────────────────────────────
function alertHtml(kind, title, items) {
  return `<div class="alert alert--${kind}"><span class="alert__title">${title}</span>` +
    `<ul>${items.map(i => `<li>${i}</li>`).join("")}</ul></div>`;
}
function reset() {
  state.draft = null; state.questions = []; state.answers = {};
  document.getElementById("pdf-input").value = "";
  document.getElementById("filename").textContent = "";
  document.getElementById("parse-btn").disabled = true;
  gotoStep(1);
}

// ── wire up ──────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setModeTag();
  wireUpload();
  document.getElementById("choose-pdf").addEventListener("click", () => gotoStep(2));
  document.querySelectorAll("[data-back]").forEach(b =>
    b.addEventListener("click", () => gotoStep(+b.dataset.back)));
  document.getElementById("review-btn").addEventListener("click", () => { collectAnswers(); gotoStep(4); });
  document.getElementById("confirm-btn").addEventListener("click", doConfirm);
  document.getElementById("new-job").addEventListener("click", reset);
});
