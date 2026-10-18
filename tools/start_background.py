"""Start ELYRA without a console window; authenticated ngrok is explicit opt-in."""
import argparse
import base64
import contextlib
import ctypes
import ipaddress
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


class StartupError(RuntimeError):
    pass


def windows_arguments(command):
    count = ctypes.c_int()
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(ctypes.c_wchar_p)
    result = parse(command, ctypes.byref(count))
    if not result:
        return []
    try:
        return [result[index] for index in range(count.value)]
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(ctypes.cast(result, ctypes.c_void_p))


def option(arguments, name):
    for index, value in enumerate(arguments):
        if value == name and index + 1 < len(arguments):
            return arguments[index + 1]
        if value.startswith(name + '='):
            return value.split('=', 1)[1]
    return None


def snapshot(port, api_port=4040):
    script = (
        "$ErrorActionPreference='Stop';"
        f"$ports=@({port},{api_port});"
        "$listeners=@(Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in $ports } | "
        "Select-Object LocalPort,OwningProcess);"
        "$processes=@(Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe' OR Name='ngrok.exe'\" | "
        "Select-Object ProcessId,Name,CommandLine);"
        "@{listeners=$listeners;processes=$processes}|ConvertTo-Json -Depth 4 -Compress"
    )
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script],
        capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise StartupError('Cannot inspect running processes/listeners. No services were changed.')
    return json.loads(result.stdout)


def owner(state, port):
    ids = {item['OwningProcess'] for item in state['listeners'] if item['LocalPort'] == port}
    if len(ids) > 1:
        raise StartupError(f'Port {port} has multiple listeners. Stop them before starting ELYRA.')
    if not ids:
        return None
    return next((item for item in state['processes'] if item['ProcessId'] in ids),
        {'ProcessId': next(iter(ids)), 'Name': 'other', 'CommandLine': ''})


def app_arguments(process, root):
    if process['Name'].lower() not in ('python.exe', 'pythonw.exe'):
        raise StartupError('The app port is occupied by another service. Choose --port or stop that service.')
    arguments = windows_arguments(process['CommandLine'])
    expected = os.path.normcase(str((root / 'app.py').resolve()))
    if not any(value == 'app.py' or os.path.normcase(str(Path(value).resolve())) == expected for value in arguments[1:]):
        raise StartupError('The app port belongs to another Python program. It was left running.')
    return arguments


def find_ngrok():
    executable = shutil.which('ngrok')
    if executable:
        return executable
    local = Path(os.environ.get('LOCALAPPDATA', ''))
    candidates = [local / 'Microsoft/WinGet/Links/ngrok.exe']
    candidates.extend((local / 'Microsoft/WinGet/Packages').glob('Ngrok.Ngrok_*/ngrok.exe'))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise StartupError('ngrok was not found. Install it, then open a new terminal and try again.')


def request_json(url, headers=None):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(urllib.request.Request(url, headers=headers or {}), timeout=1) as response:
        return json.load(response)


def tunnel_url(port, api_port=4040):
    data = request_json(f'http://127.0.0.1:{api_port}/api/tunnels')
    for tunnel in data.get('tunnels', []):
        address = str(tunnel.get('config', {}).get('addr', ''))
        if address == str(port):
            address = 'http://127.0.0.1:' + address
        elif '://' not in address:
            address = 'http://' + address
        target = urllib.parse.urlsplit(address)
        public = urllib.parse.urlsplit(tunnel.get('public_url', ''))
        if target.hostname in ('127.0.0.1', 'localhost', '::1') and target.port == port and public.scheme == 'https' and public.hostname and public.netloc == public.hostname and public.path in ('', '/'):
            return 'https://' + public.hostname
    return None


def credentials(path):
    if path.exists():
        data = json.loads(path.read_text(encoding='utf-8'))
    else:
        data = {'username': 'elyra', 'password': secrets.token_urlsafe(24)}
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also protects an existing configuration from a race.
        with path.open('x', encoding='utf-8') as stream:
            json.dump(data, stream)
    # Share the server's validation without creating a Store or reading any keys.
    import re
    username, password = data.get('username'), data.get('password')
    if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', username) or not isinstance(password, str) or not 16 <= len(password) <= 128 or not password.isascii() or any(ord(c) < 33 for c in password):
        raise StartupError('Invalid tunnel credentials. Check the private credentials JSON file.')
    return data


def launch(command, root, prefix):
    data = root / '.data'
    with (data / (prefix + '.stdout.log')).open('ab') as stdout, (data / (prefix + '.stderr.log')).open('ab') as stderr:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        return subprocess.Popen(command, cwd=root, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
            creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=startup)


def wait_for(check, process, label, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise StartupError(f'{label} exited during startup. Check .data startup logs.')
        try:
            result = check()
            if result:
                return result
        except (OSError, ValueError):
            pass
        time.sleep(.2)
    raise StartupError(f'{label} did not become ready. Check .data startup logs.')


@contextlib.contextmanager
def startup_lock(data):
    import msvcrt
    with (data / 'startup.lock').open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        try:
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise StartupError('Another ELYRA startup is in progress. Please wait.') from None
        try:
            yield
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def start(root, port=3000, lan=None, credentials_path=None, api_port=4040):
    root = Path(root).resolve()
    data = root / '.data'
    data.mkdir(exist_ok=True)
    credentials_path = Path(credentials_path or data / 'ngrok-access.json')
    if not credentials_path.is_absolute():
        credentials_path = root / credentials_path
    credentials_path = credentials_path.resolve()
    owned = []
    with startup_lock(data):
        try:
            state = snapshot(port, api_port)
            app = owner(state, port)
            arguments = app_arguments(app, root) if app else None
            if arguments and (not option(arguments, '--tunnel-origin') or not option(arguments, '--tunnel-credentials') or '--tunnel-no-auth' in arguments):
                raise StartupError(f'ELYRA is already running with different options. Run stop.bat {port} before starting both services.')
            if arguments and lan and option(arguments, '--lan') != lan:
                raise StartupError(f'ELYRA uses a different LAN option. Run stop.bat {port} first.')
            login = credentials(credentials_path)
            agent = owner(state, api_port)
            new_agent = None
            if agent:
                agent_arguments = windows_arguments(agent['CommandLine'])
                if agent['Name'].lower() != 'ngrok.exe' or '--inspect=false' not in agent_arguments:
                    raise StartupError(f'Port {api_port} is occupied by another service or an ngrok agent with inspection enabled. It was left running.')
                url = tunnel_url(port, api_port)
                if not url:
                    raise StartupError('The existing ngrok agent forwards another port. It was left running.')
            else:
                command = [find_ngrok(), 'http', f'http://127.0.0.1:{port}', '--inspect=false',
                    '--log', str(data / 'ngrok.log'), '--log-format', 'json']
                new_agent = launch(command, root, 'ngrok-start')
                owned.append(new_agent)
                url = wait_for(lambda: tunnel_url(port, api_port), new_agent, 'ngrok')
                agent = owner(snapshot(port, api_port), api_port)
                if not agent or agent['ProcessId'] != new_agent.pid:
                    raise StartupError('The ngrok API port belongs to another process. Newly started ngrok was stopped.')
            if arguments and option(arguments, '--tunnel-origin') != url:
                raise StartupError(f'The running app uses an older tunnel URL. Run stop.bat {port} and start again.')
            new_app = None
            if not app:
                command = [sys.executable, '-u', str(root / 'app.py'), '--port', str(port),
                    '--tunnel-origin', url, '--tunnel-credentials', str(credentials_path)]
                if lan:
                    command.extend(['--lan', lan])
                new_app = launch(command, root, 'server')
                owned.append(new_app)
                app = {'ProcessId': new_app.pid}
            auth = 'Basic ' + base64.b64encode((login['username'] + ':' + login['password']).encode('ascii')).decode('ascii')
            headers = {'Host': urllib.parse.urlsplit(url).netloc, 'Authorization': auth}

            def healthy():
                health = request_json(f'http://127.0.0.1:{port}/api/health', headers)
                return health.get('ok') is True and health.get('app') == 'ELYRA'

            wait_for(healthy, new_app, 'ELYRA')
            # Confirm authentication is enforced before reporting a public URL.
            try:
                request_json(f'http://127.0.0.1:{port}/api/health', {'Host': headers['Host']})
            except urllib.error.HTTPError as error:
                status = error.code
                error.close()
                if status != 401:
                    raise StartupError('Tunnel authentication could not be verified.') from None
            else:
                raise StartupError('Tunnel authentication is not enabled.')
            (data / 'server.pid').write_text(str(app['ProcessId']), encoding='ascii')
            (data / 'ngrok.pid').write_text(str(agent['ProcessId']), encoding='ascii')
            (data / 'ngrok-url.txt').write_text(url + '\n', encoding='utf-8')
            login['url'] = url
            credentials_path.write_text(json.dumps(login), encoding='utf-8')
            (data / 'start-info.txt').write_text(
                f'ELYRA: http://localhost:{port}\nPublic URL: {url}\nLogin file: {credentials_path}\nStop: stop.bat {port}\n', encoding='utf-8')
            return url
        except BaseException:
            # Stop only processes created by this invocation; never existing services.
            for process in owned:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            raise


def start_local(root, port=3000, lan=None):
    root = Path(root).resolve()
    data = root / '.data'
    data.mkdir(exist_ok=True)
    with startup_lock(data):
        app = owner(snapshot(port), port)
        arguments = app_arguments(app, root) if app else None
        if arguments and (option(arguments, '--tunnel-origin') or option(arguments, '--tunnel-credentials')):
            raise StartupError(f'ELYRA is still in tunnel mode. Run stop.bat {port} before starting locally.')
        if arguments and lan and option(arguments, '--lan') != lan:
            raise StartupError(f'ELYRA uses a different LAN option. Run stop.bat {port} first.')
        process = None
        try:
            if not app:
                command = [sys.executable, '-u', str(root / 'app.py'), '--port', str(port)]
                if lan:
                    command.extend(['--lan', lan])
                process = launch(command, root, 'server')
                app = {'ProcessId': process.pid}

            def healthy():
                health = request_json(f'http://127.0.0.1:{port}/api/health')
                return health.get('ok') is True and health.get('app') == 'ELYRA'

            wait_for(healthy, process, 'ELYRA')
            current = owner(snapshot(port), port)
            if not current or current['ProcessId'] != app['ProcessId']:
                raise StartupError('The app port belongs to a different process.')
            (data / 'server.pid').write_text(str(app['ProcessId']), encoding='ascii')
            (data / 'start-info.txt').write_text(
                f'ELYRA: http://localhost:{port}\nMode: local (ngrok disabled)\nStop: stop.bat {port}\n', encoding='utf-8')
            (data / 'ngrok-url.txt').unlink(missing_ok=True)
            return f'http://localhost:{port}'
        except BaseException:
            if process is not None and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            raise


def main():
    parser = argparse.ArgumentParser(description='Start ELYRA in the background (Windows); local-only by default.')
    parser.add_argument('--port', type=int, default=3000)
    parser.add_argument('--lan', help='Optional private IPv4 address of this computer')
    parser.add_argument('--ngrok', action='store_true', help='Explicitly enable an authenticated public tunnel')
    parser.add_argument('--tunnel-credentials', type=Path, help='Private login JSON; defaults to .data/ngrok-access.json')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or (args.ngrok and args.port == 4040):
        parser.error('Use a port from 1 to 65535 (4040 is reserved when using --ngrok)')
    if args.tunnel_credentials and not args.ngrok:
        parser.error('--tunnel-credentials requires explicit --ngrok')
    if args.lan:
        try:
            address = ipaddress.IPv4Address(args.lan)
        except ValueError:
            parser.error('--lan must be a private IPv4 address')
        if not any(address in ipaddress.ip_network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
            parser.error('--lan must be a private IPv4 address')
    if os.name != 'nt':
        parser.error('This background launcher requires Windows')
    try:
        url = start(ROOT, args.port, args.lan, args.tunnel_credentials) if args.ngrok else start_local(ROOT, args.port, args.lan)
    except (StartupError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'Startup failed: {error}', file=sys.stderr)
        return 1
    services = 'ELYRA and ngrok' if args.ngrok else 'ELYRA (local, ngrok disabled)'
    print(f'{services} running in the background.\n{url}\nDetails: .data/start-info.txt\nStop: stop.bat {args.port}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
