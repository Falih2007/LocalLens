# Validation record — 26 October 2026

## Verified on this Windows PC

- Intel Core Ultra 7 155H, 22 logical processors, 31.43 GiB RAM.
- Intel Arc integrated graphics, driver 32.0.101.8724.
- Intel AI Boost detected by PnP. OpenVINO probe returned `unavailable: No module named 'openvino'`. No NPU inference was claimed or run.
- Python 3.11; Python launcher present. App server started on loopback and Edge app window appeared in the Windows window inventory.

## Real benchmark integration (final source)

Official llama.cpp **b11900 Windows Vulkan x64**, official ggml-org `stories15M-q4_0.gguf`, four CPU threads, 128 prompt tokens / 32 generated tokens, three repetitions. These are tiny-model integration smoke tests, not usable-model rankings or predictions for larger LLMs.

| Requested target | Prompt tok/s (mean ± engine SD) | Generation tok/s (mean ± engine SD) | Evidence |
|---|---:|---:|---|
| CPU, zero GPU layers, KV offload disabled | 4529.52 ± 496.32 | 2302.33 ± 631.26 | `data/20261026T142138-dd4378bb/` |
| GPU, 99 layers requested | 25654.84 ± 4779.34 | 781.66 ± 63.36 | `data/20261026T142143-87fa5c52/` |

GPU verbose log confirms `offloaded 7/7 layers to GPU` and Vulkan0 model/KV/compute buffers. The CPU test uses a Vulkan-capable build, so JSON's `backends: Vulkan` describes available build support, not CPU offload. Its command explicitly sets `-ngl 0 -nkvo 1`. Model loading, dispatch overhead and noise dominate this tiny workload; these measurements do not imply that one processor is generally faster.

Both runs went through the actual local HTTP API and production worker. Successful records include the hardware snapshot, exact command, native rows/build metadata and untouched stdout/stderr. Engine/model downloads were used in the workspace for testing and are not bundled in the source ZIP; their original test paths remain in the evidence. Follow README to select your own downloaded assets. Earlier development runs were archived outside the deliverable so the journal contains only final-protocol results.

## Checks passed

- Seven automated tests: advisor unknown-memory behavior and fit boundaries; invalid/non-finite/non-positive throughput rejection; both prompt/generation rows required; GPU metadata without device evidence rejected; missing engine creates no result; HTTP static assets and valid token work while missing/wrong tokens and hostile Host are forbidden.
- Live API test: nonexistent executable -> failed job and unchanged measured-result count.
- Live API test: cancellation -> cancelled job and unchanged measured-result count.
- Existing successful result records parse and contain positive measured throughput for both tests.
- Python compilation and JavaScript syntax checks pass.
- Actual local hardware API and optional OpenVINO subprocess probe return usable JSON.

## Not verified / limitations

A follow-up UI review succeeded in a normal Edge window after the original app-style window could not expose a verifiable URL. Hardware and advisor content were inspected through accessibility text. Screenshots verified the card layout, spacing and journal at desktop and narrow window widths. Overview navigation worked. The NPU Check runtime button displayed `UNAVAILABLE: No module named 'openvino' Devices: none. NPU benchmarking is not implemented in this MVP.`

The Export results button downloaded `locallens-results.json`; the actual downloaded file parsed successfully and contained two measured records with schema version 1.0. Engine-path entry was also verified. A complete benchmark run initiated by clicking the UI, model-path entry, keyboard-only navigation and live running-state animation were not completed before the window was minimized and testing was interrupted. CPU/GPU execution, cancellation and failures were already verified through the production HTTP API.

NPU execution is deliberately not implemented. Only this Intel Arc/Vulkan machine and this small model were used for real inference verification. CUDA, other GPUs, large models, other Windows versions and installer distribution remain untested. Test speed varies with current workload and power/thermal state; run on AC power under consistent conditions for useful comparisons.

## Manual acceptance checklist

1. Launch Start-LocalLens.cmd; confirm CPU, RAM, Intel Arc and Intel AI Boost on the dashboard.
2. Confirm every advisor card says Estimated, with no speed prediction.
3. Enter valid engine/model paths; run CPU then GPU. Confirm running state, separate measured prompt/generation rows and inspectable evidence.
4. Enter a missing file, or cancel a run; verify no extra journal result appears.
5. Check runtime with OpenVINO absent; confirm unavailable and no NPU score.
6. Export results, parse the downloaded JSON and compare IDs/metrics with local result.json files.
7. Resize the window and use Tab navigation; inspect narrow layouts and focus indicators.


## One-click scan update — 28 October 2026 (Dubai time)

Implemented and exercised the production automatic API, download verification, prompt execution, recommendation and cleanup flow. Final successful report: `data/20261027T215817-scan-c28b2251/scan.json` (UTC folder timestamp).

- Downloaded the official b11900 Vulkan engine archive and validated its pinned size and SHA-256.
- Found the exact supported existing Ollama Qwen3 4B Q4_K_M artifact. Verified SHA-256, made a temporary copy and verified the copy again before execution. This avoids an unnecessary model download; no existing user model was modified.
- Sent the documented real laptop-AI prompt through llama-server. One 16-token warmup and two uncached 128-token completions per backend, 4096-token context, temperature 0, seed 42. Actual generated text, native timings and whole-request durations are retained.
- Intel Arc GPU: **19.46 tok/s average**, **18.57 tok/s slowest run**, **13.21 GiB minimum free RAM**. Engine log confirms **37/37 layers offloaded**. This passes the explicit 15 tok/s and 6.29 GiB memory-reserve thresholds.
- CPU: **9.80 tok/s average**, **13.79 GiB minimum free RAM**. Below the speed threshold, so CPU was not recommended.
- Quick mode correctly recommended **Qwen3 4B Q4_K_M on GPU**. It does not claim 8B is unsuitable; 8B was excluded from this quick scan.
- Verified `cleanup.status = deleted`, confirmed the scratch directory was empty, and independently rehashed the original installed model afterward: unchanged.
- Full remote model download was not completed on this slow connection. An 8B model download was cancelled after receiving real data; its partial model and engine were removed. The successful scan used a complete, checksum-verified engine download and a checksum-verified existing model copy. A fresh machine uses the same verified download function for its model; large-model transfer completion remains untested here.
- The earlier default server logging omitted offload details; explicit verbose logging fixed the evidence check. No GPU score was accepted without an offload log.
- Visually checked the new automatic card, running state and final recommendation in Edge. Clicked the actual Start button, observed download progress and an enabled Stop test button, then clicked Stop. The resulting report was cancelled with no new recommendation, and the temporary folder was empty afterward. Development cancellation reports were archived outside the deliverable to keep the delivered journal focused on final measured evidence.
- **14 automated tests pass**, including recommendation thresholds, unknown telemetry rejection, invalid/native-timing rejection, SHA mismatch rejection, ZIP traversal rejection, refusal to delete unowned files, and recovery that removes dead-process scratch while preserving an active-process scratch folder. Python compilation and JavaScript syntax checks pass. The successful scan record validates against `scan.schema.json`.

Known limits: the 8B inference path, other catalogue sizes, other GPUs and slower-connection recovery were not fully exercised. The memory guard is conservative system-RAM telemetry; dedicated VRAM headroom is not measured separately. Prompt samples measure a short fixed workload, not quality or a guarantee of long-context performance. Quick mode is the largest passing candidate up to 4B in this catalogue. Broader mode includes 8B and displays its larger download budget before starting.


## Journal visibility fix

Fixed a frontend omission where Results listed manual llama-bench records but not saved automatic prompt tests. The journal now merges completed automatic attempts with manual records, sorts them newest first, labels the protocol, shows CPU/GPU separately and highlights the recommended backend. The underlying measurements and export formats are unchanged; no model rerun was needed for this fix.

A JavaScript regression test evaluates the production journal view against fixtures copied from actual saved results. It checks both Qwen3 4B records (19.46 GPU / 9.80 CPU tok/s), recommendation labeling, sorting, retention after temporary-file deletion, protocol distinctions, exclusion of failed/missing-speed attempts, escaping and empty state. Fixtures are separate from the app journal. Run `node tests/test_journal.cjs`.

Verified in the running Edge window: Results now shows the latest user scan's Qwen3 4B GPU result at 23.42 tok/s and CPU result at 11.41 tok/s, followed by the earlier 19.46 / 9.80 measurements and then the tiny manual smoke tests. The latest GPU card is marked MEASURED / RECOMMENDED. These are separate repeated runs; the original figures were not changed.


## shadcn/ui migration verification — 28 October 2026

The user approved a React + Vite migration of the frontend. Python inference, automatic scan selection, download/cleanup behavior, result schemas and `/api/*` contracts were retained. Static delivery now prefers the compiled UI and serves only checked local asset paths. The original UI is still available as a fallback.

Resolved toolchain: React 19.3.1, Vite 8.3.5, TypeScript 7.0.2, Tailwind 4.3.3, shadcn CLI 4.23.0, Base UI 1.9.0, Lucide React 1.62.0 and Geist Variable 5.3.0. npm lockfile committed. Official Nova components were installed with the CLI, inspected, and their shared utility imports normalized. Card titles use semantic h2 elements. No second UI kit or runtime chart dependency was added.

### Automated checks
- `npm run build`: TypeScript and production build pass. Secondary pages are split into separate chunks; there is no oversized-chunk warning in the final build.
- `npm test`: **12 frontend tests pass** across real saved-result merging/sorting, failed-score exclusion, method filters, evidence selection and the actual dialog, quick/broader scan callbacks, progress and stop state, original manual payloads, NPU unavailable reporting, theme state, form drafts across navigation, a single main landmark, and skip-to-content preserving the current route.
- Python suite: **15 tests pass**, including local-session token injection, production asset MIME/content access, encoded path-traversal rejection and all existing download/cleanup/score validation regressions.
- Legacy journal JavaScript regression still passes. Saved 4B GPU/CPU results and the tiny manual smoke tests remain intact.
- `npm ls --depth=0`: resolved dependencies without conflicts. Runtime dependency audit (`npm audit --omit=dev`) reports **0 vulnerabilities** at verification time.
- Production HTTP checks: compiled JS/CSS and favicon return 200 with appropriate MIME types; `/api/state` authenticates using the same injected token and returns the original keys, two manual records and two automatic scan records. No new model run was required.

### Actual visual and interaction review

Inspected the live Vite development server in Edge, then the standalone production build served by Python. Saw the actual rendered dashboard in desktop light and dark themes; inspected a narrow window with stacked cards and a horizontally contained journal table. Opened the official mobile navigation Sheet, saw its final rendered contents, selected Overview and verified that the page changed and the Sheet closed. Viewed the unified journal with the real 23.42 / 11.41 and 19.46 / 9.80 tok/s 4B records. Opened saved evidence in the actual Dialog, saw raw model/hardware/settings content, and closed it with Escape. Tightened table wrapping so all desktop columns are visible. The production build renders correctly without the Vite server.

This is a selected native-browser visual/interaction review, not an exhaustive browser/viewport matrix or automated browser-console audit. No claim is made that every browser, OS or viewport was tested. Full model execution was not repeated for a design-only migration; its existing evidence and backend regression checks were preserved.

### Codex integration

The official shadcn skill was installed. Exactly one new shadcn MCP entry was added to existing Codex settings; existing entries were preserved and a backup saved beside the settings. Its registry cwd points to this frontend. A direct protocol test initialized the official server, listed seven tools and successfully searched @shadcn for button components. **Codex must restart to load that entry into the current client's tool list.** The server was validated directly; it was not falsely reported as hot-loaded into this existing chat.

## Portability audit

Hardware readings and benchmark timings come from the current machine and engine output. The model catalogue, prompt, token counts and comfort thresholds are fixed test settings, not measured scores. Recommendations are limited to the catalogue and selected scan mode.

Use `python package_project.py` to create a clean archive. Runtime `data/` is excluded by default; existing local reports remain untouched. Test fixtures are separate and never seed the live journal. New reports contain a hashed Windows device identifier (never the raw identifier). Only reports identified as belonging to this computer can supply its recommendation. Copied reports remain visible as Other computer; older reports without identity show Device unverified and require a new scan for a current recommendation.

The automatic engine download targets Windows x64. Python 3.11+, internet access, adequate free disk/RAM and compatible drivers are required. GPU support depends on the driver; CPU can be tested separately. NPU execution remains unavailable. Another physical laptop has not been tested: alternate memory/device identities and a clean archive are verified through regression tests.

## Connect Devices prototype

The primary frontend now includes Connect Devices. Read CONNECT-DEVICES.md for companion/build setup and DISTRIBUTED-RESEARCH.md for compatibility, security and milestone status. cluster.py, connectnet.py, companion.py and distributed.py add separate authenticated LAN transport and experimental inference workflows. Existing single-device protocols and recommendations are unchanged. Never equate discovery, pairing or a transport fixture with proven shared-model inference. Phone hardware testing remains pending; all virtual RAM is excluded from physical capacity. Run the complete Python and frontend suites after changes. Do not package runtime reports, keys or pairing credentials.

### Connect Devices verification — 28 October 2026

32 Python tests and 16 frontend tests passed; the legacy journal regression and production build passed. Real local TLS tests exercised certificate pin rejection, separate phone approval, rate limiting, expiry, authenticated echo, encrypted forwarding and stream revocation. An isolated byte-echo fixture was used, never an LLM or a live journal seed. The running production UI was inspected at 1280px and its normal narrow viewport. Live Scan nearby returned no companion, as expected without the phone; the setup dialog opened and page width matched viewport width. The Windows system card reports its CIM operating-system caption. No native distributed inference or phone performance result is claimed.

### OPPO discovery fix — 29 October 2026

The actual OPPO companion replied to subnet-directed Wi-Fi discovery while the global broadcast returned nothing. Windows discovery now enumerates private IPv4 adapter addresses/prefixes and sends on each actual subnet, with a general broadcast fallback. No laptop or phone address is hardcoded. All 33 backend tests passed, including a regression using a /28 subnet and a virtual adapter. Android compilation, worker help startup and the pinned revision were confirmed from user screenshots; model-parallel inference is still unverified.

### First actual Windows–OPPO inference — 29 October 2026

Stories15M Q4_0 completed real laptop CPU, phone RPC, and two-layer split runs. Both measured generations completed in each configuration. The split logged 2/7 offloaded layers, a local CPU model buffer, phone graph activity and bidirectional payload transfer. These are tiny-model integration measurements; the split was slower than local CPU and proves no larger-model capacity or practical-model speed improvement. See ../Distributed-Experiment-2026-10-29.md and the local raw report.

### Qwen3 0.6B actual retry — 29 October 2026

After bounded duplex forwarding/TCP_NODELAY changes and 33 passing backend tests, the real partial split completed two measured 64-token generations. Local CPU mean decode was 55.92 tok/s; laptop CPU + OPPO with 2/29 layers offloaded was 1.68 tok/s. Phone graph activity, local model buffer and bidirectional transfer were observed. Phone-only was stopped at the 2 GiB memory reserve; overall three-way status is incomplete, not a failure of the completed partial split. No larger-model capacity or power-efficiency result is claimed. See ../Distributed-Experiment-2026-10-29.md.
