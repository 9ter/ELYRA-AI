"""Run with: python app.py. Single-user development server, loopback only."""
import argparse
import hmac
import json
import mimetypes
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

from elyra import providers
from elyra.domain import MILESTONES, demo_reply, system_prompt, validate_character
from elyra.store import Store

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
MAX_BODY = 128 * 1024


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store):
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.room_lock = threading.Lock()
        self.busy_rooms = set()
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "ElyraDemo/1.0"

    def log_message(self, fmt, *args):
        # Avoid logging query strings or message bodies.
        print(f"[{self.log_date_time_string()}] {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}", flush=True)

    def access(self, mutation=False):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if host not in hosts or (origin and origin not in {f"http://{h}" for h in hosts}):
            raise PermissionError("อนุญาตเฉพาะการเข้าจากเครื่องนี้")
        if mutation and not hmac.compare_digest(self.headers.get("X-Elyra-Token", ""), self.server.token):
            raise PermissionError("กรุณารีเฟรชหน้าเว็บก่อนลองอีกครั้ง")

    def headers(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def body(self):
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("กรุณาส่งข้อมูลแบบ JSON")
        length = int(self.headers.get("Content-Length", "0"))
        if not 0 < length <= MAX_BODY:
            raise ValueError("ขนาดข้อมูลไม่ถูกต้อง")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("ข้อมูลต้องเป็น JSON object")
        return data

    @property
    def store(self):
        return self.server.store

    def bootstrap(self):
        rooms = self.store.rooms()
        for room in rooms:
            room["character"] = json.loads(room.pop("character_data"))
        settings = self.store.settings()
        for provider in ("xai", "openai", "ollama"):
            if not settings["models"].get(provider):
                settings["models"][provider] = os.environ.get(provider.upper() + "_MODEL", "")
        return {"token": self.server.token, "characters": self.store.characters(), "rooms": rooms,
                "settings": settings, "providers": providers.status(), "milestones": MILESTONES, "gallery": self.store.gallery()}

    def do_GET(self):
        try:
            self.access()
            parsed = urlsplit(self.path)
            path = parsed.path
            if path == "/api/bootstrap":
                return self.json_response(self.bootstrap())
            if path == "/api/health":
                return self.json_response({"ok": True, "app": "ELYRA", "mode": "local-single-user"})
            if path == "/api/models":
                provider = parse_qs(parsed.query).get("provider", [""])[0]
                return self.json_response({"models": providers.list_models(provider)})
            if path == "/api/export":
                if not hmac.compare_digest(self.headers.get("X-Elyra-Token", ""), self.server.token):
                    raise PermissionError("กรุณาส่งออกผ่านหน้าแอป")
                return self.json_response(self.store.export())
            if path.startswith("/api/rooms/"):
                room = self.store.room(path.split("/")[-1])
                return self.json_response(room if room else {"error": "ไม่พบห้องแชต"}, 200 if room else 404)
            if path.startswith("/api/"):
                return self.json_response({"error": "ไม่พบ endpoint"}, 404)
            filename = "index.html" if path == "/" else unquote(path).lstrip("/")
            target = (PUBLIC / filename).resolve()
            if not target.is_relative_to(PUBLIC.resolve()) or not target.is_file():
                return self.json_response({"error": "ไม่พบไฟล์"}, 404)
            body = target.read_bytes()
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if content_type.startswith("text/") or target.suffix == ".js":
                content_type += "; charset=utf-8"
            self.headers(200, content_type, len(body))
            self.wfile.write(body)
        except PermissionError as exc:
            self.json_response({"error": str(exc)}, 403)
        except (ValueError, providers.ProviderError) as exc:
            self.json_response({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def selection(self, data):
        provider, model = data.get("provider", "demo"), data.get("model", "story-demo")
        mode = data.get("mode", "general")
        if provider not in providers.PROVIDERS or not isinstance(model, str) or len(model) > 160:
            raise ValueError("การตั้งค่าโมเดลไม่ถูกต้อง")
        if provider != "demo" and not model.strip():
            raise ValueError("กรุณาระบุชื่อโมเดลในหน้าตั้งค่าก่อน")
        if mode not in ("general", "mature"):
            raise ValueError("โหมดเนื้อหาไม่ถูกต้อง")
        if mode == "mature" and not self.store.settings().get("matureConfirmed"):
            raise ValueError("กรุณายืนยันอายุ 18+ ในหน้าตั้งค่าก่อน")
        return provider, model.strip(), mode

    def do_POST(self):
        try:
            self.access(mutation=True)
            data = self.body()
            path = urlsplit(self.path).path
            if path == "/api/characters":
                return self.json_response(self.store.add_character(validate_character(data)), 201)
            if path == "/api/rooms":
                provider, model, mode = self.selection(data)
                return self.json_response(self.store.create_room(data.get("characterId"), provider, model, mode), 201)
            if path == "/api/settings":
                provider = data.get("provider", "demo")
                models = data.get("models", {})
                name = data.get("displayName", "Storyteller")
                if provider not in providers.PROVIDERS or not isinstance(models, dict) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
                    raise ValueError("การตั้งค่าไม่ถูกต้อง")
                clean_models = {}
                for key in providers.PROVIDERS:
                    value = models.get(key, "story-demo" if key == "demo" else "")
                    if not isinstance(value, str) or len(value) > 160:
                        raise ValueError("ชื่อโมเดลไม่ถูกต้อง")
                    clean_models[key] = value.strip()
                settings = {"provider": provider, "models": clean_models, "displayName": name.strip(),
                            "matureConfirmed": data.get("matureConfirmed") is True}
                return self.json_response(self.store.save_settings(settings))
            if path.startswith("/api/rooms/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise ValueError("เส้นทางไม่ถูกต้อง")
                room_id, action = parts[2:]
                room = self.store.room(room_id)
                if not room:
                    return self.json_response({"error": "ไม่พบห้องแชต"}, 404)
                if action == "chat":
                    return self.chat(room, data)
                with self.server.room_lock:
                    if room_id in self.server.busy_rooms:
                        return self.json_response({"error": "กรุณารอให้คำตอบเสร็จก่อนแก้ไขห้องนี้"}, 409)
                    if action == "configure":
                        return self.json_response(self.store.update_room(room_id, *self.selection(data)))
                    if action == "memory":
                        content = data.get("content", "")
                        if not isinstance(content, str) or not 1 <= len(content.strip()) <= 500:
                            raise ValueError("ความจำต้องมีความยาว 1–500 ตัวอักษร")
                        return self.json_response(self.store.add_memory(room_id, content.strip()))
                    if action == "forget":
                        self.store.delete_memory(room_id, str(data.get("memoryId", "")))
                        return self.json_response(self.store.room(room_id))
                    if action == "delete":
                        self.store.delete_room(room_id)
                        return self.json_response({"ok": True})
            self.json_response({"error": "ไม่พบ endpoint"}, 404)
        except PermissionError as exc:
            self.json_response({"error": str(exc)}, 403)
        except (ValueError, providers.ProviderError, TypeError) as exc:
            self.json_response({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def chat(self, room, data):
        text = data.get("text", "")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise ValueError("ข้อความต้องมีความยาว 1–4,000 ตัวอักษร")
        text = text.strip()
        with self.server.room_lock:
            if room["id"] in self.server.busy_rooms:
                return self.json_response({"error": "ห้องนี้กำลังสร้างคำตอบ กรุณารอสักครู่"}, 409)
            self.server.busy_rooms.add(room["id"])
        started = False
        try:
            # Re-read after lock so a completed turn cannot be lost to a stale snapshot.
            room = self.store.room(room["id"])
            provider, model = room["provider"], room["model"]
            memories = [m["content"] for m in room["memories"]]
            if room["mode"] == "mature" and not self.store.settings().get("matureConfirmed"):
                raise ValueError("กรุณายืนยันอายุ 18+ อีกครั้ง หรือเปลี่ยนห้องเป็นโหมดทั่วไป")
            messages = [{"role": "system", "content": system_prompt(room["character"], memories, room["mode"])}]
            # Character greeting and recent complete turns; older turns remain on disk.
            messages.extend({"role": m["role"], "content": m["content"]} for m in room["messages"][-21:])
            messages.append({"role": "user", "content": text})
            if provider == "demo":
                reply = demo_reply(room["character"], text, room["turns"] + 1, memories)
                chunks = (reply[i:i + 8] for i in range(0, len(reply), 8))
            else:
                chunks = providers.stream(provider, model, messages)
            self.headers(200, "application/x-ndjson; charset=utf-8")
            started = True
            content = ""
            for chunk in chunks:
                content += chunk
                if len(content) > 30000:
                    raise providers.ProviderError("คำตอบยาวเกินขีดจำกัดเดโม")
                self.emit({"type": "delta", "text": chunk})
                if provider == "demo":
                    time.sleep(0.014)
            if not content.strip():
                raise providers.ProviderError("โมเดลไม่ส่งข้อความตอบกลับ กรุณาลองโมเดลอื่น")
            unlocked = self.store.commit_turn(room["id"], text, content, provider, model)
            self.emit({"type": "done", "room": self.store.room(room["id"]), "unlocked": unlocked})
        except (providers.ProviderError, ValueError) as exc:
            if started:
                self.emit({"type": "error", "message": str(exc)})
            else:
                self.json_response({"error": str(exc)}, 400)
        except (TimeoutError, OSError):
            if started:
                try:
                    self.emit({"type": "error", "message": "การเชื่อมต่อหยุดลง ยังไม่ได้บันทึกข้อความที่ไม่สมบูรณ์"})
                except OSError:
                    pass
        finally:
            with self.server.room_lock:
                self.server.busy_rooms.discard(room["id"])

    def emit(self, event):
        self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser(description="ELYRA local character chat demo")
    parser.add_argument("--port", type=int, default=3000)
    args = parser.parse_args()
    providers.load_env()
    server = AppServer(("127.0.0.1", args.port), Store(ROOT / ".data" / "elyra.db"))
    print(f"\n  ELYRA demo is ready\n  http://localhost:{server.server_port}\n  Single-user local server. Ctrl+C to stop.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ELYRA.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
