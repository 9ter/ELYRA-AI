import copy
import unittest

from elyra.context import build_context, history_repetition_note
from elyra.domain import CHARACTERS


def conversation(replies):
    history = [{"role": "assistant", "content": "ยินดีต้อนรับ"}]
    for reply in replies:
        history.extend([{"role": "user", "content": "ไปต่อเลย"},
                        {"role": "assistant", "content": reply}])
    return history


class HistoryStyleTests(unittest.TestCase):
    def test_copied_narration_detected_despite_varied_dialogue(self):
        history = conversation([
            f'*เธอเอียงคอมองออกไปนอกหน้าต่างก่อนยิ้มบาง ๆ*\n\nฉันเลือกหนังสือเล่มที่ {i}'
            for i in range(3)
        ])
        self.assertIn("narration", history_repetition_note(history))

    def test_dialogue_detected_across_punctuation_case_and_whitespace(self):
        history = conversation([
            '*เธอเปิดหนังสือ*\n\n"I will take care of the bookstore tomorrow."',
            '*เธอเก็บปากกา*\n\nI WILL take care of the bookstore tomorrow!',
            '*เธอเดินไปหน้าร้าน*\n\nI will  take care of the bookstore tomorrow',
        ])
        note = history_repetition_note(history)
        self.assertIn("dialogue", note)
        self.assertIn("Preserve facts, names and promises", note)
        self.assertNotIn("bookstore", note)  # story excerpts never become system instructions

    def test_one_reply_greeting_and_user_repetition_are_not_a_habit(self):
        text = "เธอเปิดประตูไม้เก่าแล้วเดินออกไปที่สวนหลังบ้าน"
        self.assertFalse(history_repetition_note(conversation([text * 6])))
        history = conversation([text, "เธอจดรายการของที่ต้องซื้อ", "เธอเตรียมแก้วกาแฟ"])
        history[0]["content"] = text
        for message in history:
            if message["role"] == "user":
                message["content"] = text
        self.assertFalse(history_repetition_note(history))

    def test_shared_short_names_and_varied_replies_do_not_trigger(self):
        history = conversation([
            "มะลิวางหนังสือบนชั้นอย่างเป็นระเบียบ",
            "มะลิเดินไปเติมน้ำดื่มในครัว",
            "มะลิเริ่มตรวจรายการสินค้าคงคลัง",
            "มะลิบอกเวลาเปิดร้านของวันพรุ่งนี้",
        ])
        self.assertFalse(history_repetition_note(history))

    def test_old_wording_expires_and_narration_is_separate_from_dialogue(self):
        text = "เธอเอียงคอมองออกไปนอกหน้าต่างก่อนยิ้มบาง ๆ"
        history = conversation([text, f"*{text}*", text])
        self.assertFalse(history_repetition_note(history))
        history = conversation([text] * 3)
        self.assertTrue(history_repetition_note(history))
        history.extend(conversation([f"บันทึกลำดับ {i}" for i in range(8)])[1:])
        self.assertFalse(history_repetition_note(history))

    def test_context_adds_nudge_without_rewriting_history_or_new_user_input(self):
        history = conversation(['*เธอจัดหนังสือบนชั้นแล้วเลื่อนเก้าอี้เข้าที่เดิม*\n\nเสร็จแล้ว'] * 3)
        original = copy.deepcopy(history)
        for mode in ("general", "mature"):
            with self.subTest(mode=mode):
                messages, info = build_context(CHARACTERS[0], [], history, "เปลี่ยนไปเดินเล่น", mode)
                self.assertIn("History wording check", messages[-2]["content"])
                self.assertEqual(messages[1:-2], history)
                self.assertEqual(messages[-1], {"role": "user", "content": "เปลี่ยนไปเดินเล่น"})
                self.assertEqual(info["includedMessages"], len(history))
                self.assertEqual(history, original)

    def test_all_style_nudges_fit_local_budget_and_keep_core_limits(self):
        reply = '*เธอเอียงคอมองออกไปนอกหน้าต่างก่อนยิ้มบาง ๆ*\n\n"ไปดูหนังสือที่ร้านด้วยกันไหม"'
        history = conversation([reply] * 4)
        character = {**CHARACTERS[0], "personality": "ก" * 3000}
        messages, _ = build_context(character, [], history, "ข" * 1000, "mature", provider="ollama")
        self.assertIn("History wording check", messages[-2]["content"])
        self.assertIn("Initiative check", messages[-2]["content"])
        self.assertIn("minors", messages[0]["content"])
        self.assertIn("non-consent", messages[0]["content"])
        self.assertLessEqual(sum(len(m["content"].encode("utf-8")) for m in messages), 6400)


if __name__ == "__main__":
    unittest.main()
