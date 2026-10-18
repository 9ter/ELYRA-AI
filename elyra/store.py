"""SQLite persistence. Secrets are deliberately never stored here."""
import json
import base64
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .domain import ACTIVE_MILESTONES, CHARACTERS


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            old_columns = {row[1] for row in db.execute("PRAGMA table_info(rooms)")}
            if old_columns and "character_snapshot" not in old_columns:
                backup_path = self.path.with_suffix(".before-mvp.sqlite3")
                if not backup_path.exists():
                    backup_db = sqlite3.connect(backup_path)
                    try:
                        db.backup(backup_db)
                    finally:
                        backup_db.close()
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS characters(id TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS rooms(id TEXT PRIMARY KEY, character_id TEXT NOT NULL,
                    provider TEXT NOT NULL, model TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'general',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, room_id TEXT NOT NULL,
                    role TEXT NOT NULL, content TEXT NOT NULL, provider TEXT, model TEXT, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS messages_room ON messages(room_id, created_at);
                CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, room_id TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS unlocks(room_id TEXT NOT NULL, milestone_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, PRIMARY KEY(room_id, milestone_id));
                CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY, mime TEXT NOT NULL, data BLOB NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS turn_requests(room_id TEXT NOT NULL, request_id TEXT NOT NULL,
                    text_hash TEXT NOT NULL, PRIMARY KEY(room_id, request_id));
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(rooms)")}
            for column, definition in (("character_snapshot", "TEXT"), ("notes", "TEXT NOT NULL DEFAULT ''"),
                                       ("parent_room_id", "TEXT"), ("branch_message_id", "TEXT"),
                                       ("scene_id", "TEXT"), ("summary", "TEXT NOT NULL DEFAULT ''"),
                                       ("summary_count", "INTEGER NOT NULL DEFAULT 0")):
                if column not in columns:
                    db.execute(f"ALTER TABLE rooms ADD COLUMN {column} {definition}")
            for character in CHARACTERS:
                db.execute("INSERT OR IGNORE INTO characters VALUES (?,?)", (character["id"], json.dumps(character, ensure_ascii=False)))
            db.execute("""UPDATE rooms SET character_snapshot=(SELECT data FROM characters WHERE id=rooms.character_id)
                WHERE character_snapshot IS NULL""")
            db.execute("INSERT OR IGNORE INTO settings VALUES (1,?)", (json.dumps({
                "provider": "demo", "models": {"demo": "story-demo", "xai": "", "openai": "", "ollama": ""},
                "displayName": "Storyteller", "matureConfirmed": False}),))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def characters(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM characters ORDER BY rowid")]

    def character(self, character_id):
        with self.connect() as db:
            row = db.execute("SELECT data FROM characters WHERE id=?", (character_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def add_character(self, character):
        with self.connect() as db:
            db.execute("INSERT INTO characters VALUES (?,?)", (character["id"], json.dumps(character, ensure_ascii=False)))
        return character

    def update_character(self, character_id, data, expected_version):
        with self.connect() as db:
            previous = db.execute("SELECT data FROM characters WHERE id=?", (character_id,)).fetchone()
            if not previous:
                raise ValueError("ไม่พบตัวละครนี้")
            previous_raw = previous[0]
            previous = json.loads(previous_raw)
            if not previous.get("custom"):
                raise ValueError("กรุณาทำสำเนาตัวละครต้นแบบก่อนแก้ไข")
            if previous.get("version", 1) != expected_version:
                raise ValueError("ตัวละครถูกแก้ไขจากอีกหน้าต่างแล้ว กรุณาเปิดตัวแก้ไขใหม่")
            updated = {**data, "id": character_id, "version": expected_version + 1,
                       "archived": previous.get("archived", False)}
            cursor = db.execute("UPDATE characters SET data=? WHERE id=? AND data=?",
                (json.dumps(updated, ensure_ascii=False), character_id, previous_raw))
            if cursor.rowcount != 1:
                raise ValueError("ตัวละครถูกแก้ไขพร้อมกัน กรุณาเปิดตัวแก้ไขใหม่")
        return updated

    def archive_character(self, character_id, archived):
        with self.connect() as db:
            row = db.execute("SELECT data FROM characters WHERE id=?", (character_id,)).fetchone()
            if not row:
                raise ValueError("ไม่พบตัวละครนี้")
            original = row[0]
            character = json.loads(original)
            if not character.get("custom"):
                raise ValueError("เก็บเข้าคลังได้เฉพาะตัวละครที่คุณสร้าง")
            character["archived"] = archived
            character["version"] = character.get("version", 1) + 1
            changed = db.execute("UPDATE characters SET data=? WHERE id=? AND data=?",
                (json.dumps(character, ensure_ascii=False), character_id, original))
            if not changed.rowcount:
                raise ValueError("ข้อมูลเปลี่ยนแล้ว กรุณารีเฟรชก่อนลองอีกครั้ง")
        return character

    def add_media(self, media):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO media VALUES (?,?,?,?)", (media["id"], media["mime"], media["data"], now()))
        return {"id": media["id"], "url": "/media/" + media["id"]}

    def media(self, media_id):
        with self.connect() as db:
            row = db.execute("SELECT mime,data FROM media WHERE id=?", (media_id,)).fetchone()
            return dict(row) if row else None

    def validate_media_references(self, character):
        ids = [character.get("portrait_id", ""), *character.get("gallery", {}).values(),
               *(scene["media_id"] for scene in character.get("scenes", []))]
        for media_id in ids:
            if media_id and self.media(media_id) is None:
                raise ValueError("ไม่พบภาพที่เลือก กรุณาอัปโหลดอีกครั้ง")

    def settings(self):
        with self.connect() as db:
            return json.loads(db.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])

    def save_settings(self, settings):
        with self.connect() as db:
            db.execute("UPDATE settings SET data=? WHERE id=1", (json.dumps(settings, ensure_ascii=False),))
        return settings

    def rooms(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT r.*, COALESCE(r.character_snapshot,c.data) AS character_data,
                (SELECT content FROM messages WHERE room_id=r.id ORDER BY rowid DESC LIMIT 1) AS preview,
                (SELECT COUNT(*) FROM messages WHERE room_id=r.id AND role='user') AS turns
                FROM rooms r JOIN characters c ON c.id=r.character_id ORDER BY r.updated_at DESC""")]

    def create_room(self, character_id, provider, model, mode="general", snapshot=None):
        character = snapshot or self.character(character_id)
        if not character:
            raise ValueError("ไม่พบตัวละครนี้")
        if not snapshot and character.get("archived"):
            raise ValueError("กรุณานำตัวละครออกจากคลังก่อนเริ่มเรื่องใหม่")
        room_id, timestamp = uuid.uuid4().hex, now()
        with self.connect() as db:
            db.execute("""INSERT INTO rooms (id,character_id,provider,model,mode,created_at,updated_at,character_snapshot)
                VALUES (?,?,?,?,?,?,?,?)""", (room_id, character_id, provider, model, mode, timestamp, timestamp,
                    json.dumps(character, ensure_ascii=False)))
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, room_id, "assistant", character["greeting"], "greeting", "", timestamp))
        return self.room(room_id)

    def room(self, room_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            if not row:
                return None
            room = dict(row)
            snapshot = room.pop("character_snapshot", None)
            room["character"] = json.loads(snapshot) if snapshot else self.character(room["character_id"])
            room["messages"] = [dict(r) for r in db.execute("SELECT * FROM messages WHERE room_id=? ORDER BY rowid", (room_id,))]
            room["memories"] = [dict(r) for r in db.execute("SELECT * FROM memories WHERE room_id=? ORDER BY rowid DESC", (room_id,))]
            room["unlocks"] = [r[0] for r in db.execute("SELECT milestone_id FROM unlocks WHERE room_id=?", (room_id,))]
            room["turns"] = sum(m["role"] == "user" for m in room["messages"])
            return room

    def update_room(self, room_id, provider, model, mode):
        with self.connect() as db:
            db.execute("UPDATE rooms SET provider=?, model=?, mode=?, updated_at=? WHERE id=?", (provider, model, mode, now(), room_id))
        return self.room(room_id)

    def set_rooms_model(self, provider, model):
        """Switch every existing room of `provider` to `model`; returns how many rooms changed."""
        with self.connect() as db:
            return db.execute("UPDATE rooms SET model=? WHERE provider=? AND model<>?", (model, provider, model)).rowcount

    def request_completed(self, room_id, request_id, user_text):
        with self.connect() as db:
            row = db.execute("SELECT text_hash FROM turn_requests WHERE room_id=? AND request_id=?", (room_id, request_id)).fetchone()
            if row and row[0] != hashlib.sha256(user_text.encode()).hexdigest():
                raise ValueError("รหัสคำขอนี้ถูกใช้กับข้อความอื่นแล้ว กรุณาส่งเป็นคำขอใหม่")
            return bool(row)

    def commit_turn(self, room_id, user_text, assistant_text, provider, model, request_id=None):
        timestamp = now()
        unlocked = []
        with self.connect() as db:
            if request_id:
                db.execute("INSERT INTO turn_requests VALUES (?,?,?)", (room_id, request_id, hashlib.sha256(user_text.encode()).hexdigest()))
            for role, content in (("user", user_text), ("assistant", assistant_text)):
                db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, room_id, role, content, provider, model, timestamp))
            db.execute("UPDATE rooms SET updated_at=? WHERE id=?", (timestamp, room_id))
            turns = db.execute("SELECT COUNT(*) FROM messages WHERE room_id=? AND role='user'", (room_id,)).fetchone()[0]
            for milestone in ACTIVE_MILESTONES:
                if turns >= milestone["threshold"]:
                    cursor = db.execute("INSERT OR IGNORE INTO unlocks VALUES (?,?,?)", (room_id, milestone["id"], timestamp))
                    if cursor.rowcount:
                        unlocked.append(milestone)
        return unlocked

    def set_scene(self, room_id, scene_id):
        """Show a validated scene in the room; returns True when it is newly collected for this room."""
        with self.connect() as db:
            db.execute("UPDATE rooms SET scene_id=? WHERE id=?", (scene_id, room_id))
            cursor = db.execute("INSERT OR IGNORE INTO unlocks VALUES (?,?,?)", (room_id, "scene:" + scene_id, now()))
            return bool(cursor.rowcount)

    def summary_record(self, room_id):
        """Read just the recap fields for polling, without loading the entire chat history."""
        with self.connect() as db:
            row = db.execute("SELECT summary,summary_count FROM rooms WHERE id=?", (room_id,)).fetchone()
            return dict(row) if row else None

    def save_summary(self, room_id, summary, count, expected_count):
        """Optimistic write: skipped if another summary run already advanced this room."""
        with self.connect() as db:
            cursor = db.execute("UPDATE rooms SET summary=?, summary_count=? WHERE id=? AND summary_count=?",
                                (summary, count, room_id, expected_count))
            return bool(cursor.rowcount)

    def save_notes(self, room_id, content):
        with self.connect() as db:
            db.execute("UPDATE rooms SET notes=?,updated_at=? WHERE id=?", (content, now(), room_id))
        return self.room(room_id)

    def branch_room(self, room_id, message_id):
        original = self.room(room_id)
        index = next((i for i, message in enumerate(original["messages"]) if message["id"] == message_id), None)
        if index is None or original["messages"][index]["role"] != "assistant":
            raise ValueError("กรุณาเลือกข้อความตอบของตัวละครเพื่อแตกเส้นเรื่อง")
        messages = original["messages"][:index + 1]
        cutoff = messages[-1]["created_at"]
        room = {"id": uuid.uuid4().hex}
        timestamp = now()
        with self.connect() as db:
            db.execute("""INSERT INTO rooms (id,character_id,provider,model,mode,created_at,updated_at,character_snapshot)
                VALUES (?,?,?,?,?,?,?,?)""", (room["id"], original["character_id"], original["provider"],
                original["model"], original["mode"], timestamp, timestamp,
                json.dumps(original["character"], ensure_ascii=False)))
            for message in messages:
                db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, room["id"], message["role"],
                    message["content"], message["provider"], message["model"], message["created_at"]))
            for memory in original["memories"]:
                if memory["created_at"] <= cutoff:
                    db.execute("INSERT INTO memories VALUES (?,?,?,?)", (uuid.uuid4().hex, room["id"], memory["content"], memory["created_at"]))
            turns = sum(m["role"] == "user" for m in messages)
            for milestone in ACTIVE_MILESTONES:
                if turns >= milestone["threshold"]:
                    db.execute("INSERT INTO unlocks VALUES (?,?,?)", (room["id"], milestone["id"], now()))
            db.execute("UPDATE rooms SET parent_room_id=?,branch_message_id=? WHERE id=?", (room_id, message_id, room["id"]))
        return self.room(room["id"])

    def add_memory(self, room_id, content):
        with self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM memories WHERE room_id=?", (room_id,)).fetchone()[0]
            if count >= 20:
                raise ValueError("บันทึกความจำได้สูงสุด 20 รายการต่อห้อง กรุณาลบบางรายการก่อน")
            memory_id = uuid.uuid4().hex
            db.execute("INSERT INTO memories VALUES (?,?,?,?)", (memory_id, room_id, content, now()))
        return self.room(room_id)

    def delete_memory(self, room_id, memory_id):
        with self.connect() as db:
            db.execute("DELETE FROM memories WHERE id=? AND room_id=?", (memory_id, room_id))

    def delete_room(self, room_id):
        with self.connect() as db:
            for table in ("messages", "memories", "unlocks", "turn_requests"):
                db.execute(f"DELETE FROM {table} WHERE room_id=?", (room_id,))
            db.execute("DELETE FROM rooms WHERE id=?", (room_id,))

    def gallery(self):
        with self.connect() as db:
            rows = db.execute("""SELECT u.*, r.character_id, r.character_snapshot FROM unlocks u
                JOIN rooms r ON r.id=u.room_id ORDER BY u.created_at DESC""")
            return [{**{k: row[k] for k in row.keys() if k != "character_snapshot"},
                     "character": json.loads(row["character_snapshot"])} for row in rows]

    def export(self):
        characters = self.characters()
        rooms = [self.room(r["id"]) for r in self.rooms()]
        references = set()
        for character in [*characters, *(r["character"] for r in rooms)]:
            references.update([character.get("portrait_id", ""), *character.get("gallery", {}).values(),
                               *(scene["media_id"] for scene in character.get("scenes", []))])
        images = []
        for media_id in references - {""}:
            media = self.media(media_id)
            if media:
                images.append({"id": media_id, "mime": media["mime"], "data": base64.b64encode(media["data"]).decode()})
        return {"format": "elyra-local-v2", "exportedAt": now(), "characters": characters,
                "rooms": rooms, "media": images}
