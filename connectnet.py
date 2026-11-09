"""Small LAN discovery and pinned TLS transport. No remote command protocol."""
import hashlib
import http.client
import ipaddress
import json
import secrets
import socket
import ssl
import time
import os
import subprocess
import select

DISCOVERY_PORT = 45459
PROTOCOL = 'locallens-companion/1'
MAX_MESSAGE = 65536
NETWORKS = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


def lan_address(host, allow_loopback=False):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not (any(address in n for n in NETWORKS) or (allow_loopback and address.is_loopback)):
        raise ValueError('Only a private IPv4 LAN address is allowed.')
    return str(address)


def tls_socket(peer, timeout=8):
    host = lan_address(peer['host'], peer.get('_test_loopback', False))
    port = int(peer['port'])
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid companion port.')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Exact certificate pin checked BEFORE sending any data.
    raw = socket.create_connection((host, port), timeout=timeout)
    try:
        raw.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        stream = context.wrap_socket(raw, server_hostname=host)
        digest = hashlib.sha256(stream.getpeercert(binary_form=True)).hexdigest()
        if not secrets.compare_digest(digest, peer['fingerprint']):
            stream.close()
            raise ValueError('Phone certificate changed. Disconnect and compare its fingerprint again.')
        return stream
    except Exception:
        raw.close()
        raise


def request(peer, path, body=None, token=None, timeout=8):
    if path not in ('/pair', '/pair/status', '/status', '/echo', '/revoke', '/sharing', '/identity', '/session/close'):
        raise ValueError('Unsupported companion operation.')
    content = json.dumps(body or {}, allow_nan=False).encode()
    if len(content) > MAX_MESSAGE:
        raise ValueError('Request too large.')
    with tls_socket(peer, timeout) as stream:
        auth = f'Authorization: Bearer {token}\r\n' if token else ''
        stream.sendall((f'POST {path} HTTP/1.1\r\nHost: companion\r\n{auth}Content-Type: application/json\r\nContent-Length: {len(content)}\r\nConnection: close\r\n\r\n').encode() + content)
        response = http.client.HTTPResponse(stream)
        response.begin()
        data = response.read(MAX_MESSAGE + 1)
        if len(data) > MAX_MESSAGE:
            raise ValueError('Companion response too large.')
        value = json.loads(data)
        if response.status != 200:
            raise ValueError(value.get('error', 'Companion rejected the request.'))
        return value


def relay_streams(local, remote, stopped, on_transfer, on_remote_eof=None):
    """Bounded duplex forwarding: a blocked upload must not prevent downloads."""
    streams = (local, remote)
    pending = {local: bytearray(), remote: bytearray()}
    ended = set()
    last_progress = time.monotonic()
    for stream in streams: stream.setblocking(False)
    while not stopped():
        if ended and not any(pending.values()): return
        readers = [s for s in streams if s not in ended and len(pending[remote if s is local else local]) < 4*1024**2]
        writers = [s for s in streams if pending[s]]
        readable, writable, _ = select.select(readers, writers, [], .25)
        for stream in readers:
            if isinstance(stream, ssl.SSLSocket) and stream.pending() and stream not in readable: readable.append(stream)
        for stream in readable:
            try: data = stream.recv(65536)
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError): continue
            if not data:
                ended.add(stream)
                if stream is remote and on_remote_eof: on_remote_eof()
                continue
            pending[remote if stream is local else local].extend(data)
            last_progress = time.monotonic()
        for stream in writable:
            try: count = stream.send(pending[stream][:65536])
            except (BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError): continue
            if not count: raise OSError('RPC stream closed during transfer.')
            del pending[stream][:count]
            on_transfer(stream is remote, count)
            last_progress = time.monotonic()
        if time.monotonic()-last_progress > 30: raise TimeoutError('RPC stream made no progress for 30 seconds.')


def discovery_routes():
    """Use each adapter's real prefix, rather than guessing a /24 or default route."""
    routes = []
    if os.name == 'nt':
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', 'Get-NetIPAddress -AddressFamily IPv4 | Select-Object IPAddress,PrefixLength | ConvertTo-Json -Compress'], capture_output=True, text=True, timeout=8, creationflags=0x08000000)
            entries = json.loads(result.stdout)
            if isinstance(entries, dict): entries = [entries]
            for entry in entries:
                try:
                    host = lan_address(entry['IPAddress'])
                    prefix = int(entry['PrefixLength'])
                    if not 8 <= prefix <= 30: continue
                    broadcast = str(ipaddress.ip_network(f'{host}/{prefix}', strict=False).broadcast_address)
                    if (host, broadcast) not in routes: routes.append((host, broadcast))
                except (ValueError, KeyError, TypeError): continue
        except (OSError, ValueError, TypeError, subprocess.SubprocessError): pass
    return routes[:32] + [('', '255.255.255.255')]


def discover(timeout=2.5, target='255.255.255.255', port=DISCOVERY_PORT):
    nonce = secrets.token_hex(16)
    found = {}
    sockets = []
    try:
        payload = json.dumps({'protocol': PROTOCOL, 'nonce': nonce}).encode()
        routes = discovery_routes() if target == '255.255.255.255' else [('', target)]
        for source, destination in routes:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.bind((source, 0))
                sock.setblocking(False)
                sock.sendto(payload, (destination, port))
                sockets.append(sock)
            except OSError: sock.close()
        if not sockets: raise OSError('No network adapter could send a discovery request.')
        end = time.monotonic() + timeout
        while time.monotonic() < end and len(found) < 32:
            ready, _, _ = select.select(sockets, [], [], min(.25, max(0, end-time.monotonic())))
            for sock in ready:
                receive_offer(sock, nonce, found)
    finally:
        for sock in sockets: sock.close()
    return list(found.values())


def receive_offer(sock, nonce, found):
    try:
        raw, address = sock.recvfrom(2048)
        host = lan_address(address[0])
        offer = json.loads(raw)
        if not isinstance(offer, dict): return
        if offer.get('protocol') != PROTOCOL or offer.get('nonce') != nonce:
            return
        fingerprint = offer['fingerprint']
        if not isinstance(fingerprint, str) or len(fingerprint) != 64 or any(c not in '0123456789abcdef' for c in fingerprint):
            return
        worker_port = int(offer['port'])
        if not 1024 <= worker_port <= 65535:
            return
        found[fingerprint] = {'id': fingerprint, 'fingerprint': fingerprint, 'host': host, 'port': worker_port, 'name': str(offer.get('name', 'Nearby device'))[:80], 'status': 'available', 'discovered_at': time.time()}
    except (OSError, ValueError, KeyError, TypeError):
        return
