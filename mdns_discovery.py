"""DNS-SD via python-zeroconf. Advertisements are hints, never authentication."""
from pathlib import Path
import socket
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
SERVICE = '_locallens._tcp.local.'


def offer(info):
    import connectnet
    properties = {k.decode('utf-8'): v.decode('utf-8') for k, v in info.properties.items() if v is not None}
    fingerprint = properties.get('fingerprint', '')
    if len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
        raise ValueError('Invalid advertised certificate fingerprint.')
    if properties.get('protocol') not in ('locallens-companion/1', 'locallens-companion/2'):
        raise ValueError('Incompatible companion protocol.')
    host = next((h for h in info.parsed_addresses() if _private(h)), None)
    if host is None or not 1024 <= info.port <= 65535: raise ValueError('No private IPv4 endpoint.')
    return {'id': fingerprint, 'fingerprint': fingerprint, 'host': host, 'port': info.port,
            'name': properties.get('name', info.name.split('.')[0])[:80],
            'platform': properties.get('platform', 'Companion')[:40],
            'protocol': properties['protocol'], 'discovery': 'mDNS', 'status': 'available',
            'discovered_at': time.time()}


def _private(host):
    import connectnet
    try: connectnet.lan_address(host); return True
    except ValueError: return False


class Browser:
    def __init__(self):
        self.entries = {}
        self.lock = threading.RLock()
        self.zc = self.browser = None
        self.error = None
        self.started = False
        self.adapters = None
        self.next_check = 0

    def start(self):
        with self.lock:
            if self.started: return
            self.started = True
        try:
            from zeroconf import IPVersion, ServiceBrowser, Zeroconf
            self.zc = Zeroconf(ip_version=IPVersion.V4Only)
            self.browser = ServiceBrowser(self.zc, SERVICE, listener=self)
            self.error = None
        except (ImportError, OSError) as exc:
            if self.zc: self.zc.close(); self.zc = None
            self.started = False
            self.error = 'mDNS unavailable: ' + str(exc) + '. Run Setup-Devices.cmd; check private-network firewall access and Wi-Fi isolation.'

    def add_service(self, zc, type_, name): self.update_service(zc, type_, name)

    def update_service(self, zc, type_, name):
        try:
            info = zc.get_service_info(type_, name, timeout=1500)
            if info:
                candidate = offer(info)
                with self.lock:
                    if name in self.entries or len(self.entries) < 128: self.entries[name] = candidate
        except (OSError, ValueError, UnicodeError, TypeError): pass

    def remove_service(self, zc, type_, name):
        with self.lock: self.entries.pop(name, None)

    def snapshot(self):
        if time.monotonic() >= self.next_check:
            self.next_check = time.monotonic() + 15
            try:
                import ifaddr
                adapters = tuple(sorted(ip.ip for adapter in ifaddr.get_adapters() for ip in adapter.ips if isinstance(ip.ip, str) and _private(ip.ip)))
                if self.adapters is not None and self.adapters != adapters:
                    self.close()
                    with self.lock: self.entries.clear(); self.started = False
                self.adapters = adapters
            except (ImportError, OSError): pass
        self.start()
        with self.lock:
            # ServiceBrowser honours DNS TTL and goodbye records; identities deduplicate service renames.
            return list({p['id']: dict(p) for p in self.entries.values()}.values())

    def close(self):
        if self.browser: self.browser.cancel()
        if self.zc: self.zc.close()


def advertise(host, port, fingerprint, name):
    from zeroconf import IPVersion, ServiceInfo, Zeroconf
    zc = Zeroconf(ip_version=IPVersion.V4Only)
    info = ServiceInfo(SERVICE, f'LocalLens-{fingerprint[:12]}.{SERVICE}', addresses=[socket.inet_aton(host)], port=port,
                       properties={'protocol': 'locallens-companion/1', 'fingerprint': fingerprint, 'name': name, 'platform': 'Termux'})
    zc.register_service(info, allow_name_change=True)
    return zc, info
