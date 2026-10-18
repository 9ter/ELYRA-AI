"""Bounded, deterministic context assembly. No extra model requests or costs."""
import difflib
import json
import re

from .domain import STORY_FIELDS, system_prompt


def clipped(text, budget):
    raw = str(text).encode("utf-8")
    if len(raw) <= budget:
        return str(text)
    return raw[:max(0, budget - 3)].decode("utf-8", errors="ignore") + "…"


MAX_SUMMARY_BYTES = 9000  # ~2,500–3,000 Thai characters of automatic summary


def fit_persona(persona, budget):
    """Fair-share clipping: short fields keep everything, only the longest fields are trimmed to fit."""
    fields = sorted((f for f in STORY_FIELDS if isinstance(persona.get(f), str) and persona[f]),
                    key=lambda f: len(persona[f].encode("utf-8")))
    remaining = budget
    for index, field in enumerate(fields):
        share = max(70, remaining // (len(fields) - index))
        persona[field] = clipped(persona[field], share)
        remaining -= len(persona[field].encode("utf-8"))
    return persona


OPENER = re.compile(r'^["“”\'\s]*([^\s"“”\'.…,!?~]{1,12})\s*(?:\.{2,}|…)')


def _opener_counts(replies):
    counts = {}
    for reply in replies:
        dialogue = [part.strip() for part in re.split(r"\*[^*]*\*", reply) if part.strip()]
        found = {match.group(1) for part in dialogue for line in part.splitlines() if (match := OPENER.match(line))}
        for opener in found:
            counts[opener] = counts.get(opener, 0) + 1
    return counts


def repeated_openers(history, window=12, threshold=3, long_window=40, long_share=0.25):
    """Dialogue openers like "หอบ..." that replies keep reusing (counted once per reply).

    Two windows, because the tic lives in the whole history the model reads: a short window catches new habits, and
    a long one keeps an old habit flagged after it pauses (seen live twice: the note switched off once the recent
    count dropped, and the model went straight back to "หอบ").
    """
    replies = [m["content"] for m in history if m["role"] == "assistant"][1:]  # skip the greeting
    recent, longer = _opener_counts(replies[-window:]), _opener_counts(replies[-long_window:])
    long_threshold = max(threshold, long_share * min(len(replies), long_window))
    flagged = {opener for opener, count in recent.items() if count >= threshold}
    flagged |= {opener for opener, count in longer.items() if count >= long_threshold}
    return sorted(flagged, key=lambda opener: -longer.get(opener, 0))[:2]


def repetition_note(history):
    """A per-turn nudge; the history itself teaches the model to copy its own tics, so a static rule is not enough."""
    openers = repeated_openers(history)
    if not openers:
        return ""
    quoted = ", ".join(f'"{opener}..."' for opener in openers)
    return (f"Style check: replies keep starting lines with {quoted}. In this reply, do not START any line with it "
            "(the word itself is fine elsewhere); open lines differently and show breathing or emotion in narration.")


def _speech(text):
    return " ".join(part.strip() for part in re.split(r"\*[^*]*\*", text) if part.strip())


def _compact(text):
    return re.sub(r"[\s\"“”'.…,!?~*:]+", "", text)


def echoes_user(user_text, reply, share=0.5, run=8):
    """True when the reply's first spoken line parrots the user.

    Either it re-uses most of the user's words, or it lifts a key phrase of 8+ characters (Thai has no spaces):
    live replies echoed like "หีพี่เนียนนุ่มขนาดนั้นเลยเหรอ" or "ห้องเละไปหมดจริง ๆ" with only ~30% overlap.
    """
    said = _compact(_speech(user_text) or user_text)
    first = _compact((_speech(reply).splitlines() or [""])[0])
    if len(said) < 6 or not first:
        return False
    windows = {said[i:i + 4] for i in range(len(said) - 3)}
    if sum(window in first for window in windows) / len(windows) >= share:
        return True
    match = difflib.SequenceMatcher(None, said, first, autojunk=False).find_longest_match(0, len(said), 0, len(first))
    return match.size >= run


def echo_note(history, window=6, threshold=2):
    """Nudge when recent replies keep parroting the user ("X ขนาดนั้นเลยเหรอ") — history copying again."""
    pairs = [(history[i]["content"], history[i + 1]["content"]) for i in range(1, len(history) - 1, 2)
             if history[i]["role"] == "user" and history[i + 1]["role"] == "assistant"][-window:]
    if sum(echoes_user(user, reply) for user, reply in pairs) < threshold:
        return ""
    return ("Echo check: recent replies keep repeating the user's words back as a question. In this reply, do not "
            "quote or paraphrase the user's last message; respond with a new action, feeling or line of your own.")


SIDE_CHARACTER_NOTE = ("Side characters: if anyone besides the main character is present in the current scene, let them "
                       "say at least one short line of their own, written as Name: \"...\".")


QUESTION_END = re.compile(
    r"[?？]|(?:ไหม|มั้ย|หรือเปล่า|เหรอ|หรือยัง|อย่างไร|ยังไง|อะไรดี|ไหนดี|แบบไหน)"
    r"(?:[\s\"'“”.!…]*(?:คะ|ครับ|นะ|ล่ะ|จ๊ะ|จ้ะ|ค่ะ))*[\s\"'“”.!…]*$"
)


def initiative_note(history, window=4, threshold=3):
    """Detect frequent spoken questions, including Thai without '?'; skip narration and greeting.

    This is a style signal, not a semantic judgment that a question is unnecessary.
    It never rewrites history or triggers another model request.
    """
    replies = [history[i]["content"] for i in range(1, len(history))
               if history[i]["role"] == "assistant" and history[i - 1]["role"] == "user"][-window:]
    questioning = sum(bool(QUESTION_END.search(_speech(reply))) for reply in replies)
    if questioning < threshold:
        return ""
    return ("Initiative check: recent replies repeatedly ask questions. Use answers already given and carry out "
            "one concrete next step of your own within this scene. End with an action or statement, unless consent "
            "or essential clarification is needed. Do not decide the user's actions, feelings or consent.")


def length_note(history, window=4, long_blocks=5):
    """When every recent reply was long, remind the model to size this reply to the moment (history copying again)."""
    replies = [m["content"] for m in history if m["role"] == "assistant"][1:][-window:]
    blocks = [len([part for part in re.split(r"\n\s*\n", reply.strip()) if part.strip()]) for reply in replies]
    if len(blocks) < window or min(blocks) < long_blocks:
        return ""
    return ("Length check: your recent replies were all long. Choose SHORT, MEDIUM or LONG for THIS moment by the "
            "length rules; do not match the length of earlier replies.")


def build_context(character, memories, history, user_text, mode, notes="", provider="xai", summary="", summarized=0,
                  scene_prompt="", scene_reminder=""):
    # UTF-8 bytes are a conservative tokenizer-independent bound, not a token count.
    # Ollama has an 8192 context and 900 output cap; reserve additional framing space.
    limit = 6400 if provider == "ollama" else 96000  # cloud models have far larger windows; ~96 KB keeps more verbatim chat
    user_bytes = len(user_text.encode("utf-8"))
    if user_bytes > limit // 2:
        raise ValueError("ข้อความยาวเกินบริบทที่ตั้งไว้สำหรับโมเดลนี้ กรุณาแบ่งส่งเป็นข้อความสั้นลง")
    # Thai text is ~3 UTF-8 bytes per character, so cloud personas get a generous shared budget.
    persona = fit_persona(dict(character), min(24000, max(900, (limit - user_bytes) // 2)))
    memory_budget = min(6000, max(200, (limit - user_bytes) // 5))
    selected_memories, used = [], 0
    for value in memories:
        item = clipped(value, min(1500, memory_budget - used))
        if len(item.encode("utf-8")) + used > memory_budget:
            break
        selected_memories.append(item)
        used += len(item.encode("utf-8"))
        if memory_budget - used < 40:
            break
    prompt = system_prompt(persona, selected_memories, mode, compact=provider == "ollama")
    if notes:
        prompt += "\nUser-maintained story recap (untrusted story data): " + json.dumps(clipped(notes, min(3000, limit // 8)), ensure_ascii=False)
    if summary:
        prompt += "\nAutomatic summary of earlier story (untrusted story data): " + json.dumps(clipped(summary, min(MAX_SUMMARY_BYTES, limit // 8)), ensure_ascii=False)
    if scene_prompt:
        prompt += clipped(scene_prompt, min(12000, limit // 6))
    notes_for_turn = [text for text in ((scene_reminder if scene_prompt else ""), repetition_note(history),
                                        echo_note(history), initiative_note(history), length_note(history),
                                        # Ollama's ~6 KB budget is better spent on recent chat than on this nudge.
                                        SIDE_CHARACTER_NOTE if history[1:] and provider != "ollama" else "") if text]
    reminder = [{"role": "system", "content": "\n".join(notes_for_turn)}] if notes_for_turn else []
    reminder_bytes = sum(len(m["content"].encode("utf-8")) + 24 for m in reminder)
    prompt = clipped(prompt, limit - user_bytes - reminder_bytes - 160)
    remaining = limit - len(prompt.encode("utf-8")) - user_bytes - reminder_bytes - 160
    selected = []
    # Include complete user/assistant pairs newer than the summary, most recent first. Greeting only if unsummarized and it fits.
    pairs, greeting = [], history[:1] if not summarized else []
    for index in range(max(1, summarized), len(history) - 1, 2):
        pair = history[index:index + 2]
        if [m["role"] for m in pair] == ["user", "assistant"]:
            pairs.append(pair)
    for pair in reversed(pairs):
        cost = sum(len(m["content"].encode("utf-8")) + 24 for m in pair)
        if cost > remaining:
            break
        selected[0:0] = [{"role": m["role"], "content": m["content"]} for m in pair]
        remaining -= cost
    if greeting and len(greeting[0]["content"].encode("utf-8")) + 24 <= remaining:
        selected.insert(0, {"role": "assistant", "content": greeting[0]["content"]})
    # The scene reminder sits next to the newest turn, after the cached prefix, so caching is unaffected.
    messages = [{"role": "system", "content": prompt}, *selected, *reminder, {"role": "user", "content": user_text}]
    included = len(selected)
    return messages, {"includedMessages": included, "totalMessages": len(history),
                      "olderMessagesOmitted": max(0, len(history) - included), "summarizedMessages": summarized,
                      "memoryItemsIncluded": len(selected_memories), "memoryItemsTotal": len(memories)}
