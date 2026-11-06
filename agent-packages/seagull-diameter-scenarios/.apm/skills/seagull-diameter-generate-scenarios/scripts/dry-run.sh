#!/bin/sh
# Dry run of generated scenarios: each client scenario against its stub OCS, in the Seagull image.
# Usage: sh dry-run.sh OUTPUT_DIR [IMAGE]   (default IMAGE: seagull:local)
# OUTPUT_DIR is the folder that generate_scenarios.py wrote. The script exits with a non-zero status unless every
# scenario ends with at least 1 successful call and 0 failed calls.
set -eu

if [ $# -lt 1 ]; then
    echo "Usage: sh dry-run.sh OUTPUT_DIR [IMAGE]" >&2
    exit 2
fi

output=$(cd "$1" && pwd)
image="${2:-seagull:local}"
here=$(cd "$(dirname "$0")" && pwd)

docker run --rm \
    --volume "${output}:/work:ro" \
    --volume "${here}:/skill:ro" \
    "${image}" sh /skill/in-container.sh
