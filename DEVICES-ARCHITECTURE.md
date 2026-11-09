# Automatic discovery and pairing — implementation, 29 October 2026

## Existing architecture preserved

The desktop is a Python 3.11 localhost HTTP backend with React/TypeScript, Vite, Tailwind v4 and official Base UI shadcn components. `cluster.py` retains its legacy control plane and loopback RPC tunnel; `distributed.py` retains the existing pinned llama.cpp comparison runner. Benchmarking, model downloads, cleanup rules, journal evidence and localhost session/Host validation have not been replaced.

The old Termux `companion.py` uses pinned TLS, explicit terminal approval and session-only tokens. Its custom IPv4 broadcast discovery is retained only as a compatibility fallback for deployed companions. Optional DNS-SD advertising was added when `mdns_discovery.py` and python-zeroconf are available. The legacy source ZIP remains usable without mDNS.

## New components

- `mdns_discovery.py`: python-zeroconf 0.151.0 browses `_locallens._tcp.local.` using standard DNS-SD. Adds/updates/removals, TTL expiry and service goodbye messages come from the library. Entries deduplicate by certificate fingerprint. Interface changes trigger browser reconstruction. Only private IPv4 endpoints and supported protocol versions are accepted. TXT records contain friendly name, platform, protocol and certificate fingerprint, never credentials. Android advertises through the platform NsdManager, not a custom multicast implementation.
- `devices_manager.py`: incremental subclass of the existing manager. It adds native protocol v2, double approval, remembered-device reconnection, manual address lookup, disconnect/forget semantics and a periodic discovery/health task. Legacy protocol v1 and inference contracts stay intact.
- `truststore.py`: Windows user-bound DPAPI-encrypted records, atomically replaced on disk at `data/devices.dpapi`. Tokens are never included in state responses, exported results or source packages. Non-Windows systems fail closed for persistent storage; they do not save plaintext tokens.
- `android/companion`: native Kotlin app using Android NSD, Android Keystore TLS identity, system notifications, native approval dialogs and app-private trust storage. Only hashes of high-entropy random bearer credentials are stored on Android. Backup and device transfer of trust records are excluded.

## Pairing and trust

1. Discovery supplies an untrusted candidate endpoint and certificate fingerprint.
2. Windows connects using TLS 1.2+ and checks that exact certificate before sending application data.
3. Windows generates a random 256-bit bearer credential and sends a pairing request encrypted to that candidate. The phone queues it with a two-minute expiry, per-host rate limit and bounded pending queue. The requester name is display information, not authentication.
4. Both screens independently derive a request-specific verification code: the first 64 bits of SHA-256 over `locallens-pair-v2`, a newline, the phone certificate fingerprint, a newline, and this request's random bearer credential (ASCII). The phone displays that code in the corresponding request dialog. Different requests or certificates produce different codes, even when requester names match. The complete certificate fingerprint is also available. This is a visual verification digest built from SHA-256, not an encryption algorithm or a standardized PAKE. Users must reject mismatches; discovery cannot establish identity on its own.
5. The user approves on the phone and confirms the code on Windows. Windows does not request protected status or persist trust until both approvals have occurred.
6. Android retains only SHA-256(token); Windows retains the token inside DPAPI. Subsequent operations require that bearer token over the same pinned TLS identity. Changing an IP is allowed; changing a certificate is a new identity and needs new approval.
7. Revocation deletes the phone's trusted token hash. The next status poll reports expired authorization and Windows removes its remembered credential. Transient connection errors retain trust for retry; certificate pinning still applies to every retry.

This is an authenticated local application protocol using established TLS/certificate-pinning and bearer-secret mechanisms. It has automated security regressions but has not undergone an independent security audit. A compromised endpoint/Windows account can access that endpoint's authorized session. Verification is essential on a hostile local network; names and advertised IPs are never proof of identity.

## Connection, compute and error states

Available, pending, connected, disconnected, stale and offline are distinct. Discovery removal marks unpaired devices offline. Health requests detect loss of an established connection. Remembered devices are re-resolved by pinned identity and can move between private IPv4 addresses. mDNS can be blocked by firewalls, guest Wi-Fi isolation, VPN routing or different networks; Windows shows a diagnostic and offers an advanced private IPv4/port fallback. It does not alter firewall rules automatically.

The native preview reports real CPU/memory/battery/thermal telemetry when running on Android, but its worker is explicitly **unavailable**. Its compute button is disabled and authenticated RPC is rejected. The desktop disables real comparisons unless a connected worker reports ready; the existing manager also checks pinned revision before opening a tunnel. Pairing cannot silently enable compute or add phone RAM to model capacity.

The new APK's network listener binds only to the selected private Wi-Fi IPv4 interface. Worker/network errors are displayed; network changes close the listener and connections and register a new service. Request sizes, header sizes, socket timeouts, thread pool and queues are bounded. No raw RPC port is exposed. Native inference, overheating/low-battery worker shutdown and JNI lifecycle remain pending because no native worker is shipped. The existing Termux safeguards remain unchanged.

## API additions

Existing `/api/connect/*` endpoints retain local-session authentication. New actions: `confirm`, `resume`, `forget`, `manual`, `sharing`. `pair` accepts the existing v1 code/fingerprint fields or starts a v2 request without typed codes. `sharing` only allows a desktop stop request; enabling belongs to the phone. `GET /api/connect/apk` serves only the known packaged debug APK after localhost authentication; it is not a public LAN download server.

Device-state responses add optional protocol/platform/remembered/verification-code fields and discovery/trust errors. Existing measurement JSON schemas and saved evidence formats are unchanged.

## Validation boundary

Desktop tests exercise real loopback mDNS registration/removal, real TLS legacy approval/relay/revocation, real DPAPI persistence, native manager lifecycle with a simulated remote control endpoint, certificate replacement, two approvals, expiry and unavailable-worker refusal. Kotlin JVM tests use an in-memory repository. Frontend tests cover both v1 and v2 dialogs and remembered-device actions. None of those simulations count as a successful Windows–OPPO APK pairing.

Next physical test: install APK, enable discovery on private Wi-Fi, verify both codes and approve, inspect real hardware, restart both apps, reconnect, change Wi-Fi/IP, reject/expire a request, revoke on phone and verify Windows cannot reconnect. Native compute is a separate milestone.

References: [Android NSD](https://developer.android.com/develop/connectivity/wifi/use-nsd), [Android Keystore](https://developer.android.com/privacy-and-security/keystore), [foreground connected-device service](https://developer.android.com/develop/background-work/services/fgs/service-types#connected-device), [python-zeroconf API](https://python-zeroconf.readthedocs.io/en/latest/api.html).
