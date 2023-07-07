from src.utils import check_env_exists
from src.commands import lockfile_generate
from src.commands_env import env_create, env_check, get_prefix
from src.python_api import run_command
import pytest
import logging

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


def test_env_create(setup_config_files):
    """
    Test the env_create function.
    """
    config = setup_config_files
    env_name = config["settings"]["env_name"]

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
    config["paths"]["lockfile"].unlink()  # remove the lockfile

    # Call the env_create function
    with pytest.raises(SystemExit):
        env_create(config)


def test_env_check_existing(setup_config_files, mocker):
    """
    Test the env_check function when the environment exists but is not active.
    """
    config = setup_config_files
    mocker.patch("src.commands_env.check_env_exists", return_value=True)
    mocker.patch("src.commands_env.check_env_active", return_value=False)

    # Call the env_check function
    # die_on_error by default
    with pytest.raises(SystemExit):
        env_check(config)

    assert env_check(config, die_on_error=False) is False


def test_env_check_non_existing(setup_config_files, mocker):
    """
    Test the env_check function when the environment does not exist.
    """
    config = setup_config_files
    mocker.patch("src.commands_env.check_env_exists", return_value=False)
    mocker.patch("src.commands_env.check_env_active", return_value=False)

    # Call the env_check function
    # die_on_error by default
    with pytest.raises(SystemExit):
        env_check(config)

    assert env_check(config, die_on_error=False) is False


def test_env_check_active(setup_config_files, mocker):
    """
    Test the env_check function when the environment is active.
    """
    config = setup_config_files
    mocker.patch("src.commands_env.check_env_exists", return_value=True)
    mocker.patch("src.commands_env.check_env_active", return_value=True)

    assert env_check(config, die_on_error=False) is True
    assert env_check(config) is True
