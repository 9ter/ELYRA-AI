"""Exercise both Windows launchers with isolated app/agent fixtures, no real tunnel."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'

APP = '''import argparse,base64,json,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,HTTPServer
p=argparse.ArgumentParser()
p.add_argument('--port',type=int)
p.add_argument('--lan')
p.add_argument('--tunnel-origin')
p.add_argument('--tunnel-credentials')
a=p.parse_args()
Path('.data/arguments.json').write_text(json.dumps(sys.argv))
if Path('.data/fail-app').exists():raise SystemExit(1)
login=json.loads(Path(a.tunnel_credentials).read_text()) if a.tunnel_credentials else None
auth='Basic '+base64.b64encode((login['username']+':'+login['password']).encode()).decode() if login else None
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  ok=auth is None or self.headers.get('Authorization')==auth
  body=json.dumps({'ok':True,'app':'ELYRA'} if ok else {'error':'login required'}).encode()
  self.send_response(200 if ok else 401)
  self.send_header('Content-Type','application/json')
  self.send_header('Content-Length',str(len(body)))
  if not ok:self.send_header('WWW-Authenticate','Basic realm="ELYRA"')
  self.end_headers();self.wfile.write(body)
HTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
'''


@unittest.skipUnless(os.name == 'nt' and CSC.is_file(), 'Windows PowerShell/.NET compiler required')
class BackgroundStartTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='elyra start build ')
        source = Path(cls.build.name) / 'fake.cs'
        source.write_text('class Program { static void Main(string[] args) { System.Threading.Thread.Sleep(120000); } }')
        cls.agent = Path(cls.build.name) / 'ngrok.exe'
        subprocess.run([str(CSC), '/nologo', '/target:exe', '/out:' + str(cls.agent), str(source)],
            check=True, capture_output=True, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='elyra background fixture ')
        self.root = Path(self.temp.name)
        (self.root / '.data').mkdir()
        (self.root / 'tools').mkdir()
        for name in ('start.bat', 'start.ps1', 'stop.bat', 'stop.ps1'):
            shutil.copy2(ROOT / name, self.root / name)
        (self.root / 'app.py').write_text(APP)
        self.login = {'username': 'elyra', 'password': 'test-password-123456789'}
        (self.root / '.data/ngrok-access.json').write_text(json.dumps(self.login))
        # Keep the real launcher/process handling, but replace cloud/API discovery.
        # The fake executable only sleeps and never opens a tunnel or API listener.
        shim = f'''import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('launcher',{str(ROOT / 'tools/start_background.py')!r})
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.ROOT=Path(__file__).resolve().parents[1]
original_snapshot=m.snapshot
original_launch=m.launch
def snapshot(port,api_port=4040):
 state=original_snapshot(port,api_port)
 state['listeners']=[x for x in state['listeners'] if x['LocalPort']!=api_port]
 path=m.ROOT/'.data/fake-agent.pid'
 if path.exists():
  pid=int(path.read_text())
  if any(x['ProcessId']==pid for x in state['processes']):
   state['listeners'].append({{'LocalPort':api_port,'OwningProcess':pid}})
 return state
def launch(command,root,prefix):
 process=original_launch(command,root,prefix)
 with (root/'.data/launches.jsonl').open('a') as log:log.write(json.dumps(command)+'\\n')
 if prefix=='ngrok-start':(root/'.data/fake-agent.pid').write_text(str(process.pid))
 return process
m.snapshot=snapshot
m.launch=launch
m.find_ngrok=lambda:{str(self.agent)!r}
m.tunnel_url=lambda *args:'https://fixture.ngrok-free.app'
raise SystemExit(m.main())
'''
        (self.root / 'tools/start_background.py').write_text(shim)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]

    def tearDown(self):
        # Fixture PIDs only. No production PID files or services are touched.
        for name in ('server.pid', 'ngrok.pid', 'fake-agent.pid'):
            path = self.root / '.data' / name
            if path.exists():
                subprocess.run(['taskkill', '/PID', path.read_text().strip(), '/F'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)
        self.temp.cleanup()

    def run_start(self, *extra, powershell=False, local=False):
        if powershell:
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(self.root / 'start.ps1')]
        else:
            command = ['cmd.exe', '/d', '/c', str(self.root / 'start.bat')]
        return subprocess.run(command + ([] if local else ['--ngrok']) + ['--port', str(self.port), *extra],
            cwd=self.root.parent, input='\n', capture_output=True, text=True, timeout=45,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def test_batch_starts_detached_services_and_reuses_them(self):
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('running in the background', result.stdout)
        self.assertNotIn(self.login['password'], result.stdout + result.stderr)
        self.assertEqual((self.root / '.data/ngrok-url.txt').read_text().strip(), 'https://fixture.ngrok-free.app')
        pids = [(self.root / '.data' / name).read_text() for name in ('server.pid', 'ngrok.pid')]
        # The wrapper has exited; both services must survive it and be reusable.
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(pids, [(self.root / '.data' / name).read_text() for name in ('server.pid', 'ngrok.pid')])
        self.assertEqual(len((self.root / '.data/launches.jsonl').read_text().splitlines()), 2)
        stopped = subprocess.run(['cmd.exe', '/d', '/c', str(self.root / 'stop.bat'), str(self.port)],
            cwd=self.root, input='\n', capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(stopped.returncode, 0, stopped.stdout + stopped.stderr)
        self.assertFalse((self.root / '.data/server.pid').exists())
        self.assertFalse((self.root / '.data/ngrok.pid').exists())

    def test_powershell_preserves_lan_and_credential_path_with_spaces(self):
        path = self.root / 'login files/private login.json'
        path.parent.mkdir()
        path.write_text(json.dumps(self.login))
        result = self.run_start('--lan', '192.168.1.181', '--tunnel-credentials', str(path), powershell=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = json.loads((self.root / '.data/arguments.json').read_text())
        self.assertEqual(args[args.index('--lan') + 1], '192.168.1.181')
        self.assertEqual(args[args.index('--tunnel-credentials') + 1], str(path))

    def test_app_failure_rolls_back_only_new_ngrok_and_reports_failure(self):
        (self.root / '.data/fail-app').touch()
        result = self.run_start()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ELYRA exited during startup', result.stderr)
        self.assertFalse((self.root / '.data/server.pid').exists())
        pid = (self.root / '.data/fake-agent.pid').read_text().strip()
        alive = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            f'if (Get-Process -Id {int(pid)} -ErrorAction SilentlyContinue) {{ exit 1 }}'],
            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(alive.returncode, 0)

    def test_foreign_listener_is_preserved_and_no_ngrok_is_started(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', self.port))
            listener.listen(5)
            result = self.run_start()
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('another Python program', result.stderr)
            self.assertFalse((self.root / '.data/launches.jsonl').exists())
            with socket.create_connection(('127.0.0.1', self.port), timeout=1):
                pass

    def test_app_failure_does_not_stop_an_existing_agent(self):
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        app_pid = (self.root / '.data/server.pid').read_text().strip()
        agent_pid = (self.root / '.data/ngrok.pid').read_text().strip()
        subprocess.run(['taskkill', '/PID', app_pid, '/F'], check=True, capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW)
        (self.root / '.data/server.pid').unlink()
        (self.root / '.data/fail-app').touch()
        result = self.run_start()
        self.assertNotEqual(result.returncode, 0)
        alive = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
            f'if (-not (Get-Process -Id {int(agent_pid)} -ErrorAction SilentlyContinue)) {{ exit 1 }}'],
            capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(alive.returncode, 0)

    def test_default_starts_only_local_app_without_login_and_reuses_it(self):
        result = self.run_start(local=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('local, ngrok disabled', result.stdout)
        self.assertFalse((self.root / '.data/fake-agent.pid').exists())
        self.assertFalse((self.root / '.data/ngrok.pid').exists())
        arguments = json.loads((self.root / '.data/arguments.json').read_text())
        self.assertNotIn('--tunnel-origin', arguments)
        self.assertNotIn('--tunnel-credentials', arguments)
        initial_pid = (self.root / '.data/server.pid').read_text()
        result = self.run_start(local=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.root / '.data/server.pid').read_text(), initial_pid)
        self.assertEqual(len((self.root / '.data/launches.jsonl').read_text().splitlines()), 1)

    def test_local_start_refuses_to_reuse_tunnel_mode_app(self):
        result = self.run_start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        initial_pid = (self.root / '.data/server.pid').read_text()
        result = self.run_start(local=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('still in tunnel mode', result.stderr)
        self.assertEqual((self.root / '.data/server.pid').read_text(), initial_pid)


class TunnelDiscoveryTest(unittest.TestCase):
    def test_only_https_tunnels_to_the_requested_loopback_port_are_selected(self):
        from unittest.mock import patch
        from tools import start_background as launcher
        cases = [
            ('http://192.168.1.2:3000', 'https://remote.ngrok-free.app', None),
            ('http://127.0.0.1:3001', 'https://other.ngrok-free.app', None),
            ('http://127.0.0.1:3000', 'http://insecure.ngrok-free.app', None),
            ('http://localhost:3000', 'https://right.ngrok-free.app', 'https://right.ngrok-free.app'),
        ]
        for address, public, expected in cases:
            with self.subTest(address=address, public=public), patch.object(launcher, 'request_json',
                return_value={'tunnels': [{'config': {'addr': address}, 'public_url': public}]}):
                self.assertEqual(launcher.tunnel_url(3000), expected)


if __name__ == '__main__':
    unittest.main()
