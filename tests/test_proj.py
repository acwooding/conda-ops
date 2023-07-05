import pytest
from src.commands_proj import proj_create, proj_load, proj_check

# Assuming these constants are defined in src
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
    mocker.patch("src.input", return_value="n")

    config = proj_create()

    assert "settings" in config
    assert "paths" in config
    assert (tmpdir / CONDA_OPS_DIR_NAME).is_dir()
    assert (tmpdir / CONDA_OPS_DIR_NAME / CONFIG_FILENAME).exists()


def test_proj_load(mocker, shared_temp_dir):
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

    config = proj_load(die_on_error=True)

    assert "settings" in config
    assert "paths" in config
    assert len(config["paths"]) == 6
    assert len(config["settings"]) == 1


def test_proj_check(mocker, shared_temp_dir):
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
    mocker.patch("src.commands_proj.proj_load", return_value=None)

    with pytest.raises(SystemExit):
        proj_check(die_on_error=True)

    result = proj_check(die_on_error=False)

    assert not result
