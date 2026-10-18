"""Capture public README examples with isolated data and Chrome (no model calls).

Run from the repository: python tools/capture_readme.py
Requires Windows Chrome at its standard installation path. Uses a disposable
profile and database under .qa; never opens the user's database or loads .env.
"""
import base64
import json
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from browser_qa import CDP, ROOT
from app import AppServer
from elyra.domain import validate_character
from elyra.media import validate_image
from elyra.store import Store


def main():
    output = ROOT / 'docs' / 'screenshots'
    output.mkdir(parents=True, exist_ok=True)
    (ROOT / '.qa').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='readme-', dir=ROOT / '.qa', ignore_cleanup_errors=True) as scratch:
        store = Store(Path(scratch) / 'demo.db')
        server = AppServer(('127.0.0.1', 0), store)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        chrome = subprocess.Popen([
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            '--headless=new', '--disable-gpu', '--no-first-run',
            '--remote-debugging-port=0', '--remote-allow-origins=http://localhost:9223',
            f'--user-data-dir={scratch}/chrome', 'about:blank',
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        cdp = None
        try:
            port_file = Path(scratch) / 'chrome' / 'DevToolsActivePort'
            for _ in range(100):
                if port_file.exists():
                    break
                time.sleep(.1)
            port = int(port_file.read_text().splitlines()[0])
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json') as response:
                page = next(p for p in json.load(response) if p['type'] == 'page')
            cdp = CDP(page['webSocketDebuggerUrl'])
            cdp.call('Page.enable')
            cdp.call('Runtime.enable')
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':1440,'height':1000,'deviceScaleFactor':1,'mobile':False})
            cdp.call('Page.navigate', {'url': f'http://localhost:{server.server_port}'})
            cdp.wait("typeof state!=='undefined' && state.data")
            # Rasterize repository-owned SVG illustrations for the sample scene slots.
            media = []
            for asset in ('luna-first.svg', 'luna-ritual.svg'):
                encoded = cdp.evaluate("""(async()=>{const i=new Image();i.src='/assets/""" + asset + """';await i.decode();const c=document.createElement('canvas');c.width=720;c.height=960;c.getContext('2d').drawImage(i,0,0,720,960);return c.toDataURL('image/png').split(',')[1]})()""")
                media.append(store.add_media(validate_image({'data':encoded}))['id'])
            characters = []
            for name, art, subtitle in [('ลูน่า','luna','นักดูดาวกับแผนที่ท้องฟ้า'),('ไค','kael','การเดินทางครั้งใหม่ของนักสำรวจ'),('มีรา','mira','ร้านกาแฟเล็ก ๆ ในวันฝนพรำ'),('เรน','ren','ปริศนาจากจดหมายฉบับหนึ่ง')]:
                characters.append(store.add_character(validate_character({
                    'name':name,'age':25,'art':art,'subtitle':subtitle,
                    'description':subtitle + ' — ตัวละครตัวอย่างสำหรับคู่มือ',
                    'personality':'อบอุ่น ช่างสังเกต มีความเห็นของตัวเอง ชอบแบ่งปันสิ่งที่ค้นพบ',
                    'backstory':'ดูแลหอดูดาวเล็ก ๆ และกำลังเตรียมคืนชมดาวสำหรับชุมชน',
                    'greeting':'*ลูน่าวางแผนที่ดาวลงบนโต๊ะข้างหน้าต่าง* คืนนี้ฟ้าเปิดพอดี มาช่วยเตรียมกล้องดูดาวด้วยกันนะ',
                    'tips':'ลองเริ่มจากช่วยเตรียมกล้อง หรือชวนคุยเรื่องกลุ่มดาวที่ชอบ',
                    'scenes':[{'id':'observatory','media_id':media[0],'description':'นั่งวางแผนการดูดาวด้วยกัน','tier':'common','min_turns':0},
                              {'id':'nightwalk','media_id':media[1],'description':'เดินชมท้องฟ้าในยามค่ำคืน','tier':'rare','min_turns':0}],
                })))
            room = store.create_room(characters[0]['id'],'demo','story-demo')
            store.commit_turn(room['id'],'ฉันช่วยจัดกล้องให้ เราจะเริ่มดูดาวตรงไหนกันดี',
                '*ลูน่าเลื่อนแผนที่เข้ามาใกล้ แล้วแตะจุดสว่างทางทิศเหนือ*\n\nเริ่มจากดาวเหนือก่อนนะ จะได้ใช้เป็นจุดอ้างอิง ฉันจะปรับขาตั้งให้ ส่วนแผนที่วางตรงนี้ได้เลย', 'demo','story-demo')
            store.add_memory(room['id'],'เรานัดกันเตรียมกล้องที่หอดูดาวในคืนฟ้าเปิด')
            store.set_scene(room['id'],'observatory')
            cdp.evaluate('refresh()')

            def capture(name, expression):
                cdp.evaluate(expression)
                cdp.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))")
                time.sleep(.3)
                data = cdp.call('Page.captureScreenshot',{'format':'png'})['data']
                (output / name).write_bytes(base64.b64decode(data))

            capture('01-discover.png', "navigate('discover')")
            capture('02-character.png', f"navigate('character','{characters[0]['id']}')")
            capture('03-editor.png', "document.querySelector('[data-action=\"create-character\"]').click()")
            cdp.evaluate("document.querySelector('#modal').close()")
            capture('04-chat.png', f"navigate('chat','{room['id']}')")
            capture('05-collection.png', "navigate('gallery')")
            capture('06-settings.png', "navigate('settings')")
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            capture('07-mobile.png', f"navigate('chat','{room['id']}')")
            errors = [e for e in cdp.events if e.get('method') == 'Runtime.exceptionThrown']
            if errors:
                raise AssertionError(errors)
            print(json.dumps({'screenshots':7,'model_calls':0,'private_data_used':False}))
        finally:
            if cdp:
                cdp.sock.close()
            chrome.terminate()
            chrome.wait(timeout=15)
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
