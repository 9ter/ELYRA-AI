import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elyra import providers, summary
from elyra.context import build_context
from elyra.store import Store

CHARACTER = {"name": "ซออา", "age": 27, "description": "พี่สาวข้างบ้าน", "personality": "ขี้แกล้ง", "greeting": "สวัสดี"}


def history(pairs, size=1000):
    messages = [{"role": "assistant", "content": "ทักทาย"}]
    for i in range(pairs):
        messages += [{"role": "user", "content": f"u{i} " + "ก" * size}, {"role": "assistant", "content": f"a{i} " + "ข" * size}]
    return messages


class PlanTest(unittest.TestCase):
    def test_below_trigger_does_nothing(self):
        self.assertIsNone(summary.plan(history(3), 0, "xai"))

    def test_cut_is_pair_aligned_and_keeps_recent_turns(self):
        messages = history(10)  # ~60 KB of Thai text
        cut = summary.plan(messages, 0, "xai")
        self.assertEqual(cut % 2, 1)
        self.assertEqual(messages[cut]["role"], "user")
        kept = sum(summary.pair_cost(messages[i:i + 2]) for i in range(cut, len(messages) - 1, 2))
        self.assertLessEqual(kept, summary.limits("xai")[1])
        self.assertGreater(kept, 0)

    def test_resumes_after_previous_summary(self):
        messages = history(10)
        first = summary.plan(messages, 0, "xai")
        self.assertIsNone(summary.plan(messages, first, "xai"))


class ContextWithSummaryTest(unittest.TestCase):
    def test_summarized_turns_replaced_by_summary(self):
        messages = history(4, size=10)
        built, info = build_context(CHARACTER, [], messages, "ต่อเลย", "general", summary="เคยไปทะเลด้วยกัน", summarized=5)
        contents = [m["content"] for m in built[1:]]
        self.assertIn("เคยไปทะเลด้วยกัน", built[0]["content"])
        self.assertFalse(any(c.startswith(("u0", "a0", "u1", "a1")) for c in contents))
        self.assertTrue(any(c.startswith("u2") for c in contents))
        self.assertNotIn("ทักทาย", contents)  # greeting is covered by the summary
        self.assertEqual(info["summarizedMessages"], 5)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.folder.name) / "s.db")
        self.room = self.store.create_room("luna", "xai", "grok-4.3")
        for i in range(10):
            self.store.commit_turn(self.room["id"], f"u{i} " + "ก" * 1000, f"a{i} " + "ข" * 1000, "xai", "grok-4.3")

    def tearDown(self):
        self.folder.cleanup()

    def test_run_saves_summary_and_count(self):
        with mock.patch.object(providers, "complete", return_value="  ซออาป่วย ผู้ใช้มาดูแล  ") as complete:
            self.assertTrue(summary.run(self.store, self.room["id"], "xai", "grok-4.3"))
        excerpt = complete.call_args.args[2][1]["content"]
        self.assertIn("u0", excerpt)
        self.assertNotIn("u9", excerpt)  # newest turns stay verbatim, not summarized
        room = self.store.room(self.room["id"])
        self.assertEqual(room["summary"], "ซออาป่วย ผู้ใช้มาดูแล")
        self.assertEqual(room["summary_count"] % 2, 1)

    def test_demo_and_provider_errors_leave_room_unchanged(self):
        self.assertFalse(summary.run(self.store, self.room["id"], "demo", "story-demo"))
        with mock.patch.object(providers, "complete", side_effect=providers.ProviderError("down")):
            with self.assertRaises(providers.ProviderError):
                summary.run(self.store, self.room["id"], "xai", "grok-4.3")
        self.assertEqual(self.store.room(self.room["id"])["summary_count"], 0)

    def test_save_summary_is_optimistic(self):
        self.assertTrue(self.store.save_summary(self.room["id"], "a", 5, 0))
        self.assertFalse(self.store.save_summary(self.room["id"], "b", 9, 0))
        self.assertEqual(self.store.room(self.room["id"])["summary"], "a")


if __name__ == "__main__":
    unittest.main()
