# Device pairing update

Native Kotlin Android pairing preview and Windows mDNS discovery are now included. Open **Devices**, then **Android app** to download the debug APK, or use `android/LocalLens-Companion-debug.apk` directly. Installation and honest scope: [Android guide](android/companion/README.md), [architecture](DEVICES-ARCHITECTURE.md). The native APK supports pairing and device inventory; native compute remains unavailable. Phone compute is disabled in this source preview. Desktop benchmarking remains available. Historical research notes describe earlier experiments.

---

# LocalLens — Windows local AI benchmark preview

A clean desktop MVP with actual Windows hardware detection, conservative memory-fit estimates, real llama-bench runs, local evidence and an optional Intel NPU runtime probe. Python standard library backend; the bundled frontend uses React, shadcn/ui and Tailwind. No accounts, analytics or CDN assets. The optional automatic scan downloads only its pinned engine and test models.

## Run from source

Install a Node.js version compatible with the [frontend requirements](FRONTEND.md).
From the repository root, run:

```powershell
cd frontend
npm ci
npm run build
cd ..
```

Then launch LocalLens as described below. For native phone pairing, run
`Setup-Devices.cmd` to install discovery support and build the APK using the
[Android guide](android/companion/README.md).

## Start LocalLens

1. Install **Python 3.11 or newer** from https://www.python.org/downloads/windows/ (include the Python launcher).
2. Double-click **Start-LocalLens.cmd**. Edge opens in an app-style desktop window. Keep the launcher running. Close it with Ctrl+C when finished. Closing the Edge window alone does not stop the backend. If the launcher is unavailable, open a terminal in this folder and run `python app.py`.

The application listens only on a randomly assigned `127.0.0.1` port. If Edge is missing, it opens your default browser. There is no installer or bundled Python runtime in this preview. You can also run `python app.py --no-window` and open the printed address yourself. Launch only one instance against a given data directory.

## One click: find a comfortable model

Click **Find my best model** in the automatic test card. No file paths or engine setup are needed. The app checks memory, downloads and verifies a pinned official llama.cpp engine, tests real model generation on GPU and CPU, and reports the fastest comfortable backend. Quick mode starts with Qwen3 4B when memory permits, then tries 1.7B or 0.6B if necessary. Enable **Also test 8B** for a broader scan with a larger initial download. This is the best comfortable fit among that scan's candidates, not a universal model-quality ranking.

The card shows the initial and worst-case download sizes before starting. Quick mode can download up to about **5.01 GB** in total; the broader scan up to **10.04 GB**. Candidates are tested one at a time so disk space is reused. The first 4B download is about 2.50 GB; 8B is about 5.03 GB. Slow connections may take a long time. Downloads run in the background with byte/percentage progress and a Stop test button.

If the exact supported Qwen3 4B artifact is already installed in the usual Ollama cache, LocalLens verifies its SHA-256 and makes a temporary copy instead of redownloading it. **Your installed original is never changed or deleted.** The pinned original is read-only to this code. Other models/files are not searched or modified.

Each backend gets one 16-token warmup and two real, uncached **128-token** completions at **4096-token context capacity**, temperature 0 and seed 42. A fixed beginner-friendly laptop-AI prompt is shown with the generated samples in the evidence. Thinking is disabled through the Qwen prompt format. EOS stopping is disabled to keep the token workload fixed; samples may continue past a natural answer boundary. The displayed tok/s is native generation throughput, not total request time or time to first token. Both measured runs must reach **15 tok/s**, with at least **4 GiB or 20% of total RAM (whichever is greater)** kept free. A memory guard stops tests that cross that reserve. GPU offload must be confirmed in the engine log; GPU allocation failures remain explicit and CPU is tested separately.

After the scan, cancellation or a handled error, its **temporary models and engine are deleted**. Only small JSON reports, generated text and logs remain. Cleanup errors are shown honestly, with the leftover scratch path. Marked temporary folders from a process that crashed are recovered on the next launch when the previous process is no longer alive. An operating-system crash can prevent immediate cleanup; files cannot be removed while Windows is unavailable.

The model catalogue is intentionally small: official Qwen3 0.6B / 1.7B Q8_0 and 4B / 8B Q4_K_M GGUFs. All are Apache-2.0. Source revisions, sizes and SHA-256 values are pinned in `models.json`. `autotest.py` owns downloads, prompt tests and recommendation policy. Automatic scan reports are stored separately as `data/<id>/scan.json` and follow `scan.schema.json`. Export includes them under `automatic_scans` alongside manual benchmark `results`. Manual llama-bench results and real-prompt scan measurements are different protocols and should not be compared as equivalent scores.

## Advanced: run your own llama-bench test

1. Get a Windows x64 build from the official llama.cpp releases: https://github.com/ggml-org/llama.cpp/releases . Extract the **whole archive**, keeping DLLs beside llama-bench.exe. CPU builds work for CPU; Vulkan is appropriate for many Intel/AMD/NVIDIA GPUs; CUDA requires compatible NVIDIA hardware/drivers. Choose the build appropriate to your machine. Validation used **b11900 Vulkan x64**.
2. Obtain a GGUF model you have permission to use. For a small integration smoke test, the official ggml-org test model is https://huggingface.co/ggml-org/models-moved/blob/main/tinyllamas/stories15M-q4_0.gguf (about 19 MB). This tiny test model is **not a useful assistant or a representative large-model performance test**. Model licenses are separate from this app.
3. Paste full paths to **llama-bench.exe** and the **.gguf file** in the Benchmark form. File paths stay on this PC. Select CPU or GPU, choose threads and start.
4. The run uses 128 prompt tokens, 32 generated tokens and three repetitions, with the engine's default warmup. CPU requests zero offloaded layers and disables KV offload. GPU requests 99 layers; actual offload may be partial. A verbose log must confirm at least one layer offloaded, in addition to GPU JSON metadata, before a GPU result is saved.
5. Successful measurements appear in the journal. Inspect the evidence or use Export results for JSON. Cancellation, timeout, missing files and malformed output never create a score. GPU fallback without evidence is reported as a failure. Older engines with different flags/log formats may be rejected; use the validated build first.

The model executes real work. Loading larger models can take several minutes. The app enforces a 30 minute timeout; Cancel stops the directly launched benchmark process. Save other work and avoid parallel workloads when you want reproducible comparisons. The benchmark excludes tokenization and sampling time; its generation throughput is not end-to-end chat latency.

## Hardware and advisor

Windows CIM reads CPU name, logical processor count, total/free RAM and GPU adapter names/driver versions. PnP detects potential NPU device names; that alone does **not** prove usable inference support. Driver/runtime enumeration is a separate check. Memory is refreshed on request and at the start of each run.

WMI AdapterRAM is deliberately not used for GPU capacity because it can be misleading, especially with shared Intel Arc memory. The advisor estimates **CPU system-memory fit**, not GPU fit, model quality or speed. It uses roughly 0.60 bytes per parameter for Q4-class weights, adds 15% runtime overhead and 2 GiB workspace/context, and applies a 20% margin for “Likely fits.” Context, architecture, quantization and other workloads can change the requirement substantially. A listed model is never marked tested merely because a different GGUF was benchmarked.

## Intel NPU adapter — honest scope

`openvino_adapter.py` is an isolated capability probe and a machine-readable adapter contract. The UI reports `unavailable` if OpenVINO is missing or no NPU is exposed, and lists devices/versions when available. **NPU benchmarking is not implemented in this release.** No NPU score or CPU fallback is fabricated.

To experiment with detection, optionally install compatible `openvino` and `openvino-genai` packages into the same Python environment and use Intel's supported NPU driver. This is not required for the rest of the app. GGUF files cannot be passed directly to OpenVINO GenAI; an appropriately exported, supported IR model plus tokenizer is required.

The future execution contract is NPU-only LLMPipeline compilation, a warmup and three measured iterations with fixed prompt/token count, and native perf_metrics throughput/TTFT/generated-token counts. Compilation or architecture failures must remain explicit unsupported results. Reference: https://github.com/openvinotoolkit/openvino.genai/blob/master/samples/python/text_generation/benchmark_genai.py . This is a separate protocol and must not be represented as directly equivalent to llama-bench.

## Local data and schema

Each attempt has a folder under `data/<UTC timestamp>-<id>/`:

- `job.json`: outcome and diagnostic message for success/failure/cancellation.
- `stdout.json` and `stderr.log`: untouched engine output (when the process started).
- `result.json`: **successful measured runs only**, written atomically.

`result.schema.json` defines a single successful result. Export wraps results in `{ "schema_version": "1.0", "results": [...] }`. Records include model path, size and modification timestamp; hardware snapshot; exact command; UTC timestamps; native engine rows including build information; and normalized prompt/generation metrics. Model identity uses path/size/mtime, not a content hash. The same protocol and model file should be used for comparisons.

Set `LOCALLENS_DATA` to an alternate folder before launching if desired. Logs and exported results contain local paths and hardware details; review them before sharing. The automatic scan contacts GitHub and Hugging Face for public downloads (those services receive normal network request metadata). Prompts, model outputs and hardware results stay on your PC. Static UI is served only from an allowlist; API calls require a per-launch token and exact localhost Host header. Engine execution uses argument arrays, without a shell. Only select trusted engine executables: a benchmark engine is native code running with your user permissions. This prototype is not a sandbox for untrusted binaries/models.

## Development and tests

```
python -m unittest discover -s tests -v
python -m py_compile app.py openvino_adapter.py
node --check ui/app.js
node tests/test_journal.cjs
```

Node is only needed for the optional JavaScript syntax check. Tests use temporary directories and synthetic parser inputs; they do not create fake journal entries. See TESTING.md for actual hardware/engine verification and remaining limitations.

Frontend development: see FRONTEND.md. The normal launcher uses the bundled production build; Node.js is only needed for frontend development.

Project map: `app.py` (Windows probe, advisor, subprocess runner, local HTTP/API, persistence); `autotest.py` and `models.json` (one-click scan); `ui/` (accessible HTML, CSS, JavaScript); `openvino_adapter.py` (optional runtime probe); `tests/` (core regression checks). The interface uses locally bundled Geist typography, responsive cards, reduced-motion support and an animated run indicator. No remote fonts or CDN UI assets.

## MVP boundaries

This is a source-based Edge desktop-window prototype, not a packaged Tauri/Electron installer. No distributed inference, cloud sharing, quality leaderboard, NPU execution, live per-token progress or guaranteed GPU memory fit is included. Automatic setup downloads only the curated test catalogue. During a benchmark the UI shows truthful loading/running state; llama-bench does not provide reliable percentage progress. Advanced device selection is deferred; the engine chooses its default device(s).

The Benchmark journal combines completed automatic prompt-test attempts and manual llama-bench results, newest first. Each card labels its protocol; recommended automatic results are highlighted. Deleting a temporary model does not remove its saved test record.

The primary UI is now React + Vite with official shadcn/ui components, a neutral light/dark/system theme and locally bundled Geist typography. The Python API, benchmark engine integration and saved result formats are unchanged. Set `LOCALLENS_LEGACY_UI=1` before launching to use the preserved vanilla fallback.

## Portability audit

Hardware readings and benchmark timings come from the current machine and engine output. The model catalogue, prompt, token counts and comfort thresholds are fixed test settings, not measured scores. Recommendations are limited to the catalogue and selected scan mode.

Use `python package_project.py` to create a clean archive. Runtime `data/` is excluded by default; existing local reports remain untouched. Test fixtures are separate and never seed the live journal. New reports contain a hashed Windows device identifier (never the raw identifier). Only reports identified as belonging to this computer can supply its recommendation. Copied reports remain visible as Other computer; older reports without identity show Device unverified and require a new scan for a current recommendation.

The automatic engine download targets Windows x64. Python 3.11+, internet access, adequate free disk/RAM and compatible drivers are required. GPU support depends on the driver; CPU can be tested separately. NPU execution remains unavailable. Another physical laptop has not been tested: alternate memory/device identities and a clean archive are verified through regression tests.

## Connect Devices prototype

The primary frontend now includes Connect Devices. Read CONNECT-DEVICES.md for companion/build setup and DISTRIBUTED-RESEARCH.md for compatibility, security and milestone status. cluster.py, connectnet.py, companion.py and distributed.py add separate authenticated LAN transport and experimental inference workflows. Existing single-device protocols and recommendations are unchanged. Never equate discovery, pairing or a transport fixture with proven shared-model inference. Phone hardware testing remains pending; all virtual RAM is excluded from physical capacity. Run the complete Python and frontend suites after changes. Do not package runtime reports, keys or pairing credentials.
