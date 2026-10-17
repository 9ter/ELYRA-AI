"""Provider adapters using only Python's standard library. No cloud fallback."""
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROVIDERS = {"demo", "xai", "openai", "ollama"}


class ProviderError(Exception):
    pass


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def api_key(provider):
    value = os.environ.get("XAI_API_KEY" if provider == "xai" else "OPENAI_API_KEY", "").strip()
    # Existing user-supplied key file is read only in this server process.
    if not value and provider == "xai":
        path = ROOT / "xAi_api_key.text"
        if path.exists():
            raw = path.read_text(encoding="utf-8-sig").strip()
            match = re.search(r"xai-[A-Za-z0-9_-]+", raw)
            value = match.group(0) if match else raw
    return value


def ollama_base():
    url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in ("localhost", "127.0.0.1", "::1") or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ProviderError("เดโมอนุญาต Ollama บน loopback เท่านั้น กรุณาตั้ง OLLAMA_BASE_URL เป็น localhost หรือ 127.0.0.1")
    return url


def status():
    return {"demo": {"configured": True}, "xai": {"configured": bool(api_key("xai"))},
            "openai": {"configured": bool(api_key("openai"))}, "ollama": {"configured": True, "local": True}}


def endpoint(provider):
    if provider == "ollama":
        return ollama_base()
    return {"xai": "https://api.x.ai/v1", "openai": "https://api.openai.com/v1"}[provider]


def request(provider, path, body=None, timeout=90):
    headers = {"Content-Type": "application/json", "User-Agent": "Elyra-Demo/1.0"}
    if provider != "ollama":
        key = api_key(provider)
        if not key:
            raise ProviderError(f"ยังไม่ได้ตั้งค่า {provider} API key ใน .env ฝั่งเซิร์ฟเวอร์")
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(endpoint(provider) + path,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None, headers=headers)
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Do not forward provider response bodies: they can include sensitive request data.
        hints = {400: "โมเดลหรือพารามิเตอร์ไม่รองรับ", 401: "API key ไม่ถูกต้อง", 403: "บัญชีไม่มีสิทธิ์ใช้งาน",
                 404: "ไม่พบโมเดลหรือ endpoint", 429: "เกินโควตาหรือยอดคงเหลือไม่พอ"}
        raise ProviderError(f"{provider}: {hints.get(exc.code, 'ผู้ให้บริการตอบกลับผิดพลาด')} (HTTP {exc.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ProviderError(f"เชื่อมต่อ {provider} ไม่สำเร็จ กรุณาตรวจว่าเซิร์ฟเวอร์เปิดอยู่และการเชื่อมต่อพร้อมใช้งาน") from None


def list_models(provider):
    if provider not in PROVIDERS:
        raise ValueError("ไม่รู้จักผู้ให้บริการนี้")
    if provider == "demo":
        return ["story-demo"]
    with request(provider, "/api/tags" if provider == "ollama" else "/models", timeout=12) as response:
        result = json.load(response)
    if provider == "ollama":
        return sorted(item["name"] for item in result.get("models", []) if "name" in item)
    return sorted(item["id"] for item in result.get("data", []) if "id" in item)


def stream(provider, model, messages):
    if provider not in PROVIDERS - {"demo"}:
        raise ProviderError("ผู้ให้บริการไม่ถูกต้อง")
    if not isinstance(model, str) or not model.strip() or len(model) > 160:
        raise ProviderError("กรุณาเลือกหรือระบุชื่อโมเดลในหน้าตั้งค่า")
    if provider == "openai":
        path, body = "/responses", {"model": model, "input": messages, "stream": True, "store": False, "max_output_tokens": 900}
    elif provider == "xai":
        path, body = "/chat/completions", {"model": model, "messages": messages, "stream": True, "max_tokens": 900}
    else:
        path, body = "/api/chat", {"model": model, "messages": messages, "stream": True, "options": {"num_predict": 900, "num_ctx": 8192}}
    # Require an explicit successful completion; interrupted streams are never committed.
    complete = False
    with request(provider, path, body) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line or line.startswith(("event:", ":")):
                continue
            if provider != "ollama":
                if not line.startswith("data:"):
                    continue
                line = line[5:].strip()
                if line == "[DONE]":
                    complete = True
                    break
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                raise ProviderError("ผู้ให้บริการส่งข้อมูลสตรีมที่อ่านไม่ได้") from None
            if data.get("error") or data.get("type") in ("error", "response.failed", "response.incomplete"):
                raise ProviderError("ผู้ให้บริการไม่สามารถสร้างคำตอบให้เสร็จสมบูรณ์ กรุณาลองอีกครั้ง")
            if provider == "openai":
                if data.get("type") == "response.output_text.delta":
                    yield data.get("delta", "")
                elif data.get("type") == "response.completed":
                    complete = True
            elif provider == "xai":
                for choice in data.get("choices", []):
                    content = choice.get("delta", {}).get("content")
                    if content:
                        yield content
                    if choice.get("finish_reason"):
                        if choice["finish_reason"] not in ("stop",):
                            raise ProviderError("คำตอบถูกตัดหรือถูกกรอง กรุณาลองข้อความที่สั้นลง")
                        complete = True
            else:
                content = data.get("message", {}).get("content", "")
                if content:
                    yield content
                if data.get("done"):
                    if data.get("done_reason") not in (None, "stop"):
                        raise ProviderError("โมเดลหยุดก่อนจบคำตอบ กรุณาลองอีกครั้ง")
                    complete = True
    if not complete:
        raise ProviderError("การเชื่อมต่อขาดก่อนจบคำตอบ ยังไม่ได้บันทึกข้อความนี้")
