#!/bin/sh
# Validates the dictionaries of a folder against their XSD files (needs Java 11 or later).
# Usage: sh validate.sh [--plan] [--xsd-dir DIR] DICTIONARY_DIR
# Without --xsd-dir, each file needs a schema reference of its own that resolves to a file.
# See ValidateDictionaries.java for the order in which the schema of a file is chosen and for the
# exit statuses: 0 all valid, 1 some file invalid, 2 wrong arguments, 3 a schema was not found.
set -eu

here=$(cd "$(dirname "$0")" && pwd)

exec java "${here}/ValidateDictionaries.java" "$@"
