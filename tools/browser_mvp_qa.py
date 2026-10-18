"""Authoring/story browser checks. Dedicated Chrome DevTools on port 9223 required."""
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

from browser_qa import CDP, ROOT
sys.path.insert(0, str(ROOT / "tests"))
from test_mvp import png_image
from app import AppServer
from elyra.store import Store


def main():
    qa = ROOT / ".qa"
    fixture = qa / "upload-fixture.png"
    fixture.write_bytes(png_image())
    server = AppServer(("127.0.0.1", 0), Store(qa / f"mvp-browser-{time.time_ns()}.db"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    cdp = None
    try:
        with urllib.request.urlopen("http://127.0.0.1:9223/json") as response:
            page = next(item for item in json.load(response) if item["type"] == "page")
        cdp = CDP(page["webSocketDebuggerUrl"])
        for method in ("Page.enable", "Runtime.enable", "Log.enable", "DOM.enable"):
            cdp.call(method)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width":1440,"height":1100,"deviceScaleFactor":1,"mobile":False})
        cdp.call("Page.navigate", {"url":f"http://localhost:{server.server_port}"})
        cdp.wait("document.querySelectorAll('.character-card').length === 4")
        cdp.click('[data-view="characters"]')
        cdp.click('[data-action="create-character"]')
        for field,value in (("name","Orbit QA"),("description","A quiet observatory"),("personality","Kind and curious"),("greeting","Welcome to the stars"),("tips","Ask about the telescope")):
            cdp.fill(f"#char-{field}",value)
        for target in ("portrait", "first-light"):
            root = cdp.call("DOM.getDocument")["root"]["nodeId"]
            node = cdp.call("DOM.querySelector", {"nodeId":root,"selector":f'[data-upload-target="{target}"]'})["nodeId"]
            cdp.call("DOM.setFileInputFiles", {"nodeId":node,"files":[str(fixture)]})
            preview = "#character-image-preview" if target == "portrait" else "#gallery-preview-first-light"
            cdp.wait(f"document.querySelector('{preview}').getAttribute('src').startsWith('/media/') && !document.querySelector('#character-form [type=submit]').disabled")
        cdp.screenshot("desktop-character-editor.png")
        cdp.evaluate("document.querySelector('#character-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && state.data.characters.some(c=>c.name==='Orbit QA')")
        character_id = cdp.evaluate("state.data.characters.find(c=>c.name==='Orbit QA').id")
        card = f'.character-card:has([data-action="start-chat"][data-id="{character_id}"])'
        cdp.click(f'{card} [data-action="character-details"]')
        cdp.wait("document.querySelector('#modal').textContent.includes('Ask about the telescope')")
        cdp.click('[data-action="profile-chat"]')
        cdp.wait("!!document.querySelector('#chat-input')")
        original_room = cdp.evaluate("state.room.id")
        assert cdp.evaluate("document.querySelector('.character-tips').textContent.includes('Ask about the telescope')")
        cdp.fill("#chat-input", "Hello")
        cdp.evaluate("document.querySelector('#chat-form').requestSubmit()")
        cdp.wait("document.querySelectorAll('.message').length===3 && !!document.querySelector('.story-moment img[src^=\"/media/\"]') && !state.sending")
        cdp.click('[data-action="story-notes"]')
        cdp.fill("#story-notes-input", "We met at the observatory")
        cdp.evaluate("document.querySelector('#notes-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && document.querySelector('.story-notes-preview').textContent.includes('observatory')")
        cdp.screenshot("desktop-mvp-chat.png")
        cdp.click('[data-view="characters"]')
        cdp.click(f'{card} [data-action="edit-character"]')
        cdp.fill("#char-name", "Orbit revised")
        cdp.fill("#char-tips", "New version tips")
        cdp.evaluate("document.querySelector('#character-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && state.data.characters.some(c=>c.name==='Orbit revised')")
        cdp.evaluate(f"navigate('chat',{json.dumps(original_room)})")
        cdp.wait("document.querySelector('.chat-header h1').textContent==='Orbit QA'")
        assert cdp.evaluate("document.querySelector('.character-tips').textContent.includes('Ask about the telescope')")
        cdp.click('.message.assistant:last-of-type [data-action="branch-story"]')
        cdp.click('[data-action="confirm-branch"]')
        cdp.wait(f"state.room.id!=={json.dumps(original_room)} && document.querySelectorAll('.message').length===3")
        assert cdp.evaluate("state.room.notes==='' && !!state.room.parent_room_id")
        cdp.click('[data-view="characters"]')
        cdp.click(f'{card} [data-action="archive-character"]')
        cdp.click('[data-action="confirm-archive"]')
        cdp.wait(f"!document.querySelector('{card}') && !document.querySelector('#modal').open")
        cdp.click('[data-action="show-archived-characters"]')
        cdp.wait(f"!!document.querySelector('{card}')")
        assert cdp.evaluate(f"document.querySelector('{card} [data-action=\"start-chat\"]').disabled")
        cdp.click(f'{card} [data-action="restore-character"]')
        cdp.wait(f"!document.querySelector('{card}')")
        cdp.click('[data-action="show-active-characters"]')
        cdp.wait(f"!!document.querySelector('{card}')")
        cdp.click(f'{card} [data-action="clone-character"]')
        cdp.wait("document.querySelector('#char-name').value.includes('Orbit revised')")
        assert cdp.evaluate("document.querySelector('#character-image-preview').getAttribute('src').startsWith('/media/')")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width":390,"height":844,"deviceScaleFactor":1,"mobile":True})
        cdp.wait("innerWidth===390")
        assert cdp.evaluate("document.querySelector('#modal').scrollWidth<=document.querySelector('#modal').clientWidth"), "Mobile editor overflow"
        cdp.screenshot("mobile-character-editor.png")
        cdp.click('[data-action="close-modal"]')
        cdp.evaluate(f"navigate('chat',{json.dumps(original_room)})")
        cdp.wait("!!document.querySelector('.story-moment')")
        assert cdp.evaluate("document.documentElement.scrollWidth<=innerWidth"), "Mobile story overflow"
        cdp.screenshot("mobile-mvp-chat.png")
        cdp.click('.story-moment')
        cdp.wait("document.querySelector('#modal').open && !!document.querySelector('.modal-scene[src^=\"/media/\"]')")
        cdp.click('[data-action="close-modal"]')
        cdp.fill("#chat-input", "Unsent draft")
        cdp.evaluate("document.querySelector('#chat-input').dispatchEvent(new Event('input',{bubbles:true}))")
        cdp.call("Page.reload")
        cdp.wait("document.querySelector('#chat-input')?.value==='Unsent draft'")
        assert cdp.evaluate("state.room.notes.includes('observatory')")
        errors = [event for event in cdp.events if event.get("method")=="Runtime.exceptionThrown" or (event.get("method")=="Log.entryAdded" and event.get("params",{}).get("entry",{}).get("level")=="error")]
        assert not errors, errors
        print(json.dumps({"ok":True,"checks":["portrait upload","milestone image upload","tips/profile","inline unlocked image","manual story recap","versioned edit keeps old room","story branching","archive/restore","duplicate with media","mobile editor/chat","uploaded gallery modal","draft restore","no console errors"]}))
    finally:
        if cdp:
            cdp.sock.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
