"""Incremental native-companion support; legacy benchmark/tunnel contracts stay intact."""
import hashlib
import secrets
import socket
import ssl
import time
import threading
import connectnet
from mdns_discovery import Browser
from truststore import TrustStore


def upgrade(LegacyManager):
    class DeviceManager(LegacyManager):
        def __init__(self, data):
            super().__init__(data)
            self.browser = Browser()
            self.store = TrustStore(self.data/'devices.dpapi')
            self.remembered, self.paused = {}, set()
            self.persisted_ids = set()
            self.trust_error = None
            self.stopped = threading.Event()
            self.refresh_lock = threading.Lock()
            try:
                records = self.store.load()
                for identity, record in records.items():
                    peer = record['peer']
                    if identity != peer['fingerprint'] or len(record['token']) != 64: continue
                    self.remembered[identity] = record
                    self.persisted_ids.add(identity)
                    self.peers[identity] = {**peer, 'status': 'offline', 'remembered': True}
                    self.credentials[identity] = record['token']
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.trust_error = 'Remembered devices could not be loaded: ' + str(exc)

        def live_discovery(self):
            offers = self.browser.snapshot()
            live = {p['id'] for p in offers}
            with self.lock:
                for offer in offers:
                    identity = offer['id']
                    if identity in self.credentials:
                        self.peers[identity].update(host=offer['host'], port=offer['port'], discovered_at=time.time())
                    else: self.peers[identity] = {**offer, 'discovered_at': time.time()}
                for identity, peer in self.peers.items():
                    if identity not in live and peer.get('discovery') == 'mDNS' and identity not in self.credentials:
                        peer.update(status='offline', message='Open the companion on the same Wi-Fi.')
            return offers

        def scan(self):
            super().scan()  # Existing broadcast path for deployed Termux companions.
            self.live_discovery()
            return self.snapshot({})

        def manual(self, host, port):
            host = connectnet.lan_address(str(host)); port = int(port)
            if not 1024 <= port <= 65535: raise ValueError('Port must be between 1024 and 65535.')
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            with socket.create_connection((host, port), timeout=5) as raw:
                with context.wrap_socket(raw, server_hostname=host) as stream:
                    fingerprint = hashlib.sha256(stream.getpeercert(binary_form=True)).hexdigest()
            peer = {'id': fingerprint, 'fingerprint': fingerprint, 'host': host, 'port': port,
                    'status': 'available', 'name': 'Manual companion', 'discovered_at': time.time()}
            info = connectnet.request(peer, '/identity')
            if info.get('protocol') != 'locallens-companion/2': raise ValueError('Manual setup requires the native companion. Use Scan nearby for Termux.')
            peer.update(name=str(info.get('name', 'Companion'))[:80], protocol=info['protocol'], platform='Android', discovery='manual')
            with self.lock:
                if fingerprint not in self.credentials: self.peers[fingerprint] = peer
            return {'status': 'available'}

        def pair(self, identity, code='', fingerprint_confirmed=False):
            peer = self.peer(identity)
            if peer.get('protocol') != 'locallens-companion/2': return super().pair(identity, code, fingerprint_confirmed)
            with self.lock:
                if identity in self.credentials: raise ValueError('Already paired or awaiting approval.')
                if time.time()-peer.get('discovered_at', 0) > 120: raise ValueError('Discovery expired. Scan again.')
                token = secrets.token_hex(32)
                result = connectnet.request(peer, '/pair', {'token': token, 'name': socket.gethostname()})
                if result.get('status') != 'pending': raise ValueError('Unexpected pairing response.')
                self.credentials[identity] = token
                self.peers[identity].update(status='pending', verified=False, pairing_started=time.time(),
                    verification_code=' '.join(hashlib.sha256(('locallens-pair-v2\n'+peer['fingerprint']+'\n'+token).encode('ascii')).hexdigest()[:16].upper()[i:i+4] for i in range(0,16,4)),
                    message='Compare the code on both screens. Approve on the phone and confirm here.')
            return {'status': 'pending'}

        def confirm(self, identity):
            with self.lock:
                peer = self.peers[identity]
                if peer.get('status') != 'pending' or time.time()-peer['pairing_started'] > 120:
                    raise ValueError('Pairing expired. Connect again.')
                peer['verified'] = True
            return self.refresh()

        def save_trust(self):
            try:
                self.store.save(self.remembered)
                self.persisted_ids = set(self.remembered)
                self.trust_error = None
                return True
            except OSError as exc:
                self.trust_error = str(exc)
                return False

        def refresh(self):
            if not self.refresh_lock.acquire(blocking=False): return {'status': 'refreshing'}
            try: return self.refresh_locked()
            finally: self.refresh_lock.release()

        def refresh_locked(self):
            self.live_discovery()
            # Isolate native sessions: legacy refresh would trust an unconfirmed native pair.
            with self.lock: identities = list(self.credentials)
            for identity in identities:
                peer = self.peer(identity)
                if identity in self.paused: continue
                token = self.credentials.get(identity)
                if not token: continue
                try:
                    state = connectnet.request(peer, '/pair/status', token=token, timeout=3)
                    if state['status'] == 'expired':
                        self.forget(identity, remote=False)
                        with self.lock: self.peers[identity].update(message='Pairing expired, rejected or revoked. Connect again with phone approval.')
                        continue
                    if state['status'] != 'paired': continue
                    native = peer.get('protocol') == 'locallens-companion/2'
                    if native and not (peer.get('verified') or identity in self.remembered): continue
                    info = connectnet.request(peer, '/status', token=token, timeout=3)
                    with self.lock:
                        if self.credentials.get(identity) != token: continue
                        self.peers[identity].update(status='connected', hardware=info, last_seen=time.time(), message='Encrypted connection. Compute sharing is controlled on your phone.')
                        if native and identity not in self.remembered:
                            self.remembered[identity] = {'peer': {k: peer[k] for k in ('id','fingerprint','host','port','name','protocol')}, 'token': token}
                            self.save_trust()
                        if native: self.peers[identity]['remembered'] = identity in self.persisted_ids
                except (OSError, ValueError, KeyError) as exc:
                    with self.lock:
                        if identity in self.peers: self.peers[identity].update(status='disconnected', message=str(exc))
            return {'status': 'refreshed'}

        def resume(self, identity):
            if identity not in self.remembered: raise ValueError('This device is not remembered. Pair again.')
            with self.lock: self.paused.discard(identity)
            return self.refresh()

        def sharing(self, identity, enabled):
            if enabled is not False: raise ValueError('Enable compute sharing on your phone.')
            return connectnet.request(self.peer(identity), '/sharing', {'enabled': False}, self.credentials[identity])

        def forget(self, identity, remote=True):
            peer = self.peer(identity); token = self.credentials.get(identity); revoked = False
            if remote and token:
                try: connectnet.request(peer, '/revoke', token=token); revoked = True
                except (OSError, ValueError): pass
            with self.lock:
                tunnel = self.tunnels.pop(identity, None)
                self.credentials.pop(identity, None); self.remembered.pop(identity, None); self.paused.discard(identity)
                self.persisted_ids.discard(identity)
                self.peers[identity].update(status='available', remembered=False, hardware=None,
                    message='Forgotten locally.' + ('' if revoked else ' If offline, also revoke this laptop on the phone.'))
                persisted = self.save_trust()
            if tunnel: tunnel.close()
            if not persisted and remote:
                raise ValueError('Persistent trust could not be updated. Revoke this laptop on the phone before restarting Windows. '+str(self.trust_error))
            return {'status': 'forgotten', 'remote_revoked': revoked}

        def disconnect(self, identity):
            peer = self.peer(identity)
            if peer.get('protocol') != 'locallens-companion/2': return super().disconnect(identity)
            with self.lock:
                self.paused.add(identity); tunnel = self.tunnels.pop(identity, None)
                self.peers[identity].update(status='disconnected', message='Disconnected. Trust is retained; reconnect when ready.')
            if tunnel: tunnel.close()
            try: connectnet.request(peer, '/session/close', token=self.credentials.get(identity))
            except (OSError, ValueError): pass
            return {'status': 'disconnected'}

        def snapshot(self, hardware):
            state = super().snapshot(hardware)
            state.update(discovery_error=self.browser.error, trust_error=self.trust_error)
            return state

        def close(self):
            self.stopped.set()
            self.browser.close()
            for tunnel in list(self.tunnels.values()): tunnel.close()
            self.tunnels.clear()
            # Native credentials deliberately persist. Legacy credentials are session-only.
            for identity in list(self.credentials):
                if self.peers[identity].get('protocol') != 'locallens-companion/2': super().disconnect(identity)

        def start(self):
            def monitor():
                while not self.stopped.is_set():
                    try: self.refresh()
                    except (OSError, ValueError): pass
                    self.stopped.wait(5)
            threading.Thread(target=monitor, name='LocalLens device health', daemon=True).start()
    return DeviceManager
