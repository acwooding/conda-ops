# Makefile for building and testing locally

CONDA_EXE ?= ~/anaconda3/bin/conda
PYTHON = python3
PACKAGE_NAME = conda-ops
WHEEL_NAME = conda_ops
DIST_DIR = dist
PYTEST_CMD = pytest
TEST_ENV = conda-ops-test-env
DIST_FILES = $(DIST_DIR)/$(PACKAGE_NAME)-*.tar.gz $(DIST_DIR)/$(WHEEL_NAME)-*.whl
VERSION = "0.4a2"

.PHONY: local-test
## Build, install and test locally
local-test: clean install-dist test uninstall

.PHONY: pypi-test
## Build, upload to test pypi, install and test
pypi-test: upload-test install-testpypi test uninstall

.PHONY: pre-release-test
## Build, install and test locally, then upload to test pypi, install and test
pre-release-test: local-test pypi-test

.PHONY: release
## Upload to pypi, install and test the release
release: upload uninstall install-pypi test uninstall

.PHONY: clean
## Delete distribution files
clean:
	rm -rf $(DIST_DIR)

.PHONY: build
## Build distribution files
build: $(DIST_FILES)

$(DIST_FILES):
	$(PYTHON) -m build

.PHONY: upload-test
## Upload to Test-PyPI
upload-test:
	$(PYTHON) -m twine upload --repository testpypi $(DIST_DIR)/*

.PHONY: upload
## Upload to PyPI
upload: build
	$(PYTHON) -m twine upload $(DIST_DIR)/*

.PHONY: install-dist
## Install the distribution
install-dist: build
	$(CONDA_EXE) run -n $(TEST_ENV) pip install $(DIST_DIR)/*.whl

.PHONY: install-testpypi
## Install the TestPyPI version
install-testpypi:
	$(CONDA_EXE) run -n $(TEST_ENV) pip install --index-url "https://test.pypi.org/simple/" --no-deps $(PACKAGE_NAME)==$(VERSION)

.PHONY: install-pypi
## Install the PyPI version
install-pypi:
	$(CONDA_EXE) run -n $(TEST_ENV) pip install $(PACKAGE_NAME)==$(VERSION)

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
