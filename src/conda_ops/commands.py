"""
Placeholder for when we include compound functionality combining other commands. Right now we only have the consistency_check and lockfile creation.
"""
from pathlib import Path
import shutil
import sys

# from conda.cli.main_info import get_info_dict

from .utils import logger
from .commands_proj import proj_check
from .commands_reqs import reqs_check
from .commands_lockfile import lockfile_check, lockfile_reqs_check
from .commands_env import env_check, env_lockfile_check, conda_step_env_lock, pip_step_env_lock, env_delete, check_env_exists
from .conda_config import check_condarc_matches_opinions, check_config_items_match
from .split_requirements import create_split_files

##################################################################
#
# Compound Commands
#
##################################################################

# Placeholder for later when we make the compound commands


def lockfile_generate(config, regenerate=True):
    """
    Generate a lock file from the requirements file.

    Args:
        config (dict): Configuration dictionary.
        regenerate (bool, optional): Whether to regenerate the lock file. Defaults to True.

    Currently always overwrites the existing lock file when complete.

    If regenenerate=True, use a clean environment to generate the lock file. If False, use
    the conda-ops managed environment.
    """
    ops_dir = config["paths"]["ops_dir"]
    requirements_file = config["paths"]["requirements"]
    lock_file = config["paths"]["lockfile"]
    env_name = config["settings"]["env_name"]

    if regenerate:
        # create a blank environment name to create the lockfile from scratch
        raw_test_env = env_name + "-lockfile-generate"
        for i in range(100):
            test_env = raw_test_env + f"-{i}"
            if not check_env_exists(test_env):
                break
        logger.debug(f"Using environment {raw_test_env} to generate the lockfile.")
    else:
        test_env = env_name

    if not requirements_file.exists():
        logger.error(f"Requirements file does not exist: {requirements_file}")
        logger.info("To create a minimal default requirements file:")
        logger.info(">>> conda ops reqs create")
        sys.exit(1)
    if not reqs_check(config, die_on_error=False):
        logger.error("Requirements file is not in the correct format. Update it and try again.")
        sys.exit(1)

    logger.info("Generating multi-step requirements files")
    create_split_files(requirements_file, ops_dir)

    with open(ops_dir / ".ops.channel-order.include", "r", encoding="utf-8") as order_file:
        order_list = order_file.read().split()

    pip_channels = ["pypi", "sdist"]
    json_reqs = None
    extra_pip_dict = None
    for i, channel in enumerate(order_list):
        logger.debug(f"Installing from channel {channel}")

        if channel not in pip_channels:
            try:
                json_reqs = conda_step_env_lock(channel, config, env_name=test_env)
            except Exception as exception:
                print(exception)
                json_reqs = None
        else:
            try:
                json_reqs, extra_pip_dict = pip_step_env_lock(channel, config, env_name=test_env, extra_pip_dict=extra_pip_dict)
            except Exception as exception:
                print(exception)
                json_reqs = None
        if json_reqs is None:
            if i > 0:
                logger.warning(f"Last successful channel was {order_list[i-1]}")
                logger.error("Unimplemented: Decide what to do when not rolling back the environment here")
                last_good_channel = order_list[i - 1]
                sys.exit(1)
            else:
                logger.error("No successful channels were installed")
                sys.exit(1)
            break
        last_good_channel = order_list[i]

    last_good_lockfile = f".ops.lock.{last_good_channel}"
    logger.debug(f"Updating lock file from {last_good_lockfile}")
    shutil.copy(ops_dir / (ops_dir / last_good_lockfile), lock_file)

    # clean up
    for channel in order_list:
        if channel in pip_channels:
            Path(ops_dir / f".ops.{channel}-requirements.txt").unlink()
        else:
            Path(ops_dir / f".ops.{channel}-environment.txt").unlink()
        Path(ops_dir / f".ops.lock.{channel}").unlink()

    Path(ops_dir / ".ops.channel-order.include").unlink()
    if regenerate:
        env_delete(env_name=test_env)
        logger.debug("Deleted intermediate environment")
    print(f"Lockfile {lock_file} generated.")


############################################
#
# Helper Functions
#
############################################


def consistency_check(config=None, die_on_error=False):
    """
    Check the consistency of the requirements file vs. lock file vs. conda environment
    """
    proj_check(config, die_on_error=True)  # needed to continue

    config_match = check_config_items_match()
    config_opinions = check_condarc_matches_opinions(config=config, die_on_error=die_on_error)

    env_name = config["settings"]["env_name"]
    logger.info(f"Managed Conda Environment: {env_name}")

    reqs_consistent = reqs_check(config, die_on_error=die_on_error)
    lockfile_consistent = lockfile_check(config, die_on_error=die_on_error)

    if lockfile_consistent:
        lockfile_reqs_consistent = lockfile_reqs_check(config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error)

        env_consistent = env_check(config, die_on_error=die_on_error)
        if env_consistent:
            env_lockfile_consistent = env_lockfile_check(config, env_consistent=env_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error)

    if config_match and config_opinions and reqs_consistent and lockfile_consistent and env_consistent and lockfile_reqs_consistent and env_lockfile_consistent:
        logger.info(f"The conda ops project {env_name} is consistent")
