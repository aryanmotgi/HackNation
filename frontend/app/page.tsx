"use client";

import { ChangeEvent, useEffect, useMemo, useRef, useState } from "react";

type SetupData = {
  company: string;
  website: string;
  location: string;
  timezone: string;
  languages: string;
  hours: string;
  product: string;
  sku: string;
  moq: number;
  openingPrice: number;
  targetPrice: number;
  floorPrice: number;
  volumeQty: number;
  volumePrice: number;
  leadTime: number;
  paymentTerms: string;
  shippingTerms: string;
  approvalThreshold: number;
  transferValue: number;
  agentName: string;
  voice: string;
  tone: string;
  phone: string;
};

const initialData: SetupData = {
  company: "Nova Manufacturing",
  website: "novamfg.com",
  location: "Shenzhen, China",
  timezone: "Asia/Shanghai",
  languages: "English, Mandarin",
  hours: "09:00–18:00 CST",
  product: "500 ml stainless-steel bottle",
  sku: "BOT-500-CUSTOM",
  moq: 1000,
  openingPrice: 5.2,
  targetPrice: 4.8,
  floorPrice: 4.45,
  volumeQty: 5000,
  volumePrice: 4.6,
  leadTime: 25,
  paymentTerms: "30% deposit, 70% before shipment",
  shippingTerms: "FOB Shenzhen",
  approvalThreshold: 4.45,
  transferValue: 25000,
  agentName: "Alex",
  voice: "Warm & professional",
  tone: "Confident, concise, never pushy",
  phone: "+1 (415) 555-0142",
};

const steps = [
  { title: "Company", hint: "Business basics" },
  { title: "Catalog", hint: "Products & pricing" },
  { title: "Guardrails", hint: "Deal rules" },
  { title: "Voice", hint: "Agent identity" },
  { title: "Test call", hint: "Rehearse & launch" },
];

const callLines = (data: SetupData) => [
  { speaker: "agent", text: `Thank you for calling ${data.company}. I’m ${data.agentName}. How can I help with your order today?` },
  { speaker: "buyer", text: `I need 2,000 custom ${data.product}s. What’s your best price?` },
  { speaker: "agent", text: `For 2,000 units, our opening price is $${data.openingPrice.toFixed(2)} per unit. Where would the order be shipped?` },
  { speaker: "buyer", text: "Los Angeles. Another supplier offered me $4.20." },
  { speaker: "agent", text: `I understand. Does that include custom printing and inspection? For this specification, I can offer $${data.targetPrice.toFixed(2)} at 2,000 units.` },
  { speaker: "buyer", text: "If you can do $4.50, I can move forward." },
  { speaker: "agent", text: `I can reach $${data.volumePrice.toFixed(2)} if you increase the order to ${data.volumeQty.toLocaleString()} units. That stays above our authorized floor and includes inspection.` },
  { speaker: "buyer", text: `Let’s do ${data.volumeQty.toLocaleString()} at $${data.volumePrice.toFixed(2)}. Send a sample first.` },
  { speaker: "agent", text: `Perfect. I’ve recorded ${data.volumeQty.toLocaleString()} units at $${data.volumePrice.toFixed(2)}, pending sample approval. The quote will follow shortly.` },
];

function Field({ label, helper, required = false, children }: { label: string; helper?: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="field-label">{label}{required && <em>Required</em>}</span>
      {children}
      {helper && <span className="helper">{helper}</span>}
    </label>
  );
}

export default function Home() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<SetupData>(initialData);
  const [catalog, setCatalog] = useState("Nova_Product_Catalog_2026.pdf");
  const [activeLines, setActiveLines] = useState(0);
  const [calling, setCalling] = useState(false);
  const [soundOn, setSoundOn] = useState(true);
  const [saved, setSaved] = useState(false);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const lines = useMemo(() => callLines(data), [data]);

  useEffect(() => {
    const stored = window.localStorage.getItem("forge-onboarding");
    if (stored) {
      try { setData({ ...initialData, ...JSON.parse(stored) }); } catch { /* keep demo defaults */ }
    }
  }, []);

  useEffect(() => {
    if (!calling || activeLines >= lines.length) {
      if (calling && activeLines >= lines.length) setCalling(false);
      return;
    }
    const line = lines[activeLines];
    if (soundOn && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      const speech = new SpeechSynthesisUtterance(line.text);
      const voices = window.speechSynthesis.getVoices();
      speech.voice = voices[line.speaker === "agent" ? 0 : Math.min(1, voices.length - 1)] ?? null;
      speech.rate = line.speaker === "agent" ? 1 : 1.05;
      window.speechSynthesis.speak(speech);
    }
    const timer = window.setTimeout(() => setActiveLines((value) => value + 1), Math.max(1700, line.text.length * 31));
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
    return () => window.clearTimeout(timer);
  }, [activeLines, calling, lines, soundOn]);

  const set = <K extends keyof SetupData>(key: K, value: SetupData[K]) => setData((current) => ({ ...current, [key]: value }));
  const number = (key: keyof SetupData) => (event: ChangeEvent<HTMLInputElement>) => set(key, Number(event.target.value) as never);
  const text = (key: keyof SetupData) => (event: ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => set(key, event.target.value as never);

  const saveProgress = () => {
    window.localStorage.setItem("forge-onboarding", JSON.stringify(data));
    setSaved(true);
    window.setTimeout(() => setSaved(false), 1800);
  };

  const startCall = () => {
    setActiveLines(1);
    setCalling(true);
    window.setTimeout(() => setActiveLines(2), 1400);
  };

  const next = () => {
    saveProgress();
    setStep((value) => Math.min(4, value + 1));
  };

  const reset = () => {
    window.speechSynthesis?.cancel();
    setCalling(false);
    setActiveLines(0);
  };

  const priceValid = data.floorPrice <= data.targetPrice && data.targetPrice <= data.openingPrice && data.volumePrice >= data.floorPrice;
  const completion = [Boolean(data.company && data.location), Boolean(data.product && data.floorPrice), priceValid, Boolean(data.agentName && data.voice), activeLines >= lines.length].filter(Boolean).length;

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">F</span><span>FORGE</span><small>Voice sales for manufacturers</small></div>
        <div className="top-actions"><span className="draft"><i /> Draft saved</span><button className="ghost-button" onClick={saveProgress}>{saved ? "Saved ✓" : "Save & exit"}</button></div>
      </header>

      <section className="hero">
        <div><span className="eyebrow">MANUFACTURER ONBOARDING</span><h1>Train your sales agent.<br />Keep control of every deal.</h1><p>Upload what you already have. Review the extracted details. Set the limits your agent can never cross.</p></div>
        <div className="completion-card"><strong>{completion}/5</strong><span>setup sections ready</span><div className="mini-progress"><i style={{ width: `${completion * 20}%` }} /></div><small>About {Math.max(2, 10 - completion * 2)} minutes left</small></div>
      </section>

      <div className="workspace">
        <aside className="sidebar" aria-label="Setup steps">
          <p>SETUP CHECKLIST</p>
          {steps.map((item, index) => (
            <button key={item.title} className={index === step ? "step active" : index < step ? "step done" : "step"} onClick={() => setStep(index)}>
              <span>{index < step ? "✓" : index + 1}</span><div><strong>{item.title}</strong><small>{item.hint}</small></div>
            </button>
          ))}
          <div className="security-note"><span>⌁</span><div><strong>Your pricing stays private</strong><p>Floor prices are only used as internal guardrails. Buyers never see them.</p></div></div>
        </aside>

        <section className="panel">
          {step === 0 && (
            <div className="panel-content">
              <div className="section-heading"><span className="section-number">01</span><div><h2>Tell us about your factory</h2><p>This gives the agent the context it needs to greet and qualify buyers.</p></div></div>
              <div className="required-note"><strong>Only 3 things are required</strong><span>Company, location, and at least one product. Everything else can be added later.</span></div>
              <div className="form-grid">
                <Field label="Company name" required><input value={data.company} onChange={text("company")} /></Field>
                <Field label="Website" helper="Optional — used to learn your public product information"><input value={data.website} onChange={text("website")} /></Field>
                <Field label="Factory location" required><input value={data.location} onChange={text("location")} /></Field>
                <Field label="Time zone"><select value={data.timezone} onChange={text("timezone")}><option>Asia/Shanghai</option><option>America/Los_Angeles</option><option>Europe/London</option><option>Asia/Kolkata</option></select></Field>
                <Field label="Languages"><input value={data.languages} onChange={text("languages")} /></Field>
                <Field label="Sales hours" helper="The voice agent can still answer 24/7"><input value={data.hours} onChange={text("hours")} /></Field>
              </div>
            </div>
          )}

          {step === 1 && (
            <div className="panel-content">
              <div className="section-heading"><span className="section-number">02</span><div><h2>Add products and pricing</h2><p>Upload your existing catalog or enter one hero product for the demo.</p></div></div>
              <div className="upload-box">
                <div className="upload-icon">↑</div><div><strong>{catalog || "Drop a catalog or price sheet here"}</strong><span>{catalog ? "Ready to extract products, SKUs, and standard prices" : "PDF, CSV or XLSX · up to 25 MB"}</span></div>
                <label className="upload-button">{catalog ? "Replace" : "Choose file"}<input type="file" accept=".pdf,.csv,.xlsx,.xls" onChange={(event) => setCatalog(event.target.files?.[0]?.name ?? catalog)} /></label>
              </div>
              <div className="divider"><span>DEMO PRODUCT — REVIEW EXTRACTED DATA</span></div>
              <div className="form-grid three">
                <Field label="Product" required><input value={data.product} onChange={text("product")} /></Field>
                <Field label="SKU"><input value={data.sku} onChange={text("sku")} /></Field>
                <Field label="Minimum order"><div className="input-suffix"><input type="number" min="1" value={data.moq} onChange={number("moq")} /><span>units</span></div></Field>
                <Field label="Opening price"><div className="input-prefix"><span>$</span><input type="number" step=".01" value={data.openingPrice} onChange={number("openingPrice")} /></div></Field>
                <Field label="Target close"><div className="input-prefix"><span>$</span><input type="number" step=".01" value={data.targetPrice} onChange={number("targetPrice")} /></div></Field>
                <Field label="Hard floor" required helper="The agent cannot go below this"><div className="input-prefix danger"><span>$</span><input type="number" step=".01" value={data.floorPrice} onChange={number("floorPrice")} /></div></Field>
                <Field label="Volume tier"><div className="input-suffix"><input type="number" value={data.volumeQty} onChange={number("volumeQty")} /><span>units</span></div></Field>
                <Field label="Volume price"><div className="input-prefix"><span>$</span><input type="number" step=".01" value={data.volumePrice} onChange={number("volumePrice")} /></div></Field>
                <Field label="Lead time"><div className="input-suffix"><input type="number" value={data.leadTime} onChange={number("leadTime")} /><span>days</span></div></Field>
              </div>
              {!priceValid && <div className="validation-error">Check pricing: opening ≥ target ≥ floor, and the volume price cannot be below the floor.</div>}
            </div>
          )}

          {step === 2 && (
            <div className="panel-content">
              <div className="section-heading"><span className="section-number">03</span><div><h2>Set the agent’s boundaries</h2><p>These are hard rules, not suggestions. The agent escalates instead of guessing.</p></div></div>
              <div className="rule-banner"><span>LOCKED RULE</span><strong>Never quote below ${data.floorPrice.toFixed(2)} per unit.</strong><small>Only an authorized human can override this.</small></div>
              <div className="form-grid">
                <Field label="Payment terms"><input value={data.paymentTerms} onChange={text("paymentTerms")} /></Field>
                <Field label="Shipping terms"><input value={data.shippingTerms} onChange={text("shippingTerms")} /></Field>
                <Field label="Require approval below"><div className="input-prefix"><span>$</span><input type="number" step=".01" value={data.approvalThreshold} onChange={number("approvalThreshold")} /></div></Field>
                <Field label="Transfer deals above"><div className="input-prefix"><span>$</span><input type="number" value={data.transferValue} onChange={number("transferValue")} /></div></Field>
              </div>
              <h3 className="subheading">When should the agent call a human?</h3>
              <div className="toggle-list">
                {["Buyer requests a price below the floor", "Buyer asks for an unsupported customization", "Buyer is angry or asks for a manager", "Order value exceeds the transfer limit"].map((rule, index) => <label key={rule}><input type="checkbox" defaultChecked={index !== 1} /><span className="toggle" /><strong>{rule}</strong></label>)}
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="panel-content">
              <div className="section-heading"><span className="section-number">04</span><div><h2>Give your agent a voice</h2><p>Choose how buyers hear your company. You can change this any time.</p></div></div>
              <div className="form-grid">
                <Field label="Agent name" required><input value={data.agentName} onChange={text("agentName")} /></Field>
                <Field label="Assigned phone number"><input value={data.phone} onChange={text("phone")} /></Field>
              </div>
              <div className="voice-grid">
                {["Warm & professional", "Direct & efficient", "Calm & consultative"].map((voice, index) => <button key={voice} className={data.voice === voice ? "voice-card selected" : "voice-card"} onClick={() => set("voice", voice)}><span className="avatar">{["A", "M", "J"][index]}</span><div><strong>{voice}</strong><small>{["Alex · Multilingual", "Maya · US English", "James · UK English"][index]}</small></div><i>{data.voice === voice ? "✓" : "▶"}</i></button>)}
              </div>
              <Field label="Conversation style"><textarea rows={3} value={data.tone} onChange={text("tone")} /></Field>
              <div className="integration-note"><span>11</span><div><strong>ElevenLabs connection</strong><p>For the hackathon demo, Aryan connects the Sales Agent ID on the server. Never paste an API key into this page.</p></div><button>Ready for Agent ID</button></div>
            </div>
          )}

          {step === 4 && (
            <div className="panel-content call-step">
              <div className="section-heading"><span className="section-number">05</span><div><h2>Run a buyer test call</h2><p>The buyer is a demo simulator. {data.agentName} uses the factory rules you just entered.</p></div></div>
              <div className="call-layout">
                <div className="call-console">
                  <div className="call-header"><div><span className={calling ? "live-dot pulse" : "live-dot"} /><strong>{calling ? "LIVE CALL" : activeLines >= lines.length ? "CALL COMPLETE" : "READY TO REHEARSE"}</strong></div><button onClick={() => setSoundOn(!soundOn)}>{soundOn ? "Sound on ◕" : "Sound off ○"}</button></div>
                  <div className="participants"><div><span className="avatar large">A</span><strong>{data.agentName}</strong><small>{data.company}</small></div><span className="connection">•••</span><div><span className="avatar large buyer">M</span><strong>Maya Chen</strong><small>West Coast Goods</small></div></div>
                  <div className="transcript" ref={transcriptRef} aria-live="polite">
                    {activeLines === 0 && <div className="empty-transcript"><span>◎</span><strong>Your test script is ready</strong><p>Start the call to see two voices negotiate using your pricing rules.</p></div>}
                    {lines.slice(0, activeLines).map((line, index) => <div key={index} className={`bubble ${line.speaker}`}><span>{line.speaker === "agent" ? data.agentName : "Maya"}</span><p>{line.text}</p></div>)}
                    {calling && activeLines < lines.length && <div className="typing"><i /><i /><i /></div>}
                  </div>
                  <div className="call-controls">
                    {activeLines === 0 ? <button className="primary wide" onClick={startCall}>▶ Start two-voice demo</button> : <><button className="secondary" onClick={reset}>↻ Reset</button><button className="end-call" onClick={() => { setCalling(false); window.speechSynthesis?.cancel(); }}>■ End call</button></>}
                  </div>
                </div>
                <aside className="deal-card"><span className="deal-label">LIVE DEAL GUARDRAILS</span><div><small>Opening</small><strong>${data.openingPrice.toFixed(2)}</strong></div><div><small>Target</small><strong>${data.targetPrice.toFixed(2)}</strong></div><div className="floor"><small>Hard floor 🔒</small><strong>${data.floorPrice.toFixed(2)}</strong></div><hr /><p>Volume trade</p><strong>{data.volumeQty.toLocaleString()} units → ${data.volumePrice.toFixed(2)}</strong><hr /><p>Lead time</p><strong>{data.leadTime} days</strong>{activeLines >= lines.length && <div className="deal-won"><span>✓</span><div><strong>Floor protected</strong><small>Deal captured for follow-up</small></div></div>}</aside>
              </div>
            </div>
          )}

          <footer className="panel-footer">
            <button className="secondary" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}>← Back</button>
            <span>Step {step + 1} of 5</span>
            {step < 4 ? <button className="primary" disabled={step === 1 && !priceValid} onClick={next}>Save & continue →</button> : <button className="primary" onClick={saveProgress}>Finish setup ✓</button>}
          </footer>
        </section>
      </div>
    </main>
  );
}
