# Makefile for building and testing locally

CONDA_EXE ?= ~/anaconda3/bin/conda
PYTHON = python3
PACKAGE_NAME = conda-ops
WHEEL_NAME = conda_ops
DIST_DIR = dist
PYTEST_CMD = pytest
TEST_ENV = conda-ops-test-env
DIST_FILES = $(DIST_DIR)/$(PACKAGE_NAME)-*.tar.gz $(DIST_DIR)/$(WHEEL_NAME)-*.whl

.PHONY: all
## Default target: build and test
all: clean install-dist test uninstall

.PHONY: clean
## Clean up temporary files
clean:
	rm -rf $(DIST_DIR)

.PHONY: build
## Build distribution files
build: $(DIST_FILES)

$(DIST_FILES):
	$(PYTHON) -m build

.PHONY: install-dist
## Install the distribution
install-dist: build
	$(CONDA_EXE) run -n $(TEST_ENV) pip install $(DIST_DIR)/*.whl

.PHONY: install-dev
## Install the development version
install-dev: build
	$(CONDA_EXE) run -n $(TEST_ENV) pip install -e .

.PHONY: test
## Run pytest
test:
	$(PYTEST_CMD)

.PHONY: uninstall
## Uninstall the pacakge
uninstall:
	$(CONDA_EXE) run -n $(TEST_ENV) pip uninstall $(PACKAGE_NAME) -y

.PHONY: coverage
## Run pytest with coverage
coverage:
	coverage run -m pytest --doctest-modules --doctest-continue-on-failure

#################################################################################
# Self Documenting Commands                                                     #
#################################################################################

HELP_VARS := PACKAGE_NAME

.DEFAULT_GOAL := show-help
.PHONY: show-help
show-help:
	@$(PYTHON) scripts/help.py $(foreach v,$(HELP_VARS),-v $(v) $($(v))) $(MAKEFILE_LIST)
