SHELL:=/bin/bash
VENV=venv
REQ=requirements.txt

install: install_requirements

install_requirements: make_venv
	source $(VENV)/bin/activate && python3 -m pip install -r $(REQ)

make_venv:
	python3 -m venv $(VENV)
