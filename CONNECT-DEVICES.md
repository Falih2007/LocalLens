# Native Android pairing preview — 29 October 2026

For the new no-terminal discovery/pairing flow, install `android/LocalLens-Companion-debug.apk`, enable discovery on the phone, and choose **Devices → Add device** on Windows. Compare the verification code on both screens, approve on the phone and confirm on Windows. Remembered native pairings survive app restarts. **The APK does not yet bundle a compute worker; use the existing Termux flow below for actual inference.**

See [Android installation/build guide](android/companion/README.md) and [device architecture and test boundaries](DEVICES-ARCHITECTURE.md). Run `Setup-Devices.cmd` once if mDNS dependencies are missing. Bundled desktop mDNS libraries are built for Python 3.11 Windows x64; rerun setup for a different Python environment. Discovery/pairing needs no internet after setup.

---

# Connect Devices — prototype setup and evidence

## What you can do now

Open LocalLens → Connect Devices. Scan nearby, compare the phone's certificate fingerprint, request pairing, approve in Termux, and benchmark the encrypted connection. The dashboard reports the companion's current hardware and runtime status. It does not create an OPPO card before discovering a real companion.

The desktop/companion transport has been tested locally with real TLS sockets, approval, rejection, revocation and byte transfer. These transport tests use an explicitly synthetic echo worker, not an LLM. No Windows–OPPO model-parallel run or phone inference benchmark has been executed. The phone is being prepared later at the user's request.

## Android setup (on the OPPO, once)

1. Install Termux from an official distribution linked at https://termux.dev/. Open it on the same trusted Wi-Fi as the laptop. Guest Wi-Fi/client isolation and some VPNs prevent LAN discovery. Keep Termux in the foreground during the experiment. Android may kill background workers; disable neither security features nor network protections automatically.
2. Transfer `companion.py`, `connectnet.py` and `android/setup-termux.sh` from this project to the phone using your usual file-transfer method. These are source files, not a signed Android app. In Termux, put the two Python files together in `~/locallens-companion/`. Keep the `android/` subfolder beside those Python files. If using Downloads, run `termux-setup-storage` yourself, grant only the access you want, and copy those files into that folder. Run build commands inside Termux's home directory, not shared storage.
3. In Termux:

```sh
cd ~/locallens-companion
bash android/setup-termux.sh
python companion.py --name 'OPPO A77' --rpc-binary ~/locallens-worker/build/bin/ggml-rpc-server
```

The script installs Python/OpenSSL and native build tools, then builds the pinned llama.cpp source. The desktop checks its engine version against this pin and checks the companion build-revision record; keep the build record beside the source tree. It refuses to overwrite an existing worker directory. It does not download a model. Building on this particular OPPO remains untested. If compilation fails, keep the exact output; do not substitute an unrelated binary or silently downgrade the revision.

For discovery and pairing without inference, install `python`, `openssl` and `openssl-tool` with Termux's package manager and run `python companion.py --name 'OPPO A77'` without `--rpc-binary`. The dashboard will correctly say the runtime is unavailable.

The companion chooses the phone's private IPv4 interface automatically and listens on TCP 45460; LAN discovery listens on UDP 45459. An advanced `--host PRIVATE_WIFI_ADDRESS` option exists if Android routing selects the wrong interface. No public-address or wildcard TCP binding is allowed. No port forwarding is needed. If a port is busy, the companion exits with the actual error. Wi-Fi, rather than Bluetooth, carries inference traffic.

The first launch generates a local certificate and private key under `~/.locallens-companion/` using OpenSSL. The key stays on the phone. The terminal displays a full SHA-256 fingerprint and a 10-character pairing code. Compare every fingerprint character with the desktop dialog before entering the code. This manual comparison prevents a forged discovery advertisement becoming trusted.

## Pairing and connection test

1. On the laptop, open Connect Devices → Scan nearby.
2. Choose the real discovered companion → Connect.
3. Compare its full certificate fingerprint to Termux. Check the matching-fingerprint box, then enter the phone's code.
4. On the phone, inspect the requesting laptop name and address. Type the displayed `approve REQUEST_ID` command only for your own laptop. Requests expire after two minutes.
5. The desktop polls approval/status while this page is open. Once connected, select Benchmark connection. It measures five TLS echo requests and a 32 KiB payload echo; results include TLS setup, not just network latency. It does not claim sustained Wi-Fi bandwidth.

Credentials exist only in memory. Restarting either application requires pairing again. Desktop Disconnect & revoke drops local credentials, closes its tunnel and asks the phone to revoke. If the phone is unreachable, remote revocation cannot be confirmed; run `revoke-all` or `quit` on the phone. `revoke-all` immediately closes existing authenticated streams. The code is rate limited to five pairing attempts per minute per source address.

## Windows RPC build (developer setup, once)

The normal benchmark engine download is not assumed to include a compatible RPC build. Install Git, CMake and Visual Studio C++ build tools using their official installers. In a Developer PowerShell, use a new source directory:

```powershell
git clone https://github.com/ggml-org/llama.cpp.git locallens-rpc-source
Set-Location locallens-rpc-source
git checkout --detach 39febd2adb947b70da35e95f9351b3bf58ad170a
git rev-parse HEAD
cmake -S . -B build -DGGML_RPC=ON -DLLAMA_BUILD_TESTS=OFF
cmake --build build --config Release --target llama-server
```

Keep the resulting `llama-server.exe` alongside its built DLLs. The initial configuration uses laptop CPU and phone CPU, reducing dependencies on Android graphics drivers. Intel Arc and Intel AI Boost NPU do not participate in this experiment. A future adapter may add Arc after correctness is verified. Current Exo is represented by a separate unsupported backend, not pretended to run on this hardware.

## Small-model experiment

Start with an open, ungated small GGUF (for example Qwen3 0.6B from the existing `models.json` catalogue), under 2 GiB. Download the exact pinned catalogue file and verify its SHA-256. Keep the model on the laptop; RPC distributes the necessary tensors to the phone. Neither the experiment nor the companion deletes existing models. Model licenses apply separately from engine licenses.

After pairing and checking the phone runtime is ready, expand Advanced experiment setup. Enter the trusted RPC-enabled `llama-server.exe` path and the GGUF path. Keep eight remote layers initially. Run real comparison.

The runner launches three sequential server configurations for the same model/hash, context 1024, prompt, seed 42 and temperature zero:

| Run | Configuration | Meaning |
| --- | --- | --- |
| Laptop CPU | no RPC, no accelerator offload | Laptop computes model locally |
| Phone RPC only | RPC0, all layers offloaded | Phone model computation, laptop tokenization/sampling/coordinator; not an independent Android baseline |
| Laptop CPU + phone | RPC0, eight layers offloaded | Candidate partial model-layer split; remaining layers should compute on laptop CPU |

Each run has a 16-token warmup then two uncached 64-token completions. The real native timing/counts and generated text are saved. Process-start-to-ready time includes engine startup and the health-poll interval; it is not isolated disk-loading time. Local/remote RSS and system available memory are sampled. Missing values stay null. The run stops if observed laptop free RAM drops below max(4 GiB, 20% physical RAM), phone available RAM below 2 GiB, or the phone connection fails during offloaded computation. These are observed reserves, not OS-enforced hard memory limits. Keep other applications idle and stop if the phone overheats.

The laptop tunnel counts application payload bytes in each direction, connections and transport interruptions (not Ethernet/Wi-Fi/TLS overhead). EOF from the remote and socket errors increment interruptions; deliberate teardown may also do so. The phone reports RPC graph log events when the installed build actually emits them. Missing debug output is not evidence of zero work.

Inspect evidence and the logs under `data/*-distributed-*/`. A partial split, a nonzero local CPU model buffer, completed generation, bidirectional traffic and remote graph-event increase are collected for review. A successful connection or two standalone instances does not satisfy this test. The report deliberately keeps `model_parallel_verified=false` until human hardware verification; do not advertise pooled capacity from the inventory total. `GGML_RPC_DEBUG=3` is set; if this build suppresses worker debug records, preserve the logs and investigate verbosity before judging participation.

Compare prompt and generation timing across the three runs without adding their tokens/sec. The combined run may be slower. This prototype does not enforce a common hard memory cap or run a larger-than-laptop capacity experiment; `capacity_expansion.status` remains `not_tested`. Actual usable cluster model capacity remains unknown.

## Security boundary

The desktop UI and local llama-server bind only to 127.0.0.1. The phone's native RPC worker also binds only to 127.0.0.1 on an ephemeral port. Its only LAN entry is the companion's TLS endpoint with certificate pinning, per-session random bearer credentials and explicit phone approval. The authenticated tunnel forwards only to that fixed loopback worker port. No endpoint accepts a shell command, executable path, file path, arbitrary forwarding destination or model download request from another device.

Discovery announcements are unauthenticated hints. They contain only display name, protocol, nonce, port and certificate fingerprint; hardware is read after pairing. Only RFC1918 IPv4 peers are accepted. mDNS was considered; this minimal dependency-free prototype uses nonce-bound UDP broadcast. IPv6, routed discovery, Bluetooth, remote Internet pairing, mutual TLS client certificates, signed companion updates and independent security review are not implemented. Use only a trusted home LAN; do not configure router forwarding. Do not expose native llama.cpp RPC directly to any LAN or the Internet.

## Reports and limitations

Connection reports: `data/connections/*.json`. Inference experiments: `data/*-distributed-*/distributed.json` plus three engine logs. Connect Devices has a separate evidence journal and JSON export; no distributed experiment becomes a single-device model recommendation. Saved reports are historical and never prove that a worker is currently connected. `connection.schema.json` describes their envelope. Pairing codes, bearer credentials and private keys are excluded from reports/export. Clean source archives exclude runtime `data/`.

Implemented: discovery, explicit pairing, pinned TLS, status, memory reporting, echo benchmark, fixed RPC tunnel, backend abstraction, experimental runner and UI. Locally tested: transport/policy tests, authenticated desktop routes, frontend workflows and production build. Hardware pending: OPPO compilation/runtime, actual Wi-Fi discovery behavior, phone-only timings, shared inference completion, participation proof, thermal/background stability and capacity expansion. See `DISTRIBUTED-RESEARCH.md` for verified upstream findings.

### Missing OpenSSL command on Termux

If startup reports `FileNotFoundError: openssl`, run `pkg install -y openssl-tool`, then `openssl version`, and retry the companion command. Termux packages its command-line executable separately from the OpenSSL libraries. The worker does not need rebuilding. Do not rerun termux-setup-storage if shared storage already works.

### Matching Windows prebuilt engine verified

Official release b11963 matches the pinned source commit and includes ggml-rpc.dll. The CPU x64 archive can be obtained from https://github.com/ggml-org/llama.cpp/releases/tag/b11963; extract it with its DLLs together and verify the asset digest against the GitHub release API. Its llama-server --version must report commit 39febd2ad. The manual Windows compiler build above is an alternative. The desktop relay now uses bounded nonblocking duplex transfer; hardware revalidation with the practical model remains pending after the first failed upload attempt.
