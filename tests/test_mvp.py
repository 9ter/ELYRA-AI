"""Local MVP integration checks, using isolated data and mocked model streams."""
import base64
import binascii
import json
import sqlite3
import struct
import unittest
import urllib.error
import zlib
from pathlib import Path
from unittest.mock import patch

import test_app
from elyra.context import build_context
from elyra.domain import CHARACTERS
from elyra.store import Store


def png_image():
    def chunk(kind, data):
        return struct.pack(">I",len(data)) + kind + data + struct.pack(">I",binascii.crc32(kind+data)&0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR",struct.pack(">IIBBBBB",1,1,8,2,0,0,0)) + chunk(b"IDAT",zlib.compress(b"\x00\x80\x40\xc0")) + chunk(b"IEND",b"")


class MvpTests(unittest.TestCase):
    request = test_app.AppTests.request
    json = test_app.AppTests.json
    room = test_app.AppTests.room
    chat = test_app.AppTests.chat

    @classmethod
    def setUpClass(cls):
        test_app.AppTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        test_app.AppTests.tearDownClass.__func__(cls)

    def character(self, **changes):
        return self.json("/api/characters", {"name":"Nova", "age":26,"description":"นักเดินทาง",
            "personality":"ใจดีและเคารพขอบเขต","greeting":"สวัสดี", "art":"luna", **changes})

    def media(self):
        return self.json("/api/media", {"data":base64.b64encode(png_image()).decode()})

    def stream_request(self, room_id, text, request_id):
        with patch("app.time.sleep"), self.request(f"/api/rooms/{room_id}/chat", {"text":text,"requestId":request_id}) as response:
            return [json.loads(line) for line in response if line.strip()]

    def test_raster_upload_and_safe_serving(self):
        media = self.media()
        with self.request(media["url"]) as response:
            self.assertEqual(response.headers["Content-Type"],"image/png")
            self.assertEqual(response.headers["X-Content-Type-Options"],"nosniff")
            self.assertEqual(response.read(),png_image())

    def test_upload_rejects_executable_and_damaged_images(self):
        for raw in (b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',png_image()[:-3],b"<html>"*20):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.json("/api/media",{"data":base64.b64encode(raw).decode()})
            self.assertEqual(raised.exception.code,400)

    def test_character_media_and_tips_roundtrip(self):
        media = self.media()
        character = self.character(tips="เริ่มเรื่องด้วยการชวนคุยเรื่องดวงดาว",portrait_id=media["id"],gallery={"first-light":media["id"]})
        room = self.room(characterId=character["id"])
        self.assertEqual(room["character"]["tips"],character["tips"])
        self.assertEqual(room["character"]["portrait_id"],media["id"])
        done = self.chat(room["id"])[-1]
        self.assertEqual(done["unlocked"],[])  # milestones retired; the legacy gallery field still round-trips
        self.assertEqual(self.store.character(character["id"])["gallery"]["first-light"],media["id"])

    def test_missing_media_reference_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.character(portrait_id="a"*64)
        with self.assertRaises(urllib.error.HTTPError):
            self.character(gallery={"invalid-milestone":"b"*64})

    def test_versioned_edit_preserves_existing_story(self):
        character = self.character(name="Nova original",tips="Old tips")
        room = self.room(characterId=character["id"])
        updated = self.json(f"/api/characters/{character['id']}/update",{**character,"name":"Nova revised","tips":"New tips","expectedVersion":1})
        self.assertEqual(updated["version"],2)
        old_room = self.store.room(room["id"])
        self.assertEqual(old_room["character"]["name"],"Nova original")
        self.assertEqual(old_room["character"]["tips"],"Old tips")
        new_room = self.room(characterId=character["id"])
        self.assertEqual(new_room["character"]["name"],"Nova revised")
        with self.assertRaises(urllib.error.HTTPError):
            self.json(f"/api/characters/{character['id']}/update",{**character,"name":"Stale edit","expectedVersion":1})
        self.assertEqual(self.store.character(character["id"])["name"],"Nova revised")

    def test_original_characters_cannot_be_edited(self):
        with self.assertRaises(urllib.error.HTTPError):
            self.json("/api/characters/luna/update",{**CHARACTERS[0],"expectedVersion":1})

    def test_archive_restore_preserves_chat_and_gallery(self):
        character = self.character()
        room = self.room(characterId=character["id"])
        self.chat(room["id"])
        self.json(f"/api/characters/{character['id']}/archive",{"archived":True})
        with self.assertRaises(urllib.error.HTTPError):
            self.room(characterId=character["id"])
        self.assertEqual(self.store.room(room["id"])["turns"],1)
        self.assertEqual(len(self.store.room(room["id"])["messages"]),3)  # chat history kept while archived
        self.json(f"/api/characters/{character['id']}/archive",{"archived":False})
        self.assertTrue(self.room(characterId=character["id"])["id"])

    def test_request_retry_does_not_call_model_or_commit_twice(self):
        room = self.room(provider="xai",model="grok-4.3")
        with patch("elyra.providers.stream",side_effect=lambda *args: iter(["สวัสดี"])) as call:
            first = self.stream_request(room["id"],"hello","same-request-001")[-1]
            second = self.stream_request(room["id"],"hello","same-request-001")[-1]
        self.assertEqual(call.call_count,1)
        self.assertEqual(first["room"]["turns"],1)
        self.assertTrue(second["replayed"])
        self.assertEqual(second["room"]["turns"],1)
        self.assertEqual(second["unlocked"],[])

    def test_reused_request_id_cannot_change_text(self):
        room = self.room()
        self.stream_request(room["id"],"first","same-request-002")
        with self.assertRaises(urllib.error.HTTPError):
            self.stream_request(room["id"],"different","same-request-002")
        self.assertEqual(self.store.room(room["id"])["turns"],1)

    def test_story_notes_are_room_scoped_and_enter_context(self):
        room, other = self.room(provider="xai",model="grok-4.3"), self.room()
        self.json(f"/api/rooms/{room['id']}/notes",{"content":"ตอนนี้อยู่ที่หอดูดาว"})
        with patch("elyra.providers.stream",side_effect=lambda *args: iter(["รับทราบ"])) as call:
            self.stream_request(room["id"],"คุยต่อ","notes-request-001")
        self.assertIn("ตอนนี้อยู่ที่หอดูดาว",call.call_args.args[2][0]["content"])
        self.assertEqual(self.store.room(other["id"])["notes"],"")

    def test_branch_stops_at_selected_message_without_future_memories(self):
        room = self.room()
        self.json(f"/api/rooms/{room['id']}/memory",{"content":"Earlier memory"})
        first = self.chat(room["id"])[-1]["room"]
        target = first["messages"][-1]
        self.json(f"/api/rooms/{room['id']}/memory",{"content":"Future memory"})
        self.chat(room["id"])
        self.json(f"/api/rooms/{room['id']}/notes",{"content":"Future story recap"})
        branch = self.json(f"/api/rooms/{room['id']}/branch",{"messageId":target["id"]})
        self.assertEqual(branch["turns"],1)
        self.assertEqual(branch["parent_room_id"],room["id"])
        self.assertEqual(branch["notes"],"")
        self.assertEqual([m["content"] for m in branch["memories"]],["Earlier memory"])
        self.assertEqual([m["content"] for m in branch["messages"]],[m["content"] for m in first["messages"]])
        self.assertEqual(self.store.room(room["id"])["turns"],2)

    def test_export_contains_user_images_and_snapshots(self):
        media = self.media()
        character = self.character(portrait_id=media["id"])
        room = self.room(characterId=character["id"])
        export = self.json("/api/export")
        self.assertEqual(export["format"],"elyra-local-v2")
        self.assertTrue(any(item["id"]==media["id"] and base64.b64decode(item["data"])==png_image() for item in export["media"]))
        self.assertEqual(next(item for item in export["rooms"] if item["id"]==room["id"])["character"]["portrait_id"],media["id"])

    def test_existing_database_is_backed_up_and_migrated(self):
        path = Path(self.temp.name)/"legacy.db"
        db=sqlite3.connect(path)
        db.executescript("""CREATE TABLE characters(id TEXT PRIMARY KEY,data TEXT NOT NULL);
          CREATE TABLE rooms(id TEXT PRIMARY KEY,character_id TEXT NOT NULL,provider TEXT NOT NULL,
          model TEXT NOT NULL,mode TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);""")
        db.execute("INSERT INTO characters VALUES (?,?)",("luna",json.dumps(CHARACTERS[0])))
        db.execute("INSERT INTO rooms VALUES ('old-room','luna','demo','story-demo','general','2026-10-17','2026-10-17')")
        db.commit(); db.close()
        migrated=Store(path)
        self.assertTrue(path.with_suffix(".before-mvp.sqlite3").exists())
        self.assertEqual(migrated.room("old-room")["character"]["name"],"Luna")
        self.assertEqual(migrated.room("old-room")["notes"],"")


class ContextTests(unittest.TestCase):
    def test_context_is_bounded_and_retains_complete_recent_pairs(self):
        history=[{"role":"assistant","content":"Greeting"}]
        for index in range(80):
            history.extend([{"role":"user","content":f"User {index} "+"ก"*300},{"role":"assistant","content":f"Answer {index} "+"ข"*300}])
        messages,info=build_context(CHARACTERS[0],["Known fact"],history,"Continue","general","At the observatory", "ollama")
        self.assertLessEqual(sum(len(m["content"].encode()) for m in messages),6400)
        self.assertEqual(messages[-1]["content"],"Continue")
        conversation=[m for m in messages[:-1] if m["role"]!="system"]  # skip per-turn notes before the user message
        self.assertIn("Answer 79",conversation[-1]["content"])
        self.assertGreater(info["olderMessagesOmitted"],0)
        self.assertIn("Known fact",messages[0]["content"])
        self.assertIn("At the observatory",messages[0]["content"])

    def test_long_local_input_has_actionable_error(self):
        with self.assertRaises(ValueError):
            build_context(CHARACTERS[0],[],[],"ก"*3000,"general",provider="ollama")


if __name__=="__main__":
    unittest.main()
