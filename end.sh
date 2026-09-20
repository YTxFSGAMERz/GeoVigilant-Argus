#!/usr/bin/env bash
# ==============================================================================
# GeoVigilant Argus Eye — Service Stopper Alias (end.sh -> stop.sh)
# ==============================================================================

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$DIR/stop.sh" "$@"
