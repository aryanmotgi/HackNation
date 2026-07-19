# Forge manufacturer onboarding frontend

The manufacturer-facing setup and demo console for HackNation. It lets a factory
configure its company profile, catalog, pricing guardrails, escalation rules, and
voice identity, then rehearse a buyer negotiation with two simulated voices.

## Run locally

Requires Node.js 22.13 or newer.

```bash
cd frontend
npm install
npm run dev
```

Open the local URL shown in the terminal.

## What is implemented

- five-step manufacturer onboarding flow
- product catalog upload UI and extracted-product review
- opening, target, volume, and hard-floor pricing inputs
- validation that prevents unsafe pricing configurations
- human escalation and approval rules
- manufacturer voice/personality selection
- saved setup progress in browser storage
- two-speaker negotiation rehearsal based on entered values
- live deal guardrail and floor-protection display

## Backend handoff

The rehearsal currently uses browser speech synthesis so the demo works without
credentials. To connect ElevenLabs, keep the API key server-side and replace the
rehearsal transport with the manufacturer Sales Agent ID. The buyer voice is a
demo simulator; the manufacturer voice is the product agent.

The Python memory and negotiation modules remain at the repository root. A later
integration can replace the frontend's local demo transcript with calls to those
modules without changing the onboarding UI.

## Verify

```bash
npm run build
```
