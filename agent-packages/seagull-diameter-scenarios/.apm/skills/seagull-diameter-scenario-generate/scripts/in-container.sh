#!/bin/sh
# Runs inside the Seagull container, started by dry-run.sh. For each client scenario in /work/scenario it starts the
# matching stub OCS, runs the client against it, and reads the statistics. Argument: the suffix of the stub scenarios
# (default stub-server). Exits non-zero unless every scenario ends with 1 successful call and 0 failed calls.
export LD_LIBRARY_PATH=/usr/local/bin
suffix="${1:-stub-server}"
dictionary=/work/dictionary/diameter-dictionary.xml
cd /opt/seagull/diameter-env/run || exit 2
status=0
for client in /work/scenario/*.client.xml; do
    name=$(basename "${client}" .client.xml)
    rm -f ../logs/*

    seagull -conf /work/config/conf.stub-server.xml -dico "${dictionary}" \
        -scen "/work/scenario/${name}.${suffix}.xml" -log "../logs/${name}.stub" -llevel A -bg \
        > /dev/null 2>&1 < /dev/null
    sleep 2
    seagull -conf /work/config/conf.dry-run.client.xml -dico "${dictionary}" \
        -scen "${client}" -log "../logs/${name}.client" -llevel A -bg > /dev/null 2>&1 < /dev/null

    for _ in $(seq 1 60); do
        cat ../logs/*client 2> /dev/null | grep -aq "STOP  log" && break
        sleep 1
    done
    sleep 1

    errors=$(cat ../logs/*client ../logs/*stub 2> /dev/null | grep -a '|E|' | head -n 2 | tr '\n' ' ')
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
            END { print "successful calls: " ok ", failed calls: " failed }' "${stat}")
    fi
    echo "${name}: ${result} ${errors}"
    case "${result}" in
        "successful calls: 1, failed calls: 0") ;;
        *) status=1 ;;
    esac
    pkill -x seagull 2> /dev/null
    sleep 1
done
exit "${status}"
