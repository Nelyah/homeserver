# This variable is used as an argument to specify a tag for ansible to use
# The tag refers to the name of the service to backup
BACKUP_SERVICE=""

server: install_requires
	. .venv/bin/activate && ansible-playbook --ask-become-pass server.yml
.PHONY: server

backup: install_requires
	. .venv/bin/activate && ansible-playbook --tags backup,$(BACKUP_SERVICE) backup.yml
.PHONY: backup

install_requires: .venv
	. .venv/bin/activate \
		&& ansible-galaxy collection install community.docker community.general \
		&& pip install -r requirements.txt
.PHONY: install_requires

.venv:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
