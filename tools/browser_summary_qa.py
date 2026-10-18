"""Automatic recap UI regression with isolated data; requires Chrome DevTools on port 9223."""
import json
import threading
import time
import urllib.request

from browser_qa import CDP, ROOT
from app import AppServer
from elyra.store import Store


def main():
    store = Store(ROOT/'.qa'/f'summary-browser-{time.time_ns()}.db')
    first = store.create_room('luna','xai','test-model')
    second = store.create_room('kael','demo','story-demo')
    store.save_notes(first['id'],'Keep my original note')
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
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':1440,'height':1100,'deviceScaleFactor':1,'mobile':False})
        cdp.call('Page.navigate',{'url':f'http://localhost:{server.server_port}/#chat/{first["id"]}'})
        cdp.wait("!!document.querySelector('.auto-story-summary')")
        assert cdp.evaluate("document.querySelectorAll('.auto-story-summary').length===1 && !document.querySelector('.auto-story-summary [data-action]')")
        assert cdp.evaluate("document.querySelector('.legacy-story-notes').textContent.includes('Keep my original note')")
        cdp.click('[data-action="toggle-info"]')
        cdp.evaluate("window.qaMessages=document.querySelector('#messages'); const input=document.querySelector('#chat-input'); input.value='My unsent draft'; input.focus(); input.setSelectionRange(3,8)")
        with server.room_lock:
            server.summarizing.add(first['id'])
        cdp.wait("state.room.summary_state==='updating'")
        assert cdp.evaluate("document.querySelector('.auto-summary-status').textContent.includes('กำลังอัปเดต')")
        store.save_summary(first['id'],'Luna and the user met at the flower shop. <script>window.unwanted=true</script>',1,0)
        with server.room_lock:
            server.summarizing.discard(first['id'])
        cdp.wait("state.room.summary_state==='idle' && !!document.querySelector('.auto-summary-text')")
        assert cdp.evaluate("!window.unwanted && !document.querySelector('.auto-summary-text script')")
        assert cdp.evaluate("document.querySelector('#messages')===window.qaMessages && document.querySelector('#chat-input').value==='My unsent draft' && document.activeElement.id==='chat-input' && document.activeElement.selectionStart===3 && document.activeElement.selectionEnd===8")
        with server.room_lock:
            server.summary_errors.add(first['id'])
        cdp.wait("state.room.summary_state==='error'")
        assert cdp.evaluate("!!document.querySelector('.auto-summary-text')")
        cdp.screenshot('desktop-auto-summary.png')
        with server.room_lock:
            server.summary_errors.discard(first['id'])
        cdp.wait("state.room.summary_state==='idle'")
        cdp.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
        assert cdp.evaluate("document.documentElement.scrollWidth<=innerWidth")
        cdp.screenshot('mobile-auto-summary.png')
        cdp.evaluate(f"navigate('chat',{json.dumps(second['id'])})")
        cdp.wait("!!document.querySelector('.auto-story-summary') && !document.querySelector('.auto-summary-text')")
        assert cdp.evaluate("!document.querySelector('.legacy-story-notes')")
        cdp.call('Page.reload')
        cdp.wait("!!document.querySelector('.auto-story-summary')")
        assert cdp.evaluate("!document.querySelector('.auto-summary-text')")
        assert store.room(first['id'])['notes']=='Keep my original note'
        assert store.room(second['id'])['summary']==''
        errors=[event for event in cdp.events if event.get('method')=='Runtime.exceptionThrown' or
                (event.get('method')=='Log.entryAdded' and event.get('params',{}).get('entry',{}).get('level')=='error')]
        assert not errors, errors
        print(json.dumps({'ok':True,'checks':['one automatic recap panel','no manual recap required',
            'live working/completed/error status','preserve summary on error','preserve manual notes',
            'preserve chat/draft/focus/selection','escaped summary','room isolation','reload','desktop/mobile','no inference']}))
    finally:
        if cdp:
            cdp.sock.close()
        server.shutdown()
        server.server_close()
        thread.join()


if __name__=='__main__':
    main()
