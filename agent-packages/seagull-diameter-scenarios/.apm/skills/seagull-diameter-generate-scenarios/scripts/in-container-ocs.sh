#!/bin/sh
# Runs inside the Seagull container, started by run-ocs.sh. Runs the client scenario /work/scenario/<name>.client.xml
# against the OCS at HOST:PORT, with a copy of /work/config/conf.client.xml whose dest is that address, and reads the
# statistics. Arguments: the name of the scenario, and HOST:PORT. If /logs exists, the Seagull logs are copied there.
# Exits non-zero unless the scenario ends with at least 1 successful call and 0 failed calls.
export LD_LIBRARY_PATH=/usr/local/bin
name="${1:-}"
dest="${2:-}"
case "${dest}" in
    "" | *[!A-Za-z0-9.:_-]*)
        echo "error: the address must be HOST:PORT, and not '${dest}'" >&2
        exit 2
        ;;
esac
if [ ! -f "/work/scenario/${name}.client.xml" ]; then
    echo "error: no scenario ${name} in /work/scenario" >&2
    exit 2
fi
cd /opt/seagull/diameter-env/run || exit 2
rm -f ../logs/*

sed -e "s|dest=[^;\"']*|dest=${dest}|" \
    -e 's|\(name="external-data-file" *value="\)[^"]*|\1/work/scenario/external-data.csv|' \
    /work/config/conf.client.xml > /tmp/conf.client.xml

seagull -conf /tmp/conf.client.xml -dico /work/dictionary/diameter-dictionary.xml \
    -scen "/work/scenario/${name}.client.xml" -log "../logs/${name}.client" -llevel A -bg > /dev/null 2>&1 < /dev/null

for _ in $(seq 1 60); do
    cat ../logs/*client 2> /dev/null | grep -aq "STOP  log" && break
    sleep 1
done
sleep 1

errors=$(cat ../logs/*client 2> /dev/null | grep -a '|E|' | head -n 2 | tr '\n' ' ')
result="no statistics file"
stat=""
for candidate in ../logs/client-stat.*; do
    if [ -f "${candidate}" ] && { [ -z "${stat}" ] || [ "${candidate}" -nt "${stat}" ]; }; then
        stat="${candidate}"
    fi
done
if [ -n "${stat}" ]; then
    result=$(awk -F";" '
        NR == 1 { for (i = 1; i <= NF; i++) col[$i] = i; next }
        { ok = $col["TrafficSuccessfulCall(C)"]; failed = $col["FailedCall(C)"] }
        END { print "successful calls: " ok+0 ", failed calls: " failed+0 }' "${stat}")
fi
echo "${name}: ${result} ${errors}"
pkill -x seagull 2> /dev/null
if [ -d /logs ]; then
    cp -r ../logs/. /logs/
fi
case "${result}" in
    "successful calls: 0, "*) exit 1 ;;
    "successful calls: "*", failed calls: 0") exit 0 ;;
    *) exit 1 ;;
esac
