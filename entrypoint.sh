#!/bin/env bash
set -euo pipefail

python3 ./parse_appenv.py "$@" >.appenv

# This service does not have a REST API
# We use the scaffolding for convenience,
# but don't bind to a port
exec uvicorn \
    --uds /run/tilt_dummy.sock \
    --factory \
    brewblox_tilt.app_factory:create_app
