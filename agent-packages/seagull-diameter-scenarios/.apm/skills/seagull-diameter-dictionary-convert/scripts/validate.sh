#!/bin/sh
# Validates the dictionaries of a folder against the XSD files in its xsd subfolder.
# Usage: sh validate.sh DICTIONARY_DIR   (needs Java 11 or later)
# The folder needs xsd/diameter-dictionary.xsd and xsd/diameter-command.xsd.
set -eu

if [ $# -ne 1 ]; then
    echo "Usage: sh validate.sh DICTIONARY_DIR" >&2
    exit 2
fi

here=$(cd "$(dirname "$0")" && pwd)

exec java "${here}/ValidateDictionaries.java" "$1"
