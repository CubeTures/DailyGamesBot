#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

uv run python3 -m proxy.gen_launcher

MODE_ARGS=()
while IFS=$'\t' read -r port origin; do
  MODE_ARGS+=(--mode "reverse:${origin}@${port}")
done < <(uv run python3 -c "
from proxy.config import GAMES
for port, (name, origin) in sorted(GAMES.items()):
    print(f'{port}\t{origin}')
")

cleanup() {
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT

uv run python3 -m http.server "$(uv run python3 -c 'from proxy.config import LAUNCHER_PORT; print(LAUNCHER_PORT)')" \
  --directory launcher &

uv run mitmdump -s proxy/addon.py "${MODE_ARGS[@]}"
