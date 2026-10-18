import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest import mock

from elyra import providers, scenes
from elyra.domain import validate_scenes
from elyra.store import Store

MEDIA = "a" * 64
SICK = {"id": "sickbed01", "media_id": MEDIA, "description": "นอนป่วยบนเตียง หน้าแดงจากไข้", "tier": "common", "min_turns": 0}
KITCHEN = {"id": "kitchen01", "media_id": MEDIA, "description": "ยืนทำข้าวต้มในครัว", "tier": "rare", "min_turns": 3}


class ValidateScenesTest(unittest.TestCase):
    def test_accepts_and_normalizes(self):
        result = validate_scenes([{**SICK, "description": "  นอนป่วย  "}, {"media_id": MEDIA, "description": "ในครัว"}])
        self.assertEqual(result[0]["description"], "นอนป่วย")
        self.assertRegex(result[1]["id"], r"^[a-z0-9]{12}$")
        self.assertEqual((result[1]["tier"], result[1]["min_turns"], result[1]["title"]), ("common", 0, ""))
        self.assertEqual(validate_scenes([{**SICK, "title": " ยาขม "}])[0]["title"], "ยาขม")
        with self.assertRaises(ValueError):
            validate_scenes([{**SICK, "title": "ก" * 41}])

    def test_rejects_bad_input(self):
        for bad in ([{**SICK, "media_id": ""}], [{**SICK, "tier": "epic"}], [{**SICK, "min_turns": -1}],
                    [{**SICK, "min_turns": True}], [{**SICK, "description": "x"}], [SICK, SICK],
                    [{**SICK, "id": "../x"}], "nope", [SICK] * 51):
            with self.assertRaises(ValueError):
                validate_scenes(bad)


def stream(chunks):
    markers = scenes.MarkerFilter()
    shown = "".join(markers.feed(chunk) for chunk in chunks)
    rest, marked = markers.finish()
    return shown + rest, marked


class MarkerTest(unittest.TestCase):
    def test_marker_split_across_chunks_is_hidden_and_parsed(self):
        text, marked = stream(["*เธอนอนลง* พักก่อนนะ\n", "[", "[sce", "ne:sick", "bed01]", "]"])
        self.assertEqual(text.rstrip(), "*เธอนอนลง* พักก่อนนะ")  # app.py rstrips before saving
        self.assertEqual(marked, "sickbed01")

    def test_text_without_marker_passes_through_unchanged(self):
        self.assertEqual(stream(["สวัสดี [ไม่ใช่", "แท็ก] และ [[ข้อความ]] ปกติ"]), ("สวัสดี [ไม่ใช่แท็ก] และ [[ข้อความ]] ปกติ", None))
        self.assertEqual(stream(["จบด้วย ["]), ("จบด้วย [", None))

    def test_streaming_holds_only_from_marker_start(self):
        markers = scenes.MarkerFilter()
        self.assertEqual(markers.feed("ก่อนหน้า [[scene:"), "ก่อนหน้า ")
        self.assertEqual(markers.feed("sickbed01]]"), "")
        self.assertEqual(markers.finish(), ("", "sickbed01"))

    def test_accept_only_offered_ids(self):
        self.assertEqual(scenes.accept("sickbed01", [SICK]), "sickbed01")
        self.assertIsNone(scenes.accept("kitchen01", [SICK]))
        self.assertIsNone(scenes.accept(None, [SICK]))

    def test_prompt_block_lists_only_eligible_scenes(self):
        block = scenes.prompt_block(scenes.eligible([SICK, KITCHEN], turns=1))
        self.assertIn("sickbed01", block)
        self.assertNotIn("kitchen01", block)
        self.assertIn("[[scene:ID]]", block)
        self.assertEqual(scenes.prompt_block([]), "")

    def test_reminder_sits_right_before_newest_user_message(self):
        from elyra.context import build_context
        character = {"name": "ซออา", "age": 27, "description": "x", "personality": "y", "greeting": "สวัสดี"}
        history = [{"role": "assistant", "content": "สวัสดี"}, {"role": "user", "content": "u1"}, {"role": "assistant", "content": "a1"}]
        block = scenes.prompt_block([SICK])
        messages, _ = build_context(character, [], history, "ไปนอนเถอะ", "general", scene_prompt=block,
                                    scene_reminder=scenes.reminder("sickbed01"))
        self.assertEqual([m["role"] for m in messages[-2:]], ["system", "user"])
        self.assertIn("[[scene:ID]]", messages[-2]["content"])
        self.assertIn("sickbed01", messages[-2]["content"])  # tells the model which image is already shown
        plain, _ = build_context(character, [], history, "ไปนอนเถอะ", "general", scene_reminder=scenes.reminder())
        self.assertNotIn("[[scene:ID]]", json.dumps(plain, ensure_ascii=False))  # no scene list → no scene reminder

    def test_fallback_lets_model_decide_among_all_scenes(self):
        cowgirl = {"id": "cowgirl01", "media_id": MEDIA, "title": "The Cowgirl\xa0Sex", "description": "ขึ้นมาบนตัว", "tier": "common", "min_turns": 0}
        with mock.patch.object(providers, "complete", return_value='{"scene": "cowgirl01"}') as complete:
            self.assertEqual(scenes.fallback_pick("xai", "grok-4.3", [SICK, cowgirl], "งั้นขอ Cowgirl อีกรอบนะ", "...", "sickbed01"), "cowgirl01")
            offered = complete.call_args.args[2][1]["content"]
            self.assertIn("cowgirl01", offered)
            self.assertIn("sickbed01", offered)  # every eligible scene is offered
            self.assertIn("Currently shown: sickbed01", offered)
        with mock.patch.object(providers, "complete", return_value='{"scene": null}'):
            self.assertIsNone(scenes.fallback_pick("xai", "grok-4.3", [SICK, cowgirl], "พี่ชอบผลไม้อะไร", "มะม่วงสิ"))
        with mock.patch.object(providers, "complete", return_value='{"scene": "cowgirl01"}'):
            # "same situation" comes back as the current id; resolve_variant decides (no change for single scenes)
            self.assertEqual(scenes.fallback_pick("xai", "grok-4.3", [cowgirl], "x", "y", current_scene_id="cowgirl01"), "cowgirl01")
            self.assertIsNone(scenes.resolve_variant("cowgirl01", [cowgirl], "cowgirl01", []))
        with mock.patch.object(providers, "complete") as complete:
            self.assertIsNone(scenes.fallback_pick("xai", "grok-4.3", [], "x", "y"))
            complete.assert_not_called()  # character has no scene images

    def test_identical_descriptions_rotate_as_variants(self):
        bath = lambda n: {**SICK, "id": f"bath{n}xx", "title": f"Bathroom {n}", "description": "Bathroom\xa0sex "}
        group = [bath(1), bath(2), bath(3), KITCHEN]
        # The model always names the first variant; uncollected variants are shown first.
        self.assertEqual(scenes.resolve_variant("bath1xx", group, None, []), "bath1xx")
        self.assertEqual(scenes.resolve_variant("bath1xx", group, "bath1xx", ["scene:bath1xx"]), "bath2xx")
        self.assertEqual(scenes.resolve_variant("bath1xx", group, "bath2xx", ["scene:bath1xx", "scene:bath2xx"]), "bath3xx")
        # All collected: staying in the same situation rotates to the next variant, wrapping around.
        everything = ["scene:bath1xx", "scene:bath2xx", "scene:bath3xx"]
        self.assertEqual(scenes.resolve_variant("bath3xx", group, "bath3xx", everything), "bath1xx")
        # Coming from another scene with everything collected keeps the model's pick.
        self.assertEqual(scenes.resolve_variant("bath2xx", group, "kitchen01", everything), "bath2xx")
        self.assertEqual(scenes.resolve_variant("kitchen01", group, None, []), "kitchen01")
        self.assertIsNone(scenes.resolve_variant("missing", group, None, []))
        numbered = [{**SICK, "id": "nb1xxxxx", "description": "Bathroom sex 1"}, {**SICK, "id": "nb2xxxxx", "description": "Bathroom sex (2)"}]
        self.assertEqual(scenes.resolve_variant("nb1xxxxx", numbered, "nb1xxxxx", ["scene:nb1xxxxx"]), "nb2xxxxx")

    def test_short_descriptions_get_distinctive_prompt_tags(self):
        look = "anime style, 1girl, long silver hair, purple eyes"
        car = {**SICK, "id": "car01xxx", "title": "Car sex", "description": "Car sex", "prompt": f"{look}, back seat of a car, night, city lights"}
        bath = {**SICK, "id": "bath01xx", "title": "Bathroom", "description": "Bathroom", "prompt": f"{look}, shower, steam, wet hair"}
        detailed = {**SICK, "id": "kitchen1", "description": "ใส่ผ้ากันเปื้อนทำอาหารในครัว หันมายิ้มให้ ตอนกลางวัน แดดส่องหน้าต่าง", "prompt": f"{look}, apron, kitchen"}
        labels = scenes.scene_labels([car, bath, detailed])
        self.assertEqual(labels["car01xxx"], "Car sex (image shows: back seat of a car, night, city lights)")
        self.assertNotIn("silver hair", labels["bath01xx"])  # shared character look is not distinctive
        self.assertNotIn("image shows", labels["kitchen1"])  # long descriptions are used as written
        self.assertIn("back seat of a car", scenes.prompt_block([car, bath]))

    def test_background_model_precedence(self):
        bg = providers.background_model
        self.assertEqual(bg("xai", "grok-4.3"), "grok-4.20-0309-non-reasoning")  # default for xAI
        self.assertEqual(bg("ollama", "llama3"), "llama3")  # other providers reuse the chat model
        with mock.patch.dict("os.environ", {"XAI_BACKGROUND_MODEL": "grok-env"}):
            self.assertEqual(bg("xai", "grok-4.3"), "grok-env")
            self.assertEqual(bg("xai", "grok-4.3", {"backgroundModels": {"xai": " grok-settings "}}), "grok-settings")
        self.assertEqual(bg("ollama", "llama3", {"backgroundModels": {"ollama": "qwen-small"}}), "qwen-small")
        self.assertEqual(bg("xai", "grok-4.3", {"backgroundModels": {"xai": ""}}), "grok-4.20-0309-non-reasoning")

    def test_settings_api_saves_background_models_and_can_update_rooms(self):
        import tempfile, threading, urllib.request
        from pathlib import Path
        from app import AppServer
        from elyra.store import Store
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "s.db")
            room = store.create_room("luna", "xai", "grok-4.3")
            server = AppServer(("127.0.0.1", 0), store)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                body = {"provider": "xai", "displayName": "Tester", "matureConfirmed": False,
                        "models": {"xai": "grok-4.20-0309-non-reasoning"}, "backgroundModels": {"xai": "grok-bg"}, "applyToRooms": True}
                request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/settings", method="POST",
                                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "X-Elyra-Token": server.token})
                saved = json.load(urllib.request.urlopen(request))
            finally:
                server.shutdown()
            self.assertEqual(saved["backgroundModels"]["xai"], "grok-bg")
            self.assertEqual(saved["roomsUpdated"], 1)
            self.assertEqual(store.room(room["id"])["model"], "grok-4.20-0309-non-reasoning")
            self.assertEqual(providers.background_model("xai", "grok-4.3", store.settings()), "grok-bg")

    def test_fallback_rejects_unoffered_ids_and_errors(self):
        with mock.patch.object(providers, "complete", return_value='{"scene": "kitchen01"}'):
            self.assertIsNone(scenes.fallback_pick("xai", "m", [SICK], "นอนป่วยบนเตียง", "..."))
        with mock.patch.object(providers, "complete", side_effect=providers.ProviderError("down")):
            self.assertIsNone(scenes.fallback_pick("xai", "m", [SICK], "นอนป่วยบนเตียง", "..."))

    def test_demo_pick_uses_description_words(self):
        self.assertEqual(scenes.demo_pick([SICK, KITCHEN], "*เธอนอนป่วยบนเตียง* อย่าไปไหนนะ"), "sickbed01")


class StoreSceneTest(unittest.TestCase):
    def test_set_scene_records_room_scene_and_unlock_once(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "t.db")
            room = store.create_room("luna", "demo", "story-demo")
            self.assertTrue(store.set_scene(room["id"], "sickbed01"))
            self.assertFalse(store.set_scene(room["id"], "sickbed01"))
            room = store.room(room["id"])
            self.assertEqual(room["scene_id"], "sickbed01")
            self.assertIn("scene:sickbed01", room["unlocks"])


if __name__ == "__main__":
    unittest.main()
