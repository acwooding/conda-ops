import pytest
import json
from pathlib import Path
from src.commands import lockfile_generate, check_env_exists, conda_step_env_lock, lockfile_check, yaml

CONDA_OPS_DIR_NAME = '.conda-ops'

def test_lockfile_generate(shared_temp_dir):
    """
    This test checks the function lockfile_generate().
    It creates a temporary directory and checks whether the function generates the lockfile correctly.
    """
    temp_dir = shared_temp_dir

    config = {
        'paths': {
            'ops_dir': temp_dir / CONDA_OPS_DIR_NAME,
            'requirements': temp_dir / 'environment-generate.yml',
            'lockfile': temp_dir / 'lockfile-generate.json',
        },
        'settings': {
            'env_name': str(temp_dir.name),
        }
    }
    requirements_dict = {'name': str(temp_dir.name),
                         'channels': ['defaults'],
                         'channel-order': ['defaults'],
                         'dependencies': ['python', 'pip']}
    with open(config['paths']['requirements'], 'w') as f:
        yaml.dump(requirements_dict, f)
    lockfile_generate(config)

    assert config['paths']['lockfile'].exists()


def test_lockfile_check_when_file_exists_and_valid(shared_temp_dir):
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
    # Make a lockfile
    config = {"paths": {"lockfile": shared_temp_dir / CONDA_OPS_DIR_NAME / "lockfile.json"}}
    lockfile_data = [{"manager": "conda", "base_url": "http://example.com", "platform": "linux", "dist_name": "example", "extension": ".tar.gz", "md5": "md5hash", "url": "http://example.com/linux/example.tar.gz#md5hash", "name":"example"}]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Act
    result = lockfile_check(config, die_on_error=False)

    # Assert
    assert result == True

def test_lockfile_check_when_file_exists_but_invalid(shared_temp_dir):
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
    # Arrange
    config = {"paths": {"lockfile": shared_temp_dir /  "lockfile.json"}}
    lockfile_data = [{"manager": "conda", "base_url": "http://example.com", "platform": "linux", "dist_name": "example", "extension": ".tar.gz", "md5": "md5hash", "url": "http://wrong-url.com", "name": "example"}]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Act
    result = lockfile_check(config, die_on_error=False)

    # Assert
    assert result == False

def test_lockfile_check_when_file_not_exists(shared_temp_dir):
    """
    Test case to verify the behavior of lockfile_check when the lockfile does not exist.

    This test checks if the lockfile_check function correctly handles the scenario when the lockfile does not exist.
    It calls the lockfile_check function with the appropriate configuration, and asserts that the result is False.

    Args:
        shared_temp_dir: Pytest fixture providing a shared temporary directory.

    Raises:
        AssertionError: If the assertion fails.
    """
    # Arrange
    config = {"paths": {"lockfile": shared_temp_dir / CONDA_OPS_DIR_NAME /  "lockfile.json"}}
    if config['paths']['lockfile'].exists():
        config['paths']['lockfile'].unlink()

    # Act
    result = lockfile_check(config, die_on_error=False)

    # Assert
    assert result == False


def test_check_env_exists():
    """
    This test checks the function check_env_exists().
    It uses an unlikely environment name to ensure that it doesn't exist.
    """
    env_name = "very_unlikely_env_name_that_doesnt_exist"
    assert check_env_exists(env_name) is False
