"""Capture public README examples with isolated data and Chrome (no model calls).

Run from the repository: python tools/capture_readme.py
Requires Windows Chrome at its standard installation path. Uses a disposable
profile and database under .qa; never loads .env. Optional --artwork-db and
--artwork-selection copy explicitly selected names/artwork through read-only SQL;
no original persona, settings, rooms, messages or memories are copied.
"""
import argparse
import base64
from contextlib import closing
import json
import sqlite3
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


def selected_artwork(database, selection, store):
    """Import only individually reviewed artwork into the disposable fixture."""
    result = []
    with closing(sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)) as source:
        def copy_media(media_id):
            row = source.execute('SELECT data FROM media WHERE id=?', (media_id,)).fetchone()
            if not row:
                raise ValueError('Selected artwork is missing')
            return store.add_media(validate_image({'data':base64.b64encode(row[0]).decode()}))['id']

        for item in json.loads(Path(selection).read_text(encoding='utf-8')):
            if len(item.get('scene_ids', [])) > 3:
                raise ValueError('Select at most three reviewed scenes per character')
            row = source.execute('SELECT data FROM characters WHERE id=?', (item['character_id'],)).fetchone()
            if not row:
                raise ValueError('Selected character is missing')
            current = json.loads(row[0])
            scenes = []
            for index, scene_id in enumerate(item.get('scene_ids', [])):
                scene = next(s for s in current.get('scenes', []) if s['id'] == scene_id)
                scenes.append({'id':f'publicscene{index}', 'media_id':copy_media(scene['media_id']),
                               'description':['ต้อนรับกลับบ้านพร้อมชาร้อน','เตรียมอาหารเช้าด้วยกัน','อ่านหนังสือในห้องนั่งเล่น'][index],
                               'tier':['common','common','rare'][index], 'min_turns':0})
            result.append({'name':current['name'], 'art':'luna',
                           'portrait_id':copy_media(current['portrait_id']), 'scenes':scenes,
                           'subtitle':'ตัวอย่างตัวละครพร้อมภาพปัจจุบัน'})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artwork-db', type=Path)
    parser.add_argument('--artwork-selection', type=Path, help='JSON list of character_id and up to three reviewed scene_ids')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'docs' / 'screenshots')
    args = parser.parse_args()
    if bool(args.artwork_db) != bool(args.artwork_selection):
        parser.error('Both artwork options are required together')
    output = args.output_dir
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
            samples = (selected_artwork(args.artwork_db, args.artwork_selection, store) if args.artwork_db else
                       [{'name':name,'art':art,'subtitle':subtitle} for name,art,subtitle in
                        [('ลูน่า','luna','นักดูดาวกับแผนที่ท้องฟ้า'),('ไค','kael','การเดินทางครั้งใหม่ของนักสำรวจ'),
                         ('มีรา','mira','ร้านกาแฟเล็ก ๆ ในวันฝนพรำ'),('เรน','ren','ปริศนาจากจดหมายฉบับหนึ่ง')]])
            characters = []
            for sample in samples:
                name, art, subtitle = sample['name'], sample['art'], sample['subtitle']
                characters.append(store.add_character(validate_character({
                    'name':name,'age':25,'art':art,'subtitle':subtitle,
                    'description':subtitle + ' — ตัวละครตัวอย่างสำหรับคู่มือ',
                    'personality':'อบอุ่น ช่างสังเกต มีความเห็นของตัวเอง ชอบแบ่งปันสิ่งที่ค้นพบ',
                    'backstory':'ดูแลหอดูดาวเล็ก ๆ และกำลังเตรียมคืนชมดาวสำหรับชุมชน',
                    'greeting':f'*{name}วางถ้วยชาลงบนโต๊ะข้างหน้าต่าง* กลับมาแล้วเหรอ นั่งพักด้วยกันก่อนนะ',
                    'tips':'ลองเริ่มจากช่วยเตรียมกล้อง หรือชวนคุยเรื่องกลุ่มดาวที่ชอบ',
                    'scenes':[{'id':'observatory','media_id':media[0],'description':'นั่งวางแผนการดูดาวด้วยกัน','tier':'common','min_turns':0},
                              {'id':'nightwalk','media_id':media[1],'description':'เดินชมท้องฟ้าในยามค่ำคืน','tier':'rare','min_turns':0}],
                    **sample,
                })))
            room = store.create_room(characters[0]['id'],'demo','story-demo')
            store.commit_turn(room['id'],'วันนี้อากาศดีจัง มานั่งดื่มชาแล้วค่อยเลือกหนังสืออ่านกันนะ',
                f'*{characters[0]["name"]}เลื่อนถ้วยชามาให้ แล้ววางหนังสือไว้ข้างโต๊ะ*\n\nได้เลย ฉันเตรียมชาไว้พอดี นั่งตรงนี้สิ แสงจากสวนกำลังสวยเลย', 'demo','story-demo')
            store.add_memory(room['id'],'เรานัดดื่มชาและเลือกหนังสืออ่านด้วยกัน')
            if not characters or not characters[0]['scenes']:
                raise ValueError('The first selected character needs at least one reviewed scene')
            store.set_scene(room['id'],characters[0]['scenes'][0]['id'])
            cdp.evaluate('refresh()')

            def capture(name, expression):
                cdp.evaluate(expression)
                cdp.evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>{})))")
                time.sleep(.3)
                data = cdp.call('Page.captureScreenshot',{'format':'png'})['data']
                (output / name).write_bytes(base64.b64decode(data))

            capture('01-discover.png', "navigate('discover')")
            capture('02-character.png', f"navigate('character','{characters[0]['id']}')")
            cdp.evaluate("navigate('characters')")
            capture('03-editor.png', f"MvpUI.action({{dataset:{{action:'edit-character',id:'{characters[0]['id']}'}}}})")
            capture('08-scene-editor.png', "document.querySelector('#scene-editor').scrollIntoView({block:'start'}); document.querySelector('#modal').scrollTop -= 160")
            cdp.evaluate("document.querySelector('#modal').close()")
            capture('04-chat.png', f"navigate('chat','{room['id']}')")
            capture('05-collection.png', "navigate('gallery')")
            capture('06-settings.png', "navigate('settings')")
            cdp.call('Emulation.setDeviceMetricsOverride', {'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
            capture('07-mobile.png', f"navigate('chat','{room['id']}')")
            errors = [e for e in cdp.events if e.get('method') == 'Runtime.exceptionThrown']
            if errors:
                raise AssertionError(errors)
            print(json.dumps({'screenshots':8,'model_calls':0,'current_artwork':bool(args.artwork_db),
                              'private_chat_used':False}))
        finally:
            if cdp:
                cdp.sock.close()
            chrome.terminate()
            chrome.wait(timeout=15)
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    main()
