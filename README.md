# LocalLens

Find a local AI model your Windows PC can run comfortably by measuring real CPU and GPU generation speed.

![LocalLens automatic model benchmark page](docs/locallens-preview.png)

## Measured on an Intel Arc laptop

One Windows 11 laptop with an Intel Core Ultra 7 155H, integrated Intel Arc graphics and 32 GB RAM. These are average generation rates from the same automatic scan, using llama.cpp b11900 and two 128-token measurements per backend.

| Model | Intel Arc Vulkan | CPU | Comfort result |
| --- | ---: | ---: | --- |
| Qwen3 4B Q4_K_M | 21.08 tok/s | 9.39 tok/s | Arc passed |
| Qwen3 8B Q4_K_M | 11.48 tok/s | 5.99 tok/s | Both below target |

Arc generated about 2.2 times as fast as the CPU on 4B. The 8B model ran on both backends, but neither reached the 15 tok/s comfort target. These results describe one machine and one workload. [Methodology and measured samples](docs/benchmark-results.md)

## Quick start

1. Install [Python 3.11 or newer](https://www.python.org/downloads/windows/) on Windows x64. Include the Python launcher.
2. Download the Windows preview ZIP from [Releases](https://github.com/Falih2007/LocalLens/releases/tag/v0.2.0-preview.1). Extract it and double-click **Start-LocalLens.cmd**. The ZIP includes the built frontend, so Node.js is only needed for source builds.
3. Select **Find my best model**. The automatic scan downloads verified test files, benchmarks them, saves the measurements locally and cleans up its temporary downloads.

The quick scan can download up to about 5 GB. Close the launcher with **Ctrl+C** when you're done. The app uses a local address and works without an account.

### Run from source

Use Node.js 22.12+ to build the frontend, then launch with Python:

```powershell
cd frontend
npm ci
npm run build
cd ..
python app.py
```

## Scope

- **Benchmarking.** Real CPU and GPU throughput, a memory-fit advisor with labeled estimates, and a local JSON journal. The automatic recommendation is limited to its Qwen3 test catalogue. Manual llama-bench tests use a separate protocol.
- **Intel NPU.** Optional OpenVINO detection. NPU benchmarking is unavailable.
- **Android.** Optional experimental pairing and device inventory. Phone compute is disabled. Use discovery on trusted private Wi-Fi.
- **Privacy.** The server listens on localhost. Benchmarks and generated text stay on your PC. Downloads contact GitHub and Hugging Face. Only run trusted engines and models. LocalLens runs engines with your user permissions.

[Methodology and data](docs/benchmark-methodology.md) | [Development](docs/FRONTEND.md) | [Test evidence](docs/TESTING.md) | [Device pairing](CONNECT-DEVICES.md) | [Preview notes](docs/release-notes.md)
