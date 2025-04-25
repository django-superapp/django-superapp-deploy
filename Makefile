.ONESHELL:
SHELL = /bin/bash
SCRIPT_DIR?=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

setup-venv:
	set -e; \
	$(SCRIPT_DIR)/scripts/setup-venv.sh;

install-ci-requirements: setup-venv
	set -e; \
	$(SCRIPT_DIR)/scripts/install-ci-requirements.sh;

connect-remote-docker:
	set -e; \
	$(SCRIPT_DIR)/scripts/connect-remote-docker.sh;

setup-git-crypt:
	set -e; \
	git-crypt init;

generate-git-crypt:
	set -e; \
	$(SCRIPT_DIR)/scripts/generate-git-crypt.sh;

lock-git-crypt:
	set -e; \
	$(SCRIPT_DIR)/scripts/lock-git-crypt.sh;

unlock-git-crypt:
	set -e; \
	$(SCRIPT_DIR)/scripts/unlock-git-crypt.sh;

