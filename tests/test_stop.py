"""Windows stop launcher tests using isolated listeners and a fake ngrok process."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
CSC = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


@unittest.skipUnless(os.name == 'nt' and CSC.is_file(), 'Windows PowerShell/.NET compiler required')
class StopLauncherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='elyra stop build ')
        source = Path(cls.build.name) / 'fake.cs'
        source.write_text('class Program { static void Main(string[] args) { System.Threading.Thread.Sleep(120000); } }')
        cls.fake_ngrok = Path(cls.build.name) / 'ngrok.exe'
        subprocess.run([str(CSC), '/nologo', '/target:exe', '/out:' + str(cls.fake_ngrok), str(source)],
            check=True, capture_output=True, text=True, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='elyra stop fixture ')
        self.root = Path(self.temp.name)
        (self.root / '.data').mkdir()
        for name in ('stop.bat', 'stop.ps1'):
            shutil.copy2(ROOT / name, self.root / name)
        self.processes = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        self.temp.cleanup()

    def port(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def listener(self, name, port):
        script = self.root / name
        script.write_text('import socket,sys,time\ns=socket.socket()\ns.bind(("127.0.0.1",int(sys.argv[1])))\ns.listen(5)\ntime.sleep(120)\n')
        process = subprocess.Popen([sys.executable, str(script), str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        self.processes.append(process)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.assertIsNone(process.poll(), 'Fixture listener exited')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2):
                    return process
            except OSError:
                time.sleep(.05)
        self.fail('Fixture did not listen')

    def tunnel(self, target):
        # This executable sleeps; it never contacts ngrok or opens a real tunnel.
        process = subprocess.Popen([str(self.fake_ngrok), 'http', target, '--inspect=false'],
            creationflags=subprocess.CREATE_NO_WINDOW)
        self.processes.append(process)
        return process

    def pid_file(self, name, process):
        path = self.root / '.data' / name
        path.write_text(str(process.pid))
        return path

    def stop(self, port):
        return subprocess.run(['cmd.exe', '/d', '/c', str(self.root / 'stop.bat'), str(port)],
            cwd=self.root, input='\n', capture_output=True, text=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW)

    def test_stops_app_and_matching_tunnel_and_cleans_only_matching_pid_files(self):
        port = self.port()
        app = self.listener('app.py', port)
        ngrok = self.tunnel(f'http://127.0.0.1:{port}')
        other_port = self.tunnel(str(port + 1 if port < 65535 else port - 1))
        remote = self.tunnel(f'http://192.168.1.2:{port}')
        server_pid = self.pid_file('server.pid', app)
        ngrok_pid = self.pid_file('ngrok.pid', ngrok)
        result = self.stop(port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        app.wait(timeout=5)
        ngrok.wait(timeout=5)
        self.assertIsNone(other_port.poll())
        self.assertIsNone(remote.poll())
        self.assertFalse(server_pid.exists())
        self.assertFalse(ngrok_pid.exists())

    def test_stops_tunnel_when_app_is_absent_even_without_ngrok_pid_file(self):
        port = self.port()
        ngrok = self.tunnel(str(port))
        unrelated = self.listener('unrelated.py', self.port())
        stale_server_pid = self.pid_file('server.pid', unrelated)
        result = self.stop(port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        ngrok.wait(timeout=5)
        self.assertIsNone(unrelated.poll())
        self.assertTrue(stale_server_pid.exists())
        self.assertIn('ELYRA is not running', result.stdout)

    def test_leaves_foreign_listener_and_stale_ngrok_pid_untouched(self):
        port = self.port()
        foreign = self.listener('myapp.py', port)
        ngrok = self.tunnel(str(port + 1 if port < 65535 else port - 1))
        stale_pid = self.pid_file('ngrok.pid', ngrok)
        result = self.stop(port)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIsNone(foreign.poll())
        self.assertIsNone(ngrok.poll())
        self.assertTrue(stale_pid.exists())

    def test_invalid_port_exits_without_stopping_processes(self):
        ngrok = self.tunnel('39999')
        result = self.stop(0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(ngrok.poll())


if __name__ == '__main__':
    unittest.main()
