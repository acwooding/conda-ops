from src.commands import lockfile_generate
from src.commands_env import env_create, env_check, get_prefix, check_env_exists, env_lockfile_check, env_regenerate, env_delete
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


def test_env_create(mocker, setup_config_files):
    """
    Test the env_create function.
    """
    config = setup_config_files
    mocker.patch("src.commands_proj.proj_load", return_value=config)
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
    mocker.patch("src.commands_env.check_env_exists", return_value=True)
    mocker.patch("src.commands_env.check_env_active", return_value=False)

    # Call the env_check function
    # die_on_error by default
    with caplog.at_level(logging.WARNING):
        env_check(config)

    assert "exists but is not active" in caplog.text
    assert env_check(config, die_on_error=False) is True


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


def test_env_lockfile_check_missing_lockfile(caplog, setup_config_files):
    config = setup_config_files

    lockfile_consistent = False

    with caplog.at_level(logging.WARNING):
        result = env_lockfile_check(config=config, lockfile_consistent=lockfile_consistent, env_consistent=True, die_on_error=False)

    assert result is False
    assert "Lock file is missing or inconsistent" in caplog.text


def test_env_lockfile_check_missing_environment(caplog, setup_config_files):
    config = setup_config_files

    lockfile_consistent = True
    env_consistent = False

    with caplog.at_level(logging.WARNING):
        result = env_lockfile_check(config=config, env_consistent=env_consistent, lockfile_consistent=lockfile_consistent, die_on_error=False)

    assert result is False
    assert "Environment does not exist" in caplog.text


def test_env_lockfile_check_consistent_environment_and_lockfile(caplog, setup_config_files):
    config = setup_config_files
    lockfile_generate(config)

    if check_env_exists(config["settings"]["env_name"]):
        env_regenerate(config)
    else:
        env_create(config)

    with caplog.at_level(logging.DEBUG):
        result = env_lockfile_check(config=config, die_on_error=False)

    assert result is True
    assert "Conda packages in environment and lock file are in sync" in caplog.text
    assert "Pip packages in environment and lock file are in sync" in caplog.text
    env_delete(config)
