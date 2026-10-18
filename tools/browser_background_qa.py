"""Regression: old chat snapshots must display the latest portrait and scene images.

Requires a dedicated Chrome DevTools instance on port 9223; no inference or user data changes.
"""
import binascii
import json
import struct
import threading
import time
import urllib.request
import zlib

from browser_qa import CDP, ROOT
from app import AppServer
from elyra.domain import validate_character
from elyra.media import validate_image
from elyra.store import Store
import base64


def image(color):
    def chunk(kind, data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
            +chunk(b'IDAT',zlib.compress(b'\x00'+bytes(color)))+chunk(b'IEND',b''))


def main():
    qa = ROOT / '.qa'
    qa.mkdir(exist_ok=True)
    store = Store(qa / f'background-{time.time_ns()}.db')
    original = store.add_character(validate_character({'name':'Background QA','age':25,
        'description':'Original description','personality':'Original persona','greeting':'Hello','art':'luna'}))
    rooms = []
    for turns in (0,1,3):
        room = store.create_room(original['id'],'demo','story-demo')
        for _ in range(turns):
            store.commit_turn(room['id'],'Hello','Welcome','demo','story-demo')
        rooms.append(store.room(room['id']))
    media = [store.add_media(validate_image({'data':base64.b64encode(image(color)).decode()}))['id']
             for color in ((120,70,150),(40,120,100),(60,70,150))]
    live = store.update_character(original['id'],{**original,'personality':'New persona',
        'portrait_id':media[0],
        'scenes':[{'id':'scene001','media_id':media[1],'description':'At the observatory','tier':'common','min_turns':0}]},1)
    server = AppServer(('127.0.0.1',0),store)
    thread = threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    cdp = None
    try:
        with urllib.request.urlopen('http://127.0.0.1:9223/json') as response:
            page = next(item for item in json.load(response) if item['type']=='page')
        cdp = CDP(page['webSocketDebuggerUrl'])
        for method in ('Page.enable','Runtime.enable','Log.enable'):
            cdp.call(method)
        cdp.call('Page.navigate',{'url':f'http://localhost:{server.server_port}'})
        cdp.wait("typeof state!=='undefined' && state.data?.characters.length===5")
        for mobile in (False,True):
            cdp.call('Emulation.setDeviceMetricsOverride',{'width':390 if mobile else 1440,
                'height':844 if mobile else 1100,'deviceScaleFactor':1,'mobile':mobile})
            for room in rooms:
                cdp.evaluate(f"navigate('chat',{json.dumps(room['id'])})")
                cdp.wait(f"document.querySelector('.tc-chat-bg')?.getAttribute('src')==='/media/{media[0]}'")
                cdp.wait("document.querySelector('.tc-chat-bg').complete && document.querySelector('.tc-chat-bg').naturalWidth>0")
                assert cdp.evaluate(f"document.querySelector('.side-portrait').getAttribute('src')==='/media/{media[0]}'")
                cdp.wait("document.querySelector('.side-portrait').complete && document.querySelector('.side-portrait').naturalWidth>0")
                assert cdp.evaluate("state.room.character.personality==='Original persona'")
                assert cdp.evaluate("document.documentElement.scrollWidth<=innerWidth")
        store.set_scene(rooms[-1]['id'],'scene001')
        cdp.call('Page.reload')
        cdp.wait(f"document.querySelector('.tc-chat-bg')?.getAttribute('src')==='/media/{media[1]}'")
        assert cdp.evaluate(f"document.querySelector('.side-portrait').getAttribute('src')==='/media/{media[0]}'")
        # Editing the portrait updates old-room artwork without changing its persona.
        store.update_character(original['id'],{**live,'portrait_id':media[2],'scenes':[]},2)
        cdp.call('Page.reload')
        cdp.wait(f"document.querySelector('.tc-chat-bg')?.getAttribute('src')==='/media/{media[2]}'")
        assert cdp.evaluate(f"document.querySelector('.side-portrait').getAttribute('src')==='/media/{media[2]}' && state.room.character.personality==='Original persona'")
        # If the character is absent from bootstrap, a saved room still has a usable fallback.
        cdp.evaluate("state.data.characters=state.data.characters.filter(c=>c.id!==state.room.character.id); render()")
        assert cdp.evaluate("document.querySelector('.tc-chat-bg').getAttribute('src')==='/assets/luna.svg' && document.querySelector('.side-portrait').getAttribute('src')==='/assets/luna.svg'")
        errors = [event for event in cdp.events if event.get('method')=='Runtime.exceptionThrown' or
                  (event.get('method')=='Log.entryAdded' and event.get('params',{}).get('entry',{}).get('level')=='error')]
        assert not errors, errors
        print(json.dumps({'ok':True,'checks':['old room current background','right-side portrait follows latest upload',
            'portrait edit updates old room','persona snapshot unchanged','scene priority','removed scene fallback',
            'missing character fallback','reload','desktop/mobile','no console errors']}))
    finally:
        if cdp:
            cdp.sock.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__=='__main__':
    main()
