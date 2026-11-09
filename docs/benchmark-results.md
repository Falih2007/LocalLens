# Intel Arc versus CPU

Recorded on 1 November 2026 in one thorough automatic scan on a Windows 11 laptop
with a Core Ultra 7 155H, integrated Intel Arc and 32 GB RAM. The engine was
llama.cpp b11900 Vulkan x64. Both models used Q4_K_M quantization. Vulkan
offloaded 37 layers for each model.

| Model | Backend | Run 1 | Run 2 | Mean | Minimum free RAM | Comfortable |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Qwen3 4B | Arc Vulkan | 20.99 | 21.18 | 21.08 | 11.33 GiB | Yes |
| Qwen3 4B | CPU | 9.61 | 9.17 | 9.39 | 12.21 GiB | No |
| Qwen3 8B | Arc Vulkan | 11.37 | 11.60 | 11.48 | 9.60 GiB | No |
| Qwen3 8B | CPU | 5.84 | 6.14 | 5.99 | 10.01 GiB | No |

Throughput is generation tokens per second as reported by the engine. Each backend
ran one 16-token warmup and two uncached 128-token completions with a 4096-token
context capacity, temperature 0 and seed 42. Both completions must reach 15 tok/s
and the run must preserve the configured memory reserve. The 4B Arc run was the
only configuration in this scan to pass. These short runs do not measure output
quality, time to first token, power use or sustained thermal performance.

This table is a summary of measured runs. [See the full protocol](benchmark-methodology.md).
