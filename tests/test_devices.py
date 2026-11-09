"""Discovery/trust regressions. Fixtures are not real Android pairing or inference."""
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cluster
import connectnet
import mdns_discovery
from truststore import TrustStore


class FakeBrowser:
    error = None
    def __init__(self): self.offers = []
    def snapshot(self): return self.offers
    def close(self): pass


class DeviceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.browser_patch = patch('devices_manager.Browser', FakeBrowser); self.browser_patch.start()
        self.manager = cluster.Manager(self.folder.name)
        self.identity = 'a'*64
        self.peer = {'id': self.identity, 'fingerprint': self.identity, 'host': '192.168.1.20', 'port': 45460,
            'name': 'Native test fixture', 'protocol': 'locallens-companion/2', 'discovery': 'mDNS',
            'status': 'available', 'discovered_at': time.time()}
        self.manager.peers[self.identity] = dict(self.peer)
        self.manager.browser.offers = [dict(self.peer)]
        self.remote_status = 'pending'
        self.calls = []
        self.request_patch = patch.object(connectnet, 'request', side_effect=self.request); self.request_patch.start()

    def request(self, peer, path, body=None, token=None, **kwargs):
        self.calls.append((path, body, token))
        if path == '/pair': return {'status': 'pending'}
        if path == '/pair/status': return {'status': self.remote_status}
        if path == '/status': return {'physical_ram_gib': 8, 'runtime': {'status': 'unavailable'}}
        return {'status': 'revoked'}

    def tearDown(self):
        self.manager.close(); self.request_patch.stop(); self.browser_patch.stop(); self.folder.cleanup()

    def test_both_approvals_required_no_token_in_ui_and_worker_unavailable(self):
        self.manager.pair(self.identity)
        token = self.manager.credentials[self.identity]
        import hashlib
        digest = hashlib.sha256(('locallens-pair-v2\n'+self.identity+'\n'+token).encode('ascii')).hexdigest()[:16].upper()
        self.assertEqual(self.manager.peer(self.identity)['verification_code'], ' '.join(digest[i:i+4] for i in range(0,16,4)))
        self.remote_status = 'paired'; self.manager.refresh()
        self.assertEqual(self.manager.peer(self.identity)['status'], 'pending')
        self.assertNotIn('/status', [call[0] for call in self.calls])
        self.manager.confirm(self.identity)
        self.assertEqual(self.manager.peer(self.identity)['status'], 'connected')
        self.assertNotIn(token, json.dumps(self.manager.snapshot({})))
        with self.assertRaisesRegex(ValueError, 'unavailable'): self.manager.open_tunnel(self.identity)

    @unittest.skipUnless(os.name == 'nt', 'Uses Windows DPAPI')
    def test_persistence_reconnect_ip_change_disconnect_and_remote_revocation(self):
        self.manager.pair(self.identity); self.remote_status = 'paired'; self.manager.confirm(self.identity)
        token = self.manager.credentials[self.identity]
        encrypted = (Path(self.folder.name)/'devices.dpapi').read_bytes()
        self.assertNotIn(token.encode(), encrypted)
        restarted = cluster.Manager(self.folder.name)
        restarted.browser.offers = [{**self.peer, 'host': '192.168.1.99'}]
        restarted.refresh()
        self.assertEqual(restarted.peer(self.identity)['host'], '192.168.1.99')
        self.assertEqual(restarted.peer(self.identity)['status'], 'connected')
        restarted.disconnect(self.identity); restarted.refresh()
        self.assertEqual(restarted.peer(self.identity)['status'], 'disconnected')
        restarted.resume(self.identity)
        self.assertEqual(restarted.peer(self.identity)['status'], 'connected')
        self.remote_status = 'expired'; restarted.refresh()
        self.assertNotIn(self.identity, restarted.credentials)
        self.assertNotIn(self.identity, cluster.Manager(self.folder.name).credentials)
        restarted.close()

    def test_rejected_and_expired_pairing_cannot_be_confirmed(self):
        self.manager.pair(self.identity)
        self.manager.peers[self.identity]['pairing_started'] -= 121
        with self.assertRaisesRegex(ValueError, 'expired'): self.manager.confirm(self.identity)
        self.remote_status = 'expired'; self.manager.refresh()
        self.assertNotIn(self.identity, self.manager.credentials)

    def test_remembered_pin_not_replaced_by_name_or_changed_certificate(self):
        self.manager.pair(self.identity)
        replacement = {**self.peer, 'id': 'b'*64, 'fingerprint': 'b'*64}
        self.manager.browser.offers = [replacement]; self.manager.live_discovery()
        self.assertEqual(self.manager.peer(self.identity)['fingerprint'], self.identity)
        self.assertNotIn('b'*64, self.manager.credentials)

    def test_multiple_devices_dedup_and_offline(self):
        self.manager.browser.offers = [self.peer, dict(self.peer), {**self.peer, 'id': 'b'*64, 'fingerprint': 'b'*64}]
        self.manager.live_discovery(); self.assertEqual(len(self.manager.peers), 2)
        self.manager.browser.offers = []; self.manager.live_discovery()
        self.assertTrue(all(peer['status'] == 'offline' for peer in self.manager.peers.values()))

    def test_desktop_cannot_enable_compute_and_manual_rejects_public_address(self):
        with self.assertRaisesRegex(ValueError, 'phone'): self.manager.sharing(self.identity, True)
        with self.assertRaises(ValueError): self.manager.manual('8.8.8.8', 45460)


class MDNSValidationTests(unittest.TestCase):
    def test_invalid_advertisement_is_not_trusted(self):
        from types import SimpleNamespace
        info = SimpleNamespace(properties={b'protocol': b'locallens-companion/2', b'fingerprint': b'a'*64},
                               port=45460, name='test._locallens._tcp.local.', parsed_addresses=lambda: ['8.8.8.8'])
        with self.assertRaises(ValueError): mdns_discovery.offer(info)
        info.parsed_addresses = lambda: ['192.168.1.20']
        self.assertEqual(mdns_discovery.offer(info)['fingerprint'], 'a'*64)
        info.properties[b'fingerprint'] = b'wrong'
        with self.assertRaises(ValueError): mdns_discovery.offer(info)

    def test_real_loopback_dns_sd_add_and_goodbye(self):
        from zeroconf import Zeroconf, ServiceInfo, ServiceBrowser, IPVersion
        browser = mdns_discovery.Browser()
        browser.started = True
        browser.zc = Zeroconf(interfaces=['127.0.0.1'], ip_version=IPVersion.V4Only)
        browser.browser = ServiceBrowser(browser.zc, mdns_discovery.SERVICE, listener=browser)
        publisher = Zeroconf(interfaces=['127.0.0.1'], ip_version=IPVersion.V4Only)
        import socket
        info = ServiceInfo(mdns_discovery.SERVICE, 'LocalLens test fixture.'+mdns_discovery.SERVICE,
            addresses=[socket.inet_aton('192.168.1.20')], port=45460,
            properties={'protocol':'locallens-companion/2', 'fingerprint':'c'*64, 'name':'DNS-SD fixture'})
        try:
            publisher.register_service(info)
            end = time.monotonic()+6
            while not browser.entries and time.monotonic()<end: time.sleep(.05)
            self.assertTrue(browser.entries, 'Real multicast DNS fixture was not discovered')
            publisher.unregister_service(info)
            end = time.monotonic()+6
            while browser.entries and time.monotonic()<end: time.sleep(.05)
            self.assertEqual(browser.entries, {})
        finally: publisher.close(); browser.close()
