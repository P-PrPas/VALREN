#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
exec docker run --rm --network none --read-only --memory 256m --memory-swap 256m \
  --user 1000:1000 --entrypoint python \
  -e HERMES_HOME=/tmp/hermes -e VALREN_HOME=/work -e PYTHONPATH=/work/src \
  -e PYTHONDONTWRITEBYTECODE=1 --tmpfs /tmp:size=32m,mode=1777 \
  -v "$PWD:/work:ro" \
  nousresearch/hermes-agent@sha256:d4da4a40cd7a28aba983775d9fd31d94cbf153eeb0cb9e844d6d0f612b7c24db \
  -c 'import os,shutil,runpy; from pathlib import Path; home=Path(os.environ["HERMES_HOME"]); (home/"plugins").mkdir(parents=True); shutil.copy("/work/hermes/config.yaml",home/"config.yaml"); shutil.copytree("/work/hermes/valren_plugin",home/"plugins/valren-research"); runpy.run_path("/work/scripts/check_hermes.py")'
