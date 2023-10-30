import fnmatch
import os

import pytest

from conda_ops.commands_proj import proj_create, proj_load, proj_check
from conda_ops.env_handler import CondaOpsManagedCondarc

# Assuming these constants are defined in conda_ops
CONDA_OPS_DIR_NAME = ".conda-ops"
CONFIG_FILENAME = "config.ini"


def test_proj_create(mocker, shared_temp_dir):
    """
    Test case to verify the behavior of the `proj_create` function.

    This test checks if the `proj_create` function creates the appropriate directory structure and config file
    when the function is called. It mocks various dependencies and asserts the expected outcomes.

    Args:
        mocker: Pytest mocker fixture for mocking dependencies.
        shared_temp_dir: Pytest fixture providing a shared temporary directory.
    """
    tmpdir = shared_temp_dir
    mocker.patch("pathlib.Path.cwd", return_value=tmpdir)

    config, overwrite = proj_create(input_value="n")

    assert "env_settings" in config
    assert "paths" in config
    assert (tmpdir / CONDA_OPS_DIR_NAME).is_dir()
    assert (tmpdir / CONDA_OPS_DIR_NAME / CONFIG_FILENAME).exists()
    assert not overwrite


def test_proj_load(mocker, shared_temp_dir, setup_config_structure):
    """
    Test case to verify the behavior of the `proj_load` function.

    This test checks if the `proj_load` function correctly loads the conda ops configuration file. It mocks the
    'pathlib.Path.cwd' return value to use the tmpdir and asserts that the loaded config has the correct sections.

    Args:
        mocker: Pytest mocker fixture for mocking dependencies.
        shared_temp_dir: Pytest fixture providing a shared temporary directory.
    """
    tmpdir = shared_temp_dir
    mocker.patch("pathlib.Path.cwd", return_value=tmpdir)
    _ = setup_config_structure
    config = proj_load(die_on_error=True)

    assert "env_settings" in config
    assert "paths" in config
    assert len(config["paths"]) == 11
    assert len(config["env_settings"]) == 2


def test_proj_check(mocker, shared_temp_dir, setup_config_structure):
    """
    Test case to verify the behavior of the `proj_check` function when a config object is present.

    This test checks if the `proj_check` function correctly handles the case when a config object is present.
    It asserts that the result of `proj_check` is True.

    Args:
        mocker: Pytest mocker fixture for mocking dependencies.
        shared_temp_dir: Pytest fixture providing a shared temporary directory.
    """
    tmpdir = shared_temp_dir
    mocker.patch("pathlib.Path.cwd", return_value=tmpdir)
    _ = setup_config_structure
    result = proj_check(die_on_error=True)

    assert result


def test_proj_check_no_config(mocker, shared_temp_dir):
    """
    Test case to verify the behavior of the `proj_check` function when no config object is present.

    This test checks if the `proj_check` function correctly handles the case when no config object is present.
    It mocks the `proj_load` function to return None and asserts that `proj_check` raises a `SystemExit` when
    `die_on_error` is True. It also asserts that the result of `proj_check` is False when `die_on_error` is False.

    Args:
        mocker: Pytest mocker fixture for mocking dependencies.
        shared_temp_dir: Pytest fixture providing a shared temporary directory.
    """
    mocker.patch("conda_ops.commands_proj.proj_load", return_value=None)

    with pytest.raises(SystemExit):
        proj_check(die_on_error=True)

    result = proj_check(die_on_error=False)

    assert not result


def test_condarc_context_handling(mocker, setup_config_files):
    """
    Test that the context handler correctly sets and unsets the environment variable CONDARC
    """
    config = setup_config_files

    original_condarc = os.environ.get("CONDARC")
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        assert os.environ.get("CONDARC") == str(config["paths"]["condarc"])

    # the CONDARC value with the esoteric including the temp dir should never be set outside of a context handler
    assert os.environ.get("CONDARC") != str(config["paths"]["condarc"])
    assert os.environ.get("CONDARC") == original_condarc


def test_lockfile_url_lookup_gitignore(mocker, setup_config_files, shared_temp_dir):
    config = setup_config_files
    gitignore_path = config["paths"]["gitignore"]
    lockfile_url_lookup_path = config["paths"]["lockfile_url_lookup"]

    if not gitignore_path.exists():
        tmpdir = shared_temp_dir
        mocker.patch("pathlib.Path.cwd", return_value=tmpdir)
        config = proj_create(input_value="y")

    with open(gitignore_path, "r") as filehandle:
        gitignore_content = filehandle.readlines()

    check = False
    print(lockfile_url_lookup_path.name)
    for line in gitignore_content:
        print(line)
        if fnmatch.fnmatch(lockfile_url_lookup_path.name, line.strip()):
            check = True
    assert check
