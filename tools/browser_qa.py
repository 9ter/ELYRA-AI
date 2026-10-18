"""Local Chrome DevTools smoke test. Requires a headless Chrome on port 9223.

Uses Python stdlib only; temporary application data stays under .qa/.
Run: python tools/browser_qa.py
"""
import base64
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import AppServer
from elyra.store import Store


class CDP:
    def __init__(self, url):
        parsed = urlsplit(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=15)
        self.seq = 0
        self.events = []
        key = base64.b64encode(os.urandom(16)).decode()
        request = f"GET {parsed.path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\nOrigin: http://localhost:9223\r\n\r\n"
        self.sock.sendall(request.encode())
        header = b""
        while not header.endswith(b"\r\n\r\n"):
            header += self.sock.recv(1)
        if b" 101 " not in header.split(b"\r\n", 1)[0]:
            raise RuntimeError("Chrome rejected DevTools connection: " + header.split(b"\r\n", 1)[0].decode())

    def read_exact(self, count):
        data = b""
        while len(data) < count:
            chunk = self.sock.recv(count - len(data))
            if not chunk:
                raise RuntimeError("Chrome disconnected")
            data += chunk
        return data

    def send(self, data, opcode=1):
        payload = data.encode() if isinstance(data, str) else data
        length = len(payload)
        header = bytes([0x80 | opcode])
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack("!H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack("!Q", length)
        mask = os.urandom(4)
        self.sock.sendall(header + mask + bytes(value ^ mask[i % 4] for i,value in enumerate(payload)))

    def receive(self):
        chunks = b""
        while True:
            first, second = self.read_exact(2)
            length = second & 127
            if length == 126:
                length = struct.unpack("!H", self.read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self.read_exact(8))[0]
            mask = self.read_exact(4) if second & 128 else None
            payload = self.read_exact(length)
            if mask:
                payload = bytes(value ^ mask[i % 4] for i,value in enumerate(payload))
            opcode = first & 15
            if opcode == 9:
                self.send(payload, 10)
                continue
            if opcode == 8:
                raise RuntimeError("WebSocket closed")
            chunks += payload
            if first & 128:
                return json.loads(chunks)

    def call(self, method, params=None):
        self.seq += 1
        target = self.seq
        self.send(json.dumps({"id": target, "method": method, "params": params or {}}))
        while True:
            response = self.receive()
            if response.get("id") == target:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response.get("result", {})
            self.events.append(response)

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise AssertionError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=12):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.evaluate(expression):
                return
            time.sleep(.08)
        raise AssertionError(f"Timed out: {expression}")

    def click(self, selector):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).click()")

    def fill(self, selector, value):
        self.evaluate(f"document.querySelector({json.dumps(selector)}).value = {json.dumps(value)}")

    def screenshot(self, name):
        self.evaluate("document.querySelector('#toast-region')?.replaceChildren()")
        data = self.call("Page.captureScreenshot", {"format":"png", "captureBeyondViewport":False})["data"]
        (ROOT / ".qa" / name).write_bytes(base64.b64decode(data))


def main():
    qa = ROOT / ".qa"
    qa.mkdir(exist_ok=True)
    # Unique DB per run, so repeated browser tests never pollute the user's workspace.
    server = AppServer(("127.0.0.1", 0), Store(qa / f"browser-{int(time.time())}.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen("http://127.0.0.1:9223/json") as response:
            pages = json.load(response)
        page = next(item for item in pages if item["type"] == "page")
        cdp = CDP(page["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Log.enable")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1100,"deviceScaleFactor":1,"mobile":False})
        cdp.call("Page.navigate", {"url":f"http://localhost:{server.server_port}"})
        cdp.wait("document.querySelectorAll('.character-card').length === 4")
        cdp.wait("Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        assert cdp.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Desktop horizontal overflow"
        cdp.screenshot("desktop-discover.png")
        cdp.click('.hero [data-action="start-chat"]')
        cdp.wait("!!document.querySelector('#chat-input')")
        cdp.fill("#chat-input", "สวัสดี ฉันชื่อมิน")
        cdp.evaluate("document.querySelector('#chat-form').requestSubmit()")
        cdp.wait("document.querySelectorAll('.message').length === 3 && !document.querySelector('#chat-input').disabled")
        cdp.click('[data-action="add-memory"]')
        cdp.fill("#memory-content", "ฉันชื่อมิน และชอบดอกไม้สีขาว")
        cdp.evaluate("document.querySelector('#memory-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && !!document.querySelector('.memory-item')")
        for message in ("จำได้ไหมว่าฉันชื่ออะไร", "อยากคุยกันต่ออีกหน่อย"):
            before = cdp.evaluate("document.querySelectorAll('.message').length")
            cdp.fill("#chat-input", message)
            cdp.evaluate("document.querySelector('#chat-form').requestSubmit()")
            cdp.wait(f"document.querySelectorAll('.message').length === {before + 2} && !document.querySelector('#chat-input').disabled")
        assert cdp.evaluate("document.querySelectorAll('.milestone-item.unlocked').length === 2")
        assert cdp.evaluate("document.querySelector('#messages').textContent.includes('ฉันชื่อมิน และชอบดอกไม้สีขาว')")
        cdp.screenshot("desktop-chat.png")
        cdp.click('[data-view="gallery"]')
        cdp.wait("document.querySelectorAll('.gallery-card:not(.locked)').length === 2")
        cdp.click('.gallery-card:not(.locked)')
        cdp.wait("document.querySelector('#modal').open")
        cdp.click('[data-action="close-modal"]')
        cdp.click('[data-view="characters"]')
        cdp.click('[data-action="create-character"]')
        for field, value in (("#char-name", "Nova QA"),("#char-description", "นักเดินทางท่ามกลางดวงดาว"),("#char-personality", "ใจดีและเคารพขอบเขต"),("#char-greeting", "สวัสดี ยินดีที่ได้พบกัน")):
            cdp.fill(field,value)
        cdp.evaluate("document.querySelector('#character-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && document.querySelector('.character-grid').textContent.includes('Nova QA')")
        cdp.click('[data-view="settings"]')
        cdp.wait("!!document.querySelector('#settings-form')")
        cdp.fill("#display-name", "Min QA")
        cdp.evaluate("document.querySelector('#mature-confirmed').checked = true")
        cdp.evaluate("document.querySelector('#settings-form').requestSubmit()")
        cdp.wait("document.querySelector('.profile strong').textContent === 'Min QA'")
        cdp.click('[data-action="choose-provider"][data-provider="ollama"]')
        cdp.wait("!!document.querySelector('#model-name')")
        cdp.screenshot("desktop-settings.png")
        cdp.click('[data-view="discover"]')
        cdp.wait("!!document.querySelector('.hero')")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
        cdp.wait("innerWidth === 390")
        assert cdp.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile horizontal overflow"
        cdp.screenshot("mobile-discover.png")
        cdp.click('[data-action="menu"]')
        assert cdp.evaluate("document.querySelector('.sidebar').classList.contains('open')")
        cdp.click('[data-action="close-sidebar"]')
        cdp.click('.hero [data-action="start-chat"]')
        cdp.wait("!!document.querySelector('#chat-input')")
        assert cdp.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Mobile chat horizontal overflow"
        cdp.click('[data-action="toggle-info"]')
        assert cdp.evaluate("document.querySelector('#chat-side').classList.contains('open')")
        cdp.evaluate("document.querySelector('#room-mode').value='mature'; document.querySelector('#room-mode').dispatchEvent(new Event('change',{bubbles:true}))")
        cdp.wait("document.querySelector('.chat-header small').textContent.includes('18+')")
        cdp.evaluate("document.querySelector('#chat-side').classList.remove('open')")
        cdp.screenshot("mobile-chat.png")
        cdp.call("Page.reload")
        cdp.wait("document.querySelectorAll('.message').length === 7")
        assert cdp.evaluate("document.querySelector('.memory-item').textContent.includes('ฉันชื่อมิน')")
        exceptions = [item for item in cdp.events if item.get("method") == "Runtime.exceptionThrown"]
        console_errors = [item for item in cdp.events if item.get("method") == "Log.entryAdded" and item.get("params",{}).get("entry",{}).get("level") == "error"]
        assert not exceptions, exceptions
        assert not console_errors, console_errors
        print(json.dumps({"ok":True,"checks":["desktop rendering","mobile rendering","streamed chat","persistent history","isolated memory","milestone unlocks","gallery modal","character creation","settings save","adult theme confirmation","mobile menus","no console errors"],"screenshots":str(qa)},ensure_ascii=False))
        cdp.sock.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
