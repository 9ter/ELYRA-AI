"""Single-user development server. Loopback by default; --lan IP enables explicit LAN access."""
import argparse
import base64
import hmac
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs

from elyra import imagegen, providers, scenes, summary
from elyra.domain import ACTIVE_MILESTONES, demo_reply, validate_character
from elyra.store import Store
from elyra.media import validate_image
from elyra.context import build_context

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
MAX_BODY = 128 * 1024
LAN_NETWORKS = tuple(ipaddress.ip_network(value) for value in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def lan_address(value):
    address = ipaddress.IPv4Address(value)
    if not any(address in network for network in LAN_NETWORKS):
        raise ValueError("LAN address must be a private IPv4 address on this computer")
    return str(address)


def tunnel_origin(value):
    if not re.fullmatch(r"https://[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value):
        raise ValueError("Tunnel origin must be an exact HTTPS origin without a path or port")
    return value


class TunnelAuthRequired(PermissionError):
    pass


class AppServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store, lan_host=None, public_origin=None, tunnel_credentials=None, tunnel_no_auth=False):
        if (tunnel_no_auth and tunnel_credentials) or bool(public_origin) != bool(tunnel_credentials or tunnel_no_auth):
            raise ValueError("Tunnel origin requires credentials or explicit tunnel_no_auth, exclusively")
        self.public_origin = tunnel_origin(public_origin) if public_origin else None
        self.tunnel_authorization = None
        if tunnel_credentials:
            username, password = tunnel_credentials.get("username"), tunnel_credentials.get("password")
            if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", username) or not isinstance(password, str) or not 16 <= len(password) <= 128 or not password.isascii() or any(ord(c) < 33 for c in password):
                raise ValueError("Tunnel credentials require a username and a strong ASCII password (16-128 characters)")
            self.tunnel_authorization = b"Basic " + base64.b64encode(f"{username}:{password}".encode("ascii"))
        self.lan_host = lan_address(lan_host) if lan_host else None
        if address[0] != "127.0.0.1" and not self.lan_host:
            raise ValueError("Non-loopback binding requires an explicit LAN address")
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.room_lock = threading.Lock()
        self.busy_rooms = set()
        self.summarizing = set()
        self.summary_errors = set()
        self.image_lock = threading.Lock()
        super().__init__(address, Handler)
        self.allowed_hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}
        if self.lan_host:
            self.allowed_hosts.add(f"{self.lan_host}:{self.server_port}")
        if self.public_origin:
            self.allowed_hosts.add(urlsplit(self.public_origin).netloc)

    def summarize_later(self, room_id, provider, model):
        """Run the older-turn summary in the background so it never delays or blocks the chat."""
        with self.room_lock:
            if room_id in self.summarizing:
                return
            self.summarizing.add(room_id)
            self.summary_errors.discard(room_id)

        def work():
            try:
                summary.run(self.store, room_id, provider, model)
            except (providers.ProviderError, ValueError, OSError, sqlite3.Error) as exc:
                with self.room_lock:
                    self.summary_errors.add(room_id)
                print(f"[summary] skipped: {type(exc).__name__}", flush=True)
            finally:
                with self.room_lock:
                    self.summarizing.discard(room_id)

        threading.Thread(target=work, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    server_version = "ElyraDemo/1.0"

    def log_message(self, fmt, *args):
        # Avoid logging query strings or message bodies.
        print(f"[{self.log_date_time_string()}] {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}", flush=True)

    def access(self, mutation=False):
        # Gate every host, including loopback, so proxy header rewriting cannot bypass login.
        if self.server.tunnel_authorization is not None:
            supplied = self.headers.get_all("Authorization", [])
            if len(supplied) != 1 or not hmac.compare_digest(supplied[0].encode("utf-8"), self.server.tunnel_authorization):
                raise TunnelAuthRequired("ELYRA tunnel login required")
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        peer = ipaddress.ip_address(self.client_address[0])
        if not peer.is_loopback and (not self.server.lan_host or not any(peer in network for network in LAN_NETWORKS)):
            raise PermissionError("อนุญาตเฉพาะเครื่องนี้และเครือข่าย LAN ที่เปิดไว้")
        expected_origin = self.server.public_origin if self.server.public_origin and host == urlsplit(self.server.public_origin).netloc else f"http://{host}"
        if host not in self.server.allowed_hosts or len(self.headers.get_all("Host", [])) != 1 or len(self.headers.get_all("Origin", [])) > 1 or (origin and origin != expected_origin):
            raise PermissionError("Host หรือ Origin ไม่ตรงกับที่อยู่ของแอป")
        if mutation and not hmac.compare_digest(self.headers.get("X-Elyra-Token", ""), self.server.token):
            raise PermissionError("กรุณารีเฟรชหน้าเว็บก่อนลองอีกครั้ง")

    def send_headers(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Basic realm="ELYRA", charset="UTF-8"')
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def body(self):
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("กรุณาส่งข้อมูลแบบ JSON")
        length = int(self.headers.get("Content-Length", "0"))
        limit = 3 * 1024 * 1024 if urlsplit(self.path).path == "/api/media" else MAX_BODY
        if not 0 < length <= limit:
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
            room.pop("character_snapshot", None)
        settings = self.store.settings()
        for provider in ("xai", "openai", "ollama"):
            if not settings["models"].get(provider):
                settings["models"][provider] = os.environ.get(provider.upper() + "_MODEL", "")
        return {"token": self.server.token, "characters": self.store.characters(), "rooms": rooms,
                "settings": settings, "providers": providers.status(), "milestones": ACTIVE_MILESTONES, "gallery": self.store.gallery()}

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
            if path == "/api/images/options":
                saved = imagegen.validate_settings(self.store.settings().get("image", {}))
                return self.json_response({**imagegen.options(), "settings": saved})
            if path == "/api/export":
                if not hmac.compare_digest(self.headers.get("X-Elyra-Token", ""), self.server.token):
                    raise PermissionError("กรุณาส่งออกผ่านหน้าแอป")
                return self.json_response(self.store.export())
            if path.startswith("/media/"):
                media_id = path.removeprefix("/media/")
                if not re.fullmatch(r"[a-f0-9]{64}", media_id):
                    return self.json_response({"error": "ไม่พบภาพ"}, 404)
                media = self.store.media(media_id)
                if not media:
                    return self.json_response({"error": "ไม่พบภาพ"}, 404)
                self.send_headers(200, media["mime"], len(media["data"]))
                return self.wfile.write(media["data"])
            if re.fullmatch(r"/api/rooms/[^/]+/summary", path):
                room_id = path.split("/")[-2]
                recap = self.store.summary_record(room_id)
                if recap is None:
                    return self.json_response({"error": "ไม่พบห้องแชต"}, 404)
                with self.server.room_lock:
                    state = "updating" if room_id in self.server.summarizing else "error" if room_id in self.server.summary_errors else "idle"
                return self.json_response({"summary": recap["summary"] or "", "summary_count": recap["summary_count"] or 0,
                    "summary_state": state})
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
            self.send_headers(200, content_type, len(body))
            self.wfile.write(body)
        except TunnelAuthRequired as exc:
            self.json_response({"error": str(exc)}, 401)
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
            if path == "/api/media":
                return self.json_response(self.store.add_media(validate_image(data)), 201)
            if path == "/api/images/settings":
                settings = self.store.settings()
                settings["image"] = imagegen.validate_settings(data)
                return self.json_response(self.store.save_settings(settings)["image"])
            if path == "/api/images/generate":
                # One local GPU job at a time; the request blocks until Stable Diffusion finishes.
                if not self.server.image_lock.acquire(blocking=False):
                    return self.json_response({"error": "กำลังสร้างภาพอื่นอยู่ กรุณารอให้เสร็จก่อน"}, 409)
                try:
                    media = imagegen.generate(data.get("character_prompt", ""), data.get("prompt", ""), data.get("negative", ""),
                                              self.store.settings().get("image", {}), data.get("loras", []))
                finally:
                    self.server.image_lock.release()
                return self.json_response(self.store.add_media(media), 201)
            if path == "/api/characters":
                character = validate_character(data)
                self.store.validate_media_references(character)
                return self.json_response(self.store.add_character(character), 201)
            if path.startswith("/api/characters/"):
                parts = path.strip("/").split("/")
                if len(parts) != 4:
                    raise ValueError("เส้นทางตัวละครไม่ถูกต้อง")
                character_id, action = parts[2:]
                if action == "update":
                    expected = data.get("expectedVersion")
                    if type(expected) is not int or expected < 1:
                        raise ValueError("กรุณาเปิดตัวแก้ไขใหม่เพื่อโหลดเวอร์ชันล่าสุด")
                    character = validate_character(data)
                    self.store.validate_media_references(character)
                    return self.json_response(self.store.update_character(character_id, character, expected))
                if action == "archive":
                    if type(data.get("archived")) is not bool:
                        raise ValueError("สถานะคลังตัวละครไม่ถูกต้อง")
                    return self.json_response(self.store.archive_character(character_id, data["archived"]))
                return self.json_response({"error": "ไม่พบคำสั่งตัวละคร"}, 404)
            if path == "/api/rooms":
                provider, model, mode = self.selection(data)
                return self.json_response(self.store.create_room(data.get("characterId"), provider, model, mode), 201)
            if path == "/api/settings":
                provider = data.get("provider", "demo")
                models = data.get("models", {})
                name = data.get("displayName", "Storyteller")
                if provider not in providers.PROVIDERS or not isinstance(models, dict) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
                    raise ValueError("การตั้งค่าไม่ถูกต้อง")
                clean_models, clean_background = {}, {}
                background = data.get("backgroundModels", {})
                if not isinstance(background, dict):
                    raise ValueError("การตั้งค่าโมเดลงานเบื้องหลังไม่ถูกต้อง")
                for key in providers.PROVIDERS:
                    value = models.get(key, "story-demo" if key == "demo" else "")
                    extra = background.get(key, "")
                    if not isinstance(value, str) or len(value) > 160 or not isinstance(extra, str) or len(extra) > 160:
                        raise ValueError("ชื่อโมเดลไม่ถูกต้อง")
                    clean_models[key] = value.strip()
                    clean_background[key] = extra.strip()  # "" = default (xAI non-reasoning, else the chat model)
                settings = {"provider": provider, "models": clean_models, "backgroundModels": clean_background,
                            "displayName": name.strip(), "matureConfirmed": data.get("matureConfirmed") is True,
                            "image": self.store.settings().get("image", {})}  # saved separately below
                saved = self.store.save_settings(settings)
                if data.get("applyToRooms") is True and provider != "demo" and clean_models[provider]:
                    # Optional: switch existing rooms of this provider to the new chat model (history is kept).
                    saved = {**saved, "roomsUpdated": self.store.set_rooms_model(provider, clean_models[provider])}
                return self.json_response(saved)
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
                    if action == "notes":
                        content = data.get("content", "")
                        if not isinstance(content, str) or len(content) > 3000:
                            raise ValueError("สรุปเรื่องราวต้องไม่เกิน 3,000 ตัวอักษร")
                        return self.json_response(self.store.save_notes(room_id, content.strip()))
                    if action == "branch":
                        if not isinstance(data.get("messageId"), str):
                            raise ValueError("กรุณาเลือกจุดแตกเส้นเรื่อง")
                        return self.json_response(self.store.branch_room(room_id, data["messageId"]), 201)
                    if action == "forget":
                        self.store.delete_memory(room_id, str(data.get("memoryId", "")))
                        return self.json_response(self.store.room(room_id))
                    if action == "delete":
                        self.store.delete_room(room_id)
                        return self.json_response({"ok": True})
            self.json_response({"error": "ไม่พบ endpoint"}, 404)
        except TunnelAuthRequired as exc:
            self.json_response({"error": str(exc)}, 401)
        except PermissionError as exc:
            self.json_response({"error": str(exc)}, 403)
        except (ValueError, providers.ProviderError, TypeError) as exc:
            self.json_response({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def chat(self, room, data):
        room_id = room["id"]
        text = data.get("text", "")
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 4000:
            raise ValueError("ข้อความต้องมีความยาว 1–4,000 ตัวอักษร")
        text = text.strip()
        request_id = data.get("requestId") or secrets.token_hex(16)
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", request_id):
            raise ValueError("รหัสคำขอไม่ถูกต้อง")
        with self.server.room_lock:
            if room["id"] in self.server.busy_rooms:
                return self.json_response({"error": "ห้องนี้กำลังสร้างคำตอบ กรุณารอสักครู่"}, 409)
            if self.store.request_completed(room_id, request_id, text):
                self.send_headers(200, "application/x-ndjson; charset=utf-8")
                self.emit({"type": "done", "room": self.store.room(room_id), "unlocked": [], "replayed": True})
                return
            self.server.busy_rooms.add(room["id"])
        started = False
        try:
            # Re-read after lock so a completed turn cannot be lost to a stale snapshot.
            room = self.store.room(room_id)
            if not room:
                return self.json_response({"error": "ห้องนี้ถูกลบแล้ว"}, 404)
            provider, model = room["provider"], room["model"]
            memories = [m["content"] for m in room["memories"]]
            if room["mode"] == "mature" and not self.store.settings().get("matureConfirmed"):
                raise ValueError("กรุณายืนยันอายุ 18+ อีกครั้ง หรือเปลี่ยนห้องเป็นโหมดทั่วไป")
            # Scenes come from the live character so newly tagged images apply to existing rooms too.
            current = self.store.character(room["character_id"]) or room["character"]
            candidates = scenes.eligible(current.get("scenes", []), room["turns"] + 1)
            messages, context = build_context(room["character"], memories, room["messages"], text,
                                               room["mode"], room.get("notes", ""), provider,
                                               room.get("summary") or "", room.get("summary_count") or 0,
                                               "" if provider == "demo" else scenes.prompt_block(candidates),
                                               scenes.reminder(room.get("scene_id")))
            if provider == "demo":
                reply = demo_reply(room["character"], text, room["turns"] + 1, memories)
                chunks = (reply[i:i + 8] for i in range(0, len(reply), 8))
            else:
                chunks = providers.stream(provider, model, messages)
            self.send_headers(200, "application/x-ndjson; charset=utf-8")
            started = True
            content = ""
            markers = scenes.MarkerFilter()
            for chunk in chunks:
                visible = markers.feed(chunk)
                content += visible
                if len(content) > 30000:
                    raise providers.ProviderError("คำตอบยาวเกินขีดจำกัดเดโม")
                if visible:
                    self.emit({"type": "delta", "text": visible})
                if provider == "demo":
                    time.sleep(0.014)
            rest, marked = markers.finish()
            if rest:
                content += rest
                self.emit({"type": "delta", "text": rest})
            if not content.strip():
                raise providers.ProviderError("โมเดลไม่ส่งข้อความตอบกลับ กรุณาลองโมเดลอื่น")
            content = content.rstrip()
            unlocked = self.store.commit_turn(room["id"], text, content, provider, model, request_id)
            scene_id = scenes.demo_pick(candidates, content) if provider == "demo" else scenes.accept(marked, candidates)
            if not scene_id and provider != "demo":
                picker_model = providers.background_model(provider, model, self.store.settings())
                scene_id = scenes.fallback_pick(provider, picker_model, candidates, text, content, room.get("scene_id"))
            scene_id = scenes.resolve_variant(scene_id, candidates, room.get("scene_id"), room["unlocks"]) if scene_id else None
            if scene_id and scene_id != room.get("scene_id") and self.store.set_scene(room["id"], scene_id):
                title = next((s.get("title") for s in candidates if s["id"] == scene_id), "") or "ภาพใหม่"
                unlocked = [*unlocked, {"id": "scene:" + scene_id, "title": title, "scene": True}]
            self.emit({"type": "done", "room": self.store.room(room["id"]), "unlocked": unlocked, "context": context})
            self.server.summarize_later(room["id"], provider, model)
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
                self.server.busy_rooms.discard(room_id)

    def emit(self, event):
        self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser(description="ELYRA local character chat demo")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--lan", type=lan_address, metavar="PRIVATE_IP", help="Enable LAN access using this computer's private IPv4 address")
    parser.add_argument("--tunnel-origin", type=tunnel_origin, help="Exact HTTPS tunnel origin; requires credentials or explicit --tunnel-no-auth")
    tunnel_auth = parser.add_mutually_exclusive_group()
    tunnel_auth.add_argument("--tunnel-credentials", type=Path, help="Private JSON file with username/password; enables login on ALL hosts")
    tunnel_auth.add_argument("--tunnel-no-auth", action="store_true", help="Explicitly allow tunnel access without a login")
    args = parser.parse_args()
    if bool(args.tunnel_origin) != bool(args.tunnel_credentials or args.tunnel_no_auth):
        parser.error("--tunnel-origin requires --tunnel-credentials or --tunnel-no-auth")
    credentials = json.loads(args.tunnel_credentials.read_text(encoding="utf-8")) if args.tunnel_credentials else None
    providers.load_env()
    server = AppServer(("0.0.0.0" if args.lan else "127.0.0.1", args.port), Store(ROOT / ".data" / "elyra.db"), lan_host=args.lan, public_origin=args.tunnel_origin, tunnel_credentials=credentials, tunnel_no_auth=args.tunnel_no_auth)
    print(f"\n  ELYRA demo is ready\n  http://localhost:{server.server_port}\n  Single-user local server. Ctrl+C to stop.\n", flush=True)
    if args.lan:
        print(f"  LAN: http://{args.lan}:{server.server_port}\n  LAN devices share this app's chat data.\n", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping ELYRA.", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
