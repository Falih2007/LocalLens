# LocalLens Android companion — pairing preview 0.3.2

## 0.3.2: EC signing and real on-phone TLS preflight

The OPPO screenshot from 0.3.1 showed an RSA internal error in Conscrypt during the handshake; the previous authorization change was insufficient. This build avoids that RSA operation by using a fresh non-exportable Android Keystore P-256 ECDSA key. The dedicated key manager exposes only that identity. Certificate pinning, TLS 1.2+, encrypted credentials and approval requirements stay enabled. The new key creates a new fingerprint, requiring fresh verification.

Before advertising on Wi-Fi, the app now performs real encrypted loopback exchanges with its actual Keystore-backed server key, testing every supported TLS 1.2/1.3 protocol and checking the certificate pin. The phone must show **TLS self-check passed** before it becomes discoverable. A failure stays visible without advertising a broken endpoint. Key generation and the checks run off the Android UI thread. The build version is displayed at the bottom of the screen.

Install `LocalLens-Companion-0.3.2-debug.apk` over the previous build, reopen LocalLens and enable discovery. Wait for the self-check result. If it passes, retry Windows pairing. These self-checks validate TLS locally, not Wi-Fi pairing or compute. Version 0.3.2 still requires validation on the OPPO. Desktop tests include actual JVM TLS 1.2/1.3 exchanges, rejection of an incorrect certificate pin and refusal to select obsolete RSA keys; they do not substitute for Android hardware tests.

## 0.3.1 TLS compatibility correction

The first real OPPO CPH2473 attempt successfully discovered protocol v2, but TLS failed before any pairing request was delivered. Version 0.3.1 authorizes `DIGEST_NONE` on the Android Keystore signing key because Android's TLS stack hashes its transcript before requesting a signature, as described in the [Android key-generation API documentation](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec.Builder#setDigests(java.lang.String...)). TLS encryption, transcript hashing and Windows certificate pinning remain enabled. A dedicated key manager selects only the corrected key, and handshake failures now appear in the phone status.

Install this APK over 0.3.0, stop/start discovery, and pair again. The corrected key has a new alias, so its certificate fingerprint changes and must be verified anew. Existing trust must not be transferred to a new certificate automatically. This correction is built and unit-tested; successful TLS and pairing on the OPPO still require a device retry.

This is a native Kotlin Android application, not a Termux launcher or a WebView. It implements discovery, approval, remembered trust, revocation and resource reporting. **This APK does not contain a llama.cpp worker and cannot perform inference.** Phone compute is unavailable in this preview. Pairing does not pool RAM.

## Install and try

From `android/companion`, run `.\gradlew.bat assembleDebug` with the Android SDK
and Java configured. The build writes `app/build/outputs/apk/debug/app-debug.apk`.
To enable the Windows download button, copy that APK to
`android/LocalLens-Companion-debug.apk` in the repository.

1. Copy `android/LocalLens-Companion-debug.apk` onto your OPPO and open it. Android will ask whether the chosen file app may install this debug build. There is no need to enable developer mode or USB debugging for ordinary installation.
2. Open LocalLens on the phone. Notifications are optional; allowing them makes pending requests easier to notice.
3. Tap **Enable discovery**. Keep the phone app open for initial pairing. Both devices must use the same private Wi-Fi; guest/client isolation can prevent connections.
4. Open the updated Windows app, choose **Devices**, then **Add device**. Choose the Android companion, not an older Termux session with a similar name.
5. Compare all four groups of the verification code on both screens. Approve the request on the phone and confirm the match on Windows. Each pending request expires after two minutes. The complete certificate fingerprint is also available on both screens.
6. The device card should show detected RAM, CPU, battery and an **unavailable** compute runtime. This is the correct state for this pairing preview.

After approved pairing, restart either app and enable discovery on the phone. Windows can reconnect without another approval as long as trust remains valid. **Disconnect** pauses reconnection for the current Windows process; **Reconnect** resumes it. **Forget device** removes local trust and attempts remote revocation. If the phone is offline, also revoke the laptop in its trusted-computers list. Phone revocation always invalidates that token, including after either app restarts.

The app does not start at boot and does not restart itself after Android kills it. Discovery uses a visible `connectedDevice` foreground service started from the foreground screen, with a stop action. OPPO battery management can still stop it. Reopen the app and enable discovery when needed. No unrestricted background compute is claimed.

## Build

Use Android Studio's bundled JDK 17 or newer (the tested bundled JDK is newer), Android SDK platform 37 and Build Tools 36.0.0. `ANDROID_HOME` should point to your SDK, or configure `sdk.dir` in an untracked `local.properties`. Gradle 9.3.1 and Android Gradle Plugin 9.1.1 are pinned; AGP supplies Kotlin 2.2.10. There are no runtime third-party Android libraries. JUnit 4.13.2 is test-only.

From this directory:

```powershell
.\gradlew.bat assembleDebug testDebugUnitTest lintDebug
```

The first build needs internet to obtain build tools/dependencies; installed apps pair offline. Output: `app/build/outputs/apk/debug/app-debug.apk`. Copy the finished APK to `../LocalLens-Companion-debug.apk` for the Windows download button (that path resolves to `android/LocalLens-Companion-debug.apk`). Rebuilding uses your local debug signing key; a differently signed build requires uninstalling the prior APK, which removes its trust and TLS identity.

Minimum Android 8/API 26; target API 35 for this OPPO-oriented preview. This is not a Play Store release. Newer Android versions and newer target-SDK local-network permission rules need separate validation before raising the target.

## Native worker investigation and boundary

The existing Termux executable links against Termux's environment and cannot simply be copied into an Android app's private directory and executed as a supported app binary. Android application sandboxing, native-library packaging, executable restrictions and linker dependencies differ. This iteration uses the requested pairing-first fallback rather than shipping an unverified worker.

`WorkerController.kt` is an explicit unavailable adapter, not a simulated worker. It records the existing pinned source revision `39febd2adb947b70da35e95f9351b3bf58ad170a`. A follow-up integration needs an Android NDK ARM64 build of that same revision, an in-process JNI worker lifecycle (or a properly packaged native executable), a fixed loopback-only RPC listener, and an authenticated streaming route compatible with `cluster.Tunnel`. `/rpc` currently returns HTTP 409 even to trusted clients. No arbitrary remote command, file, download or port-forward API exists.

Before enabling native compute: validate NDK build provenance, runtime capability/version checks, worker shutdown and stream cancellation on revocation, thermal/battery/memory safeguards, then reproduce real inference on the OPPO. Do not turn `ready` on merely because a library file exists.

## What was tested

Nine JVM tests exercise request-specific verification (including a shared Python/Kotlin digest vector), approval, persistence, rejection, timeout, request limits, failed-storage refusal, disconnect, restart, revocation and real TLS with temporary EC test keys. The pairing tests use an in-memory trust repository. These desktop tests do not exercise Android Keystore or real Android NSD.

The APK compiles and Android lint completes with no errors. Version 0.3.1 was installed on the OPPO: native mDNS discovery worked, but TLS failed before pairing. Version 0.3.2 has not yet been installed/verified on the physical phone or an emulator. Its Keystore signing, complete approval flow and OPPO background restrictions still require that test. Existing Termux experiment evidence is separate and is not evidence for this APK.
