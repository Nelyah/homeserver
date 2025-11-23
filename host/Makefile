all: install_requires

install_requires: .venv
	. .venv/bin/activate \
		&& pip install -r requirements.txt \
		&& ansible-galaxy collection install community.docker community.general community.hashi_vault
.PHONY: install_requires

.venv:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip
