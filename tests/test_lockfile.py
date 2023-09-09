import pytest
import json
from conda_ops.commands import lockfile_generate
from conda_ops.commands_lockfile import lockfile_check, lockfile_reqs_check
from conda_ops.commands_reqs import reqs_add

CONDA_OPS_DIR_NAME = ".conda-ops"


def test_lockfile_generate(mocker, setup_config_files):
    """
    This test checks the function lockfile_generate().
    It creates a temporary directory and checks whether the function generates the lockfile correctly.
    """
    config = setup_config_files

    # make sure there is something from non-defaults channels here
    reqs_add(["flask"], channel="pip", config=config)
    reqs_add(["pylint"], channel="conda-forge", config=config)

    lockfile_generate(config)
    assert config["paths"]["lockfile"].exists()

    # reset
    config["paths"]["lockfile"].unlink()
    lockfile_generate(config, regenerate=True)
    assert config["paths"]["lockfile"].exists()


def test_lockfile_generate_no_reqs(setup_config_files):
    """
    This test checks the function lockfile_generate() when there is no requirements file present
    """
    config = setup_config_files

    config["paths"]["requirements"].unlink()
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
    lockfile_data = [
        {
            "channel": "pkgs/main",
            "hash": {"md5": "d0202dd912bfb45d3422786531717882"},
            "manager": "conda",
            "name": "zlib",
            "url": "https://repo.anaconda.com/pkgs/main/osx-64/zlib-1.2.13-h4dc903c_0.conda",
            "version": "1.2.13",
        }
    ]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result is True


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
    lockfile_data = [
        {
            "channel": "pkgs/main",
            "hash": {"md5": "d0202dd912bfb45d3422786531717882"},
            "manager": "conda",
            "name": "zlib",
            "url": "https://wrongurl.com",
            "version": "1.2.13",
        }
    ]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result is False


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
    if config["paths"]["lockfile"].exists():
        config["paths"]["lockfile"].unlink()

    # Test
    result = lockfile_check(config, die_on_error=False)

    assert result is False


def test_lockfile_reqs_check_consistent(mocker, setup_config_files):
    """
    This test checks the lockfile_reqs_check function from the commands module.

    We test the following cases:
    - When the lock file and requirements file are consistent and match
    - When the requirements file is newer than the lock file
    """
    # Create consistent requirement and lock file
    config = setup_config_files

    lockfile_generate(config, regenerate=True)
    assert lockfile_reqs_check(config) is True

    reqs_add(["git+https://github.com/lmcinnes/pynndescent.git"], config=config, channel="pip")
    lockfile_generate(config, regenerate=True)
    assert lockfile_reqs_check(config) is True

    # Make requirements newer than the lock file
    config["paths"]["requirements"].touch()

    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    assert lockfile_reqs_check(config, die_on_error=False) is False


def test_lockfile_reqs_check_consistent_equals(setup_config_files):
    """
    This checks when the requirements and lock file are individually consistent,
    the requirements are all in the lock file by name, and the version constraint
    is satisfied by the lock file.
    """
    config = setup_config_files
    reqs_add(["python==3.11"], config=config, channel="pip")

    lockfile_data = [
        {
            "channel": "pkgs/main",
            "hash": {"md5": "dc185a3787062b62e27cdbc07040b252"},
            "manager": "conda",
            "name": "python",
            "url": "https://repo.anaconda.com/pkgs/main/osx-64/python-3.11.0-h1fd4e5f_3.conda",
            "version": "3.11.0",
        },
        {
            "channel": "pkgs/main",
            "hash": {"md5": "1556eaba878214072149829197203fcf"},
            "manager": "conda",
            "name": "pip",
            "url": "https://repo.anaconda.com/pkgs/main/osx-64/pip-23.1.2-py311hecd8cb5_0.conda",
            "version": "23.1.2",
        },
    ]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    assert lockfile_reqs_check(config) is True


def test_lockfile_reqs_check_inconsistent_version(setup_config_files):
    """
    This checks when the requirments and lock file are individually consistent,
    the requirements are all in the lock file by name, but the version constraint
    is not satisfied by the lock file.
    """
    config = setup_config_files
    reqs_add(["python==3.10"], config=config)

    lockfile_data = [
        {
            "channel": "pkgs/main",
            "hash": {"md5": "dc185a3787062b62e27cdbc07040b252"},
            "manager": "conda",
            "name": "python",
            "url": "https://repo.anaconda.com/pkgs/main/osx-64/python-3.11.0-h1fd4e5f_3.conda",
            "version": "3.11.0",
        },
        {
            "channel": "pkgs/main",
            "hash": {"md5": "1556eaba878214072149829197203fcf"},
            "manager": "conda",
            "name": "pip",
            "url": "https://repo.anaconda.com/pkgs/main/osx-64/pip-23.1.2-py311hecd8cb5_0.conda",
            "version": "23.1.2",
        },
    ]

    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # check when die_on_error is True (by default)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    # check when die_on_error is False
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

    lockfile_data = [
        {
            "manager": "conda",
            "base_url": "http://example.com",
            "platform": "linux",
            "dist_name": "example",
            "extension": ".tar.gz",
            "md5": "md5hash",
            "url": "http://example.com/linux/example.tar.gz#md5hash",
            "name": "example",
        }
    ]
    with open(config["paths"]["lockfile"], "w") as f:
        json.dump(lockfile_data, f)

    # test it
    # check when die_on_error is True (by default)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    # check when die_on_error is False
    assert lockfile_reqs_check(config, die_on_error=False) is False

    # remove lockfile
    config["paths"]["lockfile"].unlink()

    # test it
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config)

    assert lockfile_reqs_check(config, die_on_error=False) is False

    # test with lockfile_consistent=False
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, lockfile_consistent=False, die_on_error=True)
    assert lockfile_reqs_check(config, lockfile_consistent=False, die_on_error=False) is False

    # test with patched lockfile_check to be False
    mocker.patch("conda_ops.commands_lockfile.lockfile_check", return_value=False)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, die_on_error=True)
    assert lockfile_reqs_check(config, die_on_error=False) is False

    # test with reqs_consistent=False
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, reqs_consistent=False, die_on_error=True)
    assert lockfile_reqs_check(config, reqs_consistent=False, die_on_error=False) is False

    # test with patched reqs_check to be False
    mocker.patch("conda_ops.commands_reqs.reqs_check", return_value=False)
    with pytest.raises(SystemExit):
        lockfile_reqs_check(config, die_on_error=True)
    assert lockfile_reqs_check(config, die_on_error=False) is False
