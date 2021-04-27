server: install_requires
	ansible-playbook --ask-become-pass server.yml
.PHONY: server

install_requires: .venv
	@source .venv/bin/activate && \
	pip install --upgrade pip && \
	pip install -r requirements.txt
.PHONY: install_requires

.venv:
	@python3 -m venv .venv
