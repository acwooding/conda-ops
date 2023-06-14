import pytest
import json
from pathlib import Path
from src.commands import lockfile_generate, lockfile_check, lockfile_reqs_check, yaml

CONDA_OPS_DIR_NAME = '.conda-ops'

def test_lockfile_generate(setup_config_files):
    """
    This test checks the function lockfile_generate().
    It creates a temporary directory and checks whether the function generates the lockfile correctly.
    """
    config = setup_config_files

    lockfile_generate(config)
    assert config['paths']['lockfile'].exists()

    # reset
    config['paths']['lockfile'].unlink()
    lockfile_generate(config, regenerate=True)
    assert config['paths']['lockfile'].exists()

def test_lockfile_generate_no_reqs(setup_config_files):
    """
    This test checks the function lockfile_generate() when there is no requirements file present
    """
    config = setup_config_files

    config['paths']['requirements'].unlink()
    with pytest.raises(SystemExit):
        lockfile_generate(config)

def test_lockfile_check_when_file_exists_and_valid(setup_config_files):
    """
    Test case to verify the behavior of lockfile_check when the lockfile exists and is valid.

    This test checks if the lockfile_check function correctly handles the scenario when the lockfile exists
    and contains valid data. It creates a temporary lockfile with valid data, calls the lockfile_check function
    with the appropriate configuration, and asserts that the result is True.

    Args:
        shared_temp_dir: Pytest fixture providing a shared temporary directory.

    Raises:
        AssertionError: If the assertion fails.
    """
    # Setup
    config = setup_config_files
    lockfile_data = [{"manager": "conda", "base_url": "http://example.com", "platform": "linux", "dist_name": "example", "extension": ".tar.gz", "md5": "md5hash", "url": "http://example.com/linux/example.tar.gz#md5hash", "name":"example"}]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result == True

def test_lockfile_check_when_file_exists_but_invalid(setup_config_files):
    """
    Test case to verify the behavior of lockfile_check when the lockfile exists but contains invalid data.

    This test checks if the lockfile_check function correctly handles the scenario when the lockfile exists
    but contains invalid data. It creates a temporary lockfile with invalid data, calls the lockfile_check function
    with the appropriate configuration, and asserts that the result is False.

    Args:
        shared_temp_dir: Pytest fixture providing a shared temporary directory.

    Raises:
        AssertionError: If the assertion fails.
    """
    # Setup
    config = setup_config_files
    lockfile_data = [{"manager": "conda", "base_url": "http://example.com", "platform": "linux", "dist_name": "example", "extension": ".tar.gz", "md5": "md5hash", "url": "http://wrong-url.com", "name": "example"}]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result == False

def test_lockfile_check_when_file_not_exists(setup_config_files):
    """
    Test case to verify the behavior of lockfile_check when the lockfile does not exist.

    This test checks if the lockfile_check function correctly handles the scenario when the lockfile does not exist.
    It calls the lockfile_check function with the appropriate configuration, and asserts that the result is False.

    Args:
        shared_temp_dir: Pytest fixture providing a shared temporary directory.

    Raises:
        AssertionError: If the assertion fails.
    """
    # Setup
    config = setup_config_files
    if config['paths']['lockfile'].exists():
        config['paths']['lockfile'].unlink()

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result == False


def test_lockfile_reqs_check_consistent(setup_config_files):
    """
    This test checks the lockfile_reqs_check function from the commands module.

    We test the following cases:
    - When the lock file and requirements file are consistent and match
    - When the requirements file is newer than the lock file
    """
    # Create consistent requirement and lock file
    config = setup_config_files

    lockfile_generate(config)
    assert lockfile_reqs_check(config) is True

    # Make requirements newer than the lock file
    config['paths']['requirements'].touch()

    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    assert lockfile_reqs_check(config, die_on_error=False) is False

def test_lockfile_reqs_check_inconsistent(setup_config_files, mocker):
    """
    This test checks the lockfile_reqs_check function from the commands module.

    We test the following cases:
    - When the lock file and requirements file are consistent but don't match
    - When the lock file is missing
    - When the requirements file is inconsistent
    - When the lock file is inconsistent


    """
    # Create individually consistent requirement and lock file with lock file newer than reqs file
    # But the data in the files doesn't match
    config = setup_config_files

    lockfile_data = [{"manager": "conda", "base_url": "http://example.com", "platform": "linux", "dist_name": "example", "extension": ".tar.gz", "md5": "md5hash", "url": "http://example.com/linux/example.tar.gz#md5hash", "name":"example"}]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # test it
    # check when die_on_error is True (by default)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    # check when die_on_error is False
    assert lockfile_reqs_check(config, die_on_error=False) is False

    # remove lockfile
    config['paths']['lockfile'].unlink()

    # test it
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    assert lockfile_reqs_check(config, die_on_error=False) is False

    # test with lockfile_consistent=False
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, lockfile_consistent=False, die_on_error=True)
    assert lockfile_reqs_check(config, lockfile_consistent=False, die_on_error=False) is False

    # test with patched lockfile_check to be False
    mocker.patch('src.commands.lockfile_check', return_value=False)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, die_on_error=True)
    assert lockfile_reqs_check(config, die_on_error=False) is False

    # test with reqs_consistent=False
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, reqs_consistent=False, die_on_error=True)
    assert lockfile_reqs_check(config, reqs_consistent=False, die_on_error=False) is False

    # test with patched reqs_check to be False
    mocker.patch('src.commands.reqs_check', return_value=False)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, die_on_error=True)
    assert lockfile_reqs_check(config, die_on_error=False) is False
