#!/bin/bash

set -euo pipefail

# Check we only have one argument
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <service_name|all>"
    exit 1
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

if [[ "$1" != "all" ]]; then
    ansible-playbook backup-remote.yml --tags "backup,$1"
    exit $?
fi

# Loop through all services
for service_name in $(yq -r '.backup_services[]' group_vars/all/enabled_services.yml); do
    ansible-playbook backup-remote.yml --tags "backup,${service_name}"
done
