#!/bin/sh
# Runs inside the Seagull container, started by check-converted.sh. For each converted
# dictionary in /dictionaries that defines CCR, it runs the stub OCS and the client of
# /assets with that dictionary and counts the successful calls. Exits non-zero if any run
# does not end with 1 successful call and 0 failed calls.
export LD_LIBRARY_PATH=/usr/local/bin
config=/opt/seagull/diameter-env/config
cd /opt/seagull/diameter-env/run || exit 2

# The bundled client configuration leaves number-calls commented out; set it to 1.
sed "s#</configuration>#<define entity=\"traffic-param\" name=\"number-calls\" value=\"1\"></define></configuration>#" \
    "${config}/conf.client.xml" > ../custom/conf.client.one-call.xml

status=0
for dictionary in /dictionaries/*.xml; do
    name=$(basename "${dictionary}" .xml)
    if ! grep -q '<define name="CCR">' "${dictionary}"; then
        echo "${name}: skipped, the dictionary defines no CCR"
        continue
    fi
    rm -f ../logs/client-stat.* ../logs/server-stat.* ../logs/chk.*

    seagull -conf "${config}/conf.server.xml" -dico "${dictionary}" \
        -scen /assets/stub-ocs.server.xml -log "../logs/chk.${name}.server" \
        -llevel A -bg > /dev/null 2>&1 < /dev/null
    sleep 2
    seagull -conf ../custom/conf.client.one-call.xml -dico "${dictionary}" \
        -scen /assets/client-gy-initial.xml -log "../logs/chk.${name}.client" \
        -llevel A -bg > /dev/null 2>&1 < /dev/null

    for _ in $(seq 1 15); do
        cat ../logs/chk.* 2> /dev/null | grep -q "STOP  log" && break
        sleep 1
    done
    sleep 1

    errors=$(cat ../logs/chk.* 2> /dev/null | grep -a '|E|' | head -n 2 | tr '\n' ' ')
    result="no statistics file"
    stat=$(ls -t ../logs/client-stat.* 2> /dev/null | head -n 1)
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
