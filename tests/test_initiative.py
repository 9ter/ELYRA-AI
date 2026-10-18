import unittest

from elyra.context import build_context, initiative_note
from elyra.domain import CHARACTERS


def conversation(replies):
    history = [{"role": "assistant", "content": "พร้อมหรือยัง?"}]
    for reply in replies:
        history.extend([{"role": "user", "content": "ไปที่ร้านกาแฟเลย"},
                        {"role": "assistant", "content": reply}])
    return history


class InitiativeTests(unittest.TestCase):
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
