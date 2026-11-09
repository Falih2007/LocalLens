# Distributed compute investigation

Investigated 28 October 2026. These are source findings and prototype status, not hardware benchmark results. Exact snapshots inspected:

| Repository | Commit | License |
| --- | --- | --- |
| Current Exo | `bc412e2230f395e652c23426a5eb88dfa515769b` | Apache-2.0 |
| Archived ex-exo | `d1c106521467a6628a45b45b34cedd4c391f43fb` | GPL-3.0 |
| llama.cpp | `39febd2adb947b70da35e95f9351b3bf58ad170a` | MIT |

## Backend decision

Current Exo's [platform matrix](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/PLATFORMS.md) maintains Apple Silicon macOS. Linux support is planned in that matrix, and Windows CPU/CUDA are longer-term items. Android is not a listed supported platform. Its [README](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/README.md) describes MLX, topology-aware placement and tensor parallelism. Those claims do not establish an Intel Windows laptop plus an OPPO as a supported cluster.

The current [Rust discovery implementation](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/rust/networking/src/discovery.rs) uses its own IPv6 multicast hello/reply exchange, nonces and interface watching; this is not generic Bluetooth pairing or a guarantee of mDNS compatibility. Zenoh provides distributed messaging. Model placement and shard metadata are represented in [placement.py](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/src/exo/master/placement.py) and [shards.py](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/src/exo/shared/types/worker/shards.py). [Download utilities](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/src/exo/download/download_utils.py) select/cache the files needed for shards. This is a distributed runtime to reuse on its supported platforms, not a small discovery library that makes unrelated runtimes compatible.

Archived Exo's [README](https://github.com/exo-explore/ex-exo/blob/d1c106521467a6628a45b45b34cedd4c391f43fb/README.md) mentions Android and heterogeneous hardware, but documentation claims are insufficient evidence of the requested combination. Its default partitioner assigns layer ranges around a memory-weighted ring; peers pass intermediate work, rather than running two independent chats. [UDP discovery](https://github.com/exo-explore/ex-exo/blob/d1c106521467a6628a45b45b34cedd4c391f43fb/exo/networking/udp/udp_discovery.py) advertises node IDs, gRPC ports and capabilities and performs peer health checks. [Shard downloading](https://github.com/exo-explore/ex-exo/blob/d1c106521467a6628a45b45b34cedd4c391f43fb/exo/download/new_shard_download.py) uses the Hugging Face repository/file/shard layer. Its [setup](https://github.com/exo-explore/ex-exo/blob/d1c106521467a6628a45b45b34cedd4c391f43fb/setup.py) pins a substantial Python/native dependency stack, including tinygrad, grpcio, OpenCV and uvloop. There is a Windows extra, but that is not successful Windows validation. The inspected source tree contains no dedicated Android application or ready-to-run Termux companion. Generic CPU code might be adaptable; no verified reusable Android worker has been found or imported.

llama.cpp provides an official [Termux/Android build path](https://github.com/ggml-org/llama.cpp/blob/39febd2adb947b70da35e95f9351b3bf58ad170a/docs/android.md). Its [RPC backend](https://github.com/ggml-org/llama.cpp/blob/39febd2adb947b70da35e95f9351b3bf58ad170a/tools/rpc/README.md) exposes remote ggml devices, including CPU when no accelerator exists. The main host can keep model computation local while offloading other layers. Weights and context buffers have per-device placement; runtime/activation traffic still costs time and memory. The model file remains on the coordinator; tensors are transferred through RPC. This makes it a more direct experimental candidate for Windows CPU ↔ Android CPU than current Exo. It does not prove the OPPO build will work or improve speed.

The first experiment intentionally uses a partial `-ngl` offload to `RPC0`, leaving remaining layers on laptop CPU. It avoids assuming Android Vulkan, Windows Arc RPC capability or Intel NPU interoperability. Both builds must come from the same pinned source revision; RPC wire protocols evolve. Raw RPC is explicitly described upstream as fragile and insecure. Our companion wraps only a fixed loopback worker in pinned TLS and requires approval before a credential can use it.

## Reuse and licensing

Verified license texts: [current Exo Apache-2.0](https://github.com/exo-explore/exo/blob/bc412e2230f395e652c23426a5eb88dfa515769b/LICENSE), [archived Exo GPL-3.0](https://github.com/exo-explore/ex-exo/blob/d1c106521467a6628a45b45b34cedd4c391f43fb/LICENSE), [llama.cpp MIT](https://github.com/ggml-org/llama.cpp/blob/39febd2adb947b70da35e95f9351b3bf58ad170a/LICENSE). They permit reuse subject to their terms; they are not interchangeable licenses. Apache requires the applicable license/notices and modification notices; MIT requires preservation of its notice; distributing GPL-derived work carries GPL source/license obligations. No Exo source has been copied into LocalLens. The new transport, planner and adapter code is project code invoking an independently built llama.cpp executable. Engine and model redistribution must retain their respective licenses. The source package does not bundle any new inference binary or model.

## Architecture shipped in this iteration

`connectnet.py`: nonce-bound IPv4 UDP discovery and exact pinned-certificate TLS requests. mDNS was considered, but custom UDP avoids a new Python service/dependency for this first prototype. This protocol discovers only our companion, not arbitrary Exo/mDNS devices.

`companion.py`: OS-reported physical/available RAM with swap separate; CPU/OS metadata; runtime status; phone-side approval; session bearer authentication; revocation; fixed native-RPC forwarding. The private experiment used a pinned Termux worker build. No command execution or arbitrary destination forwarding is accepted over the network.

`cluster.py`: backend interface with explicit Exo-unsupported and llama-RPC-experimental adapters, discovered/paired/stale state, connection benchmark, memory inventory and local-only tunnel. Unknown pooled capacity remains null.

`distributed.py`: sequential same-hash experiment runner, native prompt/generation timings and generated text, loading observation, local/remote memory samples, tunnel counters, conservative participation evidence and saved failure records. The experimental UI integrates those reports without promoting them to current single-device recommendations.

## Milestone verification

| Milestone | Implemented | Actually tested | Pending or blocked |
| --- | --- | --- | --- |
| A: research | Source/commit/license review and adapter selection | Official docs and source inspected | No supported Exo path established for these devices |
| B: discovery/pairing | UDP discovery; fingerprint check; phone approval; encrypted authenticated control | Real local TLS sockets, approval/rejection, revocation, transfer, policy and desktop API tests | Actual home-router/OPPO discovery and Android multicast/broadcast restrictions |
| C: Android worker | Companion source and pinned Termux build script | Memory parser excludes swap; Python protocol tests | No OPPO hardware session; no Android binary compiled here |
| D: shared inference | RPC tunnel and partial-offload experiment runner | Byte-relay fixture and conservative evidence-parser tests | No actual shared-model generation; matching native RPC builds and phone execution required |
| E: comparison | Real timing/memory/network collection paths and journal | TLS echo benchmark exercised inside isolated tests | No laptop/phone combined benchmark numbers or capacity-expansion result |

The local machine has Git, but CMake and ADB were not available on PATH during investigation. No toolchain or phone was silently installed. The user chose phone testing later. The exact next experiment is documented in `CONNECT-DEVICES.md`; source setup and real hardware tests are separate steps.

The old Exo Android claim, detected hardware, a paired companion and bytes flowing through a test fixture are each insufficient to announce successful distributed inference. Current report state is deliberately **hardware verification pending**. The larger-model capacity experiment is also not implemented/executed; no combined-40-GB promise or additive tokens/sec estimate is made.
