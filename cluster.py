"""Connect Devices control plane. Network discovery never grants trust."""
from copy import deepcopy
import json
from pathlib import Path
import secrets
import select
import socket
import socketserver
import statistics
import threading
import time

import connectnet

LLAMA_REVISION = '39febd2adb947b70da35e95f9351b3bf58ad170a'


class Backend:
    id = 'base'
    def describe(self): raise NotImplementedError


class ExoBackend(Backend):
    id = 'exo'
    def describe(self):
        return {'id': self.id, 'name': 'Exo', 'status': 'unsupported', 'reason': 'Current maintained platform is Apple Silicon. Windows is on the roadmap; no verified Android worker for this release.'}


class LlamaRPCBackend(Backend):
    id = 'llama-rpc'
    def describe(self):
        return {'id': self.id, 'name': 'llama.cpp RPC', 'status': 'experimental', 'reason': 'CPU RPC worker is a candidate for Termux. Needs matching builds and a real phone experiment. Discovery and pairing alone do not prove inference.', 'revision': LLAMA_REVISION}


def budget(physical, available, phone=False):
    if not isinstance(physical, (int, float)) or not isinstance(available, (int, float)):
        return None
    reserve = max(2 if phone else 4, physical * .2)
    return round(max(0, min(physical, available) - reserve), 2)


class Tunnel:
    """Loopback listener forwards only to the paired companion's fixed RPC route."""
    def __init__(self, peer, token):
        self.peer, self.token = peer, token
        self.sent = self.received = self.interruptions = self.connections = 0
        self.last_error = None
        self.streams = set()
        self.lock = threading.RLock()
        self.closed = threading.Event()
        tunnel = self
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                remote = None
                self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                with tunnel.lock:
                    tunnel.connections += 1
                    tunnel.streams.add(self.request)
                try:
                    remote = connectnet.tls_socket(tunnel.peer, 10)
                    remote.sendall((f'POST /rpc HTTP/1.1\r\nHost: companion\r\nAuthorization: Bearer {tunnel.token}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n').encode())
                    header = bytearray()
                    while not header.endswith(b'\r\n\r\n') and len(header) < 4096:
                        char = remote.recv(1)
                        if not char: raise OSError('Companion disconnected during tunnel setup.')
                        header.extend(char)
                    if not header.startswith(b'HTTP/1.0 200 ') and not header.startswith(b'HTTP/1.1 200 '):
                        raise OSError('Companion rejected the RPC tunnel.')
                    with tunnel.lock: tunnel.streams.add(remote)
                    def transferred(to_phone, count):
                        with tunnel.lock:
                            if to_phone: tunnel.sent += count
                            else: tunnel.received += count
                    def remote_eof():
                        with tunnel.lock: tunnel.interruptions += 1
                    connectnet.relay_streams(self.request, remote, tunnel.closed.is_set, transferred, remote_eof)
                except (OSError, ValueError) as exc:
                    with tunnel.lock:
                        tunnel.interruptions += 1
                        tunnel.last_error = f'{type(exc).__name__}: {exc}'
                finally:
                    with tunnel.lock:
                        tunnel.streams.discard(self.request)
                        if remote: tunnel.streams.discard(remote)
                    if remote: remote.close()
        class Server(socketserver.ThreadingTCPServer):
            daemon_threads = True
            allow_reuse_address = False
        self.server = Server(('127.0.0.1', 0), Handler)
        self.endpoint = f'127.0.0.1:{self.server.server_address[1]}'
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stats(self):
        with self.lock:
            return {'bytes_to_phone': self.sent, 'bytes_from_phone': self.received, 'interruptions': self.interruptions, 'connections': self.connections}

    def close(self):
        self.closed.set()
        with self.lock:
            for stream in list(self.streams):
                try: stream.shutdown(socket.SHUT_RDWR)
                except OSError: pass
        self.server.shutdown(); self.server.server_close()


class Manager:
    def __init__(self, data):
        self.data = Path(data)
        self.peers, self.credentials, self.tunnels, self.reports = {}, {}, {}, []
        self.lock = threading.RLock()
        self.scan_message = 'Open the companion on your phone, then scan nearby.'
        self.scanning = False

    def scan(self):
        with self.lock:
            if self.scanning: raise ValueError('A discovery scan is already running.')
            self.scanning = True
        try:
            offers = connectnet.discover()
            with self.lock:
                # Discovered offers expire; paired identities keep their pinned endpoint.
                self.peers = {k: p for k, p in self.peers.items() if k in self.credentials}
                for offer in offers:
                    if offer['id'] not in self.credentials: self.peers[offer['id']] = offer
                self.scan_message = f'{len(offers)} companion(s) found.' if offers else 'No companion found. Check that both devices share Wi-Fi, the companion is open, and the network allows nearby connections.'
        finally:
            with self.lock: self.scanning = False
        return self.snapshot({})

    def peer(self, identity):
        with self.lock:
            if identity not in self.peers: raise ValueError('Device no longer available. Scan nearby again.')
            return deepcopy(self.peers[identity])

    def pair(self, identity, code, fingerprint_confirmed):
        if fingerprint_confirmed is not True: raise ValueError('Compare the complete certificate fingerprint on your phone first.')
        peer = self.peer(identity)
        if identity in self.credentials: raise ValueError('Already paired or awaiting phone approval.')
        if time.time() - peer.get('discovered_at', 0) > 120: raise ValueError('Discovery expired. Scan again.')
        token = secrets.token_hex(32)
        result = connectnet.request(peer, '/pair', {'code': str(code), 'token': token, 'name': socket.gethostname()})
        if result.get('status') != 'pending': raise ValueError('Unexpected pairing response.')
        with self.lock:
            self.credentials[identity] = token
            self.peers[identity].update(status='pending', message='Approve the request in the phone companion.', pairing_started=time.time())
        return {'status': 'pending'}

    def refresh(self):
        with self.lock: identities = list(self.credentials)
        for identity in identities:
            peer = self.peer(identity)
            with self.lock: token = self.credentials.get(identity)
            if not token: continue
            try:
                state = connectnet.request(peer, '/pair/status', token=token)
                if state['status'] == 'expired':
                    self.disconnect(identity); continue
                if state['status'] == 'paired':
                    info = connectnet.request(peer, '/status', token=token)
                    with self.lock:
                        if self.credentials.get(identity) == token:
                            self.peers[identity].update(status='connected', hardware=info, last_seen=time.time(), message='Paired over encrypted Wi-Fi. Inference participation is not yet verified.')
            except (OSError, ValueError, KeyError) as exc:
                with self.lock:
                    if identity in self.peers: self.peers[identity].update(status='disconnected', message=str(exc))
        return {'status': 'refreshed'}

    def benchmark(self, identity):
        peer = self.peer(identity)
        if peer['status'] != 'connected': raise ValueError('Pair and connect the phone first.')
        with self.lock: token = self.credentials[identity]
        latencies = []
        for _ in range(5):
            start = time.perf_counter(); response = connectnet.request(peer, '/echo', {'echo': 'ping'}, token)
            if response.get('echo') != 'ping': raise ValueError('Connection integrity check failed.')
            latencies.append((time.perf_counter()-start)*1000)
        payload = secrets.token_hex(16384)  # 32 KiB each direction, never user data.
        start = time.perf_counter()
        response = connectnet.request(peer, '/echo', {'echo': payload}, token)
        duration = time.perf_counter()-start
        if response.get('echo') != payload: raise ValueError('Connection integrity check failed.')
        report = {'schema_version': '1.0', 'kind': 'connection', 'evidence': 'measured', 'device_id': identity, 'finished_at': time.time(), 'median_roundtrip_ms': round(statistics.median(latencies), 2), 'roundtrips_ms': latencies, 'payload_bytes_each_way': len(payload), 'payload_roundtrip_seconds': duration, 'roundtrip_payload_mib_s': len(payload)*2/1024**2/duration, 'protocol': 'Five separate pinned TLS HTTPS echo requests, then one 32 KiB echo. Includes TLS setup; not ICMP latency, sustained Wi-Fi capacity, or inference speed.'}
        folder = self.data/'connections'; folder.mkdir(parents=True, exist_ok=True)
        (folder/(str(time.time_ns())+'.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
        with self.lock:
            self.reports.append(report)
            self.peers[identity]['connection_benchmark'] = report
        return report

    def disconnect(self, identity):
        peer = self.peer(identity)
        with self.lock:
            token = self.credentials.pop(identity, None)
            tunnel = self.tunnels.pop(identity, None)
        if tunnel: tunnel.close()
        remote_revoked = False
        if token:
            try: connectnet.request(peer, '/revoke', token=token); remote_revoked = True
            except (OSError, ValueError): pass
        with self.lock:
            self.peers[identity].update(status='available', hardware=None, message='Disconnected and remote pairing revoked.' if remote_revoked else 'Local credentials removed. If the phone is offline, use revoke-all there or restart its companion.')
        return {'status': 'disconnected', 'remote_revoked': remote_revoked}

    def open_tunnel(self, identity):
        peer = self.peer(identity)
        if peer['status'] != 'connected' or time.time()-peer.get('last_seen', 0) > 15: raise ValueError('Refresh the paired phone before starting an experiment.')
        if peer['hardware']['runtime']['status'] != 'ready': raise ValueError('Phone RPC runtime is unavailable. Follow the companion setup.')
        if peer['hardware']['runtime'].get('build_record_revision') != LLAMA_REVISION:
            raise ValueError('Phone build revision is missing or different. Use the pinned Termux setup script before running inference.')
        with self.lock:
            if identity not in self.tunnels: self.tunnels[identity] = Tunnel(peer, self.credentials[identity])
            return self.tunnels[identity]

    def snapshot(self, hardware):
        with self.lock:
            devices = deepcopy(list(self.peers.values()))
            for peer in devices:
                if peer['status'] == 'connected' and time.time()-peer.get('last_seen', 0) > 15: peer['status'] = 'stale'
                if peer['id'] in self.tunnels: peer['traffic'] = self.tunnels[peer['id']].stats()
            connected = [p for p in devices if p['status'] == 'connected']
            physical = hardware.get('ram_gib')
            total = physical if isinstance(physical, (int, float)) else None
            for peer in connected:
                amount = peer.get('hardware', {}).get('physical_ram_gib')
                total = total + amount if total is not None and isinstance(amount, (int, float)) else None
            reports=[]
            for pattern in ('connections/*.json','*/distributed.json'):
                for path in sorted(self.data.glob(pattern),reverse=True)[:20]:
                    try: reports.append(json.loads(path.read_text(encoding='utf-8')))
                    except (OSError,ValueError): pass
            return {'devices': devices, 'scanning': self.scanning, 'message': self.scan_message, 'backends': [b.describe() for b in (ExoBackend(), LlamaRPCBackend())], 'summary': {'connected_workers': len(connected), 'total_reported_physical_gib': round(total, 2) if total is not None else None, 'local_model_budget_gib': budget(hardware.get('ram_gib'), hardware.get('available_gib')), 'actual_usable_cluster_capacity_gib': None, 'capacity_note': 'Physical memory is an inventory total, not pooled model memory. Usable cluster capacity needs a verified layer split, context/workspace reserve and runtime measurements. Virtual RAM is excluded.', 'inference_status': 'not_verified'}, 'reports': reports}

    def close(self):
        for identity in list(self.credentials): self.disconnect(identity)


from devices_manager import upgrade
Manager = upgrade(Manager)
