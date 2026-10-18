"""Real LAN HTTP browser check with isolated data and no model calls. Chrome DevTools:9223 required."""
import argparse
import json
import threading
import time
import urllib.request

from browser_qa import CDP, ROOT
from app import AppServer, lan_address
from elyra.store import Store


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--lan',type=lan_address,default='192.168.1.181')
    args=parser.parse_args()
    server=AppServer(('0.0.0.0',0),Store(ROOT/'.qa'/f'lan-browser-{time.time_ns()}.db'),lan_host=args.lan)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    cdp=None
    try:
        with urllib.request.urlopen('http://127.0.0.1:9223/json') as response:
            page=next(item for item in json.load(response) if item['type']=='page')
        cdp=CDP(page['webSocketDebuggerUrl'])
        for method in ('Page.enable','Runtime.enable','Log.enable'):
            cdp.call(method)
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        cdp.call('Page.navigate',{'url':f'http://{args.lan}:{server.server_port}'})
        cdp.wait("typeof state!=='undefined' && state.data?.characters.length===4")
        assert cdp.evaluate("!isSecureContext"), 'Test must cover plain HTTP on a LAN IP'
        assert cdp.evaluate("/^[a-f0-9]{32}$/.test(newId())")
        cdp.evaluate("startChat('luna')")
        cdp.wait("!!document.querySelector('#chat-input')")
        cdp.fill('#chat-input','Hello over LAN')
        cdp.evaluate("document.querySelector('#chat-form').requestSubmit()")
        cdp.wait("!state.sending && state.room.turns===1 && document.querySelectorAll('.message').length===3")
        assert cdp.evaluate("!sessionStorage.getItem('elyra-pending-'+state.room.id)")
        cdp.click('[data-action="create-character"]')
        cdp.wait("!!document.querySelector('#character-form')")
        cdp.click('[data-action="add-scene"]')
        cdp.wait("document.querySelectorAll('.scene-row').length===1")
        cdp.click('[data-action="remove-scene"][data-index="0"]')
        for field,value in (('name','LAN QA'),('description','A friendly traveller'),('personality','Curious and kind'),('greeting','Hello')):
            cdp.fill('#char-'+field,value)
        cdp.evaluate("document.querySelector('#character-form').requestSubmit()")
        cdp.wait("!document.querySelector('#modal').open && state.data.characters.some(c=>c.name==='LAN QA')")
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        assert cdp.evaluate("document.documentElement.scrollWidth<=innerWidth")
        cdp.call('Page.reload')
        cdp.wait("typeof state!=='undefined' && state.data?.characters.some(c=>c.name==='LAN QA')")
        errors=[event for event in cdp.events if event.get('method')=='Runtime.exceptionThrown' or
            (event.get('method')=='Log.entryAdded' and event.get('params',{}).get('entry',{}).get('level')=='error')]
        assert not errors, errors
        print(json.dumps({'ok':True,'checks':['plain LAN HTTP','random request IDs without secure context',
            'same-origin streamed chat','character creation','scene ID creation','mobile/reload','no console errors'],
            'testedFromOtherDevice':False}))
    finally:
        if cdp:
            cdp.sock.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__=='__main__':
    main()
