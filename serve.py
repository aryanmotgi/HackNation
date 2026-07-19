"""Combined server — frontend dashboard + voice webhooks in ONE process.

Kuzu is single-lock (only one process may hold the DB), so the dashboard and the
voice webhooks cannot run as two processes against the same database. This entry
point runs them as one Flask app sharing one Kuzu connection:

  * seeds the graph ONCE at startup (clean demo state), then
  * neutralizes further reseeds so the frontend's per-load reseed can't open a
    second connection or wipe live-call data, then
  * serves the frontend routes AND the voice blueprint on a single port.

Run:
    .venv/bin/python serve.py            # http://127.0.0.1:5055
      /            dashboard/intake        /call/init      ElevenLabs webhook
      /dashboard   overview                /tool/make_offer server tool
      /graph       3D memory graph         /call/postcall  post-call webhook
      /report      ranked live quotes      /health         liveness
"""

from __future__ import annotations

import os

# 1. Seed once at startup, then make further seed() calls a no-op. The frontend
#    imports seed lazily inside _build_snapshot, so this replacement is picked up
#    at call time — its per-load reseed becomes a no-op instead of a second Kuzu
#    connection (which would lock-conflict) and live-call data is preserved.
import memory.seed as _seedmod

_seedmod.seed()
_seedmod.seed = lambda *a, **k: None

# 2. One Flask app: frontend routes + voice blueprint, sharing memory.retrieve._conn.
from frontend.app import app as flask_app  # noqa: E402
from voice.app import voice_bp  # noqa: E402

flask_app.register_blueprint(voice_bp)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5055"))
    print(f"[serve] combined app on :{port} — dashboard + voice webhooks, one Kuzu connection")
    # debug=False → no reloader (a reloader child would open a second Kuzu connection).
    flask_app.run(host="0.0.0.0", port=port, debug=False)
