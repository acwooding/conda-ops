import logging
from packaging.requirements import Requirement
import pytest

from conda_ops.commands import lockfile_generate
from conda_ops.commands_env import env_create, env_check, get_prefix, env_lockfile_check, env_regenerate, env_delete, env_lock, active_env_check
from conda_ops.env_handler import check_env_exists
from conda_ops.commands_reqs import reqs_add
from conda_ops.python_api import run_command

logger = logging.getLogger()


def test_check_env_exists(shared_temp_dir):
    """
    This test checks the function check_env_exists().
    """
    # doesn't exist
    env_name = "very_unlikely_env_name_that_doesnt_exist"
    assert check_env_exists(env_name) is False

    # create an environment and test its existence
    env_name = shared_temp_dir.name
    if check_env_exists(env_name):
        # remove it if it exists already
        stdout, stderr, result_code = run_command("remove", "--prefix", get_prefix(env_name), "--all", use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
        assert check_env_exists(env_name) is False

    stdout, stderr, result_code = run_command("create", "--prefix", get_prefix(env_name), use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)
    assert check_env_exists(env_name) is True

    # clean up
    stdout, stderr, result_code = run_command("remove", "--prefix", get_prefix(env_name), "--all", use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)
    assert check_env_exists(env_name) is False


def test_env_create(mocker, setup_config_files):
    """
    Test the env_create function.
    """
    config = setup_config_files
    mocker.patch("conda_ops.commands_proj.proj_load", return_value=config)
    env_name = config["env_settings"]["env_name"]

    # Make sure we have a legit lockfile
    lockfile_generate(config, regenerate=True)

    # if an env with this name exists, remove it
    if check_env_exists(env_name):
        logger.warning(f"Environment already exists with name {env_name}. Attempting to remove it.")
        stdout, stderr, result_code = run_command("remove", "--prefix", get_prefix(env_name), "--all", use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
    else:
        logger.warning(f"No environment with name {env_name} found.")

    # Call the env_create function
    env_create(config)

    # Check if the environment is created
    assert check_env_exists(env_name) is True

    # Call the env_create function again
    # when it already exists
    with pytest.raises(SystemExit):
        env_create(config)

    # clean up
    stdout, stderr, result_code = run_command("remove", "--prefix", get_prefix(env_name), "--all", use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)


def test_env_create_no_lockfile(setup_config_files):
    """
    Test the env_create function when no requirements file is provided.
    """
    config = setup_config_files
    if config["paths"]["lockfile"].exists():
        config["paths"]["lockfile"].unlink()  # remove the lockfile

    # Call the env_create function
    with pytest.raises(SystemExit):
        env_create(config)


def test_env_check_existing(setup_config_files, mocker, caplog):
    """
    Test the env_check function when the environment exists but is not active.
    """
    config = setup_config_files
    mocker.patch("conda_ops.env_handler.EnvObject.exists", return_value=True)

    # Call the env_check function
    # die_on_error by default
    with caplog.at_level(logging.WARNING):
        env_check(config)

    assert env_check(config, die_on_error=False) is True


def test_env_check_non_existing(setup_config_files, mocker):
    """
    Test the env_check function when the environment does not exist.
    """
    config = setup_config_files
    mocker.patch("conda_ops.env_handler.EnvObject.exists", return_value=False)

    # Call the env_check function
    # die_on_error by default
    with pytest.raises(SystemExit):
        env_check(config)

    assert env_check(config, die_on_error=False) is False


def test_active_env_check_active(setup_config_files, mocker):
    """
    Test the active_env_check function when the environment is active.
    """
    config = setup_config_files
    mocker.patch("conda_ops.env_handler.EnvObject.active", return_value=True)

    assert active_env_check(config, die_on_error=False) is True


def test_active_env_check_not_active(setup_config_files):
    """
    Test the active_env_check function when the environment is not active.
    """
    config = setup_config_files

    assert active_env_check(config, die_on_error=False) is False


def test_env_lockfile_check_missing_lockfile(caplog, setup_config_files):
    config = setup_config_files

    lockfile_consistent = False

    with caplog.at_level(logging.WARNING):
        result = env_lockfile_check(config=config, lockfile_consistent=lockfile_consistent, env_consistent=True, die_on_error=False)

    assert result == (False, True)
    assert "Lock file is missing or inconsistent" in caplog.text


def test_env_lockfile_check_missing_environment(caplog, setup_config_files):
    config = setup_config_files

    lockfile_consistent = True
    env_consistent = False

    with caplog.at_level(logging.WARNING):
        result = env_lockfile_check(config=config, env_consistent=env_consistent, lockfile_consistent=lockfile_consistent, die_on_error=False)

    assert result == (False, True)
    assert "Environment does not exist" in caplog.text


def test_env_lockfile_check_consistent_environment_and_lockfile(caplog, setup_config_files):
    config = setup_config_files
    lockfile_generate(config)

    if check_env_exists(config["env_settings"]["env_name"]):
        env_regenerate(config)
    else:
        env_create(config)

    with caplog.at_level(logging.DEBUG):
        result = env_lockfile_check(config=config, die_on_error=False)

    assert result == (True, False)
    assert "Conda packages in environment and lock file are in sync" in caplog.text
    assert "Pip packages in environment and lock file are in sync" in caplog.text
    env_delete(config)


def test_env_lock_pip_dict(setup_config_files):
    config = setup_config_files

    test_packages = ["pip::flake8==6.1.0", "pip::GitPython==3.1.32"]
    pip_dict = {
        "flake8": {
            "version": "6.1.0",
            "url": "https://files.pythonhosted.org/packages/b0/24/bbf7175ffc47cb3d3e1eb523ddb23272968359dfcf2e1294707a2bf12fc4/flake8-6.1.0-py2.py3-none-any.whl",
            "sha256": "ffdfce58ea94c6580c77888a86506937f9a1a227dfcd15f245d694ae20a6b6e5",
        },
        "gitpython": {
            "version": "3.1.32",
            "url": "https://files.pythonhosted.org/packages/67/50/742c2fb60989b76ccf7302c7b1d9e26505d7054c24f08cc7ec187faaaea7/GitPython-3.1.32-py3-none-any.whl",
            "sha256": "e3d59b1c2c6ebb9dfa7a184daf3b6dd4914237e7488a1730a6d8f6f5d0b4187f",
        },
    }
    reqs_add(test_packages, config=config)
    lockfile_generate(config)
    env_name = config["env_settings"]["env_name"]
    if check_env_exists(env_name):
        env_regenerate(config)
    else:
        env_create(config)
    channel_lockfile = config["paths"]["ops_dir"] / ".ops.lock.pip"
    json_reqs = env_lock(config, lock_file=channel_lockfile, env_name=env_name, pip_dict=pip_dict)
    for package in test_packages:
        package_name = Requirement(package.split("pip::")[1]).name.lower()
        for json_package in json_reqs:
            if json_package["name"] == package_name:
                break
        for key, value in pip_dict[package_name].items():
            assert json_package[key] == value
    env_delete(config)
