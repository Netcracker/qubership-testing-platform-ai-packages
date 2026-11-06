#!/bin/sh
# Checks that Seagull loads each converted dictionary and completes one Credit-Control
# exchange with it: a stub OCS and a client with invented values, both in the image.
# Usage: sh check-converted.sh CONVERTED_DIR [IMAGE]   (default IMAGE: seagull:local)
# CONVERTED_DIR is the folder that convert_dictionaries.py wrote. The script exits with a
# non-zero status unless every dictionary that defines CCR ends with 1 successful call and
# 0 failed calls. A dictionary without CCR is skipped.
set -eu

if [ $# -lt 1 ]; then
    echo "Usage: sh check-converted.sh CONVERTED_DIR [IMAGE]" >&2
    exit 2
fi

converted=$(cd "$1" && pwd)
image="${2:-seagull:local}"
here=$(cd "$(dirname "$0")" && pwd)

docker run --rm \
    --volume "${converted}:/dictionaries:ro" \
    --volume "${here}/../assets:/assets:ro" \
    --volume "${here}/in-container.sh:/in-container.sh:ro" \
    "${image}" sh /in-container.sh
