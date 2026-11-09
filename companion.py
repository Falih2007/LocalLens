"""Termux prototype: explicit approval, pinned TLS, fixed loopback RPC relay.

All credentials are session-only. No shell/command/download API is exposed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import select
import socket
import ssl
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from connectnet import DISCOVERY_PORT, PROTOCOL, MAX_MESSAGE, lan_address


def memory_info(text=None):
    text = Path('/proc/meminfo').read_text() if text is None else text
    entries = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in text.splitlines() if ':' in line}
    return {'physical_ram_gib': entries.get('MemTotal', 0) / 1024**3, 'available_gib': entries.get('MemAvailable', 0) / 1024**3, 'swap_gib': entries.get('SwapTotal', 0) / 1024**3, 'memory_note': 'MemTotal is OS-reported physical RAM; SwapTotal/virtual expansion is excluded from physical capacity.'}


def process_memory(pid):
    try:
        entries = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
        return {'rss_bytes': int(entries['VmRSS'].split()[0]) * 1024, 'peak_rss_bytes': int(entries['VmHWM'].split()[0]) * 1024}
    except (OSError, KeyError, ValueError):
        return {'rss_bytes': None, 'peak_rss_bytes': None}


class Companion:
    def __init__(self, name, rpc=None, rpc_port=None, log=None):
        self.name, self.rpc, self.rpc_port, self.log = name, rpc, rpc_port, log
        self.code = secrets.token_hex(5).upper()
        self.pending, self.trusted, self.streams, self.failures = {}, {}, {}, {}
        self.lock = threading.RLock()
        self.started = time.time()
        self.binary_sha256 = None
        self.build_record_revision = None
        self.log_offset = 0
        self.log_tail = b''
        self.graph_events = 0

    def approve(self, request_id):
        with self.lock:
            p = self.pending.pop(request_id, None)
            if not p or time.time() - p['created'] > 120:
                raise ValueError('Pairing request expired or not found.')
            self.trusted[p['token']] = p['name']

    def revoke(self, token):
        with self.lock:
            self.trusted.pop(token, None)
            self.pending = {k: v for k, v in self.pending.items() if v['token'] != token}
            for stream in list(self.streams.get(token, set())):
                try: stream.shutdown(socket.SHUT_RDWR)
                except OSError: pass

    def status(self):
        try: memory = memory_info()
        except (OSError, ValueError): memory = {'physical_ram_gib': None, 'available_gib': None, 'swap_gib': None}
        android = bool(os.environ.get('ANDROID_ROOT'))
        def prop(key):
            try: return subprocess.check_output(['getprop', key], text=True, timeout=2).strip()
            except (OSError, subprocess.SubprocessError): return ''
        cpu = prop('ro.soc.model') if android else platform.processor()
        if not cpu:
            try: cpu = next((x.split(':', 1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith(('Hardware', 'model name'))), platform.machine())
            except OSError: cpu = platform.machine()
        ready = self.rpc is not None and self.rpc.poll() is None
        graph_calls = None
        if self.log and self.log.is_file():
            # Incremental bounded reads avoid repeatedly loading a large debug log on a phone.
            with self.lock:
                if self.log.stat().st_size < self.log_offset:
                    self.log_offset = 0; self.log_tail = b''; self.graph_events = 0
                with self.log.open('rb') as stream:
                    stream.seek(self.log_offset); chunk = stream.read(1024**2)
                self.log_offset += len(chunk)
                content = self.log_tail + chunk
                self.graph_events += content.count(b'GRAPH_COMPUTE') if chunk else 0
                self.log_tail = content[-12:]
                graph_calls = self.graph_events
        return {'name': self.name, 'device_type': 'phone' if android else 'computer', 'os': 'Android ' + prop('ro.build.version.release') if android else platform.system(), 'cpu': cpu, 'gpu': 'Not probed', 'npu': 'Not probed', **memory, 'runtime': {'backend': 'llama.cpp RPC', 'status': 'ready' if ready else 'unavailable', 'build_revision': None, 'build_record_revision': self.build_record_revision, 'expected_revision': '39febd2adb947b70da35e95f9351b3bf58ad170a', 'binary_sha256': self.binary_sha256, 'revision_note': 'Installed revision is not inferred. Verify build provenance using the setup record.', 'supported_models': 'GGUF architectures supported by the installed llama.cpp build; not model-by-model verified'}, 'worker_memory': process_memory(self.rpc.pid) if ready else None, 'rpc_graph_events': graph_calls, 'inference_participation': 'unverified', 'uptime_seconds': round(time.time() - self.started)}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def reply(self, status, value):
        content = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        state = self.server.companion
        try:
            lan_address(self.client_address[0], self.server.test_loopback)
            self.connection.settimeout(10)
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= MAX_MESSAGE: raise ValueError('Request too large.')
            body = json.loads(self.rfile.read(size) or b'{}')
            if not isinstance(body, dict): raise ValueError('Expected an object.')
            token = self.headers.get('Authorization', '').removeprefix('Bearer ')
            if self.path == '/pair':
                with state.lock:
                    host = self.client_address[0]
                    attempts = [t for t in state.failures.get(host, []) if time.time() - t < 60]
                    if len(attempts) >= 5: raise ValueError('Too many pairing attempts. Wait one minute.')
                    attempts.append(time.time()); state.failures[host] = attempts
                    if not secrets.compare_digest(str(body.get('code', '')), state.code): raise ValueError('Incorrect phone pairing code.')
                    candidate = body.get('token', '')
                    if not isinstance(candidate, str) or len(candidate) != 64 or any(c not in '0123456789abcdef' for c in candidate): raise ValueError('Invalid credential.')
                    state.pending = {k: v for k, v in state.pending.items() if time.time()-v['created'] < 120}
                    if len(state.pending) >= 8: raise ValueError('Too many pending requests.')
                    request_id = secrets.token_hex(4)
                    name = str(body.get('name', 'Desktop'))[:60]
                    state.pending[request_id] = {'token': candidate, 'name': name, 'created': time.time()}
                print(f'Pairing request from {name!r} at {host}. Type: approve {request_id}', flush=True)
                self.reply(200, {'status': 'pending', 'request_id': request_id}); return
            if self.path == '/pair/status':
                with state.lock:
                    pending = any(p['token'] == token and time.time() - p['created'] < 120 for p in state.pending.values())
                    status = 'paired' if token in state.trusted else 'pending' if pending else 'expired'
                self.reply(200, {'status': status}); return
            with state.lock:
                if token not in state.trusted: self.reply(403, {'error': 'Phone approval required.'}); return
            if self.path == '/status': self.reply(200, state.status())
            elif self.path == '/echo': self.reply(200, {'echo': body.get('echo', ''), 'received_at': time.time()})
            elif self.path == '/revoke': state.revoke(token); self.reply(200, {'status': 'revoked'})
            elif self.path == '/rpc': self.relay(token)
            else: self.reply(404, {'error': 'Operation not supported.'})
        except (ValueError, KeyError, TypeError, OSError) as exc:
            try: self.reply(400, {'error': str(exc)})
            except OSError: pass  # A revoked stream may already be closed.

    def relay(self, token):
        state = self.server.companion
        if state.rpc is None or state.rpc.poll() is not None:
            self.reply(409, {'error': 'RPC runtime not running on phone.'}); return
        # Fixed local port; callers cannot choose arbitrary destinations.
        with socket.create_connection(('127.0.0.1', state.rpc_port), timeout=5) as worker:
            with state.lock:
                if token not in state.trusted: raise ValueError('Pairing revoked.')
                state.streams.setdefault(token, set()).add(self.connection)
            self.send_response(200); self.send_header('Connection', 'close'); self.end_headers()
            self.wfile.flush()
            self.connection.settimeout(30); worker.settimeout(30)
            try:
                while True:
                    with state.lock:
                        if token not in state.trusted: return
                    ready, _, _ = select.select([self.connection, worker], [], [], 1)
                    if self.connection.pending() and self.connection not in ready: ready.append(self.connection)
                    for source in ready:
                        data = source.recv(65536)
                        if not data: return
                        (worker if source is self.connection else self.connection).sendall(data)
            except OSError:
                return  # Expected when a pairing is revoked or the engine disconnects.
            finally:
                with state.lock: state.streams.get(token, set()).discard(self.connection)


def discovery_loop(server, stop):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('', DISCOVERY_PORT)); sock.settimeout(.5)
        while not stop.is_set():
            try:
                data, addr = sock.recvfrom(1024)
                lan_address(addr[0]); query = json.loads(data)
                if not isinstance(query, dict): continue
                nonce = query.get('nonce')
                if query.get('protocol') != PROTOCOL or not isinstance(nonce, str) or len(nonce) != 32: continue
                sock.sendto(json.dumps({'protocol': PROTOCOL, 'nonce': nonce, 'name': server.companion.name, 'port': server.server_port, 'fingerprint': server.fingerprint}).encode(), addr)
            except socket.timeout: pass
            except (ValueError, OSError): continue


def make_server(host, port, cert, key, state, test_loopback=False):
    lan_address(host, test_loopback)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert, key)
    class Server(ThreadingHTTPServer):
        def get_request(self):
            raw, address = super().get_request()
            raw.settimeout(5)
            try: return context.wrap_socket(raw, server_side=True), address
            except Exception: raw.close(); raise
    server = Server((host, port), Handler)
    server.daemon_threads = True
    server.companion, server.test_loopback = state, test_loopback
    server.fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(Path(cert).read_text())).hexdigest()
    return server


def main():
    parser = argparse.ArgumentParser(description='LocalLens Termux companion. Private Wi-Fi only.')
    parser.add_argument('--name', default='Android companion')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int, default=45460)
    parser.add_argument('--state', type=Path, default=Path.home()/'.locallens-companion')
    args = parser.parse_args()
    folder = args.state.expanduser().resolve(); folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    cert, key = folder/'certificate.pem', folder/'key.pem'
    if not cert.exists() or not key.exists():
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-sha256', '-nodes', '-keyout', str(key), '-out', str(cert), '-days', '365', '-subj', '/CN=LocalLens companion'], check=True, capture_output=True)
        key.chmod(0o600)
    host = args.host
    if not host:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 9)); host = sock.getsockname()[0]
    lan_address(host)
    state = Companion(args.name)
    server = make_server(host, args.port, cert, key, state)
    stop = threading.Event()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=discovery_loop, args=(server, stop), daemon=True).start()
    mdns = None
    try:
        from mdns_discovery import advertise
        mdns = advertise(host, server.server_port, server.fingerprint, state.name)
    except (ImportError, OSError) as exc:
        print(f'mDNS unavailable ({exc}); legacy LAN scan remains available.', flush=True)
    print(f'LocalLens companion on private Wi-Fi.\nCertificate SHA-256: {server.fingerprint}\nPairing code: {state.code}\nCompare the fingerprint on the desktop before entering this code.\nApprove only your own laptop. Commands: approve REQUEST_ID, revoke-all, quit', flush=True)
    try:
        while True:
            command = input('companion> ').strip().split()
            if not command: continue
            if command[0] == 'quit': break
            if command[0] == 'approve' and len(command) == 2:
                try: state.approve(command[1]); print('Paired for this session.')
                except ValueError as exc: print(exc)
            elif command[0] == 'revoke-all':
                for token in list(state.trusted): state.revoke(token)
                state.pending.clear(); print('All pairings revoked.')
    except (KeyboardInterrupt, EOFError): pass
    finally:
        stop.set()
        if mdns:
            mdns[0].unregister_service(mdns[1]); mdns[0].close()
        for token in list(state.trusted): state.revoke(token)
        server.shutdown(); server.server_close()


if __name__ == '__main__': main()
