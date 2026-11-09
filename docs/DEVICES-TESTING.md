# Device pairing verification — 29 October 2026

## Current 0.3.2 correction

The physical OPPO reported a Conscrypt RSA internal error in 0.3.1. Version 0.3.2 switches the TLS identity to Keystore P-256 ECDSA and adds mandatory on-phone loopback TLS/pin checks before discovery. Current validation: Android build and lint passed (0 errors, 4 warnings); nine JVM tests passed, including actual TLS 1.2/1.3 encrypted exchanges and wrong-pin refusal; 41 Python tests and 18 frontend tests passed. The additional lint warning flags the custom X509TrustManager used solely for the loopback self-check: it verifies the complete SHA-256 certificate pin and rejects all client-certificate authentication; a negative-pin test proves rejection. The three existing SDK/Gradle/backup warnings remain. The new APK is not yet validated on the phone. No successful native pairing is claimed. Earlier sections below record the prior releases.

## Subsequent OPPO CPH2473 attempt

The installed native companion was discovered through mDNS as protocol v2. Both TLS 1.2 and TLS 1.3 failed before pairing approval, so no successful native pairing is claimed. Version 0.3.1 corrects the Android Keystore TLS signing authorization (`DIGEST_NONE`), explicitly selects the corrected certificate key, and displays handshake failures. Its Android build, six JVM tests and lint passed. Install the updated APK and retry to confirm the correction on hardware. The earlier table below describes the initial release's validation boundary.

Story: Windows Devices → discovery → explicit request → matching request-specific code on both screens → phone approval and desktop confirmation → encrypted remembered trust → reconnect/revoke. Actual inference remains the separate existing Termux workflow.

| Boundary | Evidence / result |
|---|---|
| Desktop regression suite | 41 Python tests passed. Includes real pinned TLS legacy pairing/relay/revocation, real Windows DPAPI save/load, mDNS add/remove over real loopback multicast, and simulated native control-plane lifecycle. |
| Frontend | Production TypeScript/Vite build passed; 18 tests passed across five files. Native confirmation and legacy typed-code paths, reconnect/forget actions, empty journal and existing scan workflows covered. |
| Kotlin state machine | Six JVM tests passed with no skips/failures. Approval, hashed credential persistence, restarts, revocation, timeouts, request floods, storage failure and request-specific verification code covered. Uses in-memory storage, not Android hardware. |
| Android build | `assembleDebug testDebugUnitTest lintDebug` passed. APK signing verified with Android apksigner (v2 signature). Lint: 0 errors, 3 warnings: older target SDK, pinned older Gradle, legacy backup attribute recommendation. API 26–30 already have `allowBackup=false`; API 31+ also explicitly exclude app data from transfer/backup. |
| Legacy journal | `node tests/test_journal.cjs` passed against existing real saved 4B records. |
| Actual Windows process | UI detected Windows 11, Core Ultra 7 155H, Arc graphics, AI Boost and 31.4 GiB physical RAM. No model or benchmark data seeded. |
| Actual discovery in UI | Add device found the user's OPPO A77 through the existing broadcast/Termux fallback. This does not prove discovery by the new APK or mDNS on the phone. No new phone approval was performed. |
| APK download API | Authorized download matched the built signed APK byte-for-byte. Unauthenticated download returned HTTP 403. |
| Visual inspection | Desktop-width dark and light screens inspected. Narrow dark screen inspected. Original System appearance and viewport restored. Empty/unpaired and actual legacy discovered-device states inspected. New APK UI and real native pairing dialog were not screenshot-tested. |
| Native Windows ↔ OPPO pairing | **Not yet tested on the physical phone.** |
| Native inference | **Not implemented in this APK.** Native `/rpc` rejects compute. Termux worker preserved. |

The first restricted-process test attempt could not use Windows encryption/OpenSSL/multicast and had temporary-file errors. Rerunning the suite with the normal Windows process permissions passed all 41 tests. No product security checks were disabled. The first restricted preview also lacked WMI access; the final normal Windows process detected the real hardware correctly.

## Reproduce

Project root:

```powershell
python -m unittest discover -s tests -v
node tests/test_journal.cjs
```

Frontend:

```powershell
npm ci
npm run build
npm test
```

Android companion directory:

```powershell
.\gradlew.bat assembleDebug testDebugUnitTest lintDebug
```

Use the same Python environment as `Setup-Devices.cmd`. Tests need installed python-zeroconf, local multicast permission and OpenSSL (the existing suite finds Git for Windows' copy when available). They never download a model or run an LLM benchmark.

## Physical-phone acceptance checklist still pending

Install the debug APK, enable discovery and pair by comparing this request's code. Confirm both app restarts reconnect, reject and expire requests, move between Wi-Fi addresses, stop/start discovery, deny notifications, background the app under OPPO battery management, and revoke from each side. Verify no access after revocation and no raw RPC listener. Phone CPU/RAM/battery values must come from the actual Android instance. Native compute must remain unavailable until a pinned NDK worker and its safeguards pass independent device tests.
