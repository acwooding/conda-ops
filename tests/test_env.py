from src.commands import check_env_exists, env_create, lockfile_generate, env_check, env_delete
from src.python_api import run_command
import pytest

def test_check_env_exists(shared_temp_dir):
    """
    This test checks the function check_env_exists().
    """
    # doesn't exist
    env_name = "very_unlikely_env_name_that_doesnt_exist"
    assert check_env_exists(env_name) is False

    # create an environment
    env_name = shared_temp_dir.name
    if check_env_exists(env_name):
        env_name = shared_temp_dir.name + 'test'

    stdout, stderr, result_code = run_command("create", '-n', env_name, use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)
    assert check_env_exists(env_name) is True

    # clean up
    stdout, stderr, result_code = run_command("remove", '-n', env_name, '--all', use_exception_handler=True)
    if result_code != 0:
        logger.error(stdout)
        logger.error(stderr)

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
        stdout, stderr, result_code = run_command("remove", '-n', env_name, '--all', use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)

    # Call the env_create function
    env_create(config)

    # Check if the environment is created
    assert check_env_exists(env_name) is True


    # Call the env_create function again
    # when it already exists
    with pytest.raises(SystemExit):
        env_create(config)

def test_env_create_no_lockfile(setup_config_files):
    """
    Test the env_create function when no requirements file is provided.
    """
    config = setup_config_files
    config["paths"]["lockfile"] = None

    # Call the env_create function
    with pytest.raises(SystemExit):
        env_create(config)


def test_env_check_existing(setup_config_files, mocker):
    """
    Test the env_check function when the environment exists but is not active.
    """
    config = setup_config_files
    mocker.patch('src.commands.check_env_exists', return_value=True)
    mocker.patch('src.commands.check_env_active', return_value=False)

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
    mocker.patch('src.commands.check_env_exists', return_value=False)
    mocker.patch('src.commands.check_env_active', return_value=False)

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
    mocker.patch('src.commands.check_env_exists', return_value=True)
    mocker.patch('src.commands.check_env_active', return_value=True)

    assert env_check(config) is True
    assert env_check(config, die_on_error=False) is True
