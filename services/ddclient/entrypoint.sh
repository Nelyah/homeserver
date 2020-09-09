#! /bin/bash

if [ -z "${DOMAINS_LIST}" ] || [ ! -f "${DOMAINS_LIST}" ]; then
    echo "Error: No such file ${DOMAINS_LIST}"
    do_exit=Y
fi

[ -z "${LOGIN}" ] && echo "Error: LOGIN variable is empty." && do_exit=Y
[ -z "${PASSWORD}" ] && echo "Error: PASSWORD variable is empty." && do_exit=Y

[ do_exit = Y ] && exit 1

rm -f /var/cache/ddclient/ddclient.cache

for domain in $(cat domains_list); do
    echo $domain

    sed -e "s/@@LOGIN@@/$LOGIN/" \
        -e "s/@@PASSWORD@@/$PASSWORD/" \
        -e "s/@@DOMAIN@@/$domain/" \
        ddclient_raw.conf > ddclient_tmp.conf

    ddclient -file ddclient_tmp.conf
done
