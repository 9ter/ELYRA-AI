"""SQLite persistence. Secrets are deliberately never stored here."""
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .domain import CHARACTERS, MILESTONES


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
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
            """)
            for character in CHARACTERS:
                db.execute("INSERT OR IGNORE INTO characters VALUES (?,?)", (character["id"], json.dumps(character, ensure_ascii=False)))
            db.execute("INSERT OR IGNORE INTO settings VALUES (1,?)", (json.dumps({
                "provider": "demo", "models": {"demo": "story-demo", "xai": "", "openai": "", "ollama": ""},
                "displayName": "Storyteller", "matureConfirmed": False}),))

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

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

    def settings(self):
        with self.connect() as db:
            return json.loads(db.execute("SELECT data FROM settings WHERE id=1").fetchone()[0])

    def save_settings(self, settings):
        with self.connect() as db:
            db.execute("UPDATE settings SET data=? WHERE id=1", (json.dumps(settings, ensure_ascii=False),))
        return settings

    def rooms(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT r.*, c.data AS character_data,
                (SELECT content FROM messages WHERE room_id=r.id ORDER BY rowid DESC LIMIT 1) AS preview,
                (SELECT COUNT(*) FROM messages WHERE room_id=r.id AND role='user') AS turns
                FROM rooms r JOIN characters c ON c.id=r.character_id ORDER BY r.updated_at DESC""")]

    def create_room(self, character_id, provider, model, mode="general"):
        character = self.character(character_id)
        if not character:
            raise ValueError("ไม่พบตัวละครนี้")
        room_id, timestamp = uuid.uuid4().hex, now()
        with self.connect() as db:
            db.execute("INSERT INTO rooms VALUES (?,?,?,?,?,?,?)", (room_id, character_id, provider, model, mode, timestamp, timestamp))
            db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, room_id, "assistant", character["greeting"], "greeting", "", timestamp))
        return self.room(room_id)

    def room(self, room_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM rooms WHERE id=?", (room_id,)).fetchone()
            if not row:
                return None
            room = dict(row)
            room["character"] = self.character(room["character_id"])
            room["messages"] = [dict(r) for r in db.execute("SELECT * FROM messages WHERE room_id=? ORDER BY rowid", (room_id,))]
            room["memories"] = [dict(r) for r in db.execute("SELECT * FROM memories WHERE room_id=? ORDER BY rowid DESC", (room_id,))]
            room["unlocks"] = [r[0] for r in db.execute("SELECT milestone_id FROM unlocks WHERE room_id=?", (room_id,))]
            room["turns"] = sum(m["role"] == "user" for m in room["messages"])
            return room

    def update_room(self, room_id, provider, model, mode):
        with self.connect() as db:
            db.execute("UPDATE rooms SET provider=?, model=?, mode=?, updated_at=? WHERE id=?", (provider, model, mode, now(), room_id))
        return self.room(room_id)

    def commit_turn(self, room_id, user_text, assistant_text, provider, model):
        timestamp = now()
        unlocked = []
        with self.connect() as db:
            for role, content in (("user", user_text), ("assistant", assistant_text)):
                db.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?)", (uuid.uuid4().hex, room_id, role, content, provider, model, timestamp))
            db.execute("UPDATE rooms SET updated_at=? WHERE id=?", (timestamp, room_id))
            turns = db.execute("SELECT COUNT(*) FROM messages WHERE room_id=? AND role='user'", (room_id,)).fetchone()[0]
            for milestone in MILESTONES:
                if turns >= milestone["threshold"]:
                    cursor = db.execute("INSERT OR IGNORE INTO unlocks VALUES (?,?,?)", (room_id, milestone["id"], timestamp))
                    if cursor.rowcount:
                        unlocked.append(milestone)
        return unlocked

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
            for table in ("messages", "memories", "unlocks"):
                db.execute(f"DELETE FROM {table} WHERE room_id=?", (room_id,))
            db.execute("DELETE FROM rooms WHERE id=?", (room_id,))

    def gallery(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT u.*, r.character_id FROM unlocks u
                JOIN rooms r ON r.id=u.room_id ORDER BY u.created_at DESC""")]

    def export(self):
        return {"format": "elyra-demo-v1", "exportedAt": now(), "characters": self.characters(),
                "rooms": [self.room(r["id"]) for r in self.rooms()]}
