import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from elyra.context import build_context, fit_persona
from elyra.domain import system_prompt, validate_character

BASE = {"name": "ซออา", "age": 27, "description": "พี่สาวข้างบ้าน", "personality": "ขี้แกล้ง", "greeting": "สวัสดี", "art": "luna"}


def system_story(messages):
    prompt = messages[0]["content"]
    return json.loads(prompt.split("Character story data: ", 1)[1].split("\n", 1)[0])


class PersonaTest(unittest.TestCase):
    def test_detail_fields_validated_and_stored(self):
        character = validate_character({**BASE, "speech_style": "เรียกตัวเองว่าพี่", "example_dialogue": "ผู้ใช้: หวัดดี\nซออา: มาแล้วเหรอ เด็กดี",
                                        "likes": "ข้าวต้ม", "dislikes": "ถูกมองว่าอ่อนแอ", "reactions": "ถูกแกล้งกลับจะเขิน",
                                        "relationship_arc": "ค่อย ๆ เปิดใจ"})
        self.assertEqual(character["speech_style"], "เรียกตัวเองว่าพี่")
        self.assertEqual(character["relationship_arc"], "ค่อย ๆ เปิดใจ")
        for field, maximum in (("example_dialogue", 3000), ("personality", 3000), ("likes", 600)):
            with self.assertRaises(ValueError):
                validate_character({**BASE, field: "ก" * (maximum + 1)})

    def test_long_thai_persona_reaches_cloud_model_unclipped(self):
        # 2,500 Thai characters is ~7,500 UTF-8 bytes; the old per-field cap cut this at ~440 characters.
        character = validate_character({**BASE, "personality": "ก" * 2500, "example_dialogue": "ข" * 2500, "speech_style": "พูดช้า ๆ"})
        messages, _ = build_context(character, [], [], "สวัสดี", "general", provider="xai")
        story = system_story(messages)
        self.assertEqual(story["personality"], "ก" * 2500)
        self.assertEqual(story["example_dialogue"], "ข" * 2500)
        self.assertEqual(story["speech_style"], "พูดช้า ๆ")
        self.assertNotIn("likes", story)  # empty optional fields are omitted

    def test_fair_share_trims_only_longest_fields(self):
        persona = fit_persona({"name": "ซออา", "personality": "ก" * 3000, "likes": "ข้าวต้ม"}, budget=3000)
        self.assertEqual(persona["likes"], "ข้าวต้ม")
        self.assertEqual(persona["name"], "ซออา")
        self.assertTrue(persona["personality"].endswith("…"))
        self.assertLessEqual(sum(len(v.encode()) for v in persona.values()), 3000)

    def test_content_rules_depend_on_room_mode(self):
        character = validate_character(BASE)
        general = system_prompt(character, [], "general")
        mature = system_prompt(character, [], "mature")
        self.assertIn("NO explicit sexual content", general)
        self.assertNotIn("NO explicit sexual content", mature)
        self.assertIn("Explicit sexual content between consenting adult characters is allowed", mature)
        for prompt in (general, mature):
            self.assertIn("minors", prompt)
            self.assertIn("non-consent", prompt)
            self.assertIn("real people", prompt)

    def test_side_character_rules_in_prompt(self):
        prompt = system_prompt(validate_character(BASE), [], "mature")
        self.assertIn('Name: \\"...\\"', json.dumps(prompt))
        self.assertIn("Every side character is an adult", prompt)
        self.assertIn("clear consent", prompt)
        from elyra.summary import SUMMARY_PROMPT
        self.assertIn("side characters who appeared", SUMMARY_PROMPT)

    def test_echoing_the_user_is_detected_and_nudged(self):
        from elyra.context import echo_note, echoes_user
        self.assertTrue(echoes_user("พี่กระแทกได้ไม่มีเบื่อเลย", '*เธอยิ้ม*\n\n"พี่กระแทกได้ไม่มีเบื่อขนาดนั้นเลยเหรอ เด็กแสบ"'))
        self.assertFalse(echoes_user("พี่กระแทกได้ไม่มีเบื่อเลย", '*เธอหัวเราะ*\n\n"งั้นคืนนี้พี่ขอพักก่อนนะ"'))
        self.assertFalse(echoes_user("อืม", '"อืม... ว่าไง"'))  # too short to call it an echo
        history = [{"role": "assistant", "content": "ทักทาย"}]
        for text in ("หีพี่เนียนนุ่มใครจะอดใจไหว", "พี่กระแทกได้ไม่มีเบื่อเลย"):
            history += [{"role": "user", "content": text}, {"role": "assistant", "content": f'"{text}ขนาดนั้นเลยเหรอ เด็กแสบ"'}]
        self.assertIn("Echo check", echo_note(history))
        messages, _ = build_context(validate_character(BASE), [], history, "ต่อ", "general")
        self.assertIn("Echo check", messages[-2]["content"])
        self.assertIn("Do not open by repeating or paraphrasing", messages[0]["content"])

    def test_reply_length_is_adaptive_not_fixed(self):
        prompt = system_prompt(validate_character(BASE), [], "general")
        self.assertNotIn("By default, write 4-6", prompt)
        for phrase in ("SHORT (1-2 blocks)", "MEDIUM (2-4 blocks)", "LONG (4-6 blocks", "never pad"):
            self.assertIn(phrase, prompt)

    def test_repeated_dialogue_opener_gets_a_style_note(self):
        from elyra.context import repeated_openers
        reply = lambda i: f'*เธอยิ้ม*\n\n"หอบ... เรื่องที่ {i} นะ"\n\n*เธอมองนาย*\n\n"พี่ว่านะ"'
        history = [{"role": "assistant", "content": "ทักทาย"}]
        for i in range(4):
            history += [{"role": "user", "content": f"u{i}"}, {"role": "assistant", "content": reply(i)}]
        self.assertEqual(repeated_openers(history), ["หอบ"])
        messages, _ = build_context(validate_character(BASE), [], history, "ต่อ", "general")
        self.assertEqual(messages[-2]["role"], "system")
        self.assertIn('"หอบ..."', messages[-2]["content"])
        varied = [{"role": "assistant", "content": "ทักทาย"}] + [m for i in range(4) for m in (
            {"role": "user", "content": "u"}, {"role": "assistant", "content": f'"คำ{i}... อืม"'})]
        self.assertEqual(repeated_openers(varied), [])  # different openers → no note
        plain, _ = build_context(validate_character(BASE), [], varied, "ต่อ", "general")
        self.assertNotIn("Style check", plain[-2]["content"])
        self.assertIn("Side characters", plain[-2]["content"])  # the side-character nudge is always present mid-story

    def test_old_habit_stays_flagged_after_a_pause(self):
        from elyra.context import repeated_openers, repetition_note
        history = [{"role": "assistant", "content": "ทักทาย"}]
        for i in range(30):  # long habit, then 12 clean replies
            history += [{"role": "user", "content": "u"}, {"role": "assistant", "content": f'"หอบ... {i}"' if i < 18 else f'"ข้อ{i}"'}]
        self.assertIn("หอบ", repeated_openers(history))
        self.assertIn("do not START any line", repetition_note(history))

    def test_ollama_context_stays_bounded(self):
        character = validate_character({**BASE, "personality": "ก" * 3000, "backstory": "ข" * 3000, "example_dialogue": "ค" * 3000})
        messages, _ = build_context(character, [], [], "สวัสดี", "general", provider="ollama")
        self.assertLessEqual(len(messages[0]["content"].encode("utf-8")), 6400)


if __name__ == "__main__":
    unittest.main()
