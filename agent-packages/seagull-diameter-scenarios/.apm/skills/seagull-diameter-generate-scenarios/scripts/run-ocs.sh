#!/bin/sh
# Runs one generated client scenario against an OCS, in the Seagull image. No stub starts.
# Usage: sh run-ocs.sh OUTPUT_DIR IMAGE SCENARIO HOST:PORT [LOGS_DIR]
# OUTPUT_DIR is the folder that generate_scenarios.py wrote. SCENARIO is the client file without .client.xml. The
# client runs with a copy of config/conf.client.xml whose dest is HOST:PORT; OUTPUT_DIR is mounted read-only. With
# LOGS_DIR, the Seagull logs are copied there. The script exits with a non-zero status unless the scenario ends with
# at least 1 successful call and 0 failed calls.
set -eu

if [ $# -lt 4 ]; then
    echo "Usage: sh run-ocs.sh OUTPUT_DIR IMAGE SCENARIO HOST:PORT [LOGS_DIR]" >&2
    exit 2
fi

output=$(cd "$1" && pwd)
image="$2"
scenario="$3"
dest="$4"
here=$(cd "$(dirname "$0")" && pwd)

if [ $# -ge 5 ]; then
    mkdir -p "$5"
    logs=$(cd "$5" && pwd)
    docker run --rm \
        --volume "${output}:/work:ro" \
        --volume "${here}:/skill:ro" \
        --volume "${logs}:/logs" \
        "${image}" sh /skill/in-container-ocs.sh "${scenario}" "${dest}"
else
    docker run --rm \
        --volume "${output}:/work:ro" \
        --volume "${here}:/skill:ro" \
        "${image}" sh /skill/in-container-ocs.sh "${scenario}" "${dest}"
fi
