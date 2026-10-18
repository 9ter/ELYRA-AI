"""Authenticated HTTPS tunnel access keeps local/Origin/token checks intact."""
import base64
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app import AppServer, tunnel_origin
from elyra.store import Store


class TunnelTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'tunnel.db')
        self.origin = 'https://test.ngrok-free.app'
        self.auth = 'Basic ' + base64.b64encode(b'elyra:a-long-test-password-123').decode()
        self.server = AppServer(('127.0.0.1', 0), self.store,
            public_origin=self.origin,
            tunnel_credentials={'username': 'elyra', 'password': 'a-long-test-password-123'})
        self.logs = patch('app.Handler.log_message')
        self.logs.start()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.logs.stop()
        self.temp.cleanup()

    def request(self, path='/api/health', auth=True, origin=None, token=None, data=None, host='test.ngrok-free.app', extra=None):
        headers = {'Host': host, 'Content-Type': 'application/json'}
        if auth:
            headers['Authorization'] = self.auth if auth is True else auth
        if origin is not None:
            headers['Origin'] = origin
        if token is not None:
            headers['X-Elyra-Token'] = token
        headers.update(extra or {})
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request('POST' if data is not None else 'GET', path,
                body=json.dumps(data) if data is not None else None, headers=headers)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def test_all_hosts_and_sensitive_routes_require_login(self):
        for host in ('test.ngrok-free.app', f'localhost:{self.server.server_port}', f'127.0.0.1:{self.server.server_port}'):
            for path in ('/', '/api/health', '/api/bootstrap', '/api/export', '/app.js', '/api/rooms/example'):
                status, headers, body = self.request(path, auth=False, host=host)
                self.assertEqual(status, 401)
                self.assertIn('Basic realm="ELYRA"', headers['WWW-Authenticate'])
                self.assertNotIn(b'token', body)
        self.assertEqual(self.request(auth='Basic incorrect')[0], 401)
        self.assertEqual(self.request('/api/rooms', auth=False, data={})[0], 401)

    def test_exact_origin_host_and_token_are_independently_required(self):
        self.assertEqual(self.request()[0], 200)
        for origin in ('https://evil.example', 'http://test.ngrok-free.app', 'null', self.origin + '.evil.example'):
            self.assertEqual(self.request(origin=origin)[0], 403)
        self.assertEqual(self.request(host='evil.example')[0], 403)
        self.assertEqual(self.request(host=f'localhost:{self.server.server_port}', origin=self.origin,
            extra={'X-Forwarded-Host': 'test.ngrok-free.app', 'X-Forwarded-Proto': 'https'})[0], 403)
        payload = {'characterId': 'luna', 'provider': 'demo', 'model': 'story-demo'}
        self.assertEqual(self.request('/api/rooms', data=payload, origin=self.origin)[0], 403)
        self.assertEqual(self.request('/api/rooms', data=payload, origin='https://evil.example', token=self.server.token)[0], 403)
        status, _, body = self.request('/api/rooms', data=payload, origin=self.origin, token=self.server.token)
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)['character_id'], 'luna')
        local = f'localhost:{self.server.server_port}'
        self.assertEqual(self.request(host=local, origin='http://' + local)[0], 200)

    def test_tunnel_configuration_fails_closed(self):
        for origin in ('http://test.ngrok-free.app', 'https://host/path', 'https://user:pass@host', 'https://host:443', 'https://host?query', 'https://host\n'):
            with self.assertRaises(ValueError):
                tunnel_origin(origin)
        for kwargs in ({'public_origin': self.origin},
                       {'tunnel_no_auth': True},
                       {'public_origin': self.origin, 'tunnel_no_auth': True,
                        'tunnel_credentials': {'username': 'elyra', 'password': 'long-password-123'}},
                       {'tunnel_credentials': {'username': 'elyra', 'password': 'long-password-123'}},
                       {'public_origin': self.origin, 'tunnel_credentials': {'username': 'elyra', 'password': 'short'}}):
            with self.assertRaises(ValueError):
                AppServer(('127.0.0.1', 0), self.store, **kwargs)

    def test_explicit_no_auth_mode_keeps_host_origin_and_mutation_checks(self):
        server = AppServer(('127.0.0.1', 0), self.store,
            public_origin=self.origin, tunnel_no_auth=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original = self.server
        self.server = server
        try:
            status, headers, body = self.request('/api/bootstrap', auth=False)
            self.assertEqual(status, 200)
            self.assertNotIn('WWW-Authenticate', headers)
            token = json.loads(body)['token']
            self.assertEqual(self.request(auth=False, host='evil.example')[0], 403)
            self.assertEqual(self.request(auth=False, origin='https://evil.example')[0], 403)
            self.assertEqual(self.request('/api/nonexistent', auth=False, origin=self.origin, data={})[0], 403)
            self.assertEqual(self.request('/api/nonexistent', auth=False, origin=self.origin, data={}, token=token)[0], 404)
        finally:
            self.server = original
            server.shutdown()
            server.server_close()
            thread.join()
