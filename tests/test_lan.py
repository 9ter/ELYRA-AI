"""Explicit LAN host opt-in preserves origin and mutation checks."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app import AppServer, lan_address
from elyra.store import Store


class LanTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'lan.db')
        self.server = AppServer(('127.0.0.1',0),self.store,lan_host='192.168.1.181')
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.host = f'192.168.1.181:{self.server.server_port}'
        self.logs = patch('app.Handler.log_message')
        self.logs.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.logs.stop()
        self.temp.cleanup()

    def request(self,path='/api/health',data=None,host=None,origin=None,token=None):
        headers={'Host':host or self.host,'Content-Type':'application/json'}
        if origin is not None:
            headers['Origin']=origin
        if token is not None:
            headers['X-Elyra-Token']=token
        request=urllib.request.Request(self.base+path,data=json.dumps(data).encode() if data is not None else None,headers=headers)
        try:
            return urllib.request.urlopen(request,timeout=5)
        except urllib.error.HTTPError as exc:
            exc.close()
            raise

    def test_exact_lan_and_loopback_hosts_work(self):
        for host in (self.host,f'localhost:{self.server.server_port}',f'127.0.0.1:{self.server.server_port}'):
            with self.request(host=host) as response:
                self.assertTrue(json.load(response)['ok'])

    def test_unconfigured_host_and_cross_origin_stay_blocked(self):
        for host,origin in ((f'192.168.1.182:{self.server.server_port}',None),
                            (f'evil.example:{self.server.server_port}',None),
                            (self.host,'http://evil.example'),(self.host,f'http://localhost:{self.server.server_port}')):
            with self.assertRaises(urllib.error.HTTPError) as raised:
                self.request(host=host,origin=origin)
            self.assertEqual(raised.exception.code,403)

    def test_lan_mutation_requires_token_and_correct_origin(self):
        payload={'characterId':'luna','provider':'demo','model':'story-demo'}
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request('/api/rooms',payload,origin='http://'+self.host)
        self.assertEqual(raised.exception.code,403)
        with self.request('/api/rooms',payload,origin='http://'+self.host,token=self.server.token) as response:
            self.assertEqual(response.status,201)
            self.assertEqual(json.load(response)['character_id'],'luna')

    def test_default_mode_does_not_allow_lan_host(self):
        local = AppServer(('127.0.0.1',0),self.store)
        thread = threading.Thread(target=local.serve_forever,daemon=True)
        thread.start()
        try:
            request = urllib.request.Request(f'http://127.0.0.1:{local.server_port}/api/health',
                headers={'Host':f'192.168.1.181:{local.server_port}'})
            with self.assertRaises(urllib.error.HTTPError) as raised:
                urllib.request.urlopen(request,timeout=5)
            raised.exception.close()
            self.assertEqual(raised.exception.code,403)
        finally:
            local.shutdown()
            local.server_close()
            thread.join()

    def test_lan_address_rejects_wildcards_public_and_hostnames(self):
        for value in ('0.0.0.0','8.8.8.8','127.0.0.1','localhost','192.168.1.181:3000','::1'):
            with self.assertRaises(ValueError):
                lan_address(value)
        for value in ('192.168.1.181','10.1.2.3','172.16.0.5'):
            self.assertEqual(lan_address(value),value)
        with self.assertRaises(ValueError):
            AppServer(('0.0.0.0',0),self.store)
