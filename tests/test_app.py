"""Integration checks: isolated temporary DB, no real API calls or credentials."""
import io
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app import AppServer
from elyra import providers
from elyra.store import Store


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name) / "test.db")
        cls.server = AppServer(("127.0.0.1", 0), cls.store)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.log_patch = patch("app.Handler.log_message")
        cls.log_patch.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.token = cls.server.token

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.log_patch.stop()
        cls.temp.cleanup()

    def request(self, path, data=None, token=True, headers=None):
        request_headers = {"Content-Type": "application/json"}
        if token:
            request_headers["X-Elyra-Token"] = self.token
        request_headers.update(headers or {})
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode() if data is not None else None, headers=request_headers)
        try:
            return urllib.request.urlopen(req, timeout=8)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise

    def json(self, path, data=None, **kwargs):
        with self.request(path, data, **kwargs) as response:
            return json.load(response)

    def room(self, **kwargs):
        return self.json("/api/rooms", {"characterId": "luna", "provider": "demo", "model": "story-demo", **kwargs})

    def chat(self, room_id, text="สวัสดี"):
        with patch("app.time.sleep"), self.request(f"/api/rooms/{room_id}/chat", {"text": text}) as response:
            return [json.loads(line) for line in response if line.strip()]

    def test_bootstrap_and_secret_separation(self):
        with patch("elyra.providers.api_key", return_value="test-secret-do-not-leak"):
            data = self.json("/api/bootstrap")
        self.assertEqual(len([c for c in data["characters"] if not c.get("custom")]), 4)
        self.assertTrue(data["providers"]["xai"]["configured"])
        self.assertNotIn("test-secret-do-not-leak", json.dumps(data))

    def test_static_assets_and_utf8(self):
        for path in ("/", "/app.js", "/styles.css", "/assets/luna.svg"):
            with self.request(path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertGreater(len(response.read()), 100)

    def test_secret_files_and_path_traversal_not_served(self):
        for path in ("/xAi_api_key.text", "/.env", "/app.py", "/../app.py", "/%2e%2e/app.py", "/.data/elyra.db"):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.request(path)
            self.assertEqual(raised.exception.code, 404)

    def test_cross_origin_and_dns_rebinding_rejected(self):
        for headers in ({"Origin": "https://evil.example"}, {"Host": "evil.example"}):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("/api/bootstrap", headers=headers)
            self.assertEqual(raised.exception.code, 403)

    def test_mutation_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.json("/api/rooms", {"characterId": "luna"}, token=False)
        self.assertEqual(raised.exception.code, 403)

    def test_demo_stream_and_persistent_pairs(self):
        room = self.room()
        events = self.chat(room["id"])
        self.assertTrue(any(event["type"] == "delta" for event in events))
        done = events[-1]
        self.assertEqual(done["type"], "done")
        self.assertEqual(len(done["room"]["messages"]), 3)
        self.assertEqual(done["room"]["turns"], 1)
        self.assertEqual(done["unlocked"], [])  # turn-count milestones are retired; scenes are model-picked
        reloaded = Store(self.store.path).room(room["id"])
        self.assertEqual(reloaded["messages"][-1]["provider"], "demo")

    def test_turn_count_milestones_no_longer_unlock(self):
        # User decision 2026-10-18: "ภาพความทรงจำ" (1/3/6-turn milestones) removed; only scene images unlock.
        room = self.room()
        for _ in range(6):
            self.assertEqual(self.chat(room["id"])[-1]["unlocked"], [])
        self.assertEqual(self.store.room(room["id"])["unlocks"], [])
        self.assertEqual(self.json("/api/bootstrap")["milestones"], [])

    def test_memory_isolated_and_deletion(self):
        room, other = self.room(), self.room()
        saved = self.json(f"/api/rooms/{room['id']}/memory", {"content": "ฉันชื่อมิน"})
        self.assertEqual(len(saved["memories"]), 1)
        self.assertEqual(self.store.room(other["id"])["memories"], [])
        events = self.chat(room["id"], "จำได้ไหม")
        self.assertIn("ฉันชื่อมิน", events[-1]["room"]["messages"][-1]["content"])
        self.json(f"/api/rooms/{room['id']}/forget", {"memoryId": saved["memories"][0]["id"]})
        self.assertEqual(self.store.room(room["id"])["memories"], [])

    def test_failed_provider_does_not_commit_or_fallback(self):
        room = self.room(provider="openai", model="test-model")
        with patch("elyra.providers.stream", side_effect=providers.ProviderError("provider unavailable")):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.chat(room["id"])
            self.assertEqual(raised.exception.code, 400)
            raised.exception.close()
        saved = self.store.room(room["id"])
        self.assertEqual(len(saved["messages"]), 1)
        self.assertEqual(saved["unlocks"], [])
        self.assertEqual(saved["provider"], "openai")

    def test_partial_stream_does_not_commit(self):
        room = self.room(provider="ollama", model="test")
        def interrupted(*args):
            yield "partial reply"
            raise providers.ProviderError("interrupted")
        with patch("elyra.providers.stream", side_effect=interrupted):
            events = self.chat(room["id"])
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(len(self.store.room(room["id"])["messages"]), 1)

    def test_provider_switch_preserves_memories_and_history(self):
        room = self.room()
        self.chat(room["id"])
        self.json(f"/api/rooms/{room['id']}/memory", {"content": "ชอบกาแฟ"})
        updated = self.json(f"/api/rooms/{room['id']}/configure", {"provider": "ollama", "model": "test", "mode": "general"})
        self.assertEqual(updated["provider"], "ollama")
        self.assertEqual(updated["memories"][0]["content"], "ชอบกาแฟ")
        self.assertEqual(len(updated["messages"]), 3)

    def test_concurrent_room_changes_rejected(self):
        room = self.room()
        self.server.busy_rooms.add(room["id"])
        try:
            for action, data in (("chat", {"text": "hello"}), ("delete", {}), ("memory", {"content": "test"})):
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    self.json(f"/api/rooms/{room['id']}/{action}", data)
                self.assertEqual(raised.exception.code, 409)
        finally:
            self.server.busy_rooms.discard(room["id"])

    def test_character_validation_and_custom_creation(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.json("/api/characters", {"name": "Bad", "age": 17})
        character = self.json("/api/characters", {"name": "Nova", "age": 26, "description": "นักเดินทาง", "personality": "ใจดี", "greeting": "สวัสดี", "art": "kael"})
        self.assertTrue(character["custom"])
        room = self.room(characterId=character["id"])
        self.assertEqual(room["messages"][0]["content"], "สวัสดี")

    def test_mature_requires_confirmation(self):
        settings = self.store.settings()
        settings["matureConfirmed"] = False
        self.store.save_settings(settings)
        with self.assertRaises(urllib.error.HTTPError):
            self.room(mode="mature")

    def test_export_and_room_delete_include_related_data(self):
        room = self.room()
        self.chat(room["id"])
        self.json(f"/api/rooms/{room['id']}/memory", {"content": "test"})
        export = self.json("/api/export")
        self.assertIn(room["id"], [item["id"] for item in export["rooms"]])
        self.json(f"/api/rooms/{room['id']}/delete", {})
        self.assertIsNone(self.store.room(room["id"]))
        self.assertFalse(any(item["room_id"] == room["id"] for item in self.store.gallery()))

    def test_model_listing_uses_selected_provider(self):
        with patch("elyra.providers.list_models", return_value=["local-model"]) as call:
            self.assertEqual(self.json("/api/models?provider=ollama")["models"], ["local-model"])
            call.assert_called_once_with("ollama")


class AdapterTests(unittest.TestCase):
    def run_stream(self, provider, payload):
        response = io.BytesIO(payload.encode())
        with patch("elyra.providers.request", return_value=response) as call:
            output = "".join(providers.stream(provider, "model", [{"role": "user", "content": "hello"}]))
            return output, call.call_args

    def test_openai_responses_events(self):
        payload = 'data: {"type":"response.output_text.delta","delta":"สวัสดี"}\n\ndata: {"type":"response.completed"}\n\n'
        output, args = self.run_stream("openai", payload)
        self.assertEqual(output, "สวัสดี")
        self.assertEqual(args.args[1], "/responses")
        self.assertFalse(args.args[2]["store"])

    def test_xai_chat_events(self):
        output, _ = self.run_stream("xai", 'data: {"choices":[{"delta":{"content":"hello"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\ndata: [DONE]\n\n')
        self.assertEqual(output, "hello")

    def test_ollama_ndjson(self):
        output, args = self.run_stream("ollama", '{"message":{"content":"hello"},"done":false}\n{"message":{"content":" world"},"done":true,"done_reason":"stop"}\n')
        self.assertEqual(output, "hello world")
        self.assertEqual(args.args[1], "/api/chat")

    def test_unfinished_stream_fails(self):
        for provider, payload in (("openai", 'data: {"type":"response.output_text.delta","delta":"partial"}\n'), ("ollama", '{"message":{"content":"partial"},"done":false}\n'), ("xai", 'data: {"choices":[{"delta":{"content":"partial"}}]}\n\ndata: [DONE]\n')):
            with self.assertRaises(providers.ProviderError):
                self.run_stream(provider, payload)

    def test_ollama_cannot_silently_become_cloud(self):
        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "https://example.com"}):
            with self.assertRaises(providers.ProviderError):
                providers.ollama_base()


if __name__ == "__main__":
    unittest.main()
