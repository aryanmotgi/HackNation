"""Render-level checks for the unified manufacturer workspace."""

import unittest

from frontend.app import app


class UnifiedFrontendTest(unittest.TestCase):
    def setUp(self):
        app.config.update(TESTING=True)
        self.client = app.test_client()

    def test_every_workspace_route_renders_shared_navigation(self):
        for path in ("/", "/intake", "/dashboard", "/messaging", "/graph", "/call"):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"app-sidebar", response.data)
                self.assertIn(b"Nova Manufacturing", response.data)

    def test_call_rehearsal_is_honestly_labeled(self):
        page = self.client.get("/call").data
        self.assertIn(b"Rehearsal mode", page)
        self.assertIn(b"not a live ElevenLabs call", page)
        self.assertIn(b"AI agent identifies itself", page)
        self.assertIn(b"$4.45", page)
        self.assertIn(b"$4.60", page)

    def test_intake_requests_agent_id_not_api_key(self):
        page = self.client.get("/intake").data
        self.assertIn(b"ElevenLabs Agent ID", page)
        self.assertIn(b"Never paste an API key here", page)
        self.assertNotIn(b"name=\"elevenlabs_api_key\"", page)


if __name__ == "__main__":
    unittest.main()
