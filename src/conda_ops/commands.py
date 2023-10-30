"""
Placeholder for when we include compound functionality combining other commands. Right now we only have the consistency_check and lockfile creation.
"""
import json
from pathlib import Path
import shutil
import sys
import time

# from conda.cli.main_info import get_info_dict

from .utils import logger
from .commands_proj import proj_check
from .commands_reqs import reqs_check
from .commands_lockfile import lockfile_check, lockfile_reqs_check, lock_package_consistency_check
from .commands_env import (
    active_env_check,
    conda_step_env_lock,
    env_check,
    env_create,
    env_delete,
    env_install,
    env_lockfile_check,
    env_regenerate,
    pip_step_env_lock,
)
from .env_handler import get_prefix, get_conda_info, CondaOpsManagedCondarc, EnvObject, check_env_active, check_env_exists
from .conda_config import check_condarc_matches_opinions, check_config_items_match
from .python_api import run_command
from .requirements import load_url_lookup
from .split_requirements import create_split_files

##################################################################
#
# Compound Commands
#
##################################################################


def lockfile_generate(config, regenerate=True, platform=None):
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
    env = EnvObject(**config["env_settings"], env_dir=config["paths"]["env_dir"])

    env_prefix = env.prefix

    if regenerate:
        # create a blank environment name to create the lockfile from scratch
        logger.info("Generating temporary environment for building lock file from requirements.")
        raw_test_env_prefix = str(env.prefix) + "-lockfile-generate"
        for i in range(100):
            test_env = raw_test_env_prefix + f"-{i}"
            if not check_env_exists(prefix=test_env):
                break
        logger.debug(f"Using temporary environment: {test_env}")
    else:
        test_env = env.prefix

    if not requirements_file.exists():
        logger.error(f"Requirements file does not exist: {requirements_file}")
        logger.info("To create a minimal default requirements file:")
        logger.info(">>> conda ops reqs create")
        sys.exit(1)
    if not reqs_check(config, die_on_error=False):
        logger.error("Requirements file is not in the correct format. Update it and try again.")
        sys.exit(1)

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
                json_reqs = conda_step_env_lock(channel, config, prefix=test_env)
            except Exception as exception:
                print(exception)
                json_reqs = None
        else:
            try:
                json_reqs, extra_pip_dict = pip_step_env_lock(channel, config, prefix=test_env, extra_pip_dict=extra_pip_dict)
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

    with open(ops_dir / last_good_lockfile, "r", encoding="utf-8") as jsonfile:
        new_json_reqs = json.load(jsonfile)

    # this is a platform specific lock file
    info_dict = get_conda_info()
    platform = info_dict["platform"]

    # retain lock information from different platforms
    if lock_file.exists():
        with open(lock_file, "r", encoding="utf-8") as jsonfile:
            other_reqs = json.load(jsonfile)
        for req in other_reqs:
            if req.get("platform", None) != platform:
                new_json_reqs.append(req)

    blob = json.dumps(new_json_reqs, indent=2, sort_keys=True)
    with open(lock_file, "w", encoding="utf-8") as jsonfile:
        jsonfile.write(blob)

    # clean up
    for channel in order_list:
        if channel in pip_channels:
            Path(ops_dir / f".ops.{channel}-requirements.txt").unlink()
        else:
            Path(ops_dir / f".ops.{channel}-environment.txt").unlink()
        Path(ops_dir / f".ops.lock.{channel}").unlink()

    Path(ops_dir / ".ops.channel-order.include").unlink()
    if regenerate:
        env_delete(prefix=test_env)
        logger.debug("Deleted intermediate environment")
    print(f"Lockfile {lock_file} generated.")


def populate_local_url_lookup(config, die_on_error=True, platform=None, output_instructions=False):
    """
    When a local url lookup is missing, try to resolve it and add it to the lookup file.
    """
    ops_dir = config["paths"]["ops_dir"]
    requirements_file = config["paths"]["requirements"]
    lock_file = config["paths"]["lockfile"]
    env_name = config["env_settings"]["env_name"]

    if platform is None:
        info_dict = get_conda_info()
        platform = info_dict["platform"]

    if lock_file.exists():
        with open(lock_file, "r", encoding="utf-8") as lockfile:
            try:
                json_reqs = json.load(lockfile)
            except Exception as exception:
                logger.warning(f"Unable to load lockfile {lock_file}")
                logger.debug(exception)
                if output_instructions:
                    logger.info("To regenerate the lock file:")
                    logger.info(">>> conda ops sync")
                if die_on_error:
                    sys.exit(1)
                else:
                    return False
    else:
        logger.warning("There is no lock file.")
        if output_instructions:
            logger.info("To create the lock file:")
            logger.info(">>> conda ops sync")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    consistency_dict = lock_package_consistency_check(json_reqs, config, platform)
    no_url_lookup = consistency_dict["no_url_lookup"]

    if len(no_url_lookup) < 1:
        logger.info("No missing local url lookups found. Nothing to resolve.")
        return True

    # create a blank environment name to create the lockfile from scratch
    logger.info("Generating temporary environment for resolving the local url lookups from pip-based requirements.")
    raw_test_env = env_name + "-lockfile-generate"
    for i in range(100):
        test_env = raw_test_env + f"-{i}"
        if not check_env_exists(test_env):
            break
    logger.debug(f"Using temporary environment: {raw_test_env}")

    # check if the environment exists. If not, create it and include pip.
    # XXX may need to use the same version of python as the environment. Maybe not.
    prefix = get_prefix(test_env)
    logger.debug(f"Creating environment {env_name} at {prefix} ")
    with CondaOpsManagedCondarc(config["paths"]["condarc"]):
        conda_args = ["--prefix", prefix, "pip"]
        stdout, stderr, result_code = run_command("create", conda_args, use_exception_handler=True)
        if result_code != 0:
            logger.error(stdout)
            logger.error(stderr)
            return None
        print(stdout)

    if not requirements_file.exists():
        logger.error(f"Requirements file does not exist: {requirements_file}")
        logger.info("To create a minimal default requirements file:")
        logger.info(">>> conda ops reqs create")
        if die_on_error:
            sys.exit(1)
        else:
            return False
    if not reqs_check(config, die_on_error=False):
        logger.error("Requirements file is not in the correct format. Update it and try again.")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    create_split_files(requirements_file, ops_dir)

    with open(ops_dir / ".ops.channel-order.include", "r", encoding="utf-8") as order_file:
        order_list = order_file.read().split()

    json_reqs = None
    channel = "sdist"
    try:
        json_reqs, extra_pip_dict = pip_step_env_lock(channel, config, env_name=test_env)
    except Exception as exception:
        print(exception)
        json_reqs = None
    if json_reqs is None:
        logger.error("Failed to generate local url lookup entries.")
        if output_instructions:
            logger.info("Try a full sync instead:")
            logger.info(">>> conda ops sync")
        if die_on_error:
            sys.exit(1)
        else:
            return False

    # check if missing package information has been added
    lookup = load_url_lookup(config=config)
    for package_entry in no_url_lookup:
        try:
            entry = lookup[package_entry.name]
        except Exception as e:
            print(e)
            # if it's missing add it now

    # clean up
    Path(ops_dir / f".ops.{channel}-requirements.txt").unlink()
    Path(ops_dir / f".ops.lock.{channel}").unlink()
    Path(ops_dir / ".ops.channel-order.include").unlink()

    env_delete(env_name=test_env)
    logger.debug("Deleted intermediate environment")
    logger.info("Local url entries added to lookup")
    return True


def sync(config, regenerate_lockfile=True, force=False):
    """
    Sync the requirements file with the lockfile and environment.
    """
    env = EnvObject(**config["env_settings"], env_dir=config["paths"]["env_dir"])

    complete = False
    reqs_consistent = reqs_check(config, die_on_error=True)
    lockfile_consistent, consistency_dict = lockfile_check(config, die_on_error=False, output_instructions=False)

    if lockfile_consistent:
        lockfile_reqs_consistent = lockfile_reqs_check(config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=False, output_instructions=False)
    elif len(consistency_dict) > 0:
        lockfile_reqs_consistent = False
        if len(consistency_dict["no_url_lookup"]) > 0 and len(consistency_dict["no_url"]) == 0 and len(consistency_dict["inconsistent"]) == 0 and consistency_dict["platform_in_lockfile"]:
            # try to resolve missing url lookup before doing anything else if that's all that's missing
            logger.info("Trying to resolve missing local url lookups")
            success = populate_local_url_lookup(config, die_on_error=False)
            if success:
                lockfile_consistent, consistency_dict = lockfile_check(config, die_on_error=False, output_instructions=False)
                if lockfile_consistent:
                    lockfile_reqs_consistent = lockfile_reqs_check(config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=False, output_instructions=False)
            else:
                logger.info("Trying a full sync instead")
    else:
        # cannot determine consistency if lockfile
        lockfile_reqs_consistent = False
    if not (lockfile_consistent and lockfile_reqs_consistent) or force:
        lockfile_generate(config, regenerate=regenerate_lockfile)
        lockfile_consistent, consistency_dict = lockfile_check(config, die_on_error=False, output_instructions=False)

    if env.exists():
        env_lockfile_consistent, regenerate = env_lockfile_check(config=config, lockfile_consistent=lockfile_consistent, die_on_error=False, output_instructions=False)
        if not env_lockfile_consistent and not (regenerate or force):
            logger.info(f"Updating the environment: {env.display_name} from the lock file")
            env_install(config=config)
            complete = True
        elif force or regenerate:
            if env.active():
                print("")
                logger.warning("To complete the sync, the environment needs to be regenerated, but the environment is currently active.")
                logger.info("To deactivate the environment and complete the sync:")
                logger.info(">>> conda deactivate")
                logger.info(">>> conda ops sync")
            else:
                if not force:
                    input_value = input("To finish syncing, the environment must be deleted and recreated from the lock file. Would you like to proceed? (y/n) ").lower()
                else:
                    input_value = "y"
                if input_value == "y":
                    logger.info("Regenerating the environment")
                    # attempt to figure out what's making this delete step fail
                    time.sleep(5)
                    env_delete(config=config, env_exists=True)
                    env_create(config=config)
                    complete = True
                else:
                    logger.warning("Unable to complete the sync. Please make any desired changes and then try again.")
                    logger.info(">>> conda ops sync")
        elif env_lockfile_consistent:
            complete = True
    else:
        env_create(config)
        complete = True
    return complete


############################################
#
# Helper Functions
#
###########################################
#
def consistency_check(config=None, die_on_error=False, output_instructions=False):
    """
    Check the consistency of the requirements file vs. lock file vs. conda environment
    """
    proj_check(config, die_on_error=True)  # needed to continue

    config_match = check_config_items_match()
    config_opinions = check_condarc_matches_opinions(config=config, die_on_error=die_on_error)

    env = EnvObject(**config["env_settings"], env_dir=config["paths"]["env_dir"])

    reqs_consistent = reqs_check(config, die_on_error=die_on_error)
    lockfile_consistent, _ = lockfile_check(config, die_on_error=die_on_error, output_instructions=output_instructions)

    if lockfile_consistent:
        lockfile_reqs_consistent = lockfile_reqs_check(
            config, reqs_consistent=reqs_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error, output_instructions=output_instructions
        )

        env_consistent = env_check(config, die_on_error=die_on_error, output_instructions=output_instructions)
        if env_consistent:
            logger.info(f"Found managed conda environment: {env.relative_display_name}")
            env_lockfile_consistent, _ = env_lockfile_check(config, env_consistent=env_consistent, lockfile_consistent=lockfile_consistent, die_on_error=die_on_error, output_instructions=True)
        active_env_consistent = active_env_check(config, die_on_error=die_on_error, output_instructions=output_instructions, env_exists=env_consistent)

    if not lockfile_consistent:
        print("")
        logger.info("The lock file does not exist or is not consistent. To (re)generate and sync it:")
        logger.info(">>> conda ops sync")
        print("")
    elif not lockfile_reqs_consistent:
        print("")
        logger.info("The lock file may not be in sync with the requirements.")
        logger.info("To sync the lock file and environment with the requirements:")
        logger.info(">>> conda ops sync")

        print("")
    elif not env_consistent:
        print("")
        logger.warning(f"Managed conda environment ('{env.relative_display_name}') does not yet exist.")
        logger.info("To create it:")
        logger.info(">>> conda ops sync")
        print("")
    elif not active_env_consistent:
        print("")
        logger.warning(f"Managed conda environment ('{env.relative_display_name}') exists but is not active.")
        logger.info("To activate it:")
        logger.info(f">>> conda activate {env.relative_display_name}")
        print("")

    # don't include not being active in the return value
    return_value = config_match and config_opinions and reqs_consistent and lockfile_consistent and env_consistent and lockfile_reqs_consistent and env_lockfile_consistent
    if return_value:
        print("")
        logger.info(f"The conda ops environment {env.relative_display_name} is consistent")
        print("")
    return return_value
