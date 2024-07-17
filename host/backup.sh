#!/bin/bash

set -euo pipefail

function print_usage() {
    echo "Usage: $0 <local|remote> <service_name|all>" >&2
}

if [ "$#" -ne 2 ]; then
    print_usage
    exit 1
fi

if [ "$1" != "local" ] && [ "$1" != "remote" ]; then
    print_usage
    exit 1
fi

playbook_file="backup.yml"
if [ "$1" = "remote" ]; then
    playbook_file="backup-remote.yml"
fi


# Load the python environment
if [ ! -d .venv ]; then
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ansible-galaxy collection install community.docker community.general
else
    source .venv/bin/activate
fi

if [[ "$2" != "all" ]]; then
    ansible-playbook "$playbook_file" --tags "backup,$2"
    exit $?
fi

# Loop through all services
for service_name in $(yq -r '.backup_services[]' group_vars/all/enabled_services.yml); do
    ansible-playbook "$playbook_file" --tags "backup,${service_name}"
done
