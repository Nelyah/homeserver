server: install_requires
	ansible-playbook --ask-become-pass server.yml
.PHONY: server

install_requires:
	ansible-galaxy collection install community.docker
	pip install --user -r requirements.txt
.PHONY: install_requires

.venv:
	@python3 -m venv .venv
