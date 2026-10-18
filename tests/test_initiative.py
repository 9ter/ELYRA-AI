import unittest

from elyra.context import build_context, initiative_note
from elyra.domain import CHARACTERS, system_prompt


def conversation(replies):
    history = [{"role": "assistant", "content": "พร้อมหรือยัง?"}]
    for reply in replies:
        history.extend([{"role": "user", "content": "ไปที่ร้านกาแฟเลย"},
                        {"role": "assistant", "content": reply}])
    return history


class InitiativeTests(unittest.TestCase):
    def test_conflict_continuity_reaches_existing_rooms_without_rewriting_an_exit(self):
        history = conversation(['*เธอออกจากร้านไปยืนใต้กันสาด*\n\nฉันขอสงบใจก่อน'])
        original = [dict(message) for message in history]
        for provider in ("xai", "openai", "ollama"):
            for mode in ("general", "mature"):
                with self.subTest(provider=provider, mode=mode):
                    messages, info = build_context(CHARACTERS[0], [], history,
                                                  "*ฉันส่งข้อความขอโทษ*", mode, provider=provider)
                    prompt = messages[0]["content"]
                    self.assertIn("not an automatic", prompt)
                    self.assertIn("next action", prompt)
                    self.assertIn("consequence", prompt)
                    self.assertIn("consent", prompt)
                    self.assertEqual(messages[1:1 + len(history)], original)
                    self.assertEqual(info["includedMessages"], len(history))
                    self.assertEqual(history, original)
                    self.assertEqual(messages[-1]["content"], "*ฉันส่งข้อความขอโทษ*")

    def test_character_and_player_can_both_influence_the_scene(self):
        for mode in ("general", "mature"):
            with self.subTest(mode=mode):
                prompt = system_prompt(CHARACTERS[0], [], mode)
                for phrase in ("Character agency", "may disagree, negotiate", "do not automatically agree",
                               "Shared direction", "latest proposed direction", "one concrete action",
                               "interrupt, respond or steer", "not a template to copy"):
                    self.assertIn(phrase, prompt)
                local = system_prompt(CHARACTERS[0], [], mode, compact=True)
                self.assertIn("user may persuade or redirect", local)
                self.assertIn("leave the user's choices open", local)

    def test_thai_questions_without_punctuation_trigger_nudge(self):
        history = conversation(['*เธอยิ้ม*\n\n"ไปกันไหมคะ"',
                                '"อยากไปไหนดี"', '"พร้อมหรือยัง"'])
        self.assertTrue(initiative_note(history))
        messages, _ = build_context(CHARACTERS[0], [], history, "อืม", "general")
        self.assertEqual(messages[-2]["role"], "system")
        self.assertIn("Initiative check", messages[-2]["content"])
        self.assertEqual(messages[-1]["content"], "อืม")
        self.assertEqual([m for m in messages[1:-2]], history)

    def test_greeting_narration_and_occasional_questions_do_not_trigger(self):
        self.assertFalse(initiative_note(conversation([])))
        self.assertFalse(initiative_note(conversation([
            '*ป้ายเขียนว่า "ไปไหน?"*\n\n"ฉันจะเปิดร้านแล้ว"'] * 4)))
        self.assertFalse(initiative_note(conversation([
            '"ไปกันไหม"', '"ฉันเปิดประตูร้าน"', '"ฉันสั่งกาแฟแล้ว"', '"รับชาไหมคะ"'])))

    def test_question_habit_expires_after_varied_replies(self):
        history = conversation(['"What next?"'] * 3)
        self.assertTrue(initiative_note(history))
        history += conversation(['"ฉันเริ่มชงกาแฟ"'] * 4)[1:]
        self.assertFalse(initiative_note(history))

    def test_local_budget_includes_notes_even_with_large_persona_and_input(self):
        character = {**CHARACTERS[0], "personality": "ก" * 3000}
        history = conversation(['"ไปกันไหม"'] * 4)
        messages, _ = build_context(character, [], history, "ก" * 1000, "general",
                                    provider="ollama", summary="ข" * 3000)
        self.assertIn("Initiative check", messages[-2]["content"])
        self.assertLessEqual(sum(len(m["content"].encode("utf-8")) for m in messages), 6400)


if __name__ == "__main__":
    unittest.main()
