#!/data/data/com.termux/files/usr/bin/bash
set -eu
# Run on the phone in Termux. This installs build tools; it does not expose RPC.
pkg update
pkg install -y python openssl openssl-tool git cmake clang ninja libandroid-spawn
worker_dir="$HOME/locallens-worker"
if [ -e "$worker_dir" ]; then
  echo "The worker directory already exists. Keep it; follow CONNECT-DEVICES.md to rebuild explicitly."
  exit 1
fi
git clone https://github.com/ggml-org/llama.cpp.git "$worker_dir"
cd "$worker_dir"
git checkout --detach 39febd2adb947b70da35e95f9351b3bf58ad170a
git rev-parse HEAD > locallens-build-revision.txt
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_RPC=ON -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_TESTS=OFF
cmake --build build --target ggml-rpc-server llama-server -j 2
echo "Build finished. Start companion.py as described in CONNECT-DEVICES.md."
