#!/usr/bin/env bash
# AeroFox on an Oracle Cloud "Always Free" VM (Ampere A1 ARM, Ubuntu 22.04/24.04). NOT TESTED by the team yet:
# read it before running it. Builds the same pinned llama.cpp release (b8230) from source and downloads the same
# pinned open-weight model, verified by SHA-256. Run as the normal "ubuntu" user from the repository root:
#     bash deploy/oracle/setup.sh            # 1.5B model (same as the Windows CPU profile)
#     AEROFOX_PROFILE=4b bash deploy/oracle/setup.sh   # Qwen3-4B (same as the Windows GPU profile, runs on CPU here)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PROFILE="${AEROFOX_PROFILE:-1.5b}"

echo "[AeroFox] 1/5 system packages (asks for sudo)"
sudo apt-get update -y
sudo apt-get install -y git build-essential cmake curl python3 python3-venv python3-pip

echo "[AeroFox] 2/5 llama.cpp b8230 from source"
if [ ! -x .runtime/llama.cpp/build/bin/llama-server ]; then
  mkdir -p .runtime
  git clone --depth 1 --branch b8230 https://github.com/ggml-org/llama.cpp .runtime/llama.cpp
  cmake -S .runtime/llama.cpp -B .runtime/llama.cpp/build -DCMAKE_BUILD_TYPE=Release -DLLAMA_CURL=OFF
  cmake --build .runtime/llama.cpp/build --target llama-server -j "$(nproc)"
fi

echo "[AeroFox] 3/5 pinned model weights"
mkdir -p .models
if [ "$PROFILE" = "4b" ]; then
  NAME=Qwen3-4B-Q4_K_M.gguf; ALIAS=aerofox-qwen3-4b; EXTRA="--reasoning-budget 0"
  URL=https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/bc640142c66e1fdd12af0bd68f40445458f3869b/$NAME
  SHA=7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5
else
  NAME=qwen2.5-1.5b-instruct-q4_k_m.gguf; ALIAS=aerofox-qwen-1.5b; EXTRA=""
  URL=https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/91cad51170dc346986eccefdc2dd33a9da36ead9/$NAME
  SHA=6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e
fi
if ! echo "$SHA  .models/$NAME" | sha256sum -c --status 2>/dev/null; then
  curl --fail --location --retry 3 -C - -o ".models/$NAME.part" "$URL"
  echo "$SHA  .models/$NAME.part" | sha256sum -c
  mv ".models/$NAME.part" ".models/$NAME"
fi

echo "[AeroFox] 4/5 Python environment"
python3 scripts/launch.py --setup-only

echo "[AeroFox] 5/5 systemd service (starts at boot, restarts on failure)"
THREADS=$(nproc)
sudo tee /etc/systemd/system/aerofox.service >/dev/null <<UNIT
[Unit]
Description=AeroFox (local open-weight model + web app + tunnel, supervised)
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$ROOT
Environment=PYTHONUTF8=1
Environment=AEROFOX_MODEL=$ALIAS
Environment=AEROFOX_LLM_URL=http://127.0.0.1:8793
Environment="AEROFOX_MODEL_CMD=$ROOT/.runtime/llama.cpp/build/bin/llama-server --model $ROOT/.models/$NAME --host 127.0.0.1 --port 8793 --alias $ALIAS -c 8192 -np 1 -t $THREADS --cache-ram 0 $EXTRA"
ExecStart=$ROOT/.venv/bin/python scripts/supervisor.py --port 8012 --tunnel \${AEROFOX_TUNNEL} --no-browser
Environment=AEROFOX_TUNNEL=tailscale
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
echo
echo "[AeroFox] Installed. Next (see deploy/oracle/README.md):"
echo "  1) curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up && sudo tailscale set --operator=\$USER"
echo "  2) enable Funnel for this machine in the Tailscale admin page when asked"
echo "  3) sudo systemctl enable --now aerofox && journalctl -u aerofox -f"
