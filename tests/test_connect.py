"""Real TLS/loopback transport tests. Echo fixtures are NOT inference benchmarks."""
import hashlib
import json
from pathlib import Path
import secrets
import shutil
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cluster
import companion
import connectnet
import distributed
import app


class ConnectPolicyTests(unittest.TestCase):
    def test_discovery_routes_use_each_adapters_actual_subnet(self):
        from types import SimpleNamespace
        entries = [{'IPAddress':'172.20.10.7','PrefixLength':28}, {'IPAddress':'192.168.56.1','PrefixLength':24}, {'IPAddress':'8.8.8.8','PrefixLength':24}]
        with patch.object(connectnet.subprocess, 'run', return_value=SimpleNamespace(stdout=json.dumps(entries))):
            routes = connectnet.discovery_routes()
        self.assertIn(('172.20.10.7','172.20.10.15'),routes)
        self.assertIn(('192.168.56.1','192.168.56.255'),routes)
        self.assertFalse(any(source=='8.8.8.8' for source, _ in routes))

    def test_public_addresses_and_hostnames_rejected(self):
        for host in ('8.8.8.8', 'example.com', '127.0.0.1', '0.0.0.0', '169.254.1.1', '::1'):
            with self.assertRaises(ValueError): connectnet.lan_address(host)
        self.assertEqual(connectnet.lan_address('192.168.1.20'), '192.168.1.20')

    def test_swap_is_not_physical_memory(self):
        m = companion.memory_info('MemTotal: 8388608 kB\nMemAvailable: 4194304 kB\nSwapTotal: 8388608 kB\n')
        self.assertEqual(m['physical_ram_gib'], 8)
        self.assertEqual(m['swap_gib'], 8)
        self.assertEqual(m['available_gib'], 4)

    def test_inventory_is_not_pooled_capacity_or_verified_compute(self):
        with tempfile.TemporaryDirectory() as d:
            m = cluster.Manager(d)
            m.peers['fixture'] = {'id': 'fixture', 'status': 'connected', 'last_seen': time.time(), 'hardware': {'physical_ram_gib': 8, 'available_gib': 4, 'swap_gib': 8}}
            s = m.snapshot({'ram_gib': 32, 'available_gib': 20})
            self.assertEqual(s['summary']['total_reported_physical_gib'], 40)
            self.assertIsNone(s['summary']['actual_usable_cluster_capacity_gib'])
            self.assertEqual(s['summary']['inference_status'], 'not_verified')
            m.peers['fixture']['last_seen'] -= 20
            self.assertEqual(m.snapshot({'ram_gib': 32})['summary']['connected_workers'], 0)

    def test_pairing_needs_fingerprint_comparison_and_fresh_offer(self):
        with tempfile.TemporaryDirectory() as d:
            m = cluster.Manager(d)
            m.peers['a'] = {'id': 'a', 'discovered_at': 0}
            with self.assertRaisesRegex(ValueError, 'fingerprint'): m.pair('a', 'code', False)
            with self.assertRaisesRegex(ValueError, 'expired'): m.pair('a', 'code', True)

    def test_discovery_does_not_grant_trust_and_no_devices_are_seeded(self):
        with tempfile.TemporaryDirectory() as d, patch.object(connectnet, 'discover', return_value=[]):
            m = cluster.Manager(d); m.scan()
            self.assertEqual(m.snapshot({})['devices'], [])
            self.assertEqual(m.credentials, {})

    def test_remote_activity_alone_does_not_prove_model_parallelism(self):
        result = distributed.participation('offloaded 28/28 layers', {'rpc_graph_events': 0}, {'rpc_graph_events': 50}, {'bytes_to_phone': 100, 'bytes_from_phone': 100})
        self.assertEqual(result['status'], 'not_verified')
        self.assertFalse(result['partial_layer_offload'])
        result = distributed.participation('CPU model buffer size = 250 MiB\noffloaded 8/28 layers', {'rpc_graph_events': 10}, {'rpc_graph_events': 30}, {'bytes_to_phone': 100, 'bytes_from_phone': 100})
        self.assertEqual(result['status'], 'evidence_collected_review_required')

    def test_desktop_routes_require_local_auth_and_companion_download_has_no_secrets(self):
        import urllib.request, urllib.error, zipfile, io
        with tempfile.TemporaryDirectory() as d, patch.object(app, 'CLUSTER', cluster.Manager(d)), patch.object(app, 'HARDWARE', {'ram_gib':32,'available_gib':20}, create=True):
            server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                for route in ('state','guide','companion'):
                    with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(base+'/api/connect/'+route)
                    self.assertEqual(e.exception.code,403)
                headers = {'X-LocalLens-Token': app.TOKEN}
                with urllib.request.urlopen(urllib.request.Request(base+'/api/connect/state', headers=headers)) as r:
                    self.assertEqual(json.load(r)['devices'],[])
                with urllib.request.urlopen(urllib.request.Request(base+'/api/connect/companion', headers=headers)) as r:
                    with zipfile.ZipFile(io.BytesIO(r.read())) as archive:
                        self.assertEqual(set(archive.namelist()), {'companion.py','connectnet.py','CONNECT-DEVICES.md'})
                request = urllib.request.Request(base+'/api/connect/experiment', data=b'{}', headers=headers)
                with self.assertRaises(urllib.error.HTTPError) as e:
                    urllib.request.urlopen(request)
                self.assertEqual(e.exception.code, 403)
                self.assertIn('Phone compute is unavailable', json.load(e.exception)['error'])
                with patch.object(connectnet,'discover',return_value=[]):
                    request=urllib.request.Request(base+'/api/connect/scan',data=b'{}',headers={**headers,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request) as r:self.assertEqual(json.load(r)['devices'],[])
            finally: server.shutdown();server.server_close()


class CompanionTLSTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        openssl = shutil.which('openssl')
        if not openssl:
            candidate = Path('C:/Program Files/Git/usr/bin/openssl.exe')
            if candidate.is_file(): openssl = str(candidate)
        if not openssl: raise unittest.SkipTest('OpenSSL required for real TLS test certificates.')
        cls.temp = tempfile.TemporaryDirectory()
        folder = Path(cls.temp.name)
        cls.cert, cls.key = folder/'cert.pem', folder/'key.pem'
        subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(cls.key), '-out', str(cls.cert), '-days', '1', '-subj', '/CN=LocalLens test fixture'], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self):
        self.state = companion.Companion('TLS test fixture')
        self.server = companion.make_server('127.0.0.1', 0, self.cert, self.key, self.state, test_loopback=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.peer = {'id': self.server.fingerprint, 'fingerprint': self.server.fingerprint, 'host': '127.0.0.1', 'port': self.server.server_port, '_test_loopback': True, 'name': 'TLS test fixture', 'discovered_at': time.time(), 'status': 'available'}

    def tearDown(self):
        for token in list(self.state.trusted): self.state.revoke(token)
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def pair(self):
        token = secrets.token_hex(32)
        response = connectnet.request(self.peer, '/pair', {'code': self.state.code, 'token': token, 'name': 'Test laptop'})
        self.assertEqual(response['status'], 'pending')
        self.assertNotIn(token, json.dumps(response))
        with self.assertRaisesRegex(ValueError, 'approval'): connectnet.request(self.peer, '/status', token=token)
        self.state.approve(response['request_id'])
        self.assertEqual(connectnet.request(self.peer, '/pair/status', token=token)['status'], 'paired')
        return token

    def test_pinned_tls_requires_phone_approval_and_revocation(self):
        with self.assertRaisesRegex(ValueError, 'certificate changed'):
            connectnet.request({**self.peer, 'fingerprint': '0'*64}, '/pair/status')
        token = self.pair()
        self.assertEqual(connectnet.request(self.peer, '/echo', {'echo': 'integrity'}, token)['echo'], 'integrity')
        connectnet.request(self.peer, '/revoke', token=token)
        with self.assertRaisesRegex(ValueError, 'approval'): connectnet.request(self.peer, '/echo', token=token)

    def test_wrong_code_rate_limit_and_expiry(self):
        for _ in range(5):
            with self.assertRaisesRegex(ValueError, 'Incorrect'): connectnet.request(self.peer, '/pair', {'code': 'WRONG'})
        with self.assertRaisesRegex(ValueError, 'Too many'): connectnet.request(self.peer, '/pair', {'code': self.state.code})
        self.state.pending['old'] = {'created': time.time()-121, 'token': 'old', 'name': 'old'}
        with self.assertRaisesRegex(ValueError, 'expired'): self.state.approve('old')

    def test_fixed_destination_encrypted_tunnel_and_remote_revoke(self):
        # This byte echo fixture only verifies transport; it never returns inference timings.
        class Echo(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    while True:
                        raw = self.request.recv(65536)
                        if not raw: return
                        self.request.sendall(raw)
                except OSError: pass  # Revocation deliberately closes the fixture stream.
        class Server(socketserver.ThreadingTCPServer): daemon_threads = True
        echo = Server(('127.0.0.1', 0), Echo)
        threading.Thread(target=echo.serve_forever, daemon=True).start()
        class RunningFixture:
            pid = 0
            def poll(self): return None
        self.state.rpc = RunningFixture(); self.state.rpc_port = echo.server_address[1]
        token = self.pair(); tunnel = cluster.Tunnel(self.peer, token)
        try:
            host, port = tunnel.endpoint.split(':')
            with socket.create_connection((host, int(port)), timeout=5) as sock:
                # Exercise simultaneous large upload/download without either side
                # filling its send window while the receiver waits for upload to end.
                payload = secrets.token_bytes(8*1024**2)
                sender = threading.Thread(target=sock.sendall, args=(payload,))
                sender.start(); received = bytearray()
                while len(received) < len(payload): received.extend(sock.recv(65536))
                sender.join(timeout=10)
                self.assertFalse(sender.is_alive())
                self.assertEqual(bytes(received), payload)
                self.state.revoke(token)
                self.assertEqual(sock.recv(1), b'')
            stats = tunnel.stats()
            self.assertEqual(stats['bytes_to_phone'], len(payload)); self.assertEqual(stats['bytes_from_phone'], len(payload))
        finally:
            tunnel.close(); echo.shutdown(); echo.server_close()

    def test_manager_measures_echo_and_preserves_report_without_token(self):
        with tempfile.TemporaryDirectory() as d:
            m = cluster.Manager(d); m.peers[self.peer['id']] = self.peer
            m.pair(self.peer['id'], self.state.code, True)
            self.state.approve(next(iter(self.state.pending)))
            m.refresh()
            result = m.benchmark(self.peer['id'])
            self.assertGreater(result['median_roundtrip_ms'], 0)
            self.assertEqual(result['payload_bytes_each_way'], 32768)
            raw = next((Path(d)/'connections').glob('*.json')).read_text()
            self.assertNotIn(m.credentials[self.peer['id']], raw)
            self.assertEqual(len(m.snapshot({})['reports']), 1)
            self.assertTrue(m.disconnect(self.peer['id'])['remote_revoked'])
            self.assertFalse(m.credentials)


if __name__ == '__main__': unittest.main()
